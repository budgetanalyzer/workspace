"""Offline guest CA convergence fixtures with disposable trust stores."""
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[2]
SCRATCH = REPO / 'tmp/native-local-ca-safety'
SCRATCH.mkdir(parents=True, exist_ok=True)
user_tools_spec = importlib.util.spec_from_file_location(
    'user_tools', REPO / 'scripts/native/user_tools.py')
user_tools = importlib.util.module_from_spec(user_tools_spec)
user_tools_spec.loader.exec_module(user_tools)
local_ca_spec = importlib.util.spec_from_file_location(
    'local_ca', REPO / 'scripts/native/local_ca.py')
local_ca = importlib.util.module_from_spec(local_ca_spec)
with patch.dict(sys.modules, {'user_tools': user_tools}):
    local_ca_spec.loader.exec_module(local_ca)


class TrustCommandFixture:
    """Model only the system/NSS commands used by local_ca."""

    def __init__(self, root, system_cert, legacy_cert, bundle, nss):
        self.root = root
        self.system_cert = system_cert
        self.legacy_cert = legacy_cert
        self.bundle = bundle
        self.nss = nss
        self.bundle_current = True
        self.expired = set()
        self.not_ca = set()
        self.hostname_matches = True
        self.fail_prefix = None
        self.nss_managed = None
        self.nss_entries = {'Unrelated Public Root': 'C,,'}
        self.calls = []

    @staticmethod
    def result(code=0, output=b''):
        return SimpleNamespace(returncode=code, stdout=output, stderr=b'')

    def __call__(self, args, *, data=None):
        args = [str(arg) for arg in args]
        self.calls.append(args)
        if self.fail_prefix and args[:len(self.fail_prefix)] == self.fail_prefix:
            return self.result(1)
        if args[:3] == ['openssl', 'x509', '-outform']:
            payload = Path(args[args.index('-in') + 1]).read_bytes() if '-in' in args else data
            return self.result(output=b'DER:' + payload)
        if args[:2] == ['openssl', 'x509']:
            subject = Path(args[args.index('-in') + 1])
            if '-checkend' in args:
                return self.result(1 if subject.read_bytes() in self.expired else 0)
            return self.result(output=b'CA:FALSE\n' if subject in self.not_ca else b'CA:TRUE\n')
        if args[:2] == ['openssl', 'verify']:
            ca_file = Path(args[args.index('-CAfile') + 1])
            if '-verify_hostname' in args and not self.hostname_matches:
                return self.result(2)
            return self.result(0 if ca_file != self.bundle or self.bundle_current else 1)
        if args[:4] == ['sudo', '--', 'install', '-m']:
            shutil.copyfile(args[-2], args[-1])
            Path(args[-1]).chmod(0o644)
            return self.result()
        if args[:4] == ['sudo', '--', 'rm', '--']:
            Path(args[-1]).unlink()
            return self.result()
        if args[:3] == ['sudo', '--', 'update-ca-certificates']:
            self.bundle_current = True
            self.bundle.write_bytes(b'fixture combined bundle')
            return self.result()
        if args[:2] == ['certutil', '-N']:
            (self.nss / 'cert9.db').write_bytes(b'fixture NSS database')
            return self.result()
        if args[:2] == ['certutil', '-L'] and '-n' in args:
            if self.nss_managed is None:
                return self.result(255)
            return self.result(output=self.nss_managed)
        if args[:2] == ['certutil', '-L']:
            entries = dict(self.nss_entries)
            if self.nss_managed is not None:
                entries[local_ca.NICKNAME] = 'C,,'
            output = ''.join(f'{name}   {flags}\n' for name, flags in entries.items())
            return self.result(output=output.encode())
        if args[:2] == ['certutil', '-D']:
            self.nss_managed = None
            return self.result()
        if args[:2] == ['certutil', '-A']:
            self.nss_managed = Path(args[args.index('-i') + 1]).read_bytes()
            return self.result()
        raise AssertionError(f'unexpected fixture command: {args}')

    def mutations(self):
        return [call for call in self.calls
                if call[0] == 'sudo' or call[:2] in (
                    ['certutil', '-N'], ['certutil', '-D'], ['certutil', '-A'])]


class LocalCaConvergenceTests(unittest.TestCase):
    APPROVED = b'fixture approved public root certificate\n'
    DIFFERENT = b'fixture unexplained public root certificate\n'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='trust path with spaces ', dir=SCRATCH)
        self.fixture = Path(self.temp.name)
        self.worktrees = self.fixture / 'work trees'
        self.bares = self.fixture / 'bare repos'
        self.worktrees.mkdir()
        supplied = self.fixture / 'supplied publication'
        supplied.mkdir()
        self.root = supplied / 'approved root.pem'
        self.leaf = supplied / 'current leaf.pem'
        self.root.write_bytes(self.APPROVED)
        self.leaf.write_bytes(b'fixture approved ingress leaf\n')
        self.bares.mkdir()
        self.home = self.fixture / 'home'
        self.nss = self.home / '.pki/nssdb'
        self.nss.mkdir(mode=0o700, parents=True)
        self.home.chmod(0o700)
        (self.home / '.pki').chmod(0o700)
        (self.nss / 'cert9.db').write_bytes(b'fixture NSS database')
        self.record = self.home / '.local/share/budget-analyzer-native/trust/approved-local-root.pem'
        self.system_dir = self.fixture / 'system trust'
        self.system_dir.mkdir()
        self.system_cert = self.system_dir / 'budget-analyzer-local-mkcert.crt'
        self.legacy_cert = self.system_dir / 'budget-analyzer-local-ingress-ca.crt'
        self.public_root = self.system_dir / 'unrelated-public-root.crt'
        self.public_root.write_bytes(b'fixture unrelated public trust root\n')
        self.bundle = self.fixture / 'ca-certificates.crt'
        self.bundle.write_bytes(b'fixture combined bundle')
        self.account = SimpleNamespace(
            pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name='fixture-user')
        self.runner = TrustCommandFixture(
            self.root, self.system_cert, self.legacy_cert, self.bundle, self.nss)
        self.patches = [
            patch.object(local_ca, 'SYSTEM_CERT', self.system_cert),
            patch.object(local_ca, 'LEGACY_SYSTEM_CERT', self.legacy_cert),
            patch.object(local_ca, 'SYSTEM_BUNDLE', self.bundle),
            patch.object(local_ca, 'SYSTEM_OWNER_UID', os.getuid()),
            patch.object(local_ca, 'SYSTEM_OWNER_GID', os.getgid()),
            patch.object(local_ca, 'run', self.runner),
            patch.object(local_ca, 'is_private_primary_group', return_value=True),
            patch.dict(os.environ, {
                'SSL_CERT_FILE': str(self.bundle),
                'NODE_EXTRA_CA_CERTS': str(self.bundle),
            }),
        ]
        for item in self.patches:
            item.start()
        self.quiet = contextlib.redirect_stdout(io.StringIO())
        self.quiet.__enter__()

    def tearDown(self):
        self.quiet.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def install(self):
        local_ca.install(self.root, self.leaf, self.worktrees, self.bares,
                         self.home, self.account)

    def check(self):
        local_ca.check(self.worktrees, self.bares, self.home, self.account)

    @staticmethod
    def write_system_certificate(path, content):
        path.write_bytes(content)
        path.chmod(0o644)

    def test_exact_legacy_duplicate_converges_once_and_preserves_nss_entries(self):
        self.write_system_certificate(self.legacy_cert, self.APPROVED)

        self.install()

        self.assertEqual(self.APPROVED, self.system_cert.read_bytes())
        self.assertFalse(local_ca.path_exists(self.legacy_cert))
        self.assertEqual(b'fixture unrelated public trust root\n', self.public_root.read_bytes())
        self.assertEqual(self.APPROVED, self.runner.nss_managed)
        self.assertEqual({'Unrelated Public Root': 'C,,'}, self.runner.nss_entries)
        first_mutations = self.runner.mutations()
        self.assertEqual(1, sum(call[:3] == ['sudo', '--', 'install']
                                for call in first_mutations))
        self.assertEqual(1, sum(call[:3] == ['sudo', '--', 'rm']
                                for call in first_mutations))
        self.assertEqual(1, sum(call[:3] == ['sudo', '--', 'update-ca-certificates']
                                for call in first_mutations))

        self.runner.calls.clear()
        self.install()
        self.assertEqual([], self.runner.mutations())
        self.assertEqual(b'fixture unrelated public trust root\n', self.public_root.read_bytes())
        self.assertEqual({'Unrelated Public Root': 'C,,'}, self.runner.nss_entries)

    def test_different_legacy_root_refuses_before_any_mutation(self):
        self.write_system_certificate(self.legacy_cert, self.DIFFERENT)
        approved = hashlib.sha256(b'DER:' + self.APPROVED).hexdigest()
        different = hashlib.sha256(b'DER:' + self.DIFFERENT).hexdigest()

        with self.assertRaisesRegex(
                local_ca.TrustError,
                f'approved {approved}, legacy {different}'):
            self.install()

        self.assertEqual([], self.runner.mutations())
        self.assertFalse(self.system_cert.exists())
        self.assertEqual(self.DIFFERENT, self.legacy_cert.read_bytes())

    def test_legacy_nonregular_symlink_and_unexpected_owner_are_rejected(self):
        self.legacy_cert.mkdir()
        with self.assertRaisesRegex(local_ca.TrustError, 'is not a regular file'):
            self.install()
        self.assertEqual([], self.runner.mutations())

        self.legacy_cert.rmdir()
        target = self.system_dir / 'symlink target.crt'
        self.write_system_certificate(target, self.APPROVED)
        self.legacy_cert.symlink_to(target)
        with self.assertRaisesRegex(local_ca.TrustError, 'legacy system root is a symlink'):
            self.install()
        self.assertEqual([], self.runner.mutations())

        self.legacy_cert.unlink()
        self.write_system_certificate(self.legacy_cert, self.APPROVED)
        with patch.object(local_ca, 'SYSTEM_OWNER_UID', os.getuid() + 1), \
                self.assertRaisesRegex(local_ca.TrustError, 'unexpected ownership'):
            self.install()
        self.assertEqual([], self.runner.mutations())

    def test_managed_root_rotation_and_read_only_verification(self):
        self.write_system_certificate(self.system_cert, self.DIFFERENT)
        self.runner.nss_managed = self.DIFFERENT

        self.install()

        self.assertEqual(self.APPROVED, self.system_cert.read_bytes())
        self.assertEqual(self.APPROVED, self.runner.nss_managed)
        self.assertEqual({'Unrelated Public Root': 'C,,'}, self.runner.nss_entries)
        self.runner.calls.clear()
        before = {str(path): path.read_bytes()
                  for path in self.fixture.rglob('*') if path.is_file()}

        self.check()

        after = {str(path): path.read_bytes()
                 for path in self.fixture.rglob('*') if path.is_file()}
        self.assertEqual(before, after)
        self.assertEqual([], self.runner.mutations())


    def test_explicit_inputs_record_approved_root_and_check_ignores_supplied_files(self):
        self.install()

        self.assertEqual(self.APPROVED, self.record.read_bytes())
        self.assertEqual(0o600, self.record.stat().st_mode & 0o777)
        self.assertEqual(0o700, self.record.parent.stat().st_mode & 0o777)
        self.root.unlink()
        self.leaf.unlink()
        self.runner.calls.clear()

        self.check()

        self.assertEqual([], self.runner.mutations())
        self.assertTrue(all(str(self.fixture / 'supplied publication') not in arg
                            for call in self.runner.calls for arg in call))

    def assert_rejected_before_mutation(self, pattern, code=11):
        with self.assertRaisesRegex(local_ca.TrustError, pattern) as raised:
            self.install()
        self.assertEqual(code, raised.exception.code)
        self.assertEqual([], self.runner.mutations())
        self.assertFalse(self.system_cert.exists())
        self.assertFalse(local_ca.path_exists(self.record))

    def test_rejected_inputs_leave_stores_and_record_untouched(self):
        self.root.write_bytes(self.APPROVED + b'-----BEGIN PRIVATE KEY-----\n')
        self.assert_rejected_before_mutation('supplied CA contains a signing key')
        self.root.write_bytes(self.APPROVED)

        self.leaf.write_bytes(b'leaf\n-----BEGIN EC PRIVATE KEY-----\n')
        self.assert_rejected_before_mutation('supplied leaf contains a private key')
        self.leaf.write_bytes(b'fixture approved ingress leaf\n')

        self.runner.expired = {self.APPROVED}
        self.assert_rejected_before_mutation('supplied CA invalid/expired')
        self.runner.expired = {b'fixture approved ingress leaf\n'}
        self.assert_rejected_before_mutation('supplied leaf invalid/expired')
        self.runner.expired = set()

        self.runner.not_ca = {self.root}
        self.assert_rejected_before_mutation('supplied CA is not a CA')
        self.runner.not_ca = set()

        self.runner.hostname_matches = False
        self.assert_rejected_before_mutation('does not verify exact ingress hostname/leaf')
        self.runner.hostname_matches = True

        self.leaf.unlink()
        self.assert_rejected_before_mutation('supplied CA or leaf file missing', code=10)

    def test_failed_install_leaves_no_record(self):
        for prefix, pattern in ((['sudo', '--', 'install'], 'system root import failed'),
                                (['sudo', '--', 'update-ca-certificates'], 'combined trust update failed'),
                                (['certutil', '-A'], 'NSS public root import failed')):
            self.runner.fail_prefix = prefix
            with self.assertRaisesRegex(local_ca.TrustError, pattern):
                self.install()
            self.assertFalse(local_ca.path_exists(self.record), prefix)
        self.runner.fail_prefix = None

        # Stores already current except a stale bundle: still no record on failure.
        self.runner.bundle_current = False
        self.runner.fail_prefix = ['sudo', '--', 'update-ca-certificates']
        with self.assertRaisesRegex(local_ca.TrustError, 'combined trust update failed'):
            self.install()
        self.assertFalse(local_ca.path_exists(self.record))

    def test_missing_record_fails_closed_with_human_command(self):
        self.install()
        self.record.unlink()

        with self.assertRaisesRegex(local_ca.TrustError, 'approved root record missing') as raised:
            self.check()
        self.assertEqual(10, raised.exception.code)
        self.assertIn('install-agent-vm-local-ca-trust.sh', str(raised.exception))
        self.assertIn('--ca-file CA_PEM --leaf-file LEAF_PEM', str(raised.exception))
        self.assertNotIn('orchestration', str(raised.exception))

    def test_expired_or_unsafe_record_fails(self):
        self.install()
        self.runner.expired = {self.APPROVED}
        with self.assertRaisesRegex(local_ca.TrustError, 'recorded approved root invalid/expired'):
            self.check()
        self.runner.expired = set()

        self.record.chmod(0o666)
        with self.assertRaisesRegex(local_ca.TrustError, 'record ownership/permissions'):
            self.check()
        self.record.chmod(0o600)

        target = self.fixture / 'elsewhere.pem'
        target.write_bytes(self.APPROVED)
        self.record.unlink()
        self.record.symlink_to(target)
        with self.assertRaisesRegex(local_ca.TrustError, 'record symlink collision'):
            self.check()
        with self.assertRaisesRegex(local_ca.TrustError, 'record symlink collision'):
            self.install()

    def test_stores_trusting_a_different_root_than_record_fail(self):
        self.install()
        self.runner.nss_managed = self.DIFFERENT
        with self.assertRaisesRegex(local_ca.TrustError, 'NSS root missing/stale'):
            self.check()

        self.runner.nss_managed = self.APPROVED
        self.system_cert.write_bytes(self.DIFFERENT)
        with self.assertRaisesRegex(local_ca.TrustError, 'system trust missing/stale/duplicated'):
            self.check()

        self.system_cert.write_bytes(self.APPROVED)
        self.runner.bundle_current = False
        with self.assertRaisesRegex(local_ca.TrustError, 'system trust missing/stale/duplicated'):
            self.check()

    def test_cli_requires_explicit_inputs_only_for_human_install(self):
        for argv in (['local_ca.py', 'human-install'],
                     ['local_ca.py', 'human-install', '--ca-file', str(self.root)],
                     ['local_ca.py', 'check-budget-analyzer-local-ca-trust',
                      '--ca-file', str(self.root), '--leaf-file', str(self.leaf)]):
            with patch.object(sys, 'argv', argv), \
                    contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit) as raised:
                local_ca.main()
            self.assertEqual(2, raised.exception.code)
        self.assertEqual([], self.runner.calls)

if __name__ == '__main__':
    unittest.main()
