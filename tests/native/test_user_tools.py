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
boundary = sys.modules['boundary']
local_ca_spec = importlib.util.spec_from_file_location(
    'local_ca', REPO / 'scripts/native/local_ca.py')
local_ca = importlib.util.module_from_spec(local_ca_spec)
with patch.dict(sys.modules, {'user_tools': user_tools}):
    local_ca_spec.loader.exec_module(local_ca)
proxy_spec = importlib.util.spec_from_file_location(
    'native_proxy', REPO / 'scripts/native/proxy.py')
proxy = importlib.util.module_from_spec(proxy_spec)
proxy_spec.loader.exec_module(proxy)
LOCKED_PLAYWRIGHT = json.loads((REPO / 'native/npm/package-lock.json').read_text())[
    'packages']['node_modules/playwright']['version']
REAL_POPEN = subprocess.Popen
REAL_RUN = subprocess.run


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
            patch.object(boundary.grp, 'getgrgid', return_value=group),
            patch.object(boundary.pwd, 'getpwall', return_value=[self.account]),
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
        self.docker_root_dir = '/var/lib/docker'
        self.node_version = 'v24.21.0'
        self.java_version = 'openjdk version "25.0.1"'
        self.javac_version = 'javac 25.0.1'
        self.tool_version_overrides = {}
        self.user_tool_version_overrides = {}
        self.latest = {}
        self.socket_path = SimpleNamespace(is_socket=lambda: True)
        self.missing_commands = set()
        self.osroot = root / 'system'
        (self.osroot / 'etc').mkdir(parents=True)
        (self.osroot / 'etc/os-release').write_text(
            'ID=ubuntu\nVERSION_ID="24.04"\n')
        worktrees.mkdir()
        bares.mkdir()
        for name in ('workspace', 'ai-session-handler'):
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

    def which(self, name):
        return None if name in self.missing_commands else f'/fixture/bin/{name}'

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
                      else self.docker_root_dir)
        elif name == 'dpkg-query':
            output = 'install ok installed'
        elif name == 'npm':
            if args[1] == '--version':
                output = '11.19.0'
            elif args[1] == 'install':
                # Model an npm global install: one package tree plus its bin link.
                prefix = Path(args[args.index('--prefix') + 1])
                package = args[-1].removesuffix('@latest')
                command = next(n for n, p in self.agent['providers'].items()
                               if p['package'] == package)
                self.latest[package] = self.latest.get(package, 0) + 1
                tree = prefix / 'lib/node_modules' / package
                (tree / 'bin').mkdir(parents=True, exist_ok=True)
                (tree / 'package.json').write_text(json.dumps(
                    {'name': package, 'version': f'9.{self.latest[package]}.0'}))
                (tree / 'bin/cli.js').write_text('fixture')
                (prefix / 'bin').mkdir(exist_ok=True)
                link = prefix / 'bin' / command
                link.unlink(missing_ok=True)
                link.symlink_to(Path('../lib/node_modules') / package / 'bin/cli.js')
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
        elif name in self.agent['providers']:
            output = self.user_tool_version_overrides.get(name, f'{name} 0.0.1-floating')
        elif name in ('mitmproxy', 'playwright'):
            default = (self.agent['user_tools']['mitmproxy']['version'] if name == 'mitmproxy'
                       else f'Version {LOCKED_PLAYWRIGHT}')
            output = self.user_tool_version_overrides.get(name, default)
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


class ProxyProviderLaunchTests(unittest.TestCase):
    """Proxy launches resolve providers through the managed global prefix."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='proxy launch ', dir=SCRATCH)
        base = Path(self.temp.name)
        self.root = base / 'home/.local/share/budget-analyzer-native'
        self.conf = self.root / 'inspection'
        self.conf.mkdir(parents=True)
        (self.conf / 'mitmproxy-ca-cert.pem').write_text('fixture-ca\n')
        (self.root / 'helpers').mkdir()
        shutil.copy(REPO / 'native/helpers/codex-lean.sh', self.root / 'helpers/codex-lean.sh')
        self.record = base / 'record'
        provider_bin = self.root / 'providers/bin'
        provider_bin.mkdir(parents=True)
        for name in ('claude', 'codex'):
            stub = provider_bin / name
            stub.write_text('#!/usr/bin/env bash\n'
                            'printf "%s\\n" "$0" "$HTTPS_PROXY" "${CODEX_REAL_BIN:-}" '
                            '"${CODEX_REASONING_EFFORT:-}" "$@" > "$RECORD"\n'
                            'printf "%s\\n" "${SSL_CERT_FILE:-}" "${REQUESTS_CA_BUNDLE:-}" '
                            '"${NODE_EXTRA_CA_CERTS:-}" > "$RECORD.trust"\n')
            stub.chmod(0o700)
        self.env = {'HOME': str(base / 'home'), 'PATH': '/usr/bin:/bin',
                    'RECORD': str(self.record),
                    'BUDGET_ANALYZER_NATIVE_ROOT': str(self.root),
                    'BUDGET_ANALYZER_WORKTREE_PARENT': str(base / 'worktrees'),
                    'BUDGET_ANALYZER_BARE_PARENT': str(base / 'bares')}
        self.listening = False
        self.events = []
        self.boundary_error = None

    def tearDown(self):
        self.temp.cleanup()

    def socket(self):
        test = self

        class Probe:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def settimeout(self, _):
                pass

            def connect_ex(self, _):
                return 0 if test.listening else 111
        return Probe()

    def boundary(self, worktrees, bares):
        test = self

        class Boundary:
            def check_boundary(self):
                test.events.append(('boundary', worktrees, bares, os.environ.get('SSL_CERT_FILE')))
                if test.boundary_error:
                    raise proxy.BoundaryError(test.boundary_error)
        return Boundary()

    def popen(self, args, **kwargs):
        self.events.append((args[0],))
        if args[0] != 'mitmweb':
            return REAL_POPEN(args, **kwargs)
        self.listening = True
        return SimpleNamespace(poll=lambda: None, terminate=lambda: None,
                               wait=lambda timeout=None: 0)

    def patches(self):
        stack = contextlib.ExitStack()
        stack.enter_context(patch.dict(os.environ, self.env, clear=True))
        stack.enter_context(patch.object(proxy, 'VmBoundary', side_effect=self.boundary))
        stack.enter_context(patch.object(proxy, 'proxy_arguments', return_value=(['mitmweb'], self.conf)))
        stack.enter_context(patch.object(proxy.socket, 'socket', side_effect=self.socket))
        stack.enter_context(patch.object(proxy.subprocess, 'Popen', side_effect=self.popen))
        return stack

    def launch(self, action, user_args):
        with self.patches():
            self.assertEqual(0, proxy.launch(action, user_args))
        # The boundary runs first, with the exported parents and unchanged trust.
        self.assertEqual(('boundary', self.env['BUDGET_ANALYZER_WORKTREE_PARENT'],
                          self.env['BUDGET_ANALYZER_BARE_PARENT'], None), self.events[0])
        self.assertEqual(['boundary', 'mitmweb'], [event[0] for event in self.events[:2]])
        return self.record.read_text().splitlines()

    def test_boundary_failure_starts_no_proxy_or_provider(self):
        self.boundary_error = 'SSH_AUTH_SOCK must be absent'
        for action in ('claude-with-proxy', 'codex-with-proxy', 'codex-max-with-proxy'):
            with self.subTest(action=action):
                self.events.clear()
                stdout, stderr = io.StringIO(), io.StringIO()
                with self.patches(), patch.object(sys, 'argv', ['proxy.py', action, 'tail']), \
                        contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    self.assertEqual(1, proxy.main())
                self.assertEqual(['boundary'], [event[0] for event in self.events])
                self.assertFalse(self.record.exists())
                # No private flow storage or combined trust bundle was prepared.
                self.assertFalse(Path(self.env['BUDGET_ANALYZER_WORKTREE_PARENT']).exists())
                self.assertEqual('', stdout.getvalue())
                self.assertTrue(stderr.getvalue().startswith(
                    'agent launch blocked by VM boundary: SSH_AUTH_SOCK must be absent'))

    def test_proxy_bundle_reaches_only_the_provider_child(self):
        # The caller keeps the managed trust values that component checks read;
        # only the provider child receives the combined inspection bundle.
        keys = ('SSL_CERT_FILE', 'REQUESTS_CA_BUNDLE', 'NODE_EXTRA_CA_CERTS')
        self.env.update(dict.fromkeys(keys, user_tools.SYSTEM_BUNDLE))
        with self.patches():
            self.assertEqual(0, proxy.launch('claude-with-proxy', []))
            self.assertEqual({key: user_tools.SYSTEM_BUNDLE for key in keys},
                             {key: os.environ[key] for key in keys})
        self.assertEqual(user_tools.SYSTEM_BUNDLE, self.events[0][3])
        child = Path(str(self.record) + '.trust').read_text().splitlines()
        self.assertEqual(1, len(set(child)))
        self.assertNotEqual(user_tools.SYSTEM_BUNDLE, child[0])
        self.assertEqual('mitmproxy-private', Path(child[0]).parent.name)

    def test_claude_with_proxy_runs_managed_prefix_binary_with_exact_argv(self):
        record = self.launch('claude-with-proxy', ['--model', 'fixture', 'two words'])
        self.assertEqual(str(self.root / 'providers/bin/claude'), record[0])
        self.assertEqual('http://127.0.0.1:9080', record[1])
        self.assertEqual(str(self.root / 'providers/bin/codex'), record[2])
        self.assertEqual(['--model', 'fixture', 'two words'], record[4:])
        self.assertNotIn('npm/node_modules', '\n'.join(record))

    def test_codex_proxy_uses_codex_real_bin_from_managed_prefix(self):
        record = self.launch('codex-max-with-proxy', ['tail arg'])
        self.assertEqual(str(self.root / 'providers/bin/codex'), record[0])
        self.assertEqual(str(self.root / 'providers/bin/codex'), record[2])
        self.assertEqual('xhigh', record[3])
        self.assertIn('--dangerously-bypass-approvals-and-sandbox', record)
        self.assertIn('model_reasoning_effort="xhigh"', record)
        self.assertEqual('tail arg', record[-1])
        self.assertNotIn('npm/node_modules', '\n'.join(record))


GUARD_STUB = """import os
from pathlib import Path
import sys
Path(os.environ['GUARD_LOG']).write_text('\\n'.join(sys.argv[1:]))
if os.environ.get('GUARD_FAIL'):
    print('agent launch blocked by VM boundary: SSH_AUTH_SOCK must be absent', file=sys.stderr)
    sys.exit(1)
"""
PROVIDER_STUB = ('#!/usr/bin/env bash\n'
                 'printf "%s\\n" "$0" "${CODEX_REAL_BIN:-}" "$@" > "$RECORD"\n')


class ProviderLaunchGuardTests(unittest.TestCase):
    """Every rendered provider launch path runs the installed boundary first."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='launch guard ', dir=SCRATCH)
        base = Path(self.temp.name)
        self.probe = UserToolsProbe(base)
        with patch.object(user_tools, 'REPO', self.probe.repo), \
                patch.object(boundary, 'REPO', self.probe.repo), \
                patch.object(user_tools.subprocess, 'run',
                             side_effect=AssertionError('live fixture command prohibited')), \
                contextlib.redirect_stdout(io.StringIO()):
            self.probe.preflight()
            files = {}
            for component in user_tools.COMPONENTS:
                files.update(self.probe.component_files(component))
        for path, (content, mode) in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            path.chmod(mode)
        provider_bin = self.probe.provider_bin()
        provider_bin.mkdir(parents=True)
        for name in (*self.probe.agent['providers'], 'unchecked-codex'):
            (provider_bin / name).write_text(PROVIDER_STUB)
            (provider_bin / name).chmod(0o700)
        self.record, self.guard_log = base / 'record', base / 'guard-log'
        self.env = {'HOME': str(self.probe.home), 'PATH': '/usr/bin:/bin',
                    'RECORD': str(self.record), 'GUARD_LOG': str(self.guard_log)}

    def tearDown(self):
        self.temp.cleanup()

    def stub_guard(self):
        (self.probe.root / 'boundary.py').write_text(GUARD_STUB)

    def run_command(self, name, *args, **env):
        self.record.unlink(missing_ok=True)
        self.guard_log.unlink(missing_ok=True)
        # Resolve by name through PATH, as AI Session Handler and shells do.
        return REAL_RUN(['bash', '--noprofile', '--norc', '-c', '"$@"', 'launch', name, *args],
                        env={**self.env, 'PATH': f'{self.probe.bin}:{self.env["PATH"]}', **env},
                        text=True, capture_output=True, check=False)

    launch_paths = {'claude': 'claude', 'codex': 'codex', 'gemini': 'gemini',
                    'claude-lean': 'claude', 'codex-lean': 'codex'}

    def test_boundary_failure_starts_no_provider(self):
        self.stub_guard()
        for name in self.launch_paths:
            with self.subTest(name=name):
                result = self.run_command(name, 'tail', GUARD_FAIL='1')
                self.assertEqual(1, result.returncode)
                self.assertFalse(self.record.exists())
                self.assertEqual('', result.stdout)
                self.assertIn('agent launch blocked by VM boundary', result.stderr)

    def test_boundary_success_launches_silently_with_exported_parents(self):
        self.stub_guard()
        for name, provider in self.launch_paths.items():
            with self.subTest(name=name):
                result = self.run_command(name, 'two words',
                                          CODEX_REAL_BIN=str(self.probe.provider_bin() / 'unchecked-codex'))
                self.assertEqual((0, '', ''), (result.returncode, result.stdout, result.stderr))
                self.assertEqual(['--worktree-parent', str(self.probe.worktrees),
                                  '--bare-parent', str(self.probe.bares)],
                                 self.guard_log.read_text().splitlines())
                record = self.record.read_text().splitlines()
                self.assertEqual(str(self.probe.provider_bin() / provider), record[0])
                self.assertEqual('two words', record[-1])
                if name == 'codex-lean':
                    # An inherited CODEX_REAL_BIN never selects an unchecked provider.
                    self.assertEqual(str(self.probe.provider_bin() / 'codex'), record[1])

    def test_real_installed_boundary_fails_closed_for_every_path(self):
        # The fixture HOME is not the account home, so the real rules reject it
        # (an unusual test account may fail an earlier identity rule instead).
        for name in (*self.launch_paths, 'claude-with-proxy', 'codex-with-proxy',
                     'codex-max-with-proxy'):
            with self.subTest(name=name):
                result = self.run_command(name, 'tail')
                self.assertEqual(1, result.returncode)
                self.assertFalse(self.record.exists())
                self.assertEqual('', result.stdout)
                self.assertRegex(result.stderr, r'^(check-agent-vm-boundary|'
                                                r'agent launch blocked by VM boundary): ')
                self.assertNotIn('Traceback', result.stderr)

    def test_only_provider_launchers_are_guarded(self):
        guarded = {path.name for path in self.probe.bin.iterdir()
                   if 'boundary.py' in path.read_text()}
        self.assertEqual(set(self.probe.agent['providers']) | set(user_tools.PROVIDER_LAUNCHERS),
                         guarded)


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
        self.boundary_repo_patch = patch.object(boundary, 'REPO', self.probe.repo)
        self.boundary_repo_patch.start()
        self.boundary_command_guard = patch.object(
            boundary.subprocess, 'run',
            side_effect=AssertionError('live fixture command prohibited'))
        self.boundary_command_guard.start()
        self.live_command_guard = patch.object(
            user_tools.subprocess,
            'run',
            side_effect=AssertionError('live fixture command prohibited'),
        )
        self.live_command_guard.start()
        self.quiet = contextlib.redirect_stdout(io.StringIO())
        self.quiet.__enter__()
        self.quiet_errors = contextlib.redirect_stderr(io.StringIO())
        self.quiet_errors.__enter__()

    def tearDown(self):
        self.quiet_errors.__exit__(None, None, None)
        self.quiet.__exit__(None, None, None)
        self.live_command_guard.stop()
        self.boundary_command_guard.stop()
        self.boundary_repo_patch.stop()
        self.repo_patch.stop()
        self.temp.cleanup()

    def install(self, *components, update_provider=None):
        self.probe.preflight()
        for component in components or user_tools.COMPONENTS:
            self.probe.install(component, update_provider)

    def verify(self, *components):
        for component in components or user_tools.COMPONENTS:
            self.probe.verify(component)

    def plan_files(self):
        files = {}
        for component in user_tools.COMPONENTS:
            files.update(self.probe.plan_files(component))
        return files

    def names(self):
        return set().union(*(self.probe.component_names(c) for c in user_tools.COMPONENTS))

    def state(self, component):
        return self.probe.state_dir(component) / 'managed-files.json'

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
        files = self.plan_files()
        manifest_commands = set(self.probe.agent['helpers'])
        self.assertTrue(manifest_commands.issubset(self.names()))
        for command, helper in self.probe.agent['helpers'].items():
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

    def provider_trees(self):
        return {path: path.read_bytes()
                for path in (self.probe.root / 'providers').rglob('*')
                if path.is_file()}

    def npm_project(self):
        return {path: path.read_bytes()
                for path in (self.probe.root / 'npm').rglob('*') if path.is_file()}

    def npm_calls(self):
        return [call for call in self.probe.calls if call[0] == 'npm' and
                call[1] in ('ci', 'install')]

    def test_provider_wrappers_use_managed_prefix_and_playwright_its_project(self):
        self.install()
        files = self.plan_files()
        for name in self.probe.agent['providers']:
            wrapper = files[self.probe.bin / name][0]
            target = self.probe.root / 'providers/bin' / name
            self.assertTrue(wrapper.rstrip().endswith(
                f'exec {shlex.quote(str(target))} "$@"'))
            self.assertTrue(target.resolve().is_relative_to(
                self.probe.provider_package(name)))
        playwright = files[self.probe.bin / 'playwright'][0]
        self.assertIn(shlex.quote(str(self.probe.root / 'npm/node_modules/.bin/playwright')),
                      playwright)
        for path, (content, _) in files.items():
            launcher = (path.parent == self.probe.bin or path == self.probe.root / 'proxy.py' or
                        path.is_relative_to(self.probe.root / 'helpers'))
            if launcher and path.name != 'playwright':
                self.assertNotIn('npm/node_modules/.bin', content, path)
        installs = [call for call in self.npm_calls() if call[1] == 'install']
        self.assertEqual(sorted(p['package'] + '@latest' for p in
                                self.probe.agent['providers'].values()),
                         sorted(call[-1] for call in installs))
        for call in installs:
            self.assertIn('--global', call)
            self.assertEqual(str(self.probe.root / 'providers'),
                             call[call.index('--prefix') + 1])
            self.assertNotIn('--force', call)

    def test_routine_preparation_keeps_installed_provider_versions(self):
        self.install()
        providers, project = self.provider_trees(), self.npm_project()
        self.probe.calls.clear()
        self.install()
        self.assertEqual([], self.npm_calls())
        self.assertEqual(providers, self.provider_trees())
        self.assertEqual(project, self.npm_project())

    def test_updating_one_provider_leaves_others_and_playwright_unchanged(self):
        self.install()
        providers, project = self.provider_trees(), self.npm_project()
        codex = self.probe.provider_package('codex')
        self.probe.calls.clear()
        self.install('codex', update_provider='codex')
        self.assertEqual([['npm', 'install', '--global', '--prefix',
                           str(self.probe.root / 'providers'), '--no-audit',
                           '--no-fund', '@openai/codex@latest']], self.npm_calls())
        self.assertEqual('9.2.0', json.loads((codex / 'package.json').read_text())['version'])
        after = self.provider_trees()
        self.assertEqual({p: c for p, c in providers.items() if not p.is_relative_to(codex)},
                         {p: c for p, c in after.items() if not p.is_relative_to(codex)})
        self.assertEqual(project, self.npm_project())
        self.assertEqual({'claude': '9.1.0', 'codex': '9.2.0', 'gemini': '9.1.0'},
                         {name: json.loads((self.probe.state_dir(name) / 'installation.json')
                                           .read_text())['provider_version']
                          for name in ('claude', 'codex', 'gemini')})

    def test_playwright_npm_ci_leaves_providers_unchanged(self):
        self.install()
        providers = self.provider_trees()
        (self.probe.root / 'npm/node_modules/.package-lock.json').unlink()
        self.probe.calls.clear()
        self.install()
        self.assertEqual([['npm', 'ci', '--prefix', str(self.probe.root / 'npm'),
                           '--no-audit', '--no-fund']], self.npm_calls())
        self.assertEqual(providers, self.provider_trees())

    def test_missing_or_escaped_provider_fails_verification(self):
        self.install()
        link = self.probe.root / 'providers/bin/gemini'
        link.unlink()
        link.symlink_to(self.probe.provider_package('claude') / 'bin/cli.js')
        with self.assertRaisesRegex(user_tools.UserToolsError,
                                    'gemini: provider command resolves outside'):
            self.verify()
        shutil.rmtree(self.probe.provider_package('gemini'))
        with self.assertRaisesRegex(user_tools.UserToolsError,
                                    'gemini: provider missing; human: .*--update-provider gemini'):
            self.verify()

    def test_handler_provider_wrappers_are_managed_and_verified(self):
        self.install()
        for name in ('ai-session-handler-codex-high',
                     'ai-session-handler-claude-high',
                     'ai-session-handler-claude-medium'):
            self.assertIn(name, self.probe.component_names('extras'))
            wrapper = self.probe.bin / name
            self.assertIn(wrapper, self.probe.plan_files('extras'))
            self.assertIn([str(wrapper), '--help'], self.probe.calls)

    def seed_retired_state(self, extra=()):
        """Model retired Claude-component files still recorded in its state."""
        self.install()
        fragment = shlex.quote(str(self.probe.fragment))
        proxy = shlex.quote(str(self.probe.root / 'proxy.py'))
        retired = {}
        for name in ('claude-45-custom-system-prompt',
                     'claude-46-custom-system-prompt',
                     'claude-with-custom-system-prompt'):
            retired[self.probe.bin / name] = (
                '#!/usr/bin/env bash\nset -euo pipefail\n'
                f'. {fragment}\nexec python3 {proxy} {name} "$@"\n')
        retired[self.probe.root / 'helpers/system-prompt-addon.py'] = (
            '"""Retired mitmproxy prompt-replacement addon fixture."""\n')
        for path, content in retired.items():
            path.write_text(content)
            path.chmod(0o700)
        state_path = self.state('claude')
        state = json.loads(state_path.read_text())
        state.update({str(path): user_tools.digest(path) for path in retired})
        state.update(extra)
        state_path.write_text(json.dumps(state, indent=2) + '\n')
        return list(retired), state_path

    def assert_refresh_rejected(self, retired, state_path, message):
        retained = {path: path.read_bytes() for path in retired
                    if path.exists() or path.is_symlink()}
        state = state_path.read_bytes()
        self.probe.calls.clear()
        with self.assertRaisesRegex(user_tools.UserToolsError, message):
            self.install()
        self.assertEqual(state, state_path.read_bytes())
        self.assertFalse(any(Path(call[0]).name == 'playwright'
                             for call in self.probe.calls))
        for path, content in retained.items():
            self.assertEqual(content, path.read_bytes())

    def test_refresh_removes_unchanged_retired_managed_files(self):
        retired, state_path = self.seed_retired_state()
        unrelated = self.probe.bin / 'user-owned-tool'
        unrelated.write_text('#!/bin/sh\n')
        credentials = self.probe.credentials.read_bytes()
        self.install()
        for path in retired:
            self.assertFalse(path.exists(), path)
        state = json.loads(state_path.read_text())
        self.assertEqual({str(path) for path in self.probe.plan_files('claude')},
                         set(state))
        self.assertTrue(set(map(str, retired)).isdisjoint(state))
        self.assertTrue((self.probe.bin / 'claude-lean').is_file())
        self.assertTrue((self.probe.root / 'helpers').is_dir())
        self.assertEqual('#!/bin/sh\n', unrelated.read_text())
        self.assertEqual(credentials, self.probe.credentials.read_bytes())
        self.assertTrue((self.probe.home / '.claude/settings.json').is_file())

    def test_refresh_converges_when_retired_files_are_already_missing(self):
        retired, state_path = self.seed_retired_state()
        retired[0].unlink()
        retired[3].unlink()
        self.install()
        self.install()
        for path in retired:
            self.assertFalse(path.exists(), path)
        self.assertTrue(set(map(str, retired)).isdisjoint(
            json.loads(state_path.read_text())))

    def test_modified_retired_file_rejects_before_cleanup(self):
        retired, state_path = self.seed_retired_state()
        retired[1].write_text('#!/usr/bin/env bash\necho user change\n')
        self.assert_refresh_rejected(retired, state_path,
                                     'modified or non-regular retired')
        for path in retired:
            self.assertTrue(path.exists(), path)

    def test_retired_paths_cannot_escape_the_managed_home(self):
        outside = self.probe.fixture / 'outside-home.txt'
        outside.write_text('outside')
        retired, state_path = self.seed_retired_state()
        base = json.loads(state_path.read_text())
        for key, message in (
                (str(outside), 'escaped the development home'),
                (str(self.probe.home / '..' / outside.name),
                 'malformed retired managed path'),
                ('relative/path', 'malformed retired managed path')):
            with self.subTest(key=key):
                state_path.write_text(json.dumps(
                    base | {key: user_tools.digest(outside)}))
                self.assert_refresh_rejected(retired, state_path, message)
                self.assertEqual('outside', outside.read_text())
                for path in retired:
                    self.assertTrue(path.exists(), path)

    def test_symlinked_retired_file_rejects_without_touching_target(self):
        target = self.probe.fixture / 'symlink-target.txt'
        target.write_text('target')
        link = self.probe.home / '.local/bin/retired-link'
        retired, state_path = self.seed_retired_state(
            {str(link): user_tools.digest(target)})
        link.symlink_to(target)
        self.assert_refresh_rejected(retired, state_path, 'symlink collision')
        self.assertTrue(link.is_symlink())
        self.assertEqual('target', target.read_text())

    def test_malformed_previous_state_rejects_before_cleanup(self):
        retired, state_path = self.seed_retired_state(
            {str(self.probe.home / '.local/bin/bad-digest'): 'not-a-digest'})
        self.assert_refresh_rejected(retired, state_path,
                                     'malformed claude managed-files.json')

    def test_boundary_runs_before_agent_component_checks(self):
        shutil.rmtree(self.probe.worktrees / 'ai-session-handler')
        self.probe.env['HTTPS_PROXY'] = 'fixture-secret-never-print'
        with self.assertRaisesRegex(user_tools.UserToolsError, 'HTTPS_PROXY'):
            self.probe.preflight()
        self.assertFalse((self.probe.home / '.local').exists())
        self.probe.env.pop('HTTPS_PROXY')
        # The handler checkout is an extras prerequisite, not a boundary rule.
        self.install('base')
        with self.assertRaisesRegex(user_tools.UserToolsError,
                                    'missing local checkout: ai-session-handler'):
            self.probe.install('extras')
        self.assertFalse((self.probe.root / 'npm').exists())
        self.assertFalse(self.probe.state_dir('extras').exists())

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
                self.probe, 'docker_root_dir', '/mnt/host/docker'),
             'Docker data root mismatch'),
            ('missing Docker', lambda: self.probe.missing_commands.add('docker'),
             'guest Docker is missing'),
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
                {'actionlint': '1.7.0'}), 'system release version mismatch'),
        )
        for label, mutate, message in cases:
            with self.subTest(label=label):
                mutate()
                self.probe.preflight()
                with self.assertRaisesRegex(user_tools.UserToolsError, message):
                    self.probe.install('base')
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
        self.verify()
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
        # Provider versions float; Playwright stays exact to its lockfile.
        self.probe.user_tool_version_overrides['codex'] = 'codex-cli 0.0.0'
        self.verify()
        self.probe.user_tool_version_overrides = {'playwright': 'Version 1.62.0'}
        with self.assertRaisesRegex(user_tools.UserToolsError,
                                    'playwright: installed version mismatch'):
            self.probe.verify('extras')
        self.probe.user_tool_version_overrides.clear()
        self.probe.browser_missing = True
        with self.assertRaisesRegex(user_tools.UserToolsError, 'mocked node'):
            self.probe.verify('extras')
        self.probe.browser_missing = False
        self.probe.trust_missing = True
        with self.assertRaisesRegex(user_tools.UserToolsError, 'mocked check-budget'):
            self.probe.verify('extras')
        # Installing the trust helpers never requires established trust.
        self.probe.verify('extras', require_trust=False)

    # -- Component isolation ------------------------------------------------

    def snapshot(self):
        return {path: path.read_bytes() for path in self.probe.home.rglob('*')
                if path.is_file() and not path.is_symlink()}

    def component_paths(self, component):
        paths = set(self.probe.plan_files(component))
        paths |= {self.probe.state_dir(component) / name
                  for name in ('managed-files.json', 'installation.json')}
        return paths

    def test_components_own_disjoint_files_and_commands(self):
        self.probe.preflight()
        seen_files, seen_names = set(), set()
        for component in user_tools.COMPONENTS:
            files = set(self.probe.component_files(component))
            names = self.probe.component_names(component)
            self.assertFalse(files & seen_files, component)
            self.assertFalse(names & seen_names, component)
            seen_files |= files
            seen_names |= names
        self.assertIn(self.probe.bin / 'claude-with-proxy', self.probe.component_files('extras'))
        self.assertIn(self.probe.bin / 'claude-lean', self.probe.component_files('claude'))
        self.assertIn(self.probe.bin / 'codex-lean', self.probe.component_files('codex'))

    def test_failing_codex_does_not_fail_claude(self):
        self.install()
        shutil.rmtree(self.probe.provider_package('codex'))
        self.assertEqual([], self.probe.run('check', ['claude']))
        self.assertEqual(['codex'], self.probe.run('check', list(user_tools.COMPONENTS)))
        # The proxy is an optional extra; the Claude check never requires it.
        (self.probe.bin / 'claude-with-proxy').unlink()
        self.assertEqual([], self.probe.run('check', ['claude']))
        self.assertEqual(['codex', 'extras'], self.probe.run('check', list(user_tools.COMPONENTS)))

    def make_stale(self, component, path):
        """Model a file recorded by an install from an older source revision."""
        path.write_text('#!/bin/sh\n# older reviewed revision\n')
        state = json.loads(self.state(component).read_text())
        state[str(path)] = user_tools.digest(path)
        self.state(component).write_text(json.dumps(state))

    def test_stale_extras_helper_does_not_fail_base_or_providers(self):
        self.install()
        self.make_stale('extras', self.probe.root / 'helpers/mitmflows')
        with self.assertRaisesRegex(user_tools.UserToolsError, 'missing/stale managed file'):
            self.probe.verify('extras')
        self.assertEqual([], self.probe.run('check', ['base', 'claude', 'codex', 'gemini']))
        self.assertEqual(['extras'], self.probe.run('check', list(user_tools.COMPONENTS)))
        # Stale base state does not block a provider or the extras either.
        self.make_stale('base', self.probe.root / 'aliases.sh')
        self.assertEqual(['base'], self.probe.run('check', ['base', 'claude', 'codex', 'gemini']))

    def test_boundary_failure_fails_every_selection(self):
        self.install()
        selections = [[c] for c in user_tools.COMPONENTS] + [list(user_tools.COMPONENTS)]
        failures = (
            ('HTTPS_PROXY', lambda: self.probe.env.__setitem__('HTTPS_PROXY', 'fixture-secret'),
             lambda: self.probe.env.pop('HTTPS_PROXY')),
            ('wrong origin', lambda: setattr(self.probe, 'origin_bad', True),
             lambda: setattr(self.probe, 'origin_bad', False)),
            ('guest Unix Docker socket', lambda: setattr(self.probe, 'docker_endpoint', 'tcp://host:2376'),
             lambda: setattr(self.probe, 'docker_endpoint', 'unix:///var/run/docker.sock')),
        )
        for message, mutate, restore in failures:
            for selection in selections:
                with self.subTest(message=message, selection=selection):
                    mutate()
                    argv = ['user_tools.py', 'check', '--worktree-parent', str(self.probe.worktrees),
                            '--bare-parent', str(self.probe.bares)]
                    for component in selection:
                        argv += ['--component', component]
                    self.probe.calls.clear()
                    with patch.object(sys, 'argv', argv), \
                            patch.object(user_tools, 'UserTools', lambda *_: self.probe), \
                            patch.object(self.probe, 'run', side_effect=AssertionError('component ran')):
                        self.assertEqual(1, user_tools.main())
                    restore()

    def test_trust_environment_conflict_fails_every_selection(self):
        self.install()
        managed = self.probe.environment_values()
        argv = ['user_tools.py', 'check', '--worktree-parent', str(self.probe.worktrees),
                '--bare-parent', str(self.probe.bares)]

        def check(component):
            stderr = io.StringIO()
            with patch.object(sys, 'argv', [*argv, '--component', component]), \
                    patch.object(user_tools, 'UserTools', lambda *_: self.probe), \
                    contextlib.redirect_stderr(stderr):
                return user_tools.main(), stderr.getvalue()

        self.assertEqual(['SSL_CERT_FILE', 'NODE_EXTRA_CA_CERTS', 'REQUESTS_CA_BUNDLE'],
                         self.probe.agent['trust_environment'])
        for component in user_tools.COMPONENTS:
            for key in self.probe.agent['trust_environment']:
                with self.subTest(component=component, key=key):
                    self.probe.env[key] = '/fixture/private-bundle.pem'
                    code, stderr = check(component)
                    self.assertEqual(1, code)
                    self.assertIn(f'{component}: FAIL: conflicting {key}', stderr)
                    self.assertNotIn('private-bundle', stderr)
                    with self.assertRaisesRegex(user_tools.UserToolsError, f'conflicting {key}'):
                        self.probe.install(component)
                    self.probe.env[key] = managed[key]
                    self.assertEqual((0, ''), check(component))
                    del self.probe.env[key]
                    self.assertEqual((0, ''), check(component))

    def test_cli_selects_components_and_reports_each(self):
        self.install()
        shutil.rmtree(self.probe.provider_package('gemini'))
        base = ['user_tools.py', 'check', '--worktree-parent', str(self.probe.worktrees),
                '--bare-parent', str(self.probe.bares)]
        cases = ((['--component', 'codex', '--component', 'claude'], 0, ['claude', 'codex']),
                 ([], 1, list(user_tools.COMPONENTS)),
                 (['--component', 'gemini'], 1, ['gemini']))
        for extra, code, selected in cases:
            with self.subTest(extra=extra):
                ran = []
                real_verify = self.probe.verify

                def verify(component, **kwargs):
                    ran.append(component)
                    return real_verify(component, **kwargs)
                with patch.object(sys, 'argv', base + extra), \
                        patch.object(user_tools, 'UserTools', lambda *_: self.probe), \
                        patch.object(self.probe, 'verify', side_effect=verify):
                    self.assertEqual(code, user_tools.main())
                self.assertEqual(selected, ran)
        with patch.object(sys, 'argv', [*base[:1], 'install', *base[2:], '--component', 'claude',
                                        '--update-provider', 'codex']), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            user_tools.main()
        self.assertEqual(2, raised.exception.code)

    def test_installing_one_component_leaves_other_components_unchanged(self):
        self.install()
        for component in user_tools.COMPONENTS:
            with self.subTest(component=component):
                before = self.snapshot()
                others = set().union(*(self.component_paths(c) for c in user_tools.COMPONENTS
                                       if c != component))
                provider = (self.probe.provider_package(component)
                            if component in self.probe.agent['providers'] else None)
                self.probe.calls.clear()
                self.probe.install(component, component if provider else None)
                after = self.snapshot()
                for path in others:
                    self.assertEqual(before[path], after[path], path)
                changed = {path for path in before.keys() | after.keys()
                           if before.get(path) != after.get(path)}
                self.assertTrue(all(
                    path in self.component_paths(component) or
                    (provider and path.is_relative_to(provider)) for path in changed), changed)

    def test_component_install_never_retires_another_components_files(self):
        self.install()
        # A stale record naming another component's current file is not retirement.
        extras_wrapper = self.probe.bin / 'start-proxy'
        content = extras_wrapper.read_bytes()
        state = json.loads(self.state('claude').read_text())
        state[str(extras_wrapper)] = user_tools.digest(extras_wrapper)
        self.state('claude').write_text(json.dumps(state))
        self.probe.install('claude')
        self.assertEqual(content, extras_wrapper.read_bytes())
        self.assertNotIn(str(extras_wrapper), json.loads(self.state('claude').read_text()))

    def test_non_base_components_require_installed_base_only(self):
        self.probe.preflight()
        for component in ('claude', 'codex', 'gemini', 'extras'):
            with self.subTest(component=component):
                with self.assertRaisesRegex(user_tools.UserToolsError,
                                            'base component not installed'):
                    self.probe.install(component)
        self.assertFalse((self.probe.root / 'providers').exists())
        # A stale base (failing its own system check) does not block a provider.
        self.install('base')
        self.probe.tool_version_overrides['actionlint'] = '1.7.0'
        with self.assertRaisesRegex(user_tools.UserToolsError, 'system release version mismatch'):
            self.probe.verify('base')
        self.install('claude')
        self.probe.verify('claude')


if __name__ == '__main__':
    unittest.main()
