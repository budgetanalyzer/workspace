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
        self.nss_managed = None
        self.nss_entries = {'Unrelated Public Root': 'C,,'}
        self.calls = []

    @staticmethod
    def result(code=0, output=b''):
        return SimpleNamespace(returncode=code, stdout=output, stderr=b'')

    def __call__(self, args, *, data=None):
        args = [str(arg) for arg in args]
        self.calls.append(args)
        if args[:3] == ['openssl', 'x509', '-outform']:
            payload = Path(args[args.index('-in') + 1]).read_bytes() if '-in' in args else data
            return self.result(output=b'DER:' + payload)
        if args[:2] == ['openssl', 'x509']:
            return self.result(output=b'CA:TRUE\n')
        if args[:2] == ['openssl', 'verify']:
            ca_file = Path(args[args.index('-CAfile') + 1])
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
        certs = self.worktrees / 'orchestration/nginx/certs/k8s'
        certs.mkdir(parents=True)
        self.root = certs / '_mkcert-rootCA.pem'
        self.leaf = certs / '_wildcard.budgetanalyzer.localhost.pem'
        self.root.write_bytes(self.APPROVED)
        self.leaf.write_bytes(b'fixture approved ingress leaf\n')
        self.bares.mkdir()
        self.home = self.fixture / 'home'
        self.nss = self.home / '.pki/nssdb'
        self.nss.mkdir(mode=0o700, parents=True)
        self.home.chmod(0o700)
        (self.home / '.pki').chmod(0o700)
        (self.nss / 'cert9.db').write_bytes(b'fixture NSS database')
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
        local_ca.check_or_install(
            self.worktrees, self.bares, self.home, self.account, install=True)

    def check(self):
        local_ca.check_or_install(
            self.worktrees, self.bares, self.home, self.account, install=False)

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


if __name__ == '__main__':
    unittest.main()
