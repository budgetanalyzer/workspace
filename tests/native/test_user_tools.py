"""Focused user-installer checks confined to disposable homes."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import shlex
import stat
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
    'user_tools', REPO / 'scripts/native/user_tools.py')
user_tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(user_tools)
local_ca_spec = importlib.util.spec_from_file_location(
    'local_ca', REPO / 'scripts/native/local_ca.py')
local_ca = importlib.util.module_from_spec(local_ca_spec)
with patch.dict(sys.modules, {'user_tools': user_tools}):
    local_ca_spec.loader.exec_module(local_ca)


class LocalCaPathSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            prefix='nss path with spaces ', dir=SCRATCH)
        self.home = Path(self.temp.name) / 'home'
        self.home.mkdir(mode=0o750)
        self.account = SimpleNamespace(
            pw_uid=os.getuid(),
            pw_gid=os.getgid(),
            pw_name='budgetops',
        )

    def tearDown(self):
        self.temp.cleanup()

    def private_group(self, name='budgetops', members=()):
        group = SimpleNamespace(gr_name=name, gr_mem=list(members))
        return (
            patch.object(user_tools.grp, 'getgrgid', return_value=group),
            patch.object(user_tools.pwd, 'getpwall', return_value=[self.account]),
        )

    def test_nss_parent_from_private_group_umask_is_accepted(self):
        previous_umask = os.umask(0o002)
        try:
            (self.home / '.pki/nssdb').mkdir(mode=0o700, parents=True)
        finally:
            os.umask(previous_umask)
        self.assertEqual(0o775, stat.S_IMODE((self.home / '.pki').stat().st_mode))
        self.assertEqual(0o700, stat.S_IMODE((self.home / '.pki/nssdb').stat().st_mode))
        group_patch, users_patch = self.private_group()
        with group_patch, users_patch:
            self.assertEqual(
                self.home / '.pki/nssdb',
                local_ca.validate_nss_paths(self.home, self.account),
            )

    def test_nss_group_write_requires_verified_private_primary_group(self):
        (self.home / '.pki/nssdb').mkdir(mode=0o700, parents=True)
        (self.home / '.pki').chmod(0o775)
        group_patch, users_patch = self.private_group(name='shared-developers')
        with group_patch, users_patch, self.assertRaisesRegex(
                local_ca.TrustError, 'NSS ownership/permissions collision'):
            local_ca.validate_nss_paths(self.home, self.account)

    def test_nss_world_write_remains_rejected(self):
        (self.home / '.pki/nssdb').mkdir(mode=0o700, parents=True)
        (self.home / '.pki').chmod(0o777)
        group_patch, users_patch = self.private_group()
        with group_patch, users_patch, self.assertRaisesRegex(
                local_ca.TrustError, 'NSS ownership/permissions collision'):
            local_ca.validate_nss_paths(self.home, self.account)


class UserToolsProbe(user_tools.UserTools):
    """Command shim with all writes rooted in one disposable directory."""

    def __init__(self, root):
        worktrees = root / 'work trees'
        bares = root / 'bare repos'
        super().__init__(worktrees, bares)
        self.fixture = root
        self.calls = []
        self.home = root / "guest user's disposable home"
        self.home.mkdir(mode=0o700)
        self.env = {'HOME': str(self.home), 'PATH': '/usr/bin:/bin'}
        self.uid = os.getuid()
        self.origin_bad = False
        self.git_config_output = ''
        self.browser_missing = False
        self.trust_missing = False
        self.container_type = 'none'
        self.vm_type = 'kvm'
        self.docker_context = 'default'
        self.docker_endpoint = 'unix:///var/run/docker.sock'
        self.docker_root = '/var/lib/docker'
        self.node_version = 'v24.21.0'
        self.java_version = 'openjdk version "25.0.1"'
        self.javac_version = 'javac 25.0.1'
        self.tool_version_overrides = {}
        self.user_tool_version_overrides = {}
        self.socket_path = SimpleNamespace(is_socket=lambda: True)
        self.osroot = root / 'system'
        (self.osroot / 'etc').mkdir(parents=True)
        (self.osroot / 'etc/os-release').write_text(
            'ID=ubuntu\nVERSION_ID="24.04"\n')
        worktrees.mkdir()
        bares.mkdir()
        for name in ('workspace', 'orchestration', 'ai-session-handler'):
            checkout = worktrees / name
            (checkout / '.git').mkdir(parents=True)
            bare = bares / f'{name}.git'
            bare.mkdir()
            (bare / 'config').write_text('fixture')
        self.repo = worktrees / 'workspace'
        shutil.copytree(REPO / 'native', self.repo / 'native')
        shutil.copytree(
            REPO / 'scripts/native',
            self.repo / 'scripts/native',
            ignore=shutil.ignore_patterns('__pycache__'),
        )
        handler = worktrees / 'ai-session-handler'
        (handler / 'src/ai_session_handler').mkdir(parents=True)
        (handler / 'pyproject.toml').write_text(
            '[project]\nname="ai-session-handler"\n')
        (self.home / '.claude').mkdir(mode=0o700)
        self.credentials = self.home / '.claude/.credentials.json'
        self.credentials.write_text('{"fixture":"must remain untouched"}')
        self.credentials.chmod(0o600)
        settings = self.home / '.claude/settings.json'
        settings.write_text(json.dumps({
            'env': {'keep': 'value'},
            'permissions': {'allow': ['Read']},
            'hooks': {'SessionStart': [{
                'hooks': [{'type': 'command', 'command': 'echo user-hook'}],
            }]},
        }))
        settings.chmod(0o600)
        profile = self.home / '.profile'
        profile.write_text('# user login\n')
        profile.chmod(0o600)

    def account(self):
        return SimpleNamespace(
            pw_uid=self.uid,
            pw_gid=os.getgid(),
            pw_name='developer',
            pw_dir=str(self.home),
            pw_shell='/bin/bash',
        )

    def private_primary_group(self, gid):
        # Model the fixture account's verified same-name private primary group.
        return gid == os.getgid()

    def system_path(self, path):
        if path == '/var/run/docker.sock':
            return self.socket_path
        return self.osroot / path.lstrip('/')

    def command(self, args, *, check=True, env=None):
        args = [str(arg) for arg in args]
        self.calls.append(args)
        name = Path(args[0]).name
        output, code = '', 0
        if name == 'systemd-detect-virt':
            output = (self.container_type if args[1] == '--container'
                      else self.vm_type)
            code = 1 if args[1] == '--container' and output == 'none' else 0
        elif name == 'git':
            repo = Path(args[2])
            operation = args[3]
            if operation == 'config':
                output = self.git_config_output
            elif operation == 'rev-parse':
                output = ('true' if args[4] == '--is-bare-repository'
                          else 'fixture-revision' if args[4] == 'HEAD'
                          else str(repo))
            elif operation == 'remote':
                output = '' if repo.name.endswith('.git') else 'origin'
                if len(args) > 4:
                    output = ('https://wrong.example/private' if self.origin_bad
                              else str(self.bares / f'{repo.name}.git'))
        elif name == 'docker':
            output = (self.docker_context
                      if args[1:3] == ['context', 'show']
                      else self.docker_endpoint if args[1] == 'context'
                      else self.docker_root)
        elif name == 'dpkg-query':
            output = 'install ok installed'
        elif name == 'npm':
            if args[1] == '--version':
                output = '11.19.0'
            else:
                modules = Path(args[args.index('--prefix') + 1]) / 'node_modules'
                modules.mkdir(exist_ok=True)
                (modules / '.package-lock.json').write_text('{}')
        elif name == 'pipx' and args[1] == 'runpip':
            output = 'mitmproxy==12.2.3\nfixture-dependency==1.0.0'
        elif name == 'pipx':
            package = 'ai-session-handler' if '--editable' in args else 'mitmproxy'
            (self.root / 'pipx/venvs' / package / 'bin').mkdir(parents=True)
        elif name == 'node':
            if args[1] == '--version':
                output = self.node_version
            elif self.browser_missing:
                code = 1
            else:
                output = 'fixture-browser'
        elif name == 'java':
            output = self.java_version
        elif name == 'javac':
            output = self.javac_version
        elif name in ('claude', 'codex', 'gemini', 'mitmproxy', 'playwright'):
            for tool in self.manifest['user_tools'].values():
                if tool['check'][0] == name:
                    output = self.user_tool_version_overrides.get(
                        name, tool['version'])
                    break
        elif name == 'python':
            output = str(self.handler / 'src/ai_session_handler/__init__.py')
        elif name == 'bash':
            output = str(self.bin / args[-1])
        elif name == 'check-budget-analyzer-local-ca-trust':
            code = 13 if self.trust_missing else 0
        else:
            for tool in self.manifest['downloads'].values():
                if tool.get('check', [''])[0] == name:
                    output = self.tool_version_overrides.get(name,
                                                             tool['version'])
        user_tools.require(
            not check or code == 0, f'mocked {name}: exit {code}')
        return SimpleNamespace(stdout=output, stderr='', returncode=code)


class PublicVerifierInterfaceTests(unittest.TestCase):
    def test_requires_both_repository_parent_inputs(self):
        command = REPO / 'scripts/check-agent-vm-tools.sh'
        for arguments, missing in (
                ((), '--worktree-parent'),
                (('--worktree-parent', '/fixture/worktrees'), '--bare-parent')):
            with self.subTest(missing=missing):
                result = subprocess.run(
                    [command, *arguments], text=True, capture_output=True,
                    env={'PATH': os.environ['PATH']}, check=False)
                self.assertEqual(2, result.returncode)
                self.assertIn(missing, result.stderr)


class UserInstallerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            prefix='user path with spaces ', dir=SCRATCH)
        self.probe = UserToolsProbe(Path(self.temp.name))
        self.repo_patch = patch.object(user_tools, 'REPO', self.probe.repo)
        self.repo_patch.start()
        self.live_command_guard = patch.object(
            user_tools.subprocess,
            'run',
            side_effect=AssertionError('live fixture command prohibited'),
        )
        self.live_command_guard.start()
        self.quiet = contextlib.redirect_stdout(io.StringIO())
        self.quiet.__enter__()

    def tearDown(self):
        self.quiet.__exit__(None, None, None)
        self.live_command_guard.stop()
        self.repo_patch.stop()
        self.temp.cleanup()

    def install(self):
        self.probe.preflight()
        self.probe.install()

    def test_repeat_preserves_credentials_settings_and_single_shell_hook(self):
        self.install()
        credentials = self.probe.credentials.read_bytes()
        settings_before_repeat = json.loads(
            (self.probe.home / '.claude/settings.json').read_text())
        self.probe.calls.clear()
        self.install()
        settings = json.loads(
            (self.probe.home / '.claude/settings.json').read_text())
        self.assertEqual(credentials, self.probe.credentials.read_bytes())
        self.assertEqual(settings_before_repeat, settings)
        self.assertEqual(1, (self.probe.home / '.profile').read_text().count(
            '# budget-analyzer-native'))
        self.assertFalse(any(
            call[0] in ('npm', 'pipx') and call[1] in ('ci', 'install')
            for call in self.probe.calls))
        self.assertFalse(any(
            call[0] in ('sudo', 'certutil', 'mitmdump', 'mitmweb')
            for call in self.probe.calls))

    def test_manifest_command_keys_render_exact_forwarding_wrappers(self):
        self.probe.preflight()
        files = self.probe.plan_files()
        manifest_commands = set(self.probe.manifest['helpers'])
        self.assertTrue(manifest_commands.issubset(self.probe.names))
        for command, helper in self.probe.manifest['helpers'].items():
            wrapper = files[self.probe.bin / command][0]
            source = helper['native_source']
            if source.startswith('native/helpers/'):
                target = self.probe.root / 'helpers' / Path(source).relative_to(
                    'native/helpers')
                self.assertIn(f'exec {shlex.quote(str(target))}', wrapper)
            elif source == 'scripts/native/local_ca.py':
                self.assertIn(
                    f'python3 {shlex.quote(str(self.probe.root / "local_ca.py"))} {command}',
                    wrapper,
                )
            elif source == 'scripts/native/proxy.py':
                self.assertIn(
                    f'python3 {shlex.quote(str(self.probe.root / "proxy.py"))} {command}',
                    wrapper,
                )
            else:
                self.fail(f'unexpected helper source mapping: {source}')
            self.assertTrue(wrapper.rstrip().endswith('"$@"'))

    def test_wrong_origin_rejects_before_home_mutation(self):
        self.probe.origin_bad = True
        with self.assertRaisesRegex(user_tools.UserToolsError, 'wrong origin'):
            self.probe.preflight()
        self.assertFalse((self.probe.home / '.local').exists())

    def test_native_identity_and_home_environment_reject_before_mutation(self):
        cases = (
            ('wrong OS', lambda: (self.probe.osroot / 'etc/os-release').write_text(
                'ID=debian\nVERSION_ID="12"\n'), 'Ubuntu 24.04'),
            ('container', lambda: setattr(self.probe, 'container_type', 'docker'),
             'QEMU/KVM'),
            ('non-QEMU VM', lambda: setattr(self.probe, 'vm_type', 'vmware'),
             'QEMU/KVM'),
            ('missing HOME', lambda: self.probe.env.pop('HOME'),
             'HOME must match'),
        )
        for label, mutate, message in cases:
            with self.subTest(label=label):
                mutate()
                with self.assertRaisesRegex(user_tools.UserToolsError, message):
                    self.probe.preflight()
                self.assertFalse((self.probe.home / '.local').exists())
                self.tearDown()
                self.setUp()

    def test_environment_bridges_reject_without_disclosing_values(self):
        for key in ('SSH_AUTH_SOCK', 'GITHUB_TOKEN', 'HTTPS_PROXY',
                    'DOCKER_HOST', 'GIT_CONFIG_COUNT'):
            with self.subTest(key=key):
                self.probe.env[key] = 'fixture-secret-never-print'
                with self.assertRaises(user_tools.UserToolsError) as caught:
                    self.probe.preflight()
                self.assertIn(key, str(caught.exception))
                self.assertNotIn('fixture-secret', str(caught.exception))
                self.assertFalse((self.probe.home / '.local').exists())
                self.tearDown()
                self.setUp()

    def test_forwarded_git_authority_rejects_before_home_mutation(self):
        self.probe.git_config_output = 'credential.helper\nfixture-secret-never-print\0'
        with self.assertRaises(user_tools.UserToolsError) as caught:
            self.probe.preflight()
        self.assertIn('credential/include/rewrite/forwarding',
                      str(caught.exception))
        self.assertNotIn('fixture-secret', str(caught.exception))
        self.assertFalse((self.probe.home / '.local').exists())

    def test_remote_docker_targets_reject_before_home_mutation(self):
        cases = (
            ('context', lambda: setattr(self.probe, 'docker_context', 'remote'),
             'default guest Docker'),
            ('endpoint', lambda: setattr(
                self.probe, 'docker_endpoint', 'tcp://host.example:2376'),
             'guest Unix Docker socket'),
            ('socket', lambda: setattr(
                self.probe, 'socket_path',
                SimpleNamespace(is_socket=lambda: False)),
             'guest Docker socket missing'),
            ('data root', lambda: setattr(
                self.probe, 'docker_root', '/mnt/host/docker'),
             'Docker data root mismatch'),
        )
        for label, mutate, message in cases:
            with self.subTest(label=label):
                mutate()
                with self.assertRaisesRegex(user_tools.UserToolsError, message):
                    self.probe.preflight()
                self.assertFalse((self.probe.home / '.local').exists())
                self.tearDown()
                self.setUp()

    def test_native_tool_version_drift_rejects_before_home_mutation(self):
        cases = (
            ('Node', lambda: setattr(self.probe, 'node_version', 'v20.19.0'),
             'Node major 24'),
            ('Java', lambda: setattr(self.probe, 'java_version',
                                    'openjdk version "21.0.1"'),
             'JDK major 25'),
            ('javac', lambda: setattr(self.probe, 'javac_version', 'javac 21.0.1'),
             'JDK major 25'),
            ('download', lambda: self.probe.tool_version_overrides.update(
                {'kind': 'kind v0.30.0'}), 'system release version mismatch'),
        )
        for label, mutate, message in cases:
            with self.subTest(label=label):
                mutate()
                with self.assertRaisesRegex(user_tools.UserToolsError, message):
                    self.probe.preflight()
                self.assertFalse((self.probe.home / '.local').exists())
                self.tearDown()
                self.setUp()

    def test_verifier_is_read_only_and_reports_missing_live_prerequisites(self):
        self.install()
        before = {
            str(path): path.read_bytes()
            for path in self.probe.fixture.rglob('*') if path.is_file()
        }
        self.probe.calls.clear()
        self.probe.verify()
        after = {
            str(path): path.read_bytes()
            for path in self.probe.fixture.rglob('*') if path.is_file()
        }
        self.assertEqual(before, after)
        self.assertFalse(any(
            Path(call[0]).name in ('sudo', 'install', 'certutil') or
            (Path(call[0]).name in ('npm', 'pipx') and 'install' in call)
            for call in self.probe.calls
        ))
        self.probe.user_tool_version_overrides['codex'] = 'codex-cli 0.0.0'
        with self.assertRaisesRegex(user_tools.UserToolsError,
                                    'codex: installed version mismatch'):
            self.probe.verify()
        self.probe.user_tool_version_overrides.clear()
        self.probe.browser_missing = True
        with self.assertRaisesRegex(user_tools.UserToolsError, 'mocked node'):
            self.probe.verify()
        self.probe.browser_missing = False
        self.probe.trust_missing = True
        with self.assertRaisesRegex(user_tools.UserToolsError, 'mocked check-budget'):
            self.probe.verify()


if __name__ == '__main__':
    unittest.main()
