"""Read-only VM boundary checks confined to disposable fixtures."""
import importlib.util
import json
import os
from pathlib import Path
import socket as sockets
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[2]
SCRATCH = REPO / 'tmp/native-installer-safety'
SCRATCH.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location(
    'boundary', REPO / 'scripts/native/boundary.py')
boundary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boundary)


class BoundaryProbe(boundary.VmBoundary):
    """Guest with only this workspace checkout: no providers, helpers,
    AI Session Handler, platform binaries or orchestration checkout."""

    def __init__(self, root):
        worktrees, bares = root / 'work trees', root / 'bare repos'
        super().__init__(worktrees, bares)
        self.calls = []
        self.home = root / "guest user's home"
        self.home.mkdir(mode=0o700)
        self.env = {'HOME': str(self.home), 'PATH': '/usr/bin:/bin'}
        self.account_uid = self.current = os.getuid()
        self.osroot = root / 'system'
        (self.osroot / 'etc').mkdir(parents=True)
        (self.osroot / 'etc/os-release').write_text('ID=ubuntu\nVERSION_ID="24.04"\n')
        self.container_type, self.vm_type = 'none', 'kvm'
        self.docker_context = 'default'
        self.docker_endpoint = 'unix:///var/run/docker.sock'
        self.docker_root_dir = '/var/lib/docker'
        self.socket = True
        self.missing = set()
        self.git_config_output = ''
        self.origin_bad = self.extra_remote = self.bare_remote = False
        worktrees.mkdir()
        bares.mkdir()
        self.repo = worktrees / 'workspace'
        (self.repo / '.git').mkdir(parents=True)
        (bares / 'workspace.git').mkdir()
        (bares / 'workspace.git/config').write_text('fixture')

    def account(self):
        return SimpleNamespace(pw_uid=self.account_uid, pw_gid=os.getgid(),
                               pw_name='developer', pw_dir=str(self.home),
                               pw_shell='/bin/bash')

    def current_uid(self):
        return self.current

    def private_primary_group(self, gid):
        return gid == os.getgid()

    def which(self, name):
        return None if name in self.missing else f'/fixture/bin/{name}'

    def system_path(self, path):
        if path == '/var/run/docker.sock':
            return SimpleNamespace(is_socket=lambda: self.socket,
                                   exists=lambda: self.socket)
        return self.osroot / path.lstrip('/')

    def command(self, args, *, check=True):
        args = [str(arg) for arg in args]
        self.calls.append(args)
        name, output, code = Path(args[0]).name, '', 0
        if name == 'systemd-detect-virt':
            output = self.container_type if args[1] == '--container' else self.vm_type
            code = 1 if args[1] == '--container' and output == 'none' else 0
        elif name == 'git':
            repo, operation = Path(args[2]), args[3]
            bare = repo.name.endswith('.git')
            if operation == 'config':
                output = self.git_config_output
            elif operation == 'rev-parse':
                output = 'true' if args[4] == '--is-bare-repository' else str(repo)
            elif operation == 'remote' and len(args) > 4:
                output = ('https://wrong.example/private' if self.origin_bad
                          else str(self.bares / f'{repo.name}.git'))
            elif operation == 'remote':
                output = ('origin' if self.bare_remote else '') if bare else (
                    'origin\nupstream' if self.extra_remote else 'origin')
        elif name == 'docker':
            output = (self.docker_context if args[1:3] == ['context', 'show']
                      else self.docker_endpoint if args[1] == 'context'
                      else self.docker_root_dir)
        elif name == 'dpkg-query':
            code = 1
        self.require(not check or code == 0, f'mocked {name}: exit {code}')
        return SimpleNamespace(stdout=output, stderr='', returncode=code)


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='boundary path with spaces ', dir=SCRATCH)
        self.probe = BoundaryProbe(Path(self.temp.name))
        self.repo_patch = patch.object(boundary, 'REPO', self.probe.repo)
        self.repo_patch.start()
        self.live_command_guard = patch.object(
            boundary.subprocess, 'run',
            side_effect=AssertionError('live fixture command prohibited'))
        self.live_command_guard.start()

    def tearDown(self):
        self.live_command_guard.stop()
        self.repo_patch.stop()
        self.temp.cleanup()

    def reset(self):
        self.tearDown()
        self.setUp()

    def snapshot(self):
        return {str(path): path.read_bytes() if path.is_file() else None
                for path in Path(self.temp.name).rglob('*')}

    def test_passes_without_providers_helpers_handler_or_orchestration(self):
        self.probe.missing.update({'claude', 'codex', 'gemini', 'playwright', 'ai-session-handler',
                                   'node', 'java', 'kubectl', 'helm', 'tilt', 'kind'})
        before = self.snapshot()
        self.probe.check_boundary()
        self.assertEqual(before, self.snapshot())
        self.assertEqual([self.probe.repo], self.probe.repos)
        self.assertFalse((self.probe.worktrees / 'orchestration').exists())
        self.assertFalse((self.probe.worktrees / 'ai-session-handler').exists())
        self.assertEqual({'systemd-detect-virt', 'git', 'docker'},
                         {Path(call[0]).name for call in self.probe.calls})
        self.assertFalse(any(call[1:2] in (['install'], ['ci']) for call in self.probe.calls))

    def assert_rejected(self, cases):
        for label, mutate, message in cases:
            with self.subTest(label=label):
                mutate(self.probe)
                before = self.snapshot()
                with self.assertRaises(boundary.BoundaryError) as caught:
                    self.probe.check_boundary()
                self.assertRegex(str(caught.exception), message)
                self.assertNotIn('fixture-secret', str(caught.exception))
                self.assertEqual(before, self.snapshot())
                self.reset()

    def test_identity_and_home_negative_cases(self):
        def symlink_home(probe):
            target = probe.home.with_name('real-home')
            probe.home.rename(target)
            probe.home.symlink_to(target, target_is_directory=True)

        self.assert_rejected((
            ('wrong OS', lambda p: (p.osroot / 'etc/os-release').write_text(
                'ID=debian\nVERSION_ID="12"\n'), 'Ubuntu 24.04'),
            ('container marker', lambda p: (p.osroot / '.dockerenv').write_text(''),
             'container execution rejected'),
            ('container', lambda p: setattr(p, 'container_type', 'docker'), 'QEMU/KVM'),
            ('non-QEMU VM', lambda p: setattr(p, 'vm_type', 'vmware'), 'QEMU/KVM'),
            ('no VM', lambda p: setattr(p, 'vm_type', 'none'), 'QEMU/KVM'),
            ('root', lambda p: (setattr(p, 'account_uid', 0), setattr(p, 'current', 0)),
             'normal development user'),
            ('sudo/other uid', lambda p: setattr(p, 'current', p.account_uid + 1),
             'normal development user'),
            ('missing HOME', lambda p: p.env.pop('HOME'), 'HOME must match'),
            ('symlinked home', symlink_home, 'HOME must match'),
            ('world-writable home', lambda p: p.home.chmod(0o777), 'unsafe writable path'),
        ))

    def test_denied_environment_rejects_without_disclosing_values(self):
        cases = [(key, lambda p, key=key: p.env.update({key: 'fixture-secret-never-print'}), key)
                 for key in boundary.DENIED_ENV]
        cases.append(('GIT_CONFIG_KEY_0', lambda p: p.env.update(
            {'GIT_CONFIG_KEY_0': 'fixture-secret-never-print'}), 'injected Git configuration'))
        self.assert_rejected(cases)

    def test_credential_store_and_forwarded_socket_negative_cases(self):
        def socket(probe):
            ssh = probe.home / '.ssh'
            ssh.mkdir(mode=0o700)
            server = sockets.socket(sockets.AF_UNIX)
            self.addCleanup(server.close)
            previous = os.getcwd()
            os.chdir(ssh)  # relative bind avoids the AF_UNIX path-length limit
            try:
                server.bind('agent.sock')
            finally:
                os.chdir(previous)
        self.assert_rejected((
            ('.git-credentials', lambda p: (p.home / '.git-credentials').write_text('x'),
             'credential store rejected'),
            ('.netrc', lambda p: (p.home / '.netrc').write_text('x'), 'credential store rejected'),
            ('forwarded socket', socket, 'forwarded credential socket'),
        ))

    def test_repository_and_git_authority_negative_cases(self):
        def symlink_bare_parent(probe):
            target = probe.bares.with_name('real-bare-repos')
            probe.bares.rename(target)
            probe.bares.symlink_to(target, target_is_directory=True)

        self.assert_rejected((
            ('wrong origin', lambda p: setattr(p, 'origin_bad', True), 'wrong origin'),
            ('extra remote', lambda p: setattr(p, 'extra_remote', True), 'extra or missing Git remote'),
            ('bare remote', lambda p: setattr(p, 'bare_remote', True), 'external remote'),
            ('credential helper', lambda p: setattr(
                p, 'git_config_output', 'credential.helper\nfixture-secret-never-print\0'),
             'credential/include/rewrite/forwarding'),
            ('missing bare', lambda p: (p.bares / 'workspace.git/config').unlink(),
             'missing or symlinked path'),
            ('non-canonical parent', lambda p: setattr(
                p, 'worktrees', p.worktrees / '..' / p.worktrees.name), 'canonical absolute'),
            ('symlinked parent', symlink_bare_parent, 'canonical absolute'),
            ('other workspace clone', lambda p: (
                p.repo.rename(p.worktrees / 'other'),
                p.repo.symlink_to(p.worktrees / 'other')), 'selected workspace clone'),
            ('missing git', lambda p: p.missing.add('git'), 'git is required'),
        ))

    def test_guest_docker_negative_cases(self):
        def config(probe):
            (probe.home / '.docker').mkdir()
            (probe.home / '.docker/config.json').write_text(json.dumps({'currentContext': 'remote'}))
        self.assert_rejected((
            ('missing Docker', lambda p: p.missing.add('docker'), 'guest Docker is missing'),
            ('context', lambda p: setattr(p, 'docker_context', 'remote'), 'default guest Docker'),
            ('endpoint', lambda p: setattr(p, 'docker_endpoint', 'tcp://host.example:2376'),
             'remote/custom'),
            ('socket', lambda p: setattr(p, 'socket', False), 'guest Docker socket missing'),
            ('data root', lambda p: setattr(p, 'docker_root_dir', '/mnt/host/docker'),
             'data root mismatch'),
            ('user config context', config, 'non-default context'),
        ))

    def test_installable_mode_accepts_missing_docker_and_git_only(self):
        self.probe.missing.update({'docker', 'git'})
        self.probe.socket = False
        self.probe.check_boundary(installable=True)
        self.assertFalse(self.probe.existing_docker)
        self.assertFalse(any(Path(call[0]).name == 'git' for call in self.probe.calls))
        self.probe.missing.discard('git')
        with self.assertRaisesRegex(boundary.BoundaryError, 'guest Docker is missing'):
            self.probe.check_boundary()
        self.probe.socket = True
        with self.assertRaisesRegex(boundary.BoundaryError, 'partial Docker'):
            self.probe.check_boundary(installable=True)


class PublicBoundaryInterfaceTests(unittest.TestCase):
    command = REPO / 'scripts/check-agent-vm-boundary.sh'

    def test_requires_both_repository_parent_inputs(self):
        for arguments, missing in (
                ((), '--worktree-parent'),
                (('--worktree-parent', '/fixture/worktrees'), '--bare-parent')):
            with self.subTest(missing=missing):
                result = subprocess.run(
                    [self.command, *arguments], text=True, capture_output=True,
                    env={'PATH': os.environ['PATH']}, check=False)
                self.assertEqual(2, result.returncode)
                self.assertIn(missing, result.stderr)

    def test_wrapper_and_engine_stay_independent_of_agent_components(self):
        self.assertIn('native/boundary.py', self.command.read_text())
        source = (REPO / 'scripts/native/boundary.py').read_text()
        for forbidden in ('import user_tools', 'from user_tools import', 'import provision\n',
                          'from provision import', "'orchestration'", "'ai-session-handler'",
                          'toolchain.json', "'sudo'"):
            self.assertFalse(forbidden in source, forbidden)

    def test_rejection_reports_without_traceback(self):
        result = subprocess.run(
            [self.command, '--worktree-parent', 'relative', '--bare-parent', 'relative'],
            text=True, capture_output=True, check=False,
            env={'PATH': os.environ['PATH'], 'HOME': '/nonexistent-fixture-home'})
        self.assertEqual(1, result.returncode)
        self.assertTrue(result.stderr.startswith('check-agent-vm-boundary: '))
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
