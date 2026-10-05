#!/usr/bin/env python3
"""Offline manifest/parity/document checks; no tool install or live runtime."""
import importlib.util
import json
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('provision', REPO / 'scripts/native/provision.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
data = module.load_manifest()
source = (REPO / 'ai-agent-sandbox/Dockerfile').read_text()
inventory = (REPO / 'docs/native-tool-inventory.md').read_text()
retired_guest_sources = (
    'ai-agent-sandbox/agent-vm.env.example',
    'ai-agent-sandbox/docker-compose.agent-vm.yml',
    'ai-agent-sandbox/docker-compose.agent-vm-kubeconfig.yml',
    'ai-agent-sandbox/guest-entrypoint.sh',
    'scripts/agent-vm-container-lifecycle.sh',
    'scripts/agent-vm-container-start.sh',
    'scripts/agent-vm-container-stop.sh',
    'scripts/agent-vm-container-restart.sh',
    'scripts/agent-vm-container-status.sh',
    'scripts/agent-vm-container-shell.sh',
)
assert not [path for path in retired_guest_sources if (REPO / path).exists()], 'retired guest-agent source returned'
assert 'guest-entrypoint.sh' not in source, 'Mint image still installs retired guest entrypoint'
# Essential apt RUN surface, including the later Maven/JDK/Node declarations.
block = source.split('# Install essential packages\n', 1)[1].split('&& rm -rf', 1)[0]
packages = re.findall(r'^    ([a-z0-9][a-z0-9+.-]*)\s*\\?$', block, re.M)
covered = set(data['apt'] + ['docker.io', 'docker-compose-v2', 'nodejs', 'zulu25-jdk'])
assert not set(packages) - covered, f'Dockerfile apt capability missing: {set(packages) - covered}'
for line in source.splitlines():
    if line.startswith('COPY '):
        copied = line.split()[1]
        assert (REPO / 'ai-agent-sandbox' / copied).exists(), f'Dockerfile COPY source missing: {copied}'
        if copied.startswith('scripts/'):
            assert 'ai-agent-sandbox/' + copied in data['helpers'], copied
        assert copied in inventory, f'COPY disposition undocumented: {copied}'
assert set(data['helpers']) == {str(p.relative_to(REPO)) for p in (REPO / 'ai-agent-sandbox/scripts').iterdir()}, 'helper coverage drift'
for item in ('SSL_CERT_FILE', 'JAVA_HOME', 'MAVEN_HOME', 'PLAYWRIGHT_BROWSERS_PATH', 'NODE_EXTRA_CA_CERTS', 'DEBIAN_FRONTEND', 'PATH', 'WORKDIR', 'ENTRYPOINT', 'CMD', 'CLI_CACHE_BUST', 'TARGETARCH', 'NOPASSWD', 'chown', 'clone', 'origin', 'pipx', 'skills', 'settings-overlay.json', 'bash_aliases.sh', 'system-prompt-addon.py', 'system-prompt.md'):
    assert item in inventory, f'runtime/ENV disposition missing: {item}'
# This phase consumes the existing contract without changing sibling sources.
contract = (REPO.parent / 'orchestration/scripts/lib/pinned-tool-versions.sh').read_text()
for name in ('kubectl', 'helm', 'tilt', 'kind'):
    match = re.search(rf'PHASE7_{name.upper()}_VERSION="([^"]+)"', contract)
    assert match and data['downloads'][name]['version'] == match.group(1), f'orchestration {name} version drift'
    for arch in data['architectures']:
        release = data['downloads'][name]['platforms'][arch]
        assert re.search(rf'{name}:linux-{arch}\).*?{release["sha256"]}', contract), f'orchestration {name}/{arch} checksum drift'
for name, arg in [('kubectl','KUBECTL'),('helm','HELM'),('tilt','TILT'),('actionlint','ACTIONLINT'),('via','VIA')]:
    assert f'ARG {arg}_VERSION={data["downloads"][name]["version"]}' in source, f'Dockerfile {name} drift'
assert f'ARG MITMPROXY_VERSION={data["user_tools"]["mitmproxy"]["version"]}' in source
assert 'go' + data['downloads']['go']['version'] + '.linux-amd64' in source
for name in ('go', 'kind', 'kubectl', 'helm', 'tilt', 'actionlint'):
    for arch in data['architectures']:
        url = data['downloads'][name]['platforms'][arch]['url']
        expected = 'x86_64' if name == 'tilt' and arch == 'amd64' else arch
        assert expected in url, f'{name}/{arch} URL mismatch'
for path in ('README.md','AGENTS.md','docs/host-isolation.md','docs/native-tool-inventory.md'):
    text = (REPO / path).read_text()
    for raw in re.findall(r'\]\(([^)]+)\)', text):
        if raw.startswith(('https://','http://','#','app://')):
            continue
        target = raw.split('#',1)[0].strip('<>')
        resolved = REPO / target.lstrip('/') if target.startswith('/') else (REPO / path).parent / target
        assert resolved.exists(), f'{path}: broken link {raw}'
# Guard selected installer architecture: no hidden unsafe installation fallback.
engine = (REPO / 'scripts/native/provision.py').read_text()
for forbidden in ('break-system-packages', 'shell=True', 'NOPASSWD', 'git clone', 'setup.sh', 'verify=False'):
    assert forbidden not in engine, f'unsafe provisioning construct {forbidden}'
print(f'Manifest/parity/links PASS: {len(packages)} Dockerfile apt inputs, {len(data["downloads"])} downloads on both architectures, {len(data["helpers"])} helpers; current Helm 3.20.x contract matched.')
