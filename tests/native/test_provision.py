"""Focused safety checks for the human-run system provisioner."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest


REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    'provision', REPO / 'scripts/native/provision.py')
provision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provision)


def minimal_manifest():
    return {
        'architectures': ['amd64'],
        'apt': [],
        'chromium_apt': [],
        'downloads': {},
        'repositories': {},
        'system_checks': [],
    }


class PreflightProbe(provision.Provisioner):
    """Small command shim for rejection-before-mutation checks."""

    def __init__(self, root):
        super().__init__(minimal_manifest(), 'developer')
        self.root = root
        self.calls = []
        self.missing_command = None
        self.container = 'none'
        self.vm = 'kvm'
        self.docker = False
        self.endpoint = 'unix:///var/run/docker.sock'
        self.absent_user = False
        self.account_uid = 1000
        self.current_uid = 1000
        self.path('/etc').mkdir(parents=True)
        self.path('/etc/os-release').write_text(
            'ID=ubuntu\nVERSION_ID="24.04"\n')
        self.path('/home/developer').mkdir(parents=True)
        self.env = {'HOME': str(self.path('/home/developer'))}

    def enable_docker(self):
        self.docker = True

    def path(self, value):
        if value == '/var/run/docker.sock':
            return self.root / 'docker.sock'
        return self.root / str(value).lstrip('/')

    def which(self, name):
        if name == self.missing_command:
            return None
        if name in ('docker', 'node', 'java', 'npm'):
            return f'/mock/{name}' if name == 'docker' and self.docker else None
        return f'/mock/{name}'

    def account(self):
        if self.absent_user:
            raise provision.ProvisionError('selected guest user does not exist')
        return SimpleNamespace(
            pw_name=self.user,
            pw_uid=self.account_uid,
            pw_dir='/home/developer',
            pw_shell='/bin/bash',
        )

    def uid(self):
        return self.current_uid

    def home_uid(self, home):
        return self.account_uid

    def machine(self):
        return 'x86_64'

    def environment(self):
        return self.env

    def root_owned(self, path):
        return None

    def installed(self, package):
        return False

    def command(self, argv, *, privileged=False, check=True):
        args = [str(arg) for arg in argv]
        self.calls.append((args, privileged))
        code, output = 0, ''
        if args[:2] == ['systemd-detect-virt', '--container']:
            output = self.container
            code = 1 if output == 'none' else 0
        elif args[:2] == ['systemd-detect-virt', '--vm']:
            output = self.vm
            code = 1 if output == 'none' else 0
        elif args[:2] == ['dpkg', '--print-architecture']:
            output = 'amd64'
        elif args[:2] == ['dpkg', '--audit']:
            output = ''
        elif args[:3] == ['docker', 'context', 'show']:
            output = 'default'
        elif args[:3] == ['docker', 'context', 'inspect']:
            output = self.endpoint
        elif args[:2] == ['docker', 'compose']:
            output = 'Docker Compose fixture'
        elif args[:2] == ['docker', 'info']:
            output = '/var/lib/docker'
        elif args[:2] == ['docker', 'ps']:
            output = ''
        result = subprocess.CompletedProcess(args, code, output, '')
        if check and code:
            raise provision.ProvisionError('fixture command failed')
        return result


class StageProbe(provision.Provisioner):
    def __init__(self, root):
        manifest = minimal_manifest()
        manifest['downloads']['kind'] = {
            'method': 'binary',
            'destination': '/usr/local/bin/kind',
            'platforms': {
                'amd64': {
                    'url': 'https://example.invalid/kind',
                    'sha256': hashlib.sha256(b'expected body').hexdigest(),
                }
            },
        }
        super().__init__(manifest, 'developer')
        self.root = root
        self.arch = 'amd64'
        self.pending = manifest['downloads'].copy()
        self.downloads = []
        self.privileged = []

    def download(self, url, destination):
        self.downloads.append((url, destination))
        destination.write_bytes(b'corrupt fixture body')

    def command(self, argv, *, privileged=False, check=True):
        if privileged:
            self.privileged.append([str(arg) for arg in argv])
        return subprocess.CompletedProcess(argv, 0, '', '')


class RepeatProbe(provision.Provisioner):
    def __init__(self):
        super().__init__(minimal_manifest(), 'developer')
        self.existing_docker = True
        self.pending = {}
        self.calls = []

    def installed(self, package):
        return True

    def command(self, argv, *, privileged=False, check=True):
        args = [str(arg) for arg in argv]
        self.calls.append((args, privileged))
        output = 'developer docker' if args[:2] == ['id', '-nG'] else ''
        return subprocess.CompletedProcess(args, 0, output, '')

    def validate(self):
        return None


class ProvisionSafetyTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / 'tmp/native-installer-safety'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(
            prefix='system path with spaces ', dir=scratch)
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def assert_rejected_without_mutation(self, configure, message):
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            probe = PreflightProbe(Path(directory))
            configure(probe)
            with self.assertRaisesRegex(provision.ProvisionError, message):
                probe.preflight()
            self.assertFalse(any(privileged for _, privileged in probe.calls))
            self.assertFalse(any(args[0] == 'curl' for args, _ in probe.calls))

    def test_invalid_targets_reject_before_sudo_or_download(self):
        cases = (
            ('wrong OS', lambda p: p.path('/etc/os-release').write_text(
                'ID=debian\nVERSION_ID="12"\n'), 'Ubuntu'),
            ('container', lambda p: setattr(p, 'container', 'docker'),
             'native execution'),
            ('non-VM', lambda p: setattr(p, 'vm', 'none'), 'QEMU/KVM'),
            ('remote Docker', lambda p: (
                p.enable_docker(), setattr(p, 'endpoint', 'tcp://remote:2376')),
             'remote/custom'),
            ('root target', lambda p: (
                setattr(p, 'user', 'root'), setattr(p, 'account_uid', 0),
                setattr(p, 'current_uid', 0)), 'normal development user'),
            ('missing user', lambda p: setattr(p, 'absent_user', True),
             'does not exist'),
            ('missing dependency', lambda p: setattr(
                p, 'missing_command', 'curl'), 'bootstrap command missing'),
        )
        for label, configure, message in cases:
            with self.subTest(label=label):
                self.assert_rejected_without_mutation(configure, message)

    def test_checksum_failure_precedes_mutation_and_preserves_spaced_path(self):
        probe = StageProbe(self.root)
        work = self.root / 'download staging with spaces'
        work.mkdir()
        with self.assertRaisesRegex(provision.ProvisionError, 'checksum mismatch'):
            probe.stage(work)
        self.assertEqual([], probe.privileged)
        self.assertEqual(1, len(probe.downloads))
        self.assertEqual(work / 'kind.download', probe.downloads[0][1])

    def test_repeat_with_healthy_docker_never_installs_or_restarts(self):
        probe = RepeatProbe()
        probe.install({})
        probe.install({})
        forbidden = {'apt-get', 'env', 'systemctl', 'usermod', 'install', 'cp', 'ln'}
        self.assertFalse(any(args[0] in forbidden for args, _ in probe.calls))
        self.assertFalse(any(privileged for _, privileged in probe.calls))


if __name__ == '__main__':
    unittest.main()
