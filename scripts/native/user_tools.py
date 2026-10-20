#!/usr/bin/env python3
"""Human-only component installation and read-only component verification.

The VM boundary always runs first. Each component (base, claude, codex,
gemini, extras) then installs or checks only its own files, records and
prerequisites, so one component's failure never blocks another.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from boundary import BoundaryError, VmBoundary  # noqa: E402  pylint: disable=wrong-import-position

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / 'native/toolchain.json'
AGENT_MANIFEST = REPO / 'native/agent-tools.json'
NPM_REGISTRY = 'https://registry.npmjs.org/'
SYSTEM_BUNDLE = '/etc/ssl/certs/ca-certificates.crt'
COMPONENTS = ('base', 'claude', 'codex', 'gemini', 'extras')
# Checks that gate installation before any write; all others verify installed state.
PREREQUISITE_CHECKS = ('system-packages', 'node-npm', 'jdk', 'system-downloads', 'bwrap-apparmor',
                       'chromium-apt', 'ai-session-handler-checkout', 'playwright-lock')
SHELL_FILES = ('.profile', '.bashrc', '.bash_profile', '.bash_login', '.zprofile', '.zshrc')


class UserToolsError(BoundaryError):
    pass


def require(condition, message):
    if not condition:
        raise UserToolsError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def merge_settings(settings, overlay):
    """Own only the two controls; preserve all other user keys."""
    result = json.loads(json.dumps(settings))
    for key in ('promptSuggestionEnabled', 'autoCompactEnabled'):
        result[key] = overlay[key]
    return result


class UserTools(VmBoundary):
    error = UserToolsError

    def __init__(self, worktrees, bares):
        super().__init__(worktrees, bares)
        self.manifest = json.loads(MANIFEST.read_text())
        self.agent = json.loads(AGENT_MANIFEST.read_text())
        self.handler = Path(worktrees) / 'ai-session-handler'

    def command(self, args, *, check=True, env=None):
        # Never print Git config, provider output, credentials or a full env.
        result = subprocess.run([str(a) for a in args], text=True, capture_output=True,
                                env=env or self.env)
        require(not check or result.returncode == 0,
                f'{Path(str(args[0])).name}: command failed (exit {result.returncode}); inspect privately')
        return result

    def home_path(self, path):
        require(path.is_relative_to(self.home), 'managed path escaped the development home')
        for item in (path, *path.parents):
            if not item.is_relative_to(self.home):
                break
            require(not item.is_symlink(), f'symlink collision: {item}')
            if item.exists():
                self.owned(item)

    def preflight(self):
        """The shared VM boundary; it runs first for every component selection."""
        self.check_boundary()
        self.root = self.home / '.local/share/budget-analyzer-native'
        self.bin = self.home / '.local/bin'
        self.fragment = self.home / '.config/budget-analyzer-native/env.sh'
        print(f'Native preflight: user={self.user}; home={self.home}; local repositories={len(self.repos)}')

    # -- Component declarations -------------------------------------------------

    def spec(self, component):
        return self.agent['components'][component]

    def state_dir(self, component):
        return self.root / 'state' / component

    def prerequisites(self, component):
        """Only this component's own prerequisites; never another component's state."""
        spec = self.spec(component)
        for key in spec['environment']:
            # Installer owns these exports; conflicting user settings need review.
            if key in self.env:
                expected = self.environment_values().get(key)
                require(expected is not None and self.env[key] == expected, f'conflicting {key}; review privately')
        paths = [self.root, self.bin, self.state_dir(component),
                 *(self.home / path for path in spec['home_paths'])]
        if 'provider_home' in spec:
            paths.append(self.home / spec['provider_home'])
        if component == 'base':
            paths += [self.fragment, *(self.home / name for name in SHELL_FILES)]
        if component == 'claude':
            paths += [self.home / '.claude/settings.json', self.home / '.claude/skills/save-conversation/SKILL.md']
        for path in paths:
            self.home_path(path)
        if component != 'base':
            # Every wrapper sources the base fragment; base need not be current.
            require((self.state_dir('base') / 'managed-files.json').is_file() and self.fragment.is_file(),
                    'base component not installed; human: install-agent-vm-user-tools.sh --component base')
        for name in spec['checks']:
            if name in PREREQUISITE_CHECKS:
                self.run_check(name)

    def run_check(self, name, *, require_trust=True):
        method = getattr(self, 'check_' + name.replace('-', '_'))
        if name == 'local-ca-trust':
            method(require_trust)
        else:
            method()

    def owned_commands(self, component):
        """Map each installed command of this component to its exec target."""
        targets = {}
        # shlex quotes handle apostrophes, shell substitutions and spaces in account homes.
        for name, provider in self.agent['providers'].items():
            if provider['component'] == component:
                targets[name] = shlex.quote(str(self.provider_bin() / name))
        for tool in self.agent['user_tools'].values():
            if tool['component'] != component:
                continue
            for name in tool['commands']:
                path = (self.root / 'npm/node_modules/.bin' / name if tool['method'] == 'npm-lock'
                        else self.root / 'pipx-bin' / name)
                targets[name] = shlex.quote(str(path))
        for name, helper in self.agent['helpers'].items():
            if helper['component'] != component:
                continue
            source = Path(helper['native_source'])
            if source.is_relative_to('native/helpers'):
                targets[name] = shlex.quote(str(self.root / 'helpers' / source.relative_to('native/helpers')))
            else:
                targets[name] = f'python3 {shlex.quote(str(self.root / source.name))} {shlex.quote(name)}'
        return targets

    def component_names(self, component):
        return set(self.owned_commands(component))

    def component_files(self, component):
        files = {}
        if component == 'base':
            files[self.fragment] = (self.environment(), 0o600)
        for target, source in self.spec(component)['files'].items():
            mode = 0o700 if target.startswith('helpers/') else 0o600
            files[self.root / target] = ((REPO / source).read_text() if source else '', mode)
        for name, target in self.owned_commands(component).items():
            files[self.bin / name] = ('#!/usr/bin/env bash\nset -euo pipefail\n'
                                      f'. {shlex.quote(str(self.fragment))}\nexec {target} "$@"\n', 0o700)
        return files

    def all_planned_paths(self):
        return {str(path) for component in COMPONENTS for path in self.component_files(component)}

    # -- Shared environment -----------------------------------------------------

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

    def install_env(self):
        env = self.env | self.environment_values()
        env['PATH'] = str(self.bin) + ':' + env.get('PATH', '')
        env['NPM_CONFIG_CACHE'] = str(self.root / 'npm-cache')
        env['NPM_CONFIG_USERCONFIG'] = str(self.root / 'npm-user.conf')
        env['NPM_CONFIG_GLOBALCONFIG'] = str(self.root / 'npm-global.conf')
        env['NPM_CONFIG_STRICT_SSL'] = 'true'
        env['NPM_CONFIG_REGISTRY'] = NPM_REGISTRY
        env['PIP_CONFIG_FILE'] = '/dev/null'
        env['PIP_INDEX_URL'] = 'https://pypi.org/simple'
        env['PIP_EXTRA_INDEX_URL'] = ''
        return env

    # -- Managed-file convergence (per component) -------------------------------

    def write(self, path, text, mode=0o600):
        self.home_path(path)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temp = path.with_name(path.name + '.native-tmp')
        require(not temp.exists() and not temp.is_symlink(), 'temporary installation path collision')
        with temp.open('x') as stream:
            stream.write(text)
        temp.chmod(mode)
        temp.replace(path)

    def plan_files(self, component):
        # Review all collisions before invoking an installation command.
        files = self.component_files(component)
        previous = self.previous_state(component)
        for path, (content, _) in files.items():
            self.home_path(path)
            if path.exists():
                require(path.read_text() == content or previous.get(str(path)) == digest(path),
                        f'unmanaged or modified file collision: {path}; review privately')
        return files

    def previous_state(self, component):
        state_path = self.state_dir(component) / 'managed-files.json'
        self.home_path(state_path)
        if not state_path.exists():
            return {}
        try:
            previous = json.loads(state_path.read_text())
        except ValueError:
            previous = None
        require(isinstance(previous, dict) and all(
            isinstance(key, str) and isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value)
            for key, value in previous.items()), f'malformed {component} managed-files.json; review privately')
        return previous

    def retired_files(self, previous, files):
        # Review every retired candidate before any is removed; no partial cleanup.
        # A path another component now manages is never retired here.
        current = {str(path) for path in files} | self.all_planned_paths()
        retired = []
        for key, recorded in previous.items():
            if key in current:
                continue
            path = Path(key)
            require(path.is_absolute() and os.path.normpath(key) == key,
                    f'malformed retired managed path: {key}; review privately')
            self.home_path(path)
            if not path.exists():
                continue
            require(path.is_file() and digest(path) == recorded,
                    f'modified or non-regular retired managed file: {path}; review privately')
            retired.append(path)
        return retired

    # -- Installation -----------------------------------------------------------

    def install(self, component, update_provider=None):
        self.prerequisites(component)
        files = self.plan_files(component)
        state = self.state_dir(component)
        previous = self.previous_state(component)
        self.retired_files(previous, files)
        for path in (state / 'managed-files.json', state / 'installation.json'):
            self.home_path(path)
        apply = getattr(self, 'prepare_' + component)()
        for path, (content, mode) in files.items():
            self.write(path, content, mode)
        env = self.install_env()
        report = {'component': component,
                  'workspace_revision': self.command(['git', '-C', self.worktrees / 'workspace', 'rev-parse', 'HEAD']).stdout.strip(),
                  'workspace_dirty_paths': self.command(['git', '-C', self.worktrees / 'workspace', 'status', '--porcelain']).stdout.splitlines(),
                  'user': self.user, 'home': str(self.home), 'worktree_parent': str(self.worktrees),
                  'bare_parent': str(self.bares)}
        report.update(apply(env, update_provider))
        self.write(state / 'installation.json', json.dumps(report, indent=2) + '\n')
        for path in self.retired_files(previous, files):
            path.unlink()
        self.write(state / 'managed-files.json', json.dumps({str(p): digest(p) for p in files}, indent=2) + '\n')
        self.env = env
        self.verify(component, require_trust=False)

    def prepare_base(self):
        line = f'. {shlex.quote(str(self.fragment))} # budget-analyzer-native\n'
        shell_updates = {}
        for name in SHELL_FILES:
            path = self.home / name
            if not path.exists() and (name in ('.bash_profile', '.bash_login') or
                                      (name in ('.zprofile', '.zshrc') and not self.shell.endswith('/zsh'))):
                continue
            original = path.read_text() if path.exists() else ''
            managed = [l for l in original.splitlines() if l.endswith('# budget-analyzer-native')]
            require(not managed or managed == [line.strip()], 'shell environment fragment collision')
            if not managed:
                shell_updates[path] = original + ('\n' if original and not original.endswith('\n') else '') + line

        def apply(_env, _update):
            for path in self.spec('base')['home_paths']:
                (self.home / path).mkdir(mode=0o700, parents=True, exist_ok=True)
            for path, content in shell_updates.items():
                self.write(path, content)
            return {}
        return apply

    def prepare_provider(self, name):
        self.home_path(self.provider_package(name) / 'package.json')

        def apply(env, update_provider):
            # Providers float: resolve latest only when missing or explicitly requested,
            # one global package at a time in the separate provider prefix.
            if name == update_provider or not (self.provider_package(name) / 'package.json').exists():
                self.command(['npm', 'install', '--global', '--prefix', self.root / 'providers',
                              '--no-audit', '--no-fund', self.agent['providers'][name]['package'] + '@latest'], env=env)
            return {'provider_version': json.loads((self.provider_package(name) / 'package.json').read_text()).get('version')}
        return apply

    def prepare_claude(self):
        provider = self.prepare_provider('claude')
        overlay = json.loads((REPO / 'native/helpers/settings-overlay.json').read_text())
        settings_path = self.home / '.claude/settings.json'
        settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
        merged = merge_settings(settings, overlay)
        skill = self.home / '.claude/skills/save-conversation/SKILL.md'
        skill_source = REPO / 'native/helpers/skills/save-conversation/SKILL.md'
        require(not skill.exists() or skill.read_bytes() == skill_source.read_bytes(), 'conversation skill collision')

        def apply(env, update_provider):
            report = provider(env, update_provider)
            self.write(settings_path, json.dumps(merged, indent=2) + '\n')
            self.write(skill, skill_source.read_text())
            return report
        return apply

    def prepare_codex(self):
        return self.prepare_provider('codex')

    def prepare_gemini(self):
        return self.prepare_provider('gemini')

    def prepare_extras(self):
        npm_dir = self.root / 'npm'
        npm_files = [REPO / 'native/npm' / name for name in ('package.json', 'package-lock.json')]
        for source in npm_files:
            target = npm_dir / source.name
            self.home_path(target)
            require(not target.exists() or target.read_bytes() == source.read_bytes(),
                    'npm inputs changed; review explicit refresh in docs/native-user-tools.md')
        playwright = self.validate_lock(REPO / 'native/npm')
        for path in (self.root / 'pipx', self.root / 'pipx-bin', self.root / 'npm-cache'):
            self.home_path(path)

        def apply(env, _update):
            for source in npm_files:
                self.write(npm_dir / source.name, source.read_text())
            # No upstream interactive startup, auto-clone, --force or pipx ensurepath.
            if not (npm_dir / 'node_modules/.package-lock.json').exists():
                self.command(['npm', 'ci', '--prefix', npm_dir, '--no-audit', '--no-fund'], env=env)
            for package, source in [('mitmproxy', 'mitmproxy==' + self.agent['user_tools']['mitmproxy']['version']),
                                    ('ai-session-handler', str(self.handler))]:
                if not (self.root / 'pipx/venvs' / package).exists():
                    args = ['pipx', 'install']
                    if package == 'ai-session-handler':
                        args.append('--editable')
                    self.command([*args, source], env=env)
            for path in self.spec('extras')['home_paths']:
                (self.home / path).mkdir(mode=0o700, parents=True, exist_ok=True)
            self.command([self.bin / 'playwright', 'install', 'chromium'], env=env)
            return {'handler_revision': self.command(['git', '-C', self.handler, 'rev-parse', 'HEAD']).stdout.strip(),
                    'handler_dirty_paths': self.command(['git', '-C', self.handler, 'status', '--porcelain']).stdout.splitlines(),
                    'npm_lock_sha256': digest(npm_files[1]), 'playwright_version': playwright,
                    'mitmproxy_version': self.agent['user_tools']['mitmproxy']['version'],
                    'mitmproxy_resolved_dependencies': self.command(
                        ['pipx', 'runpip', 'mitmproxy', 'freeze', '--all'], env=env).stdout.splitlines()}
        return apply

    def validate_lock(self, directory):
        """Return the locked Playwright version; the lock is its only release source."""
        dependencies = json.loads((directory / 'package.json').read_text()).get('dependencies') or {}
        packages = json.loads((directory / 'package-lock.json').read_text())['packages']
        require(dependencies == {'playwright': dependencies.get('playwright')} and
                packages['']['dependencies'] == dependencies, 'npm package/lock direct dependencies disagree')
        entry = packages['node_modules/playwright']
        version = entry['version']
        require(re.fullmatch(r'\d+\.\d+\.\d+', version) and dependencies['playwright'] == version,
                'Playwright package/lock version disagree')
        require(entry['resolved'] == f'{NPM_REGISTRY}playwright/-/playwright-{version}.tgz',
                'Playwright lock tarball does not match its version')
        for name, entry in packages.items():
            if name:
                require(entry.get('resolved', '').startswith(NPM_REGISTRY) and
                        entry.get('integrity', '').startswith('sha512-'),
                        'transitive npm dependency lacks registry HTTPS/integrity')
        # Reviewed apt provenance is never derived from the lock; a lock-only
        # upgrade fails until the Chromium system inputs are reviewed.
        require(f'playwright-core {version} ' in self.manifest['chromium_apt_source'],
                'Chromium apt source does not match locked Playwright version')
        return version

    # -- Verification -----------------------------------------------------------

    def verify(self, component, *, require_trust=True):
        """Read-only: this component's prerequisites, files, checks and command resolution."""
        self.prerequisites(component)
        spec = self.spec(component)
        for path, (text, _) in self.plan_files(component).items():
            require(path.is_file() and path.read_text() == text, f'missing/stale managed file: {path}')
        homes = [self.home / path for path in spec['home_paths']]
        if 'provider_home' in spec and (self.home / spec['provider_home']).exists():
            homes.append(self.home / spec['provider_home'])
        for path in homes:
            self.home_path(path)
            require(path.is_dir() and os.access(path, os.W_OK | os.X_OK), f'home path not writable: {path}')
        for name in spec['checks']:
            if name not in PREREQUISITE_CHECKS:
                self.run_check(name, require_trust=require_trust)
        env = self.env | self.environment_values()
        # Fresh noninteractive shell never sources a whole interactive profile.
        probe = '. ' + shlex.quote(str(self.fragment)) + '; command -v "$1"'
        for name in sorted(self.component_names(component)):
            result = self.command(['bash', '--noprofile', '--norc', '-c', probe, 'native-check', name], env=env)
            require(result.stdout.strip() == str(self.bin / name), f'command resolution collision: {name}')

    def packages_installed(self, packages):
        for package in packages:
            result = self.command(['dpkg-query', '-W', '-f=${Status}', package], check=False)
            require(result.returncode == 0 and result.stdout.strip() == 'install ok installed',
                    f'missing system package {package}; human: ' + shlex.join([
                        './scripts/provision-agent-vm-guest.sh', '--docker-user', self.user,
                        '--worktree-parent', str(self.worktrees), '--bare-parent', str(self.bares)]))

    def check_system_packages(self):
        self.packages_installed(self.manifest['apt'] + ['nodejs', 'zulu25-jdk'])

    def check_node_npm(self):
        source = self.manifest['repositories']['nodesource']['source']
        selected_node = re.search(r'/node_(\d+)\.x ', source)
        require(selected_node, 'invalid reviewed NodeSource major selection')
        node_major = selected_node.group(1)
        require(self.command(['node', '--version']).stdout.startswith(f'v{node_major}.'),
                f'requires reviewed Node major {node_major}')
        require(int(self.command(['npm', '--version']).stdout.split('.')[0]) >= 10, 'requires npm >=10')

    def check_jdk(self):
        for command in ('java', 'javac'):
            result = self.command([command, '-version'])
            require(re.search(r'(?:openjdk|java|javac) (?:version )?"?25(?:[.\s"]|$)',
                              result.stdout + result.stderr),
                    f'requires reviewed JDK major 25 from active {command}')

    def check_system_downloads(self):
        for tool in self.manifest['downloads'].values():
            if 'check' in tool:
                r = self.command(tool['check'])
                require(re.search(tool['version_pattern'], r.stdout + r.stderr), 'system release version mismatch')

    def check_bwrap_apparmor(self):
        # Distro bubblewrap/AppArmor integration is a human gate, never a sysctl mutation.
        restrict = self.system_path('/proc/sys/kernel/apparmor_restrict_unprivileged_userns')
        if restrict.exists() and restrict.read_text().strip() == '1':
            profile = self.system_path('/etc/apparmor.d/bwrap')
            require(profile.is_file() and 'userns' in profile.read_text(),
                    'restricted user namespaces need Ubuntu bwrap AppArmor profile; see docs/native-user-tools.md')

    def provider_bin(self):
        return self.root / 'providers/bin'

    def provider_package(self, name):
        return self.root / 'providers/lib/node_modules' / self.agent['providers'][name]['package']

    def check_provider(self, name):
        """Ownership and containment only; provider versions intentionally float."""
        package, link = self.provider_package(name), self.provider_bin() / name
        self.home_path(package / 'package.json')
        require((package / 'package.json').is_file(),
                f'{name}: provider missing; human: install-agent-vm-user-tools.sh --update-provider {name}')
        self.home_path(link.parent)
        require(link.exists() and link.lstat().st_uid == self.uid, f'{name}: provider command missing or foreign')
        target = link.resolve(strict=True)
        require(target.is_relative_to(package), f'{name}: provider command resolves outside its managed package')
        self.home_path(target)
        self.command([self.bin / name, *self.agent['providers'][name]['check'][1:]])
        print(f'{name}: provider present (version floats)')

    def check_claude_cli(self):
        self.check_provider('claude')

    def check_codex_cli(self):
        self.check_provider('codex')

    def check_gemini_cli(self):
        self.check_provider('gemini')

    def check_claude_settings_overlay(self):
        overlay = json.loads((REPO / 'native/helpers/settings-overlay.json').read_text())
        settings_path = self.home / '.claude/settings.json'
        require(settings_path.is_file(), 'managed provider settings missing')
        settings = json.loads(settings_path.read_text())
        require(merge_settings(settings, overlay) == settings, 'managed controls missing or stale')

    def check_conversation_skill(self):
        skill = self.home / '.claude/skills/save-conversation/SKILL.md'
        require(skill.is_file() and skill.read_bytes() == (REPO / 'native/helpers/skills/save-conversation/SKILL.md').read_bytes(),
                'managed conversation skill missing/stale')

    def check_chromium_apt(self):
        self.packages_installed(self.manifest['chromium_apt'])

    def check_ai_session_handler_checkout(self):
        require(self.handler in self.repos, 'missing local checkout: ai-session-handler')
        require((self.handler / 'pyproject.toml').is_file() and
                (self.handler / 'src/ai_session_handler').is_dir(), 'handler source/metadata missing')

    def check_playwright_lock(self):
        self.validate_lock(REPO / 'native/npm')

    def check_agent_user_tools(self):
        versions = {'playwright': self.validate_lock(self.root / 'npm'),
                    'mitmproxy': self.agent['user_tools']['mitmproxy']['version']}
        for name, tool in self.agent['user_tools'].items():
            if tool['method'] in ('npm-lock', 'pipx', 'pipx-editable-guest-checkout'):
                command = tool['check'][0]
                result = self.command([self.bin / command, *tool['check'][1:]])
                if name in versions:
                    require(re.search(r'(?<![\d.])' + re.escape(versions[name]) + r'(?![\d.])', result.stdout + result.stderr),
                            f'{command}: installed version mismatch')
                print(f'{command}: version check passed')
        python = self.root / 'pipx/venvs/ai-session-handler/bin/python'
        origin = self.command([python, '-c', 'from pathlib import Path; import ai_session_handler; print(Path(ai_session_handler.__file__).resolve())']).stdout.strip()
        require(Path(origin).is_absolute() and Path(origin).is_relative_to(self.handler / 'src/ai_session_handler'), 'handler import origin mismatch')
        for name in self.agent['user_tools']['ai-session-handler']['commands'][1:]:
            self.command([self.bin / name, '--help'])
        for name in self.agent['user_tools']['mitmproxy']['commands'][1:]:
            self.command([self.bin / name, '--version'])
        print(f'Handler import: {origin}')

    def check_helper_commands(self):
        for name in ('mitmflows', 'mitmflow-detail', 'mitmflow-body', 'ai-run'):
            self.command([self.bin / name, '--help'])
        self.command([self.bin / 'via-annotator', '--check'])

    def check_playwright_chromium(self):
        env = self.env | self.environment_values()
        browser = self.command(['node', '-e', 'const fs=require("fs");const p=require("playwright");const e=p.chromium.executablePath(); if(!e.startsWith(process.env.PLAYWRIGHT_BROWSERS_PATH+"/")) process.exit(2);fs.accessSync(e,fs.constants.X_OK);console.log(e)'], env=env)
        require(bool(browser.stdout.strip()), 'missing Chromium; human: playwright install chromium')
        self.command([self.bin / 'playwright', 'install', '--list'])

    def check_local_ca_trust(self, require_trust):
        # Installing the trust helpers never requires trust; the read-only check does.
        if require_trust:
            self.command([self.bin / 'check-budget-analyzer-local-ca-trust'])

    # -- Selection --------------------------------------------------------------

    def run(self, action, components, update_provider=None):
        """Run each selected component independently; return the failed names."""
        failed = []
        for component in components:
            try:
                if action == 'install':
                    self.install(component, update_provider)
                else:
                    self.verify(component)
            except (UserToolsError, OSError, ValueError, KeyError) as exc:
                failed.append(component)
                print(f'native-user-tools: {component}: FAIL: {exc}', file=sys.stderr)
            else:
                print(f'{component}: PASS')
        print(f'Components: {len(components) - len(failed)} passed, {len(failed)} failed'
              + (f' ({", ".join(failed)})' if failed else ''))
        return failed


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=('install', 'check'))
    parser.add_argument('--worktree-parent', required=True)
    parser.add_argument('--bare-parent', required=True)
    parser.add_argument('--component', action='append', choices=COMPONENTS, dest='components',
                        help='repeatable; default: every component')
    parser.add_argument('--update-provider', choices=tuple(json.loads(AGENT_MANIFEST.read_text())['providers']),
                        help='install: update one provider CLI to the latest published release')
    args = parser.parse_args()
    if args.update_provider and args.action != 'install':
        parser.error('--update-provider requires install')
    components = [c for c in COMPONENTS if not args.components or c in args.components]
    if args.update_provider and args.update_provider not in components:
        parser.error('--update-provider requires its component to be selected')
    try:
        setup = UserTools(args.worktree_parent, args.bare_parent)
        setup.preflight()
    except (UserToolsError, OSError, ValueError, KeyError) as exc:
        print(f'native-user-tools: {exc}', file=sys.stderr)
        return 1
    if setup.run(args.action, components, args.update_provider):
        return 1
    if args.action == 'install':
        print('User tools installed. Trust and authentication are separate human actions.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
