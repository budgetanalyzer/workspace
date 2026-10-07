#!/usr/bin/env python3
"""Offline native manifest, capability and local-link checks."""
import argparse
import importlib.util
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser()
parser.add_argument(
    '--workspace-only', action='store_true',
    help='skip sibling orchestration source and contract checks')
args = parser.parse_args()

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    'provision', REPO / 'scripts/native/provision.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
data = module.load_manifest()

for command, helper in data['helpers'].items():
    assert re.fullmatch(r'[a-z0-9][a-z0-9.-]*', command), f'invalid helper command: {command}'
    source = Path(helper['native_source'])
    assert not source.is_absolute() and '..' not in source.parts, f'unsafe helper source: {source}'
    assert (REPO / source).is_file(), f'native helper source missing: {source}'
    assert helper['method'] == 'reviewed-native-user-helper-install'

for key in ('aliases', 'settings', 'skill', 'system_prompt',
            'system_prompt_addon', 'npm_lock'):
    source = REPO / data['reviewed_sources'][key]
    assert source.is_file(), f'reviewed source missing: {key}={source}'

if not args.workspace_only:
    for key in ('helm_contract', 'orchestration_tools'):
        source = REPO / data['reviewed_sources'][key]
        assert source.is_file(), f'reviewed source missing: {key}={source}'

settings = json.loads((REPO / data['reviewed_sources']['settings']).read_text())
hook = settings['hooks']['SessionStart'][0]['hooks'][0]
assert hook == {
    'type': 'command',
    'command': ('if [ -f "$CLAUDE_PROJECT_DIR/AGENTS.md" ]; then '
                'cat "$CLAUDE_PROJECT_DIR/AGENTS.md"; fi'),
}, 'managed AGENTS.md SessionStart hook drift'

if not args.workspace_only:
    # Local native validation consumes orchestration's current binary contract
    # without changing sibling source. Standalone hosted CI validates only this
    # repository's committed inputs.
    contract = (REPO.parent / 'orchestration/scripts/lib/pinned-tool-versions.sh').read_text()
    for name in ('kubectl', 'helm', 'tilt', 'kind'):
        match = re.search(rf'PHASE7_{name.upper()}_VERSION="([^"]+)"', contract)
        assert match and data['downloads'][name]['version'] == match.group(1), (
            f'orchestration {name} version drift')
        for arch in data['architectures']:
            release = data['downloads'][name]['platforms'][arch]
            assert re.search(
                rf'{name}:linux-{arch}\).*?{release["sha256"]}', contract), (
                f'orchestration {name}/{arch} checksum drift')

for name in ('go', 'kind', 'kubectl', 'helm', 'tilt', 'actionlint'):
    for arch in data['architectures']:
        url = data['downloads'][name]['platforms'][arch]['url']
        expected = 'x86_64' if name == 'tilt' and arch == 'amd64' else arch
        assert expected in url, f'{name}/{arch} URL mismatch'

active_docs = (
    'README.md', 'AGENTS.md', 'docs/dependency-automation.md',
    'docs/design-decisions.md', 'docs/launch-options.md',
    'docs/local-budget-analyzer-tls.md', 'docs/native-tool-inventory.md',
    'docs/native-user-tools.md', 'docs/traffic-inspection.md',
)
for relative in active_docs:
    text = (REPO / relative).read_text()
    for raw in re.findall(r'\]\(([^)]+)\)', text):
        if raw.startswith(('https://', 'http://', '#', 'app://')):
            continue
        target = raw.split('#', 1)[0].strip('<>')
        resolved = (REPO / target.lstrip('/') if target.startswith('/')
                    else (REPO / relative).parent / target)
        assert resolved.exists(), f'{relative}: broken link {raw}'

# Guard selected installer architecture: no hidden unsafe installation fallback.
for relative in ('scripts/native/provision.py', 'scripts/native/user_tools.py',
                 'scripts/native/proxy.py'):
    engine = (REPO / relative).read_text()
    for forbidden in ('break-system-packages', 'shell=True', 'NOPASSWD',
                      'git clone', 'setup.sh', 'verify=False'):
        assert forbidden not in engine, f'{relative}: unsafe construct {forbidden}'

print(
    'Manifest/capability/links PASS: '
    f'{len(data["apt"])} apt inputs, {len(data["downloads"])} downloads on '
    f'{len(data["architectures"])} architectures, {len(data["helpers"])} '
    'native command mappings; '
    + ('workspace-owned inputs checked.' if args.workspace_only
       else 'orchestration contract matched.')
)
