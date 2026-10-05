#!/usr/bin/env python3
"""Offline parity, rendered shell validation, source guards and local links."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('user_tools', REPO / 'scripts/native/user_tools.py')
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)
data = json.loads((REPO / 'native/toolchain.json').read_text())
setup = u.UserTools('/fixture/work trees', '/fixture/bare repos')
setup.validate_lock(REPO / 'native/npm/package-lock.json')
for source, tool in data['helpers'].items():
    assert (REPO / tool['native_source']).is_file(), f'native helper unmapped: {source}'
    assert tool['method'] == 'reviewed-native-user-helper-install'
assert (REPO / 'native/helpers/skills/save-conversation/SKILL.md').read_bytes() == (REPO / 'ai-agent-sandbox/skills/save-conversation/SKILL.md').read_bytes()
for module in ('user_tools.py', 'proxy.py', 'local_ca.py'):
    text = (REPO / 'scripts/native' / module).read_text()
    for forbidden in ('shell=True', 'verify=False', 'ssl_insecure=true', 'ignore_https_errors', 'NOPASSWD', "'sudo', '-n'", 'git clone', '/home/vscode', ':-/workspace'):
        assert forbidden not in text, f'unsafe/container-specific construct in {module}: {forbidden}'

scratch = REPO / 'tmp/native-phase-2/rendered'
scratch.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='shells-', dir=scratch) as name:
    home = Path(name)
    setup.home, setup.uid = home, os.getuid()
    setup.root, setup.bin, setup.fragment = home / 'resources', home / 'bin', home / 'env.sh'
    files = setup.plan_files()
    for tool in data['helpers'].values():
        assert setup.bin / tool['command'] in files, f'command not installed: {tool["command"]}'
    shells = []
    for path, (text, mode) in files.items():
        if text.startswith('#!/usr/bin/env bash') or path.name == 'env.sh':
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            path.chmod(mode)
            shells.append(path)
    shells += list((REPO / 'native/helpers').glob('*.sh'))
    shells += [REPO / 'native/helpers' / name for name in ('mitmflows', 'mitmflow-detail', 'mitmflow-body')]
    shells += [REPO / 'scripts' / name for name in ('provision-agent-vm-guest.sh', 'install-agent-vm-user-tools.sh', 'check-agent-vm-tools.sh', 'install-agent-vm-local-ca-trust.sh', 'install-agent-vm-bwrap-profile.sh', 'prepare-agent-vm-native.sh')]
    for path in shells:
        subprocess.run(['bash', '-n', str(path)], check=True)
    subprocess.run(['shellcheck', '--shell=bash', *map(str, shells)], check=True)

for doc in ('README.md', 'AGENTS.md', 'docs/host-isolation.md', 'docs/native-user-tools.md',
            'docs/native-tool-inventory.md', 'docs/local-budget-analyzer-tls.md'):
    text = (REPO / doc).read_text()
    for raw in re.findall(r'\]\(([^)]+)\)', text):
        if raw.startswith(('https://', 'http://', '#')):
            continue
        target = raw.split('#', 1)[0].strip('<>')
        path = REPO / target.lstrip('/') if target.startswith('/') else (REPO / doc).parent / target
        assert path.exists(), f'{doc}: broken link {raw}'
# Newly created files are not covered by ordinary git diff --check.
for parent in ('native', 'scripts/native', 'tests/native'):
    for path in (REPO / parent).rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:
            lines = path.read_text().splitlines()
            assert all(line == line.rstrip() for line in lines), f'trailing whitespace: {path}'
print(f'Native environment PASS: locked npm dependencies; {len(data["helpers"])} command mappings; {len(shells)} shell files/wrappers; source guards, links and new-file whitespace.')
