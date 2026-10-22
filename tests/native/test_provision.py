"""Focused safety checks for the human-run system provisioner."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    'provision', REPO / 'scripts/native/provision.py')
provision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provision)
boundary = sys.modules['boundary']


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
        self.root = root
        super().__init__(minimal_manifest(), 'developer',
                         root / 'work trees', root / 'bare repos')
        self.calls = []
        self.missing_command = None
        self.container = 'none'
        self.vm = 'kvm'
        self.docker = False
        self.git = True
        self.socket = False
        self.origin_bad = False
        self.installed_packages = set()
        self.endpoint = 'unix:///var/run/docker.sock'
        self.real_commands = ()
        self.absent_user = False
        self.account_uid = self.current = os.getuid()
        self.path('/etc').mkdir(parents=True)
        self.path('/etc/os-release').write_text(
            'ID=ubuntu\nVERSION_ID="24.04"\n')
        self.home = self.path('/home/developer')
        self.home.mkdir(parents=True, mode=0o700)
        self.env = {'HOME': str(self.home)}
        self.repo = self.worktrees / 'workspace'
        (self.repo / '.git').mkdir(parents=True)
        (self.bares / 'workspace.git').mkdir(parents=True)
        (self.bares / 'workspace.git/config').write_text('fixture')

    def enable_docker(self):
        self.docker = True
        self.socket = True

    def path(self, value):
        if value == '/var/run/docker.sock':
            return SimpleNamespace(is_socket=lambda: self.socket,
                                   exists=lambda: self.socket)
        return self.root / str(value).lstrip('/')

    def which(self, name):
        if name == self.missing_command:
            return None
        if name == 'git':
            return '/mock/git' if self.git else None
        if name == 'docker':
            return '/mock/docker' if self.docker else None
        # Fresh Ubuntu: only bootstrap commands; Node, Java, npm and every
        # manifest download are absent and therefore installable.
        bootstrap = ('systemd-detect-virt', 'sudo', 'curl', 'gpg', 'dpkg', 'dpkg-query',
                     'apt-get', 'install', 'systemctl', 'usermod', 'id', 'cp', 'ln', 'chmod')
        return f'/mock/{name}' if name in bootstrap else None

    def account(self):
        if self.absent_user:
            raise provision.ProvisionError('selected guest user does not exist')
        return SimpleNamespace(
            pw_name=self.user,
            pw_uid=self.account_uid,
            pw_gid=os.getgid(),
            pw_dir=str(self.root / 'home/developer'),
            pw_shell='/bin/bash',
        )

    def current_uid(self):
        return self.current

    def private_primary_group(self, gid):
        return gid == os.getgid()

    def machine(self):
        return 'x86_64'

    def root_owned(self, path):
        return None

    def installed(self, package):
        return package in self.installed_packages

    def command(self, argv, *, privileged=False, check=True):
        args = [str(arg) for arg in argv]
        self.calls.append((args, privileged))
        if args[:2] in self.real_commands:
            # Production command handling over a patched subprocess.run.
            return provision.Provisioner.command(self, argv, privileged=privileged, check=check)
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
        elif args[0] == 'git':
            repo, operation = Path(args[2]), args[3]
            if operation == 'rev-parse':
                output = 'true' if args[4] == '--is-bare-repository' else str(repo)
            elif operation == 'remote' and len(args) > 4:
                output = ('https://wrong.example/private' if self.origin_bad
                          else str(self.bares / f'{repo.name}.git'))
            elif operation == 'remote':
                output = '' if repo.name.endswith('.git') else 'origin'
        result = subprocess.CompletedProcess(args, code, output, '')
        if check and code:
            raise provision.ProvisionError('fixture command failed')
        return result


class StageProbe(provision.Provisioner):
    def __init__(self, root):
        manifest = minimal_manifest()
        manifest['downloads']['fixture-tool'] = {
            'method': 'binary',
            'destination': '/usr/local/bin/fixture-tool',
            'platforms': {
                'amd64': {
                    'url': 'https://example.invalid/fixture-tool',
                    'sha256': hashlib.sha256(b'expected body').hexdigest(),
                }
            },
        }
        super().__init__(manifest, 'developer', '/fixture/worktrees', '/fixture/bares')
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
        super().__init__(minimal_manifest(), 'developer', '/fixture/worktrees', '/fixture/bares')
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

    def probe(self, directory):
        probe = PreflightProbe(Path(directory))
        repo_patch = patch.object(boundary, 'REPO', probe.repo)
        repo_patch.start()
        self.addCleanup(repo_patch.stop)
        return probe

    def assert_rejected_without_mutation(self, configure, message):
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            probe = self.probe(directory)
            configure(probe)
            with self.assertRaisesRegex(provision.ProvisionError, message):
                probe.preflight()
            self.assertFalse(any(privileged for _, privileged in probe.calls))
            self.assertFalse(any(args[0] == 'curl' for args, _ in probe.calls))

    def assert_manifest_rejected(self, mutate, message):
        manifest = json.loads(provision.MANIFEST.read_text())
        mutate(manifest)
        path = self.root / 'toolchain.json'
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(provision.ProvisionError, message):
            provision.load_manifest(path)

    def test_failing_boundary_probes_never_surface_command_output(self):
        secret = 'fatal: https://user:fixture-secret@host.example/private'
        cases = (
            ('git probe', [['git', '-C']], lambda p: None, 'git: boundary probe failed'),
            ('privileged docker root', [['docker', 'info']], lambda p: p.enable_docker(),
             'docker: boundary probe failed'),
        )
        for label, commands, configure, message in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory(dir=self.root) as directory:
                probe = self.probe(directory)
                configure(probe)
                probe.real_commands = commands
                failed = subprocess.CompletedProcess([], 128, 'fixture-secret stdout', secret)
                with patch.object(provision.subprocess, 'run', return_value=failed) as run, \
                        patch('sys.stdout', new_callable=io.StringIO) as stdout:
                    with self.assertRaisesRegex(provision.ProvisionError, message) as raised:
                        probe.preflight()
                self.assertTrue(run.called)
                self.assertNotIn('fixture-secret', str(raised.exception))
                self.assertNotIn('fixture-secret', stdout.getvalue())
        # The privileged override still pins the guest socket through sudo.
        argv = run.call_args.args[0]
        self.assertEqual(['sudo', '-n', '--', 'docker', '--host', 'unix:///var/run/docker.sock',
                          'info'], argv[:7])

    def test_non_boundary_command_failures_keep_detail(self):
        probe = provision.Provisioner(minimal_manifest(), 'developer', '/fixture/w', '/fixture/b')
        failed = subprocess.CompletedProcess([], 2, '', 'apt detail')
        with patch.object(provision.subprocess, 'run', return_value=failed):
            with self.assertRaisesRegex(provision.ProvisionError, 'apt detail'):
                probe.command(['apt-get', 'update'])

    def test_invalid_targets_reject_before_sudo_or_download(self):
        cases = (
            ('wrong OS', lambda p: p.path('/etc/os-release').write_text(
                'ID=debian\nVERSION_ID="12"\n'), 'Ubuntu'),
            ('container', lambda p: setattr(p, 'container', 'docker'),
             'container execution rejected'),
            ('non-VM', lambda p: setattr(p, 'vm', 'none'), 'QEMU/KVM'),
            ('remote Docker', lambda p: (
                p.enable_docker(), setattr(p, 'endpoint', 'tcp://remote:2376')),
             'remote/custom'),
            ('root target', lambda p: (
                setattr(p, 'user', 'root'), setattr(p, 'account_uid', 0),
                setattr(p, 'current', 0)), 'normal development user'),
            ('sudo entry point', lambda p: setattr(p, 'current', 0),
             'normal development user'),
            ('missing user', lambda p: setattr(p, 'absent_user', True),
             'does not exist'),
            ('missing dependency', lambda p: setattr(
                p, 'missing_command', 'curl'), 'bootstrap command missing'),
        )
        for label, configure, message in cases:
            with self.subTest(label=label):
                self.assert_rejected_without_mutation(configure, message)

    def test_unsafe_existing_state_rejects_before_sudo_or_download(self):
        def docker_config(probe):
            (probe.home / '.docker').mkdir()
            (probe.home / '.docker/config.json').write_text('{"currentContext": "remote"}')
        cases = (
            ('partial Docker socket', lambda p: setattr(p, 'socket', True),
             'partial Docker installation'),
            ('partial Docker package', lambda p: p.installed_packages.add('docker.io'),
             'partial Docker installation'),
            ('Docker data root', lambda p: (
                p.enable_docker(), setattr(p, 'docker_root', lambda: '/mnt/host/docker')),
             'data root mismatch'),
            ('Docker config context', docker_config, 'non-default context'),
            ('Docker endpoint override', lambda p: p.env.update(
                {'DOCKER_HOST': 'tcp://remote:2376'}), 'DOCKER_HOST'),
            ('forwarded agent', lambda p: p.env.update(
                {'SSH_AUTH_SOCK': '/tmp/fixture-agent'}), 'SSH_AUTH_SOCK'),
            ('credential store', lambda p: (p.home / '.netrc').write_text('x'),
             'credential store'),
            ('world-writable home', lambda p: p.home.chmod(0o777), 'unsafe writable path'),
            ('symlinked repository parent', lambda p: setattr(
                p, 'worktrees', p.worktrees / '..' / p.worktrees.name), 'canonical absolute'),
            ('wrong origin', lambda p: setattr(p, 'origin_bad', True), 'wrong origin'),
            ('missing bare origin', lambda p: (
                p.bares / 'workspace.git/config').unlink(), 'missing or symlinked path'),
            ('unsafe repo without Git', lambda p: (
                setattr(p, 'git', False), (p.bares / 'workspace.git/config').unlink()),
             'missing or symlinked path'),
        )
        for label, configure, message in cases:
            with self.subTest(label=label):
                self.assert_rejected_without_mutation(configure, message)

    def test_fresh_system_reaches_provisioning_without_installed_tools(self):
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            probe = self.probe(directory)
            probe.manifest = provision.load_manifest()
            probe.git = False
            probe.preflight()
            self.assertFalse(probe.existing_docker)
            self.assertEqual(set(probe.manifest['downloads']), set(probe.pending))
            self.assertFalse(any(privileged for _, privileged in probe.calls))
            self.assertFalse(any(args[0] in ('docker', 'node', 'java', 'npm', 'git')
                                 for args, _ in probe.calls))
            # The runtime boundary on the same observations still requires Docker.
            probe.git = True
            with self.assertRaisesRegex(provision.ProvisionError, 'guest Docker is missing'):
                probe.check_boundary()

    def test_existing_healthy_docker_passes_with_privileged_read_only_checks(self):
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            probe = self.probe(directory)
            probe.manifest = provision.load_manifest()
            probe.enable_docker()
            probe.preflight()
            self.assertTrue(probe.existing_docker)
            privileged = [args for args, flag in probe.calls if flag]
            self.assertEqual({('docker', 'info'), ('docker', 'ps')},
                             {tuple(args[:2]) for args in privileged})

    def test_checksum_failure_precedes_mutation_and_preserves_spaced_path(self):
        probe = StageProbe(self.root)
        work = self.root / 'download staging with spaces'
        work.mkdir()
        with self.assertRaisesRegex(provision.ProvisionError, 'checksum mismatch'):
            probe.stage(work)
        self.assertEqual([], probe.privileged)
        self.assertEqual(1, len(probe.downloads))
        self.assertEqual(work / 'fixture-tool.download', probe.downloads[0][1])

    def test_system_manifest_excludes_agent_tool_declarations(self):
        manifest = json.loads(provision.MANIFEST.read_text())
        self.assertFalse({'user_tools', 'providers', 'helpers'} & set(manifest))
        # A corrupt sibling agent manifest cannot affect system provisioning.
        (self.root / 'agent-tools.json').write_text('{not json')
        path = self.root / 'toolchain.json'
        path.write_text(json.dumps(manifest))
        self.assertEqual(manifest, provision.load_manifest(path))
        self.assertNotIn('agent-tools', provision.Path(provision.__file__).read_text())

    def test_download_version_requires_matching_urls(self):
        self.assert_manifest_rejected(
            lambda manifest: manifest['downloads']['actionlint'].update(
                {'version': '1.7.13'}),
            'actionlint/amd64: URL does not match reviewed version',
        )

    def test_download_version_requires_matching_validation_pattern(self):
        def mutate(manifest):
            tool = manifest['downloads']['actionlint']
            tool['version'] = '1.7.13'
            for release in tool['platforms'].values():
                release['url'] = release['url'].replace('1.7.12', '1.7.13')

        self.assert_manifest_rejected(
            mutate, 'actionlint: validation pattern does not match reviewed version')

    def test_go_version_requires_matching_destination(self):
        def mutate(manifest):
            tool = manifest['downloads']['go']
            tool['version'] = '1.24.2'
            tool['version_pattern'] = r'(?<![0-9.])1\.24\.2(?![0-9.])'
            for release in tool['platforms'].values():
                release['url'] = release['url'].replace('1.24.1', '1.24.2')

        self.assert_manifest_rejected(
            mutate, 'go: destination does not match reviewed version')

    def test_node_major_requires_matching_repository_policy(self):
        self.assert_manifest_rejected(
            lambda manifest: manifest['repositories']['nodesource'].update({
                'source': manifest['repositories']['nodesource']['source'].replace(
                    'node_24.x', 'node_25.x'),
            }),
            'nodesource: policy does not match NodeSource major selection',
        )

    def test_repeat_with_healthy_docker_never_installs_or_restarts(self):
        probe = RepeatProbe()
        probe.install({})
        probe.install({})
        forbidden = {'apt-get', 'env', 'systemctl', 'usermod', 'install', 'cp', 'ln'}
        self.assertFalse(any(args[0] in forbidden for args, _ in probe.calls))
        self.assertFalse(any(privileged for _, privileged in probe.calls))


if __name__ == '__main__':
    unittest.main()
