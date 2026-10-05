#!/usr/bin/env python3
"""Human-only native installation and read-only environment verification."""
import argparse
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / 'native/toolchain.json'
SYSTEM_BUNDLE = '/etc/ssl/certs/ca-certificates.crt'
DENIED_ENV = ('SSH_AUTH_SOCK', 'GITHUB_TOKEN', 'GH_TOKEN', 'GIT_ASKPASS', 'SSH_ASKPASS',
              'GPG_AGENT_INFO', 'DOCKER_HOST', 'DOCKER_CONTEXT', 'TESTCONTAINERS_HOST_OVERRIDE',
              'GIT_CONFIG', 'GIT_CONFIG_GLOBAL', 'GIT_CONFIG_SYSTEM', 'GIT_CONFIG_COUNT',
              'GIT_SSH', 'GIT_SSH_COMMAND', 'GIT_CONFIG_PARAMETERS', 'HTTP_PROXY', 'HTTPS_PROXY',
              'ALL_PROXY', 'NODE_TLS_REJECT_UNAUTHORIZED', 'PYTHONHTTPSVERIFY', 'PIP_TRUSTED_HOST', 'NPM_TOKEN', 'NODE_AUTH_TOKEN', 'http_proxy', 'https_proxy', 'all_proxy')


class UserToolsError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise UserToolsError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def merge_settings(settings, overlay):
    """Own only the two controls and one hook; preserve all other user keys."""
    result = json.loads(json.dumps(settings))
    for key in ('promptSuggestionEnabled', 'autoCompactEnabled'):
        result[key] = overlay[key]
    hooks = result.setdefault('hooks', {}).setdefault('SessionStart', [])
    managed = overlay['hooks']['SessionStart'][0]
    command = managed['hooks'][0]['command']
    if not any(h.get('command') == command for group in hooks for h in group.get('hooks', [])):
        hooks.append(managed)
    return result


class UserTools:
    def __init__(self, worktrees, bares):
        self.worktrees, self.bares = Path(worktrees), Path(bares)
        self.manifest = json.loads(MANIFEST.read_text())
        self.env = dict(os.environ)

    def command(self, args, *, check=True, env=None):
        # Never print Git config, provider output, credentials or a full env.
        result = subprocess.run([str(a) for a in args], text=True, capture_output=True,
                                env=env or self.env)
        require(not check or result.returncode == 0,
                f'{Path(str(args[0])).name}: command failed (exit {result.returncode}); inspect privately')
        return result

    def account(self):
        return pwd.getpwuid(os.getuid())

    def system_path(self, path):
        return Path(path)

    def private_primary_group(self, gid):
        if gid != self.gid:
            return False
        try:
            group = grp.getgrgid(gid)
        except KeyError:
            return False
        primary_users = {entry.pw_name for entry in pwd.getpwall() if entry.pw_gid == gid}
        return (group.gr_name == self.user and primary_users == {self.user} and
                not set(group.gr_mem) - {self.user})

    def owned(self, path, *, directory=False, private=True):
        require(path.exists() and not path.is_symlink(), f'missing or symlinked path: {path}')
        status = path.stat()
        require(status.st_uid == self.uid, f'wrong owner: {path}')
        unsafe_group_write = (private and status.st_mode & 0o020 and
                              not self.private_primary_group(status.st_gid))
        require(not status.st_mode & 0o002 and not unsafe_group_write,
                f'unsafe writable path: {path}')
        if directory:
            require(path.is_dir(), f'expected directory: {path}')

    def home_path(self, path):
        require(path.is_relative_to(self.home), 'managed path escaped the development home')
        for item in (path, *path.parents):
            if not item.is_relative_to(self.home):
                break
            require(not item.is_symlink(), f'symlink collision: {item}')
            if item.exists():
                self.owned(item)

    def git_config(self, repo):
        result = self.command(['git', '-C', repo, 'config', '--null', '--list', '--includes'])
        for record in result.stdout.split('\0'):
            key = record.split('\n', 1)[0].lower()
            require(not re.search(r'^(credential\.|include\.|includeif\.|url\.|http\..*extraheader|core\.sshcommand|core\.askpass|gpg\.)', key),
                    'Git credential/include/rewrite/forwarding configuration rejected; inspect privately')

    def preflight(self):
        account = self.account()
        self.uid, self.gid = account.pw_uid, account.pw_gid
        self.home, self.user = Path(account.pw_dir), account.pw_name
        self.shell = account.pw_shell
        require(self.shell in ('/bin/bash', '/usr/bin/bash', '/bin/sh', '/bin/zsh', '/usr/bin/zsh'),
                'requires a supported normal-user login shell')
        require(self.uid >= 1000 and os.getuid() == self.uid, 'run as the normal development user, without sudo')
        require(self.env.get('HOME') == str(self.home) and self.home.resolve() == self.home,
                'HOME must match the canonical account home')
        self.owned(self.home, directory=True)
        release = self.system_path('/etc/os-release').read_text()
        require(re.search(r'^ID=ubuntu$', release, re.M) and
                re.search(r'^VERSION_ID="?24\.04"?$', release, re.M), 'requires Ubuntu 24.04 guest OS')
        require(not self.system_path('/.dockerenv').exists() and
                not self.system_path('/run/.containerenv').exists(), 'container execution rejected')
        c = self.command(['systemd-detect-virt', '--container'], check=False)
        v = self.command(['systemd-detect-virt', '--vm'], check=False)
        require(c.returncode == 1 and c.stdout.strip() == 'none' and v.returncode == 0 and
                v.stdout.strip() in ('kvm', 'qemu'), 'requires native QEMU/KVM execution')
        for key in DENIED_ENV:
            require(key not in self.env, f'{key} must be absent; remove credential/endpoint/proxy bridges privately')
        require(not any(k.startswith('GIT_CONFIG_KEY_') or k.startswith('GIT_CONFIG_VALUE_') for k in self.env),
                'injected Git configuration rejected')
        for path in (self.worktrees, self.bares):
            require(path.is_absolute() and path.resolve() == path, 'repository parents must be canonical absolute paths')
            self.owned(path, directory=True, private=False)
        require((self.worktrees / 'workspace').resolve() == REPO, 'installer must come from the selected workspace clone')
        repos = [p for p in self.worktrees.iterdir() if (p / '.git').exists()]
        for name in ('workspace', 'orchestration', 'ai-session-handler'):
            require(self.worktrees / name in repos, f'missing local checkout: {name}')
        for repo in repos:
            self.owned(repo, directory=True, private=False)
            self.owned(repo / '.git', directory=True, private=False)
            bare = self.bares / (repo.name + '.git')
            self.owned(bare, directory=True, private=False)
            self.owned(bare / 'config', private=False)
            require(self.command(['git', '-C', bare, 'rev-parse', '--is-bare-repository']).stdout.strip() == 'true',
                    'matching guest-local bare origin is absent')
            require(self.command(['git', '-C', bare, 'remote']).stdout.strip() == '', 'bare origin has an external remote')
            self.git_config(repo)
            self.git_config(bare)
            require(self.command(['git', '-C', repo, 'rev-parse', '--show-toplevel']).stdout.strip() == str(repo),
                    'checkout is not a standalone local clone')
            require(self.command(['git', '-C', repo, 'remote']).stdout.strip() == 'origin', 'extra or missing Git remote')
            for push in (False, True):
                argv = ['git', '-C', repo, 'remote', 'get-url', '--all']
                if push:
                    argv.append('--push')
                require(self.command([*argv, 'origin']).stdout.strip() == str(bare),
                        'wrong origin/push URL; human must inspect, no automatic Git repair')
        self.handler = self.worktrees / 'ai-session-handler'
        require((self.handler / 'pyproject.toml').is_file() and
                (self.handler / 'src/ai_session_handler').is_dir(), 'handler source/metadata missing')
        for key in ('CLAUDE_CONFIG_DIR', 'CODEX_HOME', 'GEMINI_CLI_HOME', 'GRADLE_USER_HOME',
                    'MAVEN_OPTS', 'NPM_CONFIG_PREFIX', 'PIPX_HOME', 'PIPX_BIN_DIR', 'NODE_PATH',
                    'PLAYWRIGHT_BROWSERS_PATH', 'SSL_CERT_FILE', 'NODE_EXTRA_CA_CERTS'):
            # Installer owns these exports after this gate; conflicting user settings need review.
            if key in self.env:
                expected = self.environment_values().get(key)
                require(expected is not None and self.env[key] == expected, f'conflicting {key}; review privately')
        for path in (self.home / '.git-credentials', self.home / '.netrc'):
            require(not path.exists(), 'Git/network credential store rejected; inspect privately')
        for path in (self.home / '.ssh', self.home / '.gnupg'):
            if path.exists():
                require(not any(p.is_socket() for p in path.rglob('*')), 'agent/forwarded credential socket rejected')
        require(self.command(['docker', 'context', 'show']).stdout.strip() == 'default', 'requires default guest Docker context')
        require(self.command(['docker', 'context', 'inspect', 'default', '--format', '{{.Endpoints.docker.Host}}']).stdout.strip()
                == 'unix:///var/run/docker.sock', 'requires guest Unix Docker socket')
        require(self.system_path('/var/run/docker.sock').is_socket(), 'guest Docker socket missing')
        require(self.command(['docker', 'info', '--format', '{{.DockerRootDir}}']).stdout.strip() == '/var/lib/docker',
                'guest Docker data root mismatch')
        self.system_checks()
        self.root = self.home / '.local/share/budget-analyzer-native'
        self.bin = self.home / '.local/bin'
        self.fragment = self.home / '.config/budget-analyzer-native/env.sh'
        for path in (self.root, self.bin, self.fragment, self.home / '.claude/settings.json',
                     self.home / '.claude/skills/save-conversation/SKILL.md',
                     self.home / '.profile', self.home / '.bashrc', self.home / '.bash_profile',
                     self.home / '.bash_login', self.home / '.zprofile', self.home / '.zshrc',
                     self.home / '.m2/repository', self.home / '.gradle',
                     self.home / '.pki/nssdb', self.home / '.cache/ms-playwright',
                     self.home / '.codex', self.home / '.gemini'):
            self.home_path(path)
        print(f'Native preflight: user={self.user}; home={self.home}; local repositories={len(repos)}')

    def system_checks(self):
        for package in self.manifest['apt'] + self.manifest['chromium_apt'] + ['nodejs', 'zulu25-jdk']:
            result = self.command(['dpkg-query', '-W', '-f=${Status}', package], check=False)
            require(result.returncode == 0 and result.stdout.strip() == 'install ok installed',
                    f'missing system package {package}; human: ./scripts/provision-agent-vm-guest.sh --docker-user {self.user}')
        require(self.command(['node', '--version']).stdout.startswith('v24.'), 'requires reviewed Node major 24')
        require(int(self.command(['npm', '--version']).stdout.split('.')[0]) >= 10, 'requires npm >=10')
        for tool in self.manifest['downloads'].values():
            if 'check' in tool:
                r = self.command(tool['check'])
                require(re.search(tool['version_pattern'], r.stdout + r.stderr), 'system release version mismatch')
        # Distro bubblewrap/AppArmor integration is a human gate, never a sysctl mutation.
        restrict = self.system_path('/proc/sys/kernel/apparmor_restrict_unprivileged_userns')
        if restrict.exists() and restrict.read_text().strip() == '1':
            profile = self.system_path('/etc/apparmor.d/bwrap')
            require(profile.is_file() and 'userns' in profile.read_text(),
                    'restricted user namespaces need Ubuntu bwrap AppArmor profile; see docs/native-user-tools.md')

    def environment_values(self):
        root = self.home / '.local/share/budget-analyzer-native'
        java = shutil.which('javac')
        return {'BUDGET_ANALYZER_WORKTREE_PARENT': str(self.worktrees),
                'BUDGET_ANALYZER_BARE_PARENT': str(self.bares),
                'BUDGET_ANALYZER_NATIVE_ROOT': str(root),
                'PIPX_HOME': str(root / 'pipx'), 'PIPX_BIN_DIR': str(root / 'pipx-bin'),
                'GRADLE_USER_HOME': str(self.home / '.gradle'),
                'PLAYWRIGHT_BROWSERS_PATH': str(self.home / '.cache/ms-playwright'),
                'NODE_PATH': str(root / 'npm/node_modules'),
                'SSL_CERT_FILE': SYSTEM_BUNDLE, 'REQUESTS_CA_BUNDLE': SYSTEM_BUNDLE,
                'NODE_EXTRA_CA_CERTS': SYSTEM_BUNDLE,
                'JAVA_HOME': str(Path(java).resolve().parents[1]) if java else '',
                'MAVEN_HOME': '/usr/share/maven'}

    def environment(self):
        exports = '\n'.join(f'export {key}={shlex.quote(value)}' for key, value in self.environment_values().items())
        return ('# Workspace-managed native environment; no proxies, credentials or aliases.\n' + exports +
                '\ncase "$PATH" in\n  "$HOME/.local/bin"|"$HOME/.local/bin":*) ;;\n'
                '  *) export PATH="$HOME/.local/bin:$PATH" ;;\nesac\n')

    def write(self, path, text, mode=0o600):
        self.home_path(path)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temp = path.with_name(path.name + '.native-tmp')
        require(not temp.exists() and not temp.is_symlink(), 'temporary installation path collision')
        with temp.open('x') as stream:
            stream.write(text)
        temp.chmod(mode)
        temp.replace(path)

    def plan_files(self):
        # Review all collisions before invoking an installation command.
        files = {self.fragment: (self.environment(), 0o600)}
        for source in (REPO / 'native/helpers').rglob('*'):
            if source.is_file():
                files[self.root / 'helpers' / source.relative_to(REPO / 'native/helpers')] = (source.read_text(), 0o700)
        files[self.root / 'user_tools.py'] = (Path(__file__).read_text(), 0o600)
        for module in ('local_ca.py', 'proxy.py'):
            files[self.root / module] = ((REPO / 'scripts/native' / module).read_text(), 0o600)
        files[self.root / 'npm-user.conf'] = ('', 0o600)
        files[self.root / 'npm-global.conf'] = ('', 0o600)
        files[self.root / 'toolchain.json'] = (MANIFEST.read_text(), 0o600)
        files[self.root / 'aliases.sh'] = ((REPO / 'native/helpers/bash_aliases.sh').read_text(), 0o600)
        targets = {name: f'"{self.root}/npm/node_modules/.bin/{name}"' for name in ('claude', 'codex', 'gemini', 'playwright')}
        targets.update({name: f'"{self.root}/pipx-bin/{name}"' for name in
                        ('ai-session-handler', 'ai-session-handler-codex-high', 'mitmproxy', 'mitmweb', 'mitmdump')})
        helper_sources = {'ai-run': 'ai-run.sh', 'codex-lean': 'codex-lean.sh', 'via-annotator': 'via-annotator.sh',
                          'statusline-command': 'statusline-command.sh', 'mitmflows': 'mitmflows',
                          'mitmflow-body': 'mitmflow-body', 'mitmflow-detail': 'mitmflow-detail',
                          'mitmflow-render.py': 'mitmflow-render.py'}
        for name, source in helper_sources.items():
            targets[name] = shlex.quote(str(self.root / 'helpers' / source))
        for tool in self.manifest['helpers'].values():
            name = tool['command']
            if name in targets:
                continue
            module = 'local_ca.py' if 'local-ca-trust' in name else 'proxy.py'
            targets[name] = f'python3 {shlex.quote(str(self.root / module))} {shlex.quote(name)}'
        for name, target in targets.items():
            # shlex quotes handle apostrophes, shell substitutions and spaces in account homes.
            if name in ('claude', 'codex', 'gemini', 'playwright'):
                target = shlex.quote(str(self.root / 'npm/node_modules/.bin' / name))
            elif name in ('ai-session-handler', 'ai-session-handler-codex-high', 'mitmproxy', 'mitmweb', 'mitmdump'):
                target = shlex.quote(str(self.root / 'pipx-bin' / name))
            files[self.bin / name] = ('#!/usr/bin/env bash\nset -euo pipefail\n'
                                     f'. {shlex.quote(str(self.fragment))}\nexec {target} "$@"\n', 0o700)
        self.names = set(targets)
        state_path = self.root / 'managed-files.json'
        self.home_path(state_path)
        previous = json.loads(state_path.read_text()) if state_path.exists() else {}
        for path, (content, _) in files.items():
            self.home_path(path)
            if path.exists():
                require(path.read_text() == content or previous.get(str(path)) == digest(path),
                        f'unmanaged or modified file collision: {path}; review privately')
        return files

    def install(self):
        files = self.plan_files()
        for path in (self.root / 'pipx', self.root / 'pipx-bin', self.root / 'npm-cache',
                     self.root / 'managed-files.json', self.root / 'installation.json'):
            self.home_path(path)
        overlay = json.loads((REPO / 'ai-agent-sandbox/settings-overlay.json').read_text())
        settings_path = self.home / '.claude/settings.json'
        settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
        merged = merge_settings(settings, overlay)
        skill = self.home / '.claude/skills/save-conversation/SKILL.md'
        skill_source = REPO / 'native/helpers/skills/save-conversation/SKILL.md'
        line = f'. {shlex.quote(str(self.fragment))} # budget-analyzer-native\n'
        shell_updates = {}
        for name in ('.profile', '.bashrc', '.bash_profile', '.bash_login', '.zprofile', '.zshrc'):
            path = self.home / name
            if not path.exists() and (name in ('.bash_profile', '.bash_login') or
                                      (name in ('.zprofile', '.zshrc') and not self.shell.endswith('/zsh'))):
                continue
            original = path.read_text() if path.exists() else ''
            managed = [l for l in original.splitlines() if l.endswith('# budget-analyzer-native')]
            require(not managed or managed == [line.strip()], 'shell environment fragment collision')
            if not managed:
                shell_updates[path] = original + ('\n' if original and not original.endswith('\n') else '') + line
        require(not skill.exists() or skill.read_bytes() == skill_source.read_bytes(), 'conversation skill collision')
        npm_dir = self.root / 'npm'
        npm_files = [REPO / 'native/npm' / name for name in ('package.json', 'package-lock.json')]
        for source in npm_files:
            target = npm_dir / source.name
            self.home_path(target)
            require(not target.exists() or target.read_bytes() == source.read_bytes(),
                    'npm inputs changed; review explicit refresh in docs/native-user-tools.md')
        self.validate_lock(npm_files[1])
        for path, (content, mode) in files.items():
            self.write(path, content, mode)
        for source in npm_files:
            self.write(npm_dir / source.name, source.read_text())
        env = self.env | self.environment_values()
        env['PATH'] = str(self.bin) + ':' + env.get('PATH', '')
        env['NPM_CONFIG_CACHE'] = str(self.root / 'npm-cache')
        env['NPM_CONFIG_USERCONFIG'] = str(self.root / 'npm-user.conf')
        env['NPM_CONFIG_GLOBALCONFIG'] = str(self.root / 'npm-global.conf')
        env['NPM_CONFIG_STRICT_SSL'] = 'true'
        env['PIP_CONFIG_FILE'] = '/dev/null'
        env['PIP_INDEX_URL'] = 'https://pypi.org/simple'
        env['PIP_EXTRA_INDEX_URL'] = ''
        # No upstream interactive startup, auto-clone, --force or pipx ensurepath.
        if not (npm_dir / 'node_modules/.package-lock.json').exists():
            self.command(['npm', 'ci', '--prefix', npm_dir, '--no-audit', '--no-fund'], env=env)
        for package, source in [('mitmproxy', 'mitmproxy==' + self.manifest['user_tools']['mitmproxy']['version']),
                                ('ai-session-handler', str(self.handler))]:
            if not (self.root / 'pipx/venvs' / package).exists():
                args = ['pipx', 'install']
                if package == 'ai-session-handler':
                    args.append('--editable')
                self.command([*args, source], env=env)
        for path in (self.home / '.m2/repository', self.home / '.gradle', self.home / '.pki/nssdb',
                     self.home / '.cache/ms-playwright'):
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.command([self.bin / 'playwright', 'install', 'chromium'], env=env)
        self.write(settings_path, json.dumps(merged, indent=2) + '\n')
        self.write(skill, skill_source.read_text())
        for path, content in shell_updates.items():
            self.write(path, content)
        report = {'workspace_revision': self.command(['git', '-C', self.worktrees / 'workspace', 'rev-parse', 'HEAD']).stdout.strip(),
                  'handler_revision': self.command(['git', '-C', self.handler, 'rev-parse', 'HEAD']).stdout.strip(),
                  'handler_dirty_paths': self.command(['git', '-C', self.handler, 'status', '--porcelain']).stdout.splitlines(),
                  'workspace_dirty_paths': self.command(['git', '-C', self.worktrees / 'workspace', 'status', '--porcelain']).stdout.splitlines(),
                  'user': self.user, 'home': str(self.home), 'worktree_parent': str(self.worktrees),
                  'bare_parent': str(self.bares), 'npm_lock_sha256': digest(npm_files[1]),
                  'user_tool_versions': {n: t['version'] for n, t in self.manifest['user_tools'].items()}}
        report['mitmproxy_resolved_dependencies'] = self.command(['pipx', 'runpip', 'mitmproxy', 'freeze', '--all'], env=env).stdout.splitlines()
        self.write(self.root / 'installation.json', json.dumps(report, indent=2) + '\n')
        self.write(self.root / 'managed-files.json', json.dumps({str(p): digest(p) for p in files}, indent=2) + '\n')
        self.env = env
        self.verify(require_trust=False)
        print('User tools installed. Trust/authentication are separate human Checkpoint B actions.')

    def validate_lock(self, lock):
        packages = json.loads(lock.read_text())['packages']
        for name, tool in self.manifest['user_tools'].items():
            if tool['method'] == 'npm':
                entry = packages['node_modules/' + name]
                require(entry['version'] == tool['version'] and entry['integrity'] == tool['integrity'] and
                        entry['resolved'] == tool['tarball'], 'reviewed npm version/integrity mismatch')
        for name, entry in packages.items():
            if name:
                require(entry.get('resolved', '').startswith('https://registry.npmjs.org/') and entry.get('integrity'),
                        'transitive npm dependency lacks registry HTTPS/integrity')

    def verify(self, *, require_trust=True):
        files = self.plan_files()
        for path, (text, _) in files.items():
            require(path.is_file() and path.read_text() == text, f'missing/stale managed file: {path}')
        for path in (self.home / '.m2/repository', self.home / '.gradle', self.home / '.pki/nssdb',
                     self.home / '.cache/ms-playwright', self.home / '.claude'):
            self.home_path(path)
            require(path.is_dir() and os.access(path, os.W_OK | os.X_OK), f'home path not writable: {path}')
        overlay = json.loads((REPO / 'ai-agent-sandbox/settings-overlay.json').read_text())
        settings_path = self.home / '.claude/settings.json'
        require(settings_path.is_file(), 'managed provider settings missing')
        settings = json.loads(settings_path.read_text())
        require(merge_settings(settings, overlay) == settings, 'managed controls/hook missing or stale')
        hook = overlay['hooks']['SessionStart'][0]['hooks'][0]['command']
        require(sum(h.get('command') == hook for g in settings['hooks']['SessionStart'] for h in g.get('hooks', [])) == 1,
                'duplicate managed SessionStart hook; inspect privately')
        skill = self.home / '.claude/skills/save-conversation/SKILL.md'
        require(skill.is_file() and skill.read_bytes() == (REPO / 'native/helpers/skills/save-conversation/SKILL.md').read_bytes(),
                'managed conversation skill missing/stale')
        self.validate_lock(self.root / 'npm/package-lock.json')
        for name, tool in self.manifest['user_tools'].items():
            if tool['method'] in ('npm', 'pipx', 'pipx-editable-guest-checkout'):
                command = tool['check'][0]
                result = self.command([self.bin / command, *tool['check'][1:]])
                if tool['method'] != 'pipx-editable-guest-checkout':
                    require(re.search(r'(?<![\d.])' + re.escape(tool['version']) + r'(?![\d.])', result.stdout + result.stderr),
                            f'{command}: installed version mismatch')
                print(f'{command}: version check passed')
        python = self.root / 'pipx/venvs/ai-session-handler/bin/python'
        origin = self.command([python, '-c', 'from pathlib import Path; import ai_session_handler; print(Path(ai_session_handler.__file__).resolve())']).stdout.strip()
        require(Path(origin).is_absolute() and Path(origin).is_relative_to(self.handler / 'src/ai_session_handler'), 'handler import origin mismatch')
        self.command([self.bin / 'ai-session-handler-codex-high', '--help'])
        for name in ('mitmweb', 'mitmdump'):
            self.command([self.bin / name, '--version'])
        for name in ('mitmflows', 'mitmflow-detail', 'mitmflow-body', 'ai-run'):
            self.command([self.bin / name, '--help'])
        env = self.env | self.environment_values()
        # Fresh noninteractive shell never sources a whole interactive profile.
        probe = '. ' + shlex.quote(str(self.fragment)) + '; command -v "$1"'
        for name in self.names:
            result = self.command(['bash', '--noprofile', '--norc', '-c', probe, 'native-check', name], env=env)
            require(result.stdout.strip() == str(self.bin / name), f'command resolution collision: {name}')
        self.command([self.bin / 'via-annotator', '--check'])
        browser = self.command(['node', '-e', 'const fs=require("fs");const p=require("playwright");const e=p.chromium.executablePath(); if(!e.startsWith(process.env.PLAYWRIGHT_BROWSERS_PATH+"/")) process.exit(2);fs.accessSync(e,fs.constants.X_OK);console.log(e)'], env=env)
        require(bool(browser.stdout.strip()), 'missing Chromium; human: playwright install chromium')
        self.command([self.bin / 'playwright', 'install', '--list'])
        if require_trust:
            self.command([self.bin / 'check-budget-analyzer-local-ca-trust'])
        print(f'Handler import: {origin}; browser/package/home and fresh-shell resolution verified.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'check'))
    parser.add_argument('--worktree-parent', required=True)
    parser.add_argument('--bare-parent', required=True)
    args = parser.parse_args()
    try:
        setup = UserTools(args.worktree_parent, args.bare_parent)
        setup.preflight()
        setup.install() if args.action == 'install' else setup.verify()
    except (UserToolsError, OSError, ValueError, KeyError) as exc:
        print(f'native-user-tools: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
