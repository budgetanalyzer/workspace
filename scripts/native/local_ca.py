#!/usr/bin/env python3
"""Exact-local-ingress trust: read-only agents, explicit human installation."""
import argparse
import hashlib
import os
from pathlib import Path
import pwd
import shlex
import subprocess
import sys

SYSTEM_CERT = Path('/usr/local/share/ca-certificates/budget-analyzer-local-mkcert.crt')
SYSTEM_BUNDLE = Path('/etc/ssl/certs/ca-certificates.crt')
NICKNAME = 'Budget Analyzer local mkcert CA'


class TrustError(RuntimeError):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


def run(args, *, data=None):
    return subprocess.run([str(a) for a in args], input=data, capture_output=True)


def require(ok, message, code):
    if not ok:
        raise TrustError(message, code)


def fingerprint(path=None, data=None):
    args = ['openssl', 'x509', '-outform', 'DER']
    if path:
        args += ['-in', path]
    result = run(args, data=data)
    require(result.returncode == 0, 'invalid public root certificate', 11)
    return hashlib.sha256(result.stdout).hexdigest()


def human_command(worktrees, bares):
    return shlex.join([str(worktrees / 'workspace/scripts/install-agent-vm-local-ca-trust.sh'),
                       '--worktree-parent', str(worktrees), '--bare-parent', str(bares)])


def check_or_install(worktrees, bares, home, install=False):
    root = worktrees / 'orchestration/nginx/certs/k8s/_mkcert-rootCA.pem'
    leaf = root.with_name('_wildcard.budgetanalyzer.localhost.pem')
    require(root.is_file() and leaf.is_file(),
            'approved ingress publication missing; human must renew on personal host and transfer only the three approved files', 10)
    require(b'PRIVATE KEY' not in root.read_bytes(), 'publication contains a signing key; refuse import', 11)
    require(run(['openssl', 'x509', '-in', root, '-checkend', '0', '-noout']).returncode == 0,
            'public root invalid/expired; renew only on personal host', 11)
    text = run(['openssl', 'x509', '-in', root, '-text', '-noout'])
    require(text.returncode == 0 and b'CA:TRUE' in text.stdout, 'publication is not a CA', 11)
    require(run(['openssl', 'verify', '-CAfile', root, '-verify_hostname', 'app.budgetanalyzer.localhost', leaf]).returncode == 0,
            'approved public root does not verify exact ingress hostname/leaf', 11)
    wanted = fingerprint(root)
    nss = home / '.pki/nssdb'
    for path in (home, home / '.pki', nss):
        require(not path.is_symlink(), 'NSS path symlink collision', 15)
        if path.exists():
            require(path.stat().st_uid == os.getuid() and not path.stat().st_mode & 0o022,
                    'NSS ownership/permissions collision', 15)
    system_current = SYSTEM_CERT.is_file() and fingerprint(SYSTEM_CERT) == wanted
    bundle_current = SYSTEM_BUNDLE.is_file() and run(['openssl', 'verify', '-CAfile', SYSTEM_BUNDLE, leaf]).returncode == 0
    command = human_command(worktrees, bares)
    if install:
        print('Approved public root SHA256: ' + wanted)
        if not system_current:
            require(run(['sudo', '--', 'install', '-m', '0644', root, SYSTEM_CERT]).returncode == 0,
                    'human system root import failed', 13)
        if not system_current or not bundle_current:
            require(run(['sudo', '--', 'update-ca-certificates']).returncode == 0,
                    'human combined trust update failed', 13)
        nss.mkdir(parents=True, mode=0o700, exist_ok=True)
        if not (nss / 'cert9.db').exists():
            require(run(['certutil', '-N', '-d', 'sql:' + str(nss), '--empty-password']).returncode == 0,
                    'human NSS initialization failed', 15)
        current = run(['certutil', '-L', '-d', 'sql:' + str(nss), '-n', NICKNAME, '-a'])
        trusted = run(['certutil', '-L', '-d', 'sql:' + str(nss)])
        flags = any(line.startswith(NICKNAME) and line.split()[-1] == 'C,,' for line in trusted.stdout.decode().splitlines())
        if current.returncode or fingerprint(data=current.stdout) != wanted or not flags:
            run(['certutil', '-D', '-d', 'sql:' + str(nss), '-n', NICKNAME, '-f', '/dev/null'])
            require(run(['certutil', '-A', '-d', 'sql:' + str(nss), '-n', NICKNAME, '-t', 'C,,', '-i', root, '-f', '/dev/null']).returncode == 0,
                    'human NSS public root import failed (password-protected DB needs private human review)', 15)
        return check_or_install(worktrees, bares, home)
    require(system_current and bundle_current, 'system trust missing/stale; human command: ' + command, 13)
    require(os.environ.get('SSL_CERT_FILE') == str(SYSTEM_BUNDLE) and
            os.environ.get('NODE_EXTRA_CA_CERTS') == str(SYSTEM_BUNDLE), 'load the native environment fragment for Python/Node trust', 14)
    require((nss / 'cert9.db').is_file(), 'NSS trust missing; human command: ' + command, 15)
    exported = run(['certutil', '-L', '-d', 'sql:' + str(nss), '-n', NICKNAME, '-a'])
    require(exported.returncode == 0 and fingerprint(data=exported.stdout) == wanted,
            'NSS root missing/stale; human command: ' + command, 15)
    flags = run(['certutil', '-L', '-d', 'sql:' + str(nss)])
    require(flags.returncode == 0 and any(line.startswith(NICKNAME) and line.split()[-1] == 'C,,'
                                        for line in flags.stdout.decode().splitlines()), 'NSS CA flags stale; human command: ' + command, 15)
    print('Verified established local trust SHA256: ' + wanted)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('human-install', 'check-budget-analyzer-local-ca-trust',
                                         'ensure-budget-analyzer-local-ca-trust'))
    parser.add_argument('--worktree-parent')
    parser.add_argument('--bare-parent')
    args = parser.parse_args()
    try:
        account = pwd.getpwuid(os.getuid())
        home = Path(account.pw_dir)
        require(account.pw_uid >= 1000 and os.environ.get('HOME') == str(home), 'requires normal development home/user', 12)
        worktrees = Path(args.worktree_parent or os.environ['BUDGET_ANALYZER_WORKTREE_PARENT'])
        bares = Path(args.bare_parent or os.environ['BUDGET_ANALYZER_BARE_PARENT'])
        if args.action == 'human-install':
            from user_tools import UserTools
            setup = UserTools(worktrees, bares)
            setup.preflight()
        check_or_install(worktrees, bares, home, args.action == 'human-install')
    except TrustError as exc:
        print('local-ca-trust: ' + str(exc), file=sys.stderr)
        return exc.code
    except (OSError, KeyError, ValueError, RuntimeError):
        print('local-ca-trust: prerequisite unavailable or native identity preflight failed; inspect privately', file=sys.stderr)
        return 12
    return 0


if __name__ == '__main__':
    sys.exit(main())
