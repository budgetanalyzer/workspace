#!/usr/bin/env python3
"""Explicit optional inspection. Never initialize or globally trust a CA."""
import argparse
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import tempfile
import time


class ProxyError(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise ProxyError(message)


def proxy_arguments(action, port, home, root, worktrees):
    require(1024 <= port < 65535, 'proxy port must be 1024..65534')
    conf = home / '.local/share/budget-analyzer-native/inspection'
    for path in (conf, conf / 'mitmproxy-ca.pem', conf / 'mitmproxy-ca-cert.pem', conf / 'web-token'):
        require(path.exists() and not path.is_symlink() and path.stat().st_uid == os.getuid()
                and not path.stat().st_mode & 0o077, 'private inspection CA/token missing or unsafe; human optional setup required')
    token = (conf / 'web-token').read_text().strip()
    require(len(token) >= 24 and '\n' not in token, 'private mitmweb token must be at least 24 characters')
    args = ['mitmweb', '--listen-host', '127.0.0.1', '--listen-port', str(port), '--web-host', '127.0.0.1',
            '--web-port', str(port + 1), '--set', 'web_open_browser=false', '--set', 'ssl_insecure=false',
            '--set', 'ssl_verify_upstream_trusted_ca=/etc/ssl/certs/ca-certificates.crt', '--set', 'confdir=' + str(conf), '--set', 'web_password=' + token]
    if 'custom-system-prompt' in action:
        args += ['-s', str(root / 'helpers/system-prompt-addon.py')]
    return args, conf


def provider_arguments(action, user_args, root=None):
    if action.startswith('codex'):
        return [str(root / 'helpers/codex-lean.sh') if root else 'codex-lean', *user_args]
    if 'custom-system-prompt' in action:
        args = [str(root / 'npm/node_modules/.bin/claude') if root else 'claude', '--verbose', '--dangerously-skip-permissions']
        explicit_model = any(a == '--model' or a.startswith('--model=') for a in user_args)
        if action.startswith('claude-45') and not explicit_model:
            args += ['--model', 'claude-opus-4-5-20251101']
        elif action.startswith('claude-46') and not explicit_model:
            args += ['--model', 'claude-opus-4-6']
        return [*args, *user_args]
    return [str(root / 'npm/node_modules/.bin/claude') if root else 'claude', *user_args]


def launch(action, user_args):
    home = Path(os.environ['HOME'])
    root = Path(os.environ['BUDGET_ANALYZER_NATIVE_ROOT'])
    worktrees = Path(os.environ['BUDGET_ANALYZER_WORKTREE_PARENT'])
    port = int(user_args[0]) if action == 'start-proxy' and user_args else int(os.environ.get('PROXY_PORT', '9080'))
    args, conf = proxy_arguments(action, port, home, root, worktrees)
    # An arbitrary existing listener cannot prove inspection identity or addon selection.
    for candidate in (port, port + 1):
        with socket.socket() as probe:
            probe.settimeout(0.2)
            require(probe.connect_ex(('127.0.0.1', candidate)) != 0, 'proxy/UI port occupied; stop or inspect the existing listener privately')
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    flow_dir = worktrees / 'workspace/tmp/mitmproxy-private'
    require(not flow_dir.is_symlink(), 'private flow directory symlink collision')
    flow_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(flow_dir.stat().st_uid == os.getuid() and not flow_dir.stat().st_mode & 0o077, 'unsafe private flow storage')
    os.umask(0o077)
    if action == 'start-proxy':
        return subprocess.run(args, env=env).returncode
    bundle = None
    proxy = None
    try:
        with tempfile.NamedTemporaryFile(dir=flow_dir, suffix='.pem', delete=False) as stream:
            bundle = Path(stream.name)
            stream.write(Path('/etc/ssl/certs/ca-certificates.crt').read_bytes())
            stream.write(b'\n' + (conf / 'mitmproxy-ca-cert.pem').read_bytes())
        endpoint = f'http://127.0.0.1:{port}'
        env['CODEX_REAL_BIN'] = str(root / 'npm/node_modules/.bin/codex')
        env.update(HTTP_PROXY=endpoint, HTTPS_PROXY=endpoint, SSL_CERT_FILE=str(bundle),
                   REQUESTS_CA_BUNDLE=str(bundle), NODE_EXTRA_CA_CERTS=str(bundle))
        if action == 'codex-max-with-proxy':
            env['CODEX_REASONING_EFFORT'] = 'xhigh'
        if action.startswith('claude'):
            env.update(CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS='true', ENABLE_CLAUDEAI_MCP_SERVERS='false',
                       CLAUDE_CODE_EFFORT_LEVEL='max', CLAUDE_CODE_DISABLE_1M_CONTEXT='1')
            if 'custom-system-prompt' in action:
                env.update(CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING='1', MAX_THINKING_TOKENS='128000')
        proxy = subprocess.Popen(args, env=os.environ.copy(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            require(proxy.poll() is None, 'inspection proxy failed to start; inspect privately')
            with socket.socket() as probe:
                probe.settimeout(0.1)
                if probe.connect_ex(('127.0.0.1', port)) == 0:
                    break
            time.sleep(0.1)
        else:
            raise ProxyError('inspection proxy readiness timed out')
        return subprocess.run(provider_arguments(action, user_args, root), env=env).returncode
    finally:
        if proxy:
            proxy.terminate()
            try:
                proxy.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proxy.kill()
                proxy.wait()
        if bundle:
            bundle.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start-proxy', 'claude-with-proxy', 'claude-with-custom-system-prompt',
                                         'claude-45-custom-system-prompt', 'claude-46-custom-system-prompt',
                                         'codex-with-proxy', 'codex-max-with-proxy'))
    args, remaining = parser.parse_known_args()
    try:
        return launch(args.action, remaining)
    except (ProxyError, OSError, ValueError, KeyError) as exc:
        print('native-proxy: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
