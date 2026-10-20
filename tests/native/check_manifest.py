#!/usr/bin/env python3
"""Offline native manifest, capability and local-link checks."""
import importlib.util
import json
import os
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    'provision', REPO / 'scripts/native/provision.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
data = module.load_manifest()
# System provisioning inputs and agent-tool declarations stay in separate files.
assert not {'user_tools', 'providers', 'helpers'} & set(data), 'agent tools in system manifest'
agent = json.loads((REPO / 'native/agent-tools.json').read_text())

for command, helper in agent['helpers'].items():
    assert re.fullmatch(r'[a-z0-9][a-z0-9.-]*', command), f'invalid helper command: {command}'
    source = Path(helper['native_source'])
    assert not source.is_absolute() and '..' not in source.parts, f'unsafe helper source: {source}'
    assert (REPO / source).is_file(), f'native helper source missing: {source}'
    assert helper['method'] == 'reviewed-native-user-helper-install'

# Every managed file, command, home path, environment key and check belongs to
# exactly one component; each check names an implemented installer method.
components = agent['components']
assert list(components) == ['base', 'claude', 'codex', 'gemini', 'extras'], 'component set/order'
user_spec = importlib.util.spec_from_file_location('user_tools', REPO / 'scripts/native/user_tools.py')
user_module = importlib.util.module_from_spec(user_spec)
user_spec.loader.exec_module(user_module)
assert tuple(components) == user_module.COMPONENTS, 'installer component order mismatch'
owners = {}
for component, spec in components.items():
    for key in ('files', 'home_paths', 'environment', 'checks'):
        values = spec[key]
        if key == 'files':
            for target, source in values.items():
                assert not Path(target).is_absolute() and '..' not in Path(target).parts, target
                assert not source or (REPO / source).is_file(), f'{component}: missing source {source}'
        for value in values:
            assert (key, value) not in owners, f'{key} {value} owned by {owners[(key, value)]} and {component}'
            owners[(key, value)] = component
    if 'provider_home' in spec:
        assert component in agent['providers'], f'{component}: provider home without provider'
    for check in spec['checks']:
        assert hasattr(user_module.UserTools, 'check_' + check.replace('-', '_')), f'unimplemented check {check}'
helper_sources = {source for spec in components.values() for source in spec['files'].values()
                  if source.startswith('native/helpers/')}
for path in (REPO / 'native/helpers').rglob('*'):
    if path.is_file():
        relative = str(path.relative_to(REPO))
        targets = [(c, t) for c, spec in components.items() for t, s in spec['files'].items()
                   if s == relative and t.startswith('helpers/')]
        assert len(targets) == 1, f'helper resource not owned by exactly one component: {relative}'
for name, provider in agent['providers'].items():
    assert provider['component'] == name, f'provider {name} must be its own component'
for name, tool in agent['user_tools'].items():
    assert tool['component'] in components, f'user tool {name}: unknown component'
for command, helper in agent['helpers'].items():
    component = helper['component']
    assert component in components, f'helper {command}: unknown component'
    sources = components[component]['files'].values()
    source = helper['native_source']
    assert source in sources, f'helper {command}: source {source} not installed by {component}'
commands = [*agent['providers'], *agent['helpers'],
            *(c for tool in agent['user_tools'].values() for c in tool['commands'])]
assert len(commands) == len(set(commands)), 'command owned by more than one component'
for key, relative in agent['reviewed_sources'].items():
    if relative.startswith('native/helpers/'):
        assert relative in helper_sources, f'reviewed source {key} not owned by a component'

for key in ('aliases', 'settings', 'skill', 'system_prompt', 'npm_lock'):
    source = REPO / agent['reviewed_sources'][key]
    assert source.is_file(), f'reviewed source missing: {key}={source}'

settings = json.loads((REPO / agent['reviewed_sources']['settings']).read_text())
assert 'hooks' not in settings, 'managed settings must not define hooks'

for name in ('go', 'actionlint'):
    for arch in data['architectures']:
        url = data['downloads'][name]['platforms'][arch]['url']
        assert arch in url, f'{name}/{arch} URL mismatch'

active_docs = (
    'README.md', 'AGENTS.md', 'docs/dependency-automation.md',
    'docs/design-decisions.md', 'docs/host-isolation.md', 'docs/launch-options.md',
    'docs/local-budget-analyzer-tls.md', 'docs/native-tool-inventory.md',
    'docs/native-user-tools.md', 'docs/traffic-inspection.md',
)
# Documentation links into the orchestration sibling are checked only when that
# checkout exists; workspace validation never requires it.
orchestration = REPO.parent / 'orchestration'
for relative in active_docs:
    text = (REPO / relative).read_text()
    for raw in re.findall(r'\]\(([^)]+)\)', text):
        if raw.startswith(('https://', 'http://', '#', 'app://')):
            continue
        target = raw.split('#', 1)[0].strip('<>')
        resolved = Path(os.path.normpath(
            REPO / target.lstrip('/') if target.startswith('/')
            else (REPO / relative).parent / target))
        if resolved.is_relative_to(orchestration):
            if not orchestration.is_dir():
                continue
        else:
            assert resolved.is_relative_to(REPO), f'{relative}: link escapes repository {raw}'
        assert resolved.exists(), f'{relative}: broken link {raw}'

# Guard selected installer architecture: no hidden unsafe installation fallback.
for relative in ('scripts/native/boundary.py', 'scripts/native/provision.py',
                 'scripts/native/user_tools.py', 'scripts/native/proxy.py'):
    engine = (REPO / relative).read_text()
    for forbidden in ('break-system-packages', 'shell=True', 'NOPASSWD',
                      'git clone', 'setup.sh', 'verify=False'):
        assert forbidden not in engine, f'{relative}: unsafe construct {forbidden}'

print(
    'Manifest/capability/links PASS: '
    f'{len(data["apt"])} apt inputs, {len(data["downloads"])} downloads on '
    f'{len(data["architectures"])} architectures, {len(agent["helpers"])} '
    f'native command mappings, {len(agent["components"])} components.'
)
