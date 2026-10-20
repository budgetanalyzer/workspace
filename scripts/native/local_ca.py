#!/usr/bin/env python3
"""Exact-local-ingress trust: read-only agents, explicit human installation."""
import argparse
import hashlib
import os
from pathlib import Path
import pwd
import shlex
import stat
import subprocess
import sys

from boundary import is_private_primary_group

SYSTEM_CERT = Path('/usr/local/share/ca-certificates/budget-analyzer-local-mkcert.crt')
LEGACY_SYSTEM_CERT = Path('/usr/local/share/ca-certificates/budget-analyzer-local-ingress-ca.crt')
SYSTEM_BUNDLE = Path('/etc/ssl/certs/ca-certificates.crt')
SYSTEM_OWNER_UID = 0
SYSTEM_OWNER_GID = 0
NICKNAME = 'Budget Analyzer local mkcert CA'
HOSTNAME = 'app.budgetanalyzer.localhost'
RECORD_NAME = 'approved-local-root.pem'


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


def path_exists(path):
    """Include broken symlinks in collision checks."""
    return os.path.lexists(path)


def system_certificate_fingerprint(path, label):
    if not path_exists(path):
        return None
    require(not path.is_symlink(), f'{label} is a symlink; inspect privately', 13)
    status = path.stat()
    require(stat.S_ISREG(status.st_mode), f'{label} is not a regular file; inspect privately', 13)
    require(status.st_uid == SYSTEM_OWNER_UID and status.st_gid == SYSTEM_OWNER_GID,
            f'{label} has unexpected ownership; inspect privately', 13)
    require(not status.st_mode & 0o022,
            f'{label} is group/world writable; inspect privately', 13)
    try:
        return fingerprint(path)
    except TrustError:
        raise TrustError(f'{label} is not a valid public root; inspect privately', 13) from None


def inspect_system_certificates(wanted):
    canonical = system_certificate_fingerprint(SYSTEM_CERT, 'managed system root')
    legacy = system_certificate_fingerprint(LEGACY_SYSTEM_CERT, 'legacy system root')
    if legacy is not None and legacy != wanted:
        raise TrustError('legacy system root differs from approved publication; '
                         f'review fingerprints explicitly (approved {wanted}, legacy {legacy})', 13)
    return canonical, legacy


def human_command(worktrees, bares):
    return shlex.join([str(worktrees / 'workspace/scripts/install-agent-vm-local-ca-trust.sh'),
                       '--worktree-parent', str(worktrees), '--bare-parent', str(bares),
                       '--ca-file', 'CA_PEM', '--leaf-file', 'LEAF_PEM']) + \
        ' (see docs/local-budget-analyzer-tls.md)'


def record_path(home):
    return home / '.local/share/budget-analyzer-native/trust' / RECORD_NAME


def validate_record_path(record, account):
    for path in (record.parent.parent, record.parent, record):
        require(not path.is_symlink(), 'approved root record symlink collision; inspect privately', 16)
        if path.exists():
            status = path.stat()
            expected = stat.S_ISDIR if path != record else stat.S_ISREG
            unsafe_group_write = (status.st_mode & 0o020 and not
                                  is_private_primary_group(account.pw_name, account.pw_gid,
                                                           status.st_gid))
            require(expected(status.st_mode) and status.st_uid == account.pw_uid and
                    not status.st_mode & 0o002 and not unsafe_group_write,
                    'approved root record ownership/permissions collision; inspect privately', 16)


def validate_root(root, label):
    require(root.is_file(), f'{label} missing', 10)
    require(b'PRIVATE KEY' not in root.read_bytes(), f'{label} contains a signing key; refuse import', 11)
    require(run(['openssl', 'x509', '-in', root, '-checkend', '0', '-noout']).returncode == 0,
            f'{label} invalid/expired; renew only on personal host', 11)
    text = run(['openssl', 'x509', '-in', root, '-text', '-noout'])
    require(text.returncode == 0 and b'CA:TRUE' in text.stdout, f'{label} is not a CA', 11)
    return fingerprint(root)


def validate_publication(root, leaf):
    require(root.is_file() and leaf.is_file(),
            'supplied CA or leaf file missing; human must renew on personal host and transfer only the three approved files', 10)
    wanted = validate_root(root, 'supplied CA')
    require(b'PRIVATE KEY' not in leaf.read_bytes(), 'supplied leaf contains a private key; refuse import', 11)
    require(run(['openssl', 'x509', '-in', leaf, '-checkend', '0', '-noout']).returncode == 0,
            'supplied leaf invalid/expired; renew only on personal host', 11)
    require(run(['openssl', 'verify', '-no-CApath', '-no-CAstore', '-CAfile', root,
                 '-verify_hostname', HOSTNAME, leaf]).returncode == 0,
            'supplied CA does not verify exact ingress hostname/leaf', 11)
    return wanted


def write_record(record, root, account):
    validate_record_path(record, account)
    record.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = record.with_name(record.name + '.native-tmp')
    require(not path_exists(temp), 'approved root record temporary path collision; inspect privately', 16)
    with temp.open('xb') as stream:
        stream.write(root.read_bytes())
    temp.chmod(0o600)
    temp.replace(record)


def validate_nss_paths(home, account):
    nss = home / '.pki/nssdb'
    for path in (home, home / '.pki', nss):
        require(not path.is_symlink(), 'NSS path symlink collision', 15)
        if path.exists():
            status = path.stat()
            unsafe_group_write = (status.st_mode & 0o020 and not
                                  is_private_primary_group(account.pw_name, account.pw_gid,
                                                           status.st_gid))
            require(status.st_uid == account.pw_uid and not status.st_mode & 0o002 and
                    not unsafe_group_write, 'NSS ownership/permissions collision', 15)
    return nss


def install(root, leaf, worktrees, bares, home, account):
    """Human-only: import the supplied public CA, then record it as approved."""
    record = record_path(home)
    validate_record_path(record, account)
    wanted = validate_publication(root, leaf)
    nss = validate_nss_paths(home, account)
    system_identity, legacy_identity = inspect_system_certificates(wanted)
    print('Approved public root SHA256: ' + wanted)
    system_changed = False
    if system_identity != wanted:
        require(run(['sudo', '--', 'install', '-m', '0644', root, SYSTEM_CERT]).returncode == 0,
                'human system root import failed', 13)
        require(system_certificate_fingerprint(SYSTEM_CERT, 'managed system root') == wanted,
                'installed managed system root identity mismatch', 13)
        system_changed = True
    if legacy_identity is not None:
        # Recheck immediately before deleting this one exact, known duplicate.
        require(system_certificate_fingerprint(LEGACY_SYSTEM_CERT, 'legacy system root') == wanted,
                'legacy system root changed during convergence; inspect privately', 13)
        require(run(['sudo', '--', 'rm', '--', LEGACY_SYSTEM_CERT]).returncode == 0,
                'legacy duplicate removal failed', 13)
        require(not path_exists(LEGACY_SYSTEM_CERT),
                'legacy duplicate remains after removal', 13)
        system_changed = True
    if system_changed or not bundle_trusts(root):
        require(run(['sudo', '--', 'update-ca-certificates']).returncode == 0,
                'human combined trust update failed', 13)
    nss.mkdir(parents=True, mode=0o700, exist_ok=True)
    if not (nss / 'cert9.db').exists():
        require(run(['certutil', '-N', '-d', 'sql:' + str(nss), '--empty-password']).returncode == 0,
                'human NSS initialization failed', 15)
    current = run(['certutil', '-L', '-d', 'sql:' + str(nss), '-n', NICKNAME, '-a'])
    if current.returncode or fingerprint(data=current.stdout) != wanted or not nss_flags_current(nss):
        if current.returncode == 0:
            require(run(['certutil', '-D', '-d', 'sql:' + str(nss), '-n', NICKNAME,
                         '-f', '/dev/null']).returncode == 0,
                    'human NSS managed-root replacement failed', 15)
        require(run(['certutil', '-A', '-d', 'sql:' + str(nss), '-n', NICKNAME, '-t', 'C,,', '-i', root, '-f', '/dev/null']).returncode == 0,
                'human NSS public root import failed (password-protected DB needs private human review)', 15)
    command = human_command(worktrees, bares)
    verify_stores(root, wanted, nss, command)
    require(run(['openssl', 'verify', '-no-CApath', '-no-CAstore', '-CAfile', SYSTEM_BUNDLE,
                 '-verify_hostname', HOSTNAME, leaf]).returncode == 0,
            'combined system trust does not verify supplied ingress leaf', 13)
    write_record(record, root, account)
    check(worktrees, bares, home, account)


def bundle_trusts(root):
    return SYSTEM_BUNDLE.is_file() and run(['openssl', 'verify', '-no-CApath', '-no-CAstore',
                                            '-CAfile', SYSTEM_BUNDLE, root]).returncode == 0


def nss_flags_current(nss):
    flags = run(['certutil', '-L', '-d', 'sql:' + str(nss)])
    return flags.returncode == 0 and any(line.startswith(NICKNAME) and line.split()[-1] == 'C,,'
                                         for line in flags.stdout.decode().splitlines())


def verify_stores(root, wanted, nss, command):
    system_identity, legacy_identity = inspect_system_certificates(wanted)
    require(system_identity == wanted and legacy_identity is None and bundle_trusts(root),
            'system trust missing/stale/duplicated; human command: ' + command, 13)
    require((nss / 'cert9.db').is_file(), 'NSS trust missing; human command: ' + command, 15)
    exported = run(['certutil', '-L', '-d', 'sql:' + str(nss), '-n', NICKNAME, '-a'])
    require(exported.returncode == 0 and fingerprint(data=exported.stdout) == wanted,
            'NSS root missing/stale; human command: ' + command, 15)
    require(nss_flags_current(nss), 'NSS CA flags stale; human command: ' + command, 15)


def check(worktrees, bares, home, account):
    """Read-only: compare OS/NSS stores with the recorded approved root."""
    command = human_command(worktrees, bares)
    record = record_path(home)
    validate_record_path(record, account)
    require(record.is_file(), 'approved root record missing; human command: ' + command, 10)
    wanted = validate_root(record, 'recorded approved root')
    nss = validate_nss_paths(home, account)
    verify_stores(record, wanted, nss, command)
    require(os.environ.get('SSL_CERT_FILE') == str(SYSTEM_BUNDLE) and
            os.environ.get('NODE_EXTRA_CA_CERTS') == str(SYSTEM_BUNDLE), 'load the native environment fragment for Python/Node trust', 14)
    print('Verified OS/NSS stores trust recorded root SHA256: ' + wanted)
    print('Store state only; browser acceptance needs the exact-URL check in docs/local-budget-analyzer-tls.md.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('human-install', 'check-budget-analyzer-local-ca-trust',
                                         'ensure-budget-analyzer-local-ca-trust'))
    parser.add_argument('--worktree-parent')
    parser.add_argument('--bare-parent')
    parser.add_argument('--ca-file', help='human-install: approved public mkcert root PEM')
    parser.add_argument('--leaf-file', help='human-install: current ingress leaf PEM for ' + HOSTNAME)
    args = parser.parse_args()
    if args.action == 'human-install' and not (args.ca_file and args.leaf_file):
        parser.error('human-install requires --ca-file and --leaf-file')
    if args.action != 'human-install' and (args.ca_file or args.leaf_file):
        parser.error('read-only checks use the recorded approved root, not supplied files')
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
            install(Path(args.ca_file).resolve(), Path(args.leaf_file).resolve(),
                    worktrees, bares, home, account)
        else:
            check(worktrees, bares, home, account)
    except TrustError as exc:
        print('local-ca-trust: ' + str(exc), file=sys.stderr)
        return exc.code
    except (OSError, KeyError, ValueError, RuntimeError):
        print('local-ca-trust: prerequisite unavailable or native identity preflight failed; inspect privately', file=sys.stderr)
        return 12
    return 0


if __name__ == '__main__':
    sys.exit(main())
