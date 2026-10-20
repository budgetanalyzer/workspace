#!/usr/bin/env python3
"""Human-run Ubuntu VM system provisioning; no user setup/runtime bootstrap."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from boundary import BoundaryError, VmBoundary  # noqa: E402  pylint: disable=wrong-import-position

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / 'native/toolchain.json'


class ProvisionError(BoundaryError):
    pass


def require(condition, message):
    if not condition:
        raise ProvisionError(message)


def node_major(data):
    source = data['repositories']['nodesource']['source']
    match = re.fullmatch(
        r'deb \[signed-by=/etc/apt/keyrings/nodesource\.gpg\] '
        r'https://deb\.nodesource\.com/node_(\d+)\.x nodistro main',
        source,
    )
    require(match, 'invalid NodeSource major selection')
    return match.group(1)


def load_manifest(path=MANIFEST):
    data = json.loads(path.read_text())
    require(data['schema'] == 1, 'unsupported tool manifest schema')
    require(data['os'] == {'id': 'ubuntu', 'release': '24.04'}, 'unsupported manifest OS')
    require(data['architectures'] == ['amd64', 'arm64'], 'incomplete architecture table')
    for package in data['apt'] + data['chromium_apt']:
        require(re.fullmatch(r'[a-z0-9][a-z0-9+.-]*', package), 'invalid apt package')
    for name, tool in data['downloads'].items():
        require(re.fullmatch(r'[a-z][a-z0-9-]*', name), 'invalid tool name')
        require(tool['method'] in ('binary', 'tar-binary', 'go', 'via'), 'invalid download method')
        require(re.fullmatch(r'v?\d+\.\d+\.\d+', tool['version']), 'unreviewed tool version')
        for arch in data['architectures']:
            release = tool['platforms'][arch]
            require(release['url'].startswith('https://'), 'downloads require HTTPS')
            require(re.fullmatch(r'[0-9a-f]{64}', release['sha256']), 'invalid release SHA-256')
        if tool['method'] == 'via':
            require(re.fullmatch(r'[0-9a-f]{64}', tool['asset_sha256']), 'invalid VIA asset SHA-256')
        else:
            require(tool['check'][0] == name, 'tool validation command mismatch')
            release = tool['version'].removeprefix('v')
            for arch in data['architectures']:
                require(release in tool['platforms'][arch]['url'],
                        f'{name}/{arch}: URL does not match reviewed version')
            expected_pattern = rf'(?<![0-9.]){re.escape(release)}(?![0-9.])'
            require(tool['version_pattern'] == expected_pattern,
                    f'{name}: validation pattern does not match reviewed version')
            if tool['method'] == 'go':
                require(tool['destination'].endswith(f'/go-{release}'),
                        'go: destination does not match reviewed version')
    for repository in data['repositories'].values():
        require(repository['key_url'].startswith('https://'), 'repository key requires HTTPS')
        require(re.fullmatch(r'[A-F0-9]{40}', repository['fingerprint']), 'invalid repository fingerprint')
        require('signed-by=' in repository['source'], 'apt repository must scope its key')
    selected_node_major = node_major(data)
    for name, repository in data['repositories'].items():
        require(re.findall(r'Node major (\d+)', repository['policy']) ==
                [selected_node_major],
                f'{name}: policy does not match NodeSource major selection')
    return data


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def semantic_version(value, context):
    match = re.search(r'(?<![0-9.])v?(\d+)\.(\d+)\.(\d+)(?![0-9.])', value)
    require(match, f'could not determine {context} semantic version')
    return tuple(int(part) for part in match.groups())


class Provisioner(VmBoundary):
    """Fixtures substitute OS observations/commands, never production gates."""
    error = ProvisionError

    def __init__(self, manifest, user, worktrees, bares):
        super().__init__(worktrees, bares)
        self.manifest, self.user = manifest, user
        self.existing_docker, self.before = False, None

    def path(self, value):
        return Path(value)

    def system_path(self, path):
        return self.path(path)

    def command(self, argv, *, privileged=False, check=True):
        argv = [str(arg) for arg in argv]
        if privileged:
            if argv[0] == 'docker':
                # sudo may select root's Docker config; pin the verified guest
                # socket rather than inheriting a different root context.
                argv = ['docker', '--host', 'unix:///var/run/docker.sock', *argv[1:]]
            argv = ['sudo', '-n', '--'] + argv
            print('System command: ' + shlex.join(argv), flush=True)
        result = subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check and result.returncode:
            detail = result.stderr.strip() or result.stdout.strip()
            raise ProvisionError(f'{shlex.join(argv)} exited {result.returncode}: {detail}')
        return result

    def account(self):
        try:
            return pwd.getpwnam(self.user)
        except KeyError as exc:
            raise ProvisionError('selected guest user does not exist') from exc

    def machine(self):
        return os.uname().machine

    def docker_root(self):
        # The user may not be in the docker group before first provisioning.
        return self.command(['docker', 'info', '--format', '{{.DockerRootDir}}'], privileged=True).stdout.strip()

    def preflight(self):
        require(re.fullmatch(r'[a-z_][a-z0-9_-]*\$?', self.user), 'invalid guest user name')
        # Shared VM boundary first; missing Docker/Git is installable here,
        # unsafe or partial existing state still fails before any write.
        self.check_boundary(installable=True)
        for name in ('systemd-detect-virt', 'sudo', 'curl', 'gpg', 'dpkg', 'dpkg-query', 'apt-get', 'install', 'systemctl', 'usermod', 'id', 'cp', 'ln', 'chmod'):
            require(self.which(name), f'required bootstrap command missing: {name}')
        self.arch = self.command(['dpkg', '--print-architecture']).stdout.strip()
        require(self.arch in self.manifest['architectures'], 'unsupported architecture')
        require({'x86_64': 'amd64', 'aarch64': 'arm64'}.get(self.machine()) == self.arch,
                'kernel and package architectures disagree')
        audit = self.command(['dpkg', '--audit'])
        require(not audit.stdout.strip() and not audit.stderr.strip(),
                'pending package configuration needs human repair before provisioning')
        if self.existing_docker:
            require(self.command(['docker', 'compose', 'version'], check=False).returncode == 0,
                    'existing Docker needs Compose; review its package provider before repair')
            self.before = self.workloads()
        self.check_major(
            'node', ['node', '--version'], rf'^v{node_major(self.manifest)}\.')
        self.check_major('java', ['java', '-version'], r'(?:openjdk|java) version "25(?:[."])')
        if self.which('npm'):
            version = self.command(['npm', '--version']).stdout.strip()
            require(int(version.split('.')[0]) >= 10, 'npm must be 10 or newer')
        self.check_destinations()
        print(f'Preflight: Ubuntu 24.04 QEMU/KVM; {self.arch}; user {self.user}; home {self.home}')

    def check_major(self, name, argv, pattern):
        if self.which(name):
            self.root_owned(Path(self.which(name)))
            self.root_owned(Path(self.which(name)).resolve())
            result = self.command(argv)
            require(re.search(pattern, result.stdout + result.stderr), f'existing {name} violates required major; review before replacing')

    def root_owned(self, path):
        require(path.stat().st_uid == 0, f'ownership collision: {path}')
        require(not (path.stat().st_mode & 0o022), f'writable install destination: {path}')
        for parent in path.parents:
            require(not parent.is_symlink(), f'symlinked install parent: {parent}')
            require(parent.stat().st_uid == 0 and not (parent.stat().st_mode & 0o022), f'unsafe install parent: {parent}')

    def check_destinations(self):
        self.pending = {}
        for name, tool in self.manifest['downloads'].items():
            destination = self.path(tool['destination'])
            if tool['method'] == 'via':
                if destination.exists():
                    self.root_owned(destination)
                    require(not destination.is_symlink(), 'VIA directory symlink collision')
                    asset = destination / 'via_image_annotator.html'
                    require(asset.is_file() and not asset.is_symlink(), 'existing VIA asset collision')
                    require((destination / 'LICENSE').is_file() and (destination / 'README.md').is_file(), 'incomplete VIA installation')
                    via_version = re.search(r"const _VIA_VERSION = '([^']+)'", asset.read_text())
                    require(via_version, 'could not determine installed VIA semantic version')
                    installed = semantic_version(via_version.group(1), 'installed VIA')
                    selected = semantic_version(tool['version'], 'selected VIA')
                    require(installed <= selected,
                            f"existing VIA {'.'.join(map(str, installed))} is newer than reviewed {tool['version']}")
                    if installed < selected:
                        self.pending[name] = tool
                    else:
                        require(sha256(asset) == tool['asset_sha256'], 'existing VIA asset collision')
                    continue
            elif self.which(name):
                self.root_owned(Path(self.which(name)))
                self.root_owned(Path(self.which(name)).resolve())
                result = self.command(tool['check'])
                installed = semantic_version(result.stdout + result.stderr, f'installed {name}')
                selected = semantic_version(tool['version'], f'selected {name}')
                require(installed <= selected,
                        f"existing {name} {'.'.join(map(str, installed))} is newer than reviewed {tool['version']}")
                if name == 'go':
                    require(self.which('gofmt'), 'existing Go installation lacks gofmt; review before repair')
                    self.root_owned(Path(self.which('gofmt')))
                    self.root_owned(Path(self.which('gofmt')).resolve())
                if installed < selected:
                    self.pending[name] = tool
                continue
            require(not destination.exists() and not destination.is_symlink(), f'destination collision: {destination}')
            parent = destination.parent
            while not parent.exists():
                parent = parent.parent
            require(not parent.is_symlink(), f'symlinked install parent: {parent}')
            self.root_owned(parent)
            if name == 'go':
                for binary in ('go', 'gofmt'):
                    target = self.path('/usr/local/bin/' + binary)
                    require(not target.exists() and not target.is_symlink(), f'Go command collision: {target}')
            self.pending[name] = tool
        for name, repository in self.manifest['repositories'].items():
            source, key = self.path(repository['source_path']), self.path(repository['key_path'])
            if source.exists():
                self.root_owned(source)
                require(not source.is_symlink() and source.read_text().strip() == repository['source'], f'apt source collision: {name}')
            if key.exists():
                self.root_owned(key)
                require(not key.is_symlink(), f'apt key collision: {name}')
            for path in (source, key):
                require(not path.is_symlink(), f'dangling apt path collision: {name}')
                parent = path.parent
                while not parent.exists():
                    parent = parent.parent
                require(not parent.is_symlink(), f'symlinked apt parent: {parent}')
                self.root_owned(parent)

    def workloads(self):
        ids = self.command(['docker', 'ps', '-q', '--no-trunc'], privileged=True).stdout.split()
        if not ids:
            return []
        result = self.command(['docker', 'inspect', '--format', '{{.Id}} {{.State.StartedAt}}', *ids], privileged=True)
        return sorted(result.stdout.splitlines())

    def download(self, url, destination):
        print(f'Downloading {url}', flush=True)
        self.command(['curl', '--fail', '--show-error', '--silent', '--location',
                      '--connect-timeout', '10', '--max-time', '45', '--retry', '2',
                      '--retry-max-time', '90', '--retry-all-errors',
                      '--proto', '=https', '--proto-redir', '=https',
                      '--output', str(destination), url])

    def key_fingerprints(self, key, work):
        result = self.command(['gpg', '--homedir', str(work / 'gnupg'), '--batch', '--show-keys', '--with-colons', str(key)])
        fingerprints, primary = [], False
        for line in result.stdout.splitlines():
            fields = line.split(':')
            if fields[0] in ('pub', 'sub'):
                primary = fields[0] == 'pub'
            elif fields[0] == 'fpr' and primary:
                fingerprints.append(fields[9])
                primary = False
        return fingerprints

    def stage(self, work):
        # Finish verification/extraction before any privileged OS mutation.
        (work / 'gnupg').mkdir(mode=0o700)
        staged = {}
        for name, repository in self.manifest['repositories'].items():
            key = work / (name + '.key')
            self.download(repository['key_url'], key)
            require(self.key_fingerprints(key, work) == [repository['fingerprint']], f'repository signing key mismatch: {name}')
            existing = self.path(repository['key_path'])
            if existing.exists():
                require(self.key_fingerprints(existing, work) == [repository['fingerprint']], f'existing repository key collision: {name}')
            ring = work / (name + '.gpg')
            self.command(['gpg', '--homedir', str(work / 'gnupg'), '--batch', '--dearmor', '--output', str(ring), str(key)])
            source = work / (name + '.list')
            source.write_text(repository['source'] + '\n')
            staged[name] = (ring, source)
        for name, tool in self.pending.items():
            archive = work / (name + '.download')
            release = tool['platforms'][self.arch]
            self.download(release['url'], archive)
            require(sha256(archive) == release['sha256'], f'checksum mismatch: {name}; no system changes made')
            extracted = work / name
            extracted.mkdir()
            if tool['method'] == 'binary':
                shutil.copyfile(archive, extracted / name)
            elif tool['method'] == 'tar-binary':
                with tarfile.open(archive, 'r:gz') as tar:
                    member = tool['member'].replace('{arch}', self.arch)
                    info = tar.getmember(member)
                    require(info.isfile(), f'non-file archive member: {name}')
                    with tar.extractfile(info) as src, (extracted / name).open('wb') as dst:
                        shutil.copyfileobj(src, dst)
            elif tool['method'] == 'go':
                with tarfile.open(archive, 'r:gz') as tar:
                    # Official archives include the top-level directory as
                    # "go" (without a trailing slash), followed by its contents.
                    require(all((member.name == 'go' and member.isdir()) or member.name.startswith('go/')
                                for member in tar.getmembers()), 'unexpected Go archive layout')
                    tar.extractall(extracted, filter='data')
            else:
                with zipfile.ZipFile(archive) as zip_file:
                    for filename in ('via_image_annotator.html', 'LICENSE', 'README.md'):
                        (extracted / filename).write_bytes(zip_file.read(f"via-{tool['version']}/{filename}"))
                require(sha256(extracted / 'via_image_annotator.html') == tool['asset_sha256'], 'VIA asset checksum mismatch')
            staged[name] = extracted
        return staged

    def copy_file(self, source, destination, mode):
        destination = self.path(destination)
        if destination.exists() and sha256(source) == sha256(destination):
            return
        if not destination.parent.exists():
            self.command(['install', '-d', '-m', '0755', str(destination.parent)], privileged=True)
        self.command(['install', '-m', mode, str(source), str(destination)], privileged=True)

    def install(self, staged):
        for name, repository in self.manifest['repositories'].items():
            ring, source = staged[name]
            self.copy_file(ring, repository['key_path'], '0644')
            self.copy_file(source, repository['source_path'], '0644')
        packages = self.manifest['apt'] + self.manifest['chromium_apt'] + ['nodejs', 'zulu25-jdk']
        if not self.existing_docker:
            packages += ['docker.io', 'docker-compose-v2']
        missing = sorted({package for package in packages if not self.installed(package)})
        if missing:
            self.command(['apt-get', 'update'], privileged=True)
            simulation = self.command(['apt-get', '--simulate', 'install', '-y', '--no-upgrade', *missing], privileged=True)
            # Installed-version brackets follow the package name. Brackets
            # inside/after the candidate describe architecture or dependencies.
            require(not any(line.startswith('Remv ') or re.match(r'^Inst \S+ \[', line)
                            for line in simulation.stdout.splitlines()),
                    'apt would remove/upgrade existing packages; review maintenance outside this installer')
            self.command(['env', 'NEEDRESTART_MODE=l', 'DEBIAN_FRONTEND=noninteractive', 'apt-get', 'install', '-y', '--no-upgrade', *missing], privileged=True)
        for name, tool in self.pending.items():
            source = staged[name]
            if tool['method'] == 'go':
                destination = self.path(tool['destination'])
                self.command(['install', '-d', '-m', '0755', str(destination)], privileged=True)
                self.command(['cp', '-R', '--no-preserve=ownership', str(source / 'go') + '/.', str(destination)], privileged=True)
                for binary in ('go', 'gofmt'):
                    self.command(['ln', '-sfn', str(destination / 'bin' / binary), str(self.path('/usr/local/bin/' + binary))], privileged=True)
            elif tool['method'] == 'via':
                for filename in ('via_image_annotator.html', 'LICENSE', 'README.md'):
                    self.copy_file(source / filename, tool['destination'] + '/' + filename, '0444')
                self.command(['chmod', '0555', str(self.path(tool['destination']))], privileged=True)
            else:
                self.copy_file(source / name, tool['destination'], '0755')
        if not self.existing_docker:
            self.command(['systemctl', 'enable', '--now', 'docker'], privileged=True)
        if 'docker' not in self.command(['id', '-nG', self.user]).stdout.split():
            self.command(['usermod', '-aG', 'docker', self.user], privileged=True)
        self.validate()

    def validate(self):
        require(self.which('node') and self.which('java') and self.which('npm'), 'installed Node/JDK/npm missing from PATH')
        self.check_major(
            'node', ['node', '--version'], rf'^v{node_major(self.manifest)}\.')
        self.check_major('java', ['java', '-version'], r'(?:openjdk|java) version "25(?:[."])')
        require(int(self.command(['npm', '--version']).stdout.strip().split('.')[0]) >= 10, 'npm must be 10 or newer')
        require(self.command(['docker', 'info', '--format', '{{.DockerRootDir}}'], privileged=True).stdout.strip() == '/var/lib/docker', 'Docker data-root drift')
        if self.existing_docker:
            require(self.workloads() == self.before, 'running workload set/start times changed; stop and inspect')
        for name, tool in self.manifest['downloads'].items():
            if tool['method'] == 'via':
                require(sha256(self.path(tool['destination']) / 'via_image_annotator.html') == tool['asset_sha256'], 'VIA validation failed')
            else:
                result = self.command(tool['check'])
                require(re.search(tool['version_pattern'], result.stdout + result.stderr), f'installed {name} version mismatch')
                print(f'Resolved {name}: {(result.stdout + result.stderr).strip()}')
        for argv in self.manifest['system_checks']:
            if argv == ['certutil', '-H']:
                # NSS prints its help with status 1. Require recognizable
                # command sections so a real execution failure still rejects.
                result = self.command(argv, check=False)
                help_text = result.stdout + result.stderr
                require(result.returncode in (0, 1) and
                        all(re.search(rf'^{flag}\s+', help_text, re.M) for flag in ('-A', '-L', '-N')),
                        'certutil help validation failed')
            else:
                result = self.command(argv)
            lines = (result.stdout + result.stderr).splitlines()
            print('Validated ' + shlex.join(argv) + (': ' + lines[0] if lines else ''))
        for package in sorted(set(self.manifest['apt'] + self.manifest['chromium_apt'] + ['nodejs', 'zulu25-jdk'])):
            version = self.command(['dpkg-query', '-W', '-f=${Version}', package]).stdout.strip()
            print(f'Resolved apt {package}: {version}')

    def run(self):
        self.preflight()
        scratch = REPO / 'tmp/native-agent-installer'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='provision-', dir=scratch) as directory:
            self.install(self.stage(Path(directory)))
        print(f'System tools ready. Reconnect as {self.user} if Docker membership changed, then install user tools/configuration.')


def main():
    parser = argparse.ArgumentParser(prog='provision-agent-vm-guest.sh', description='Human-run system installer for a native Ubuntu 24.04 QEMU/KVM development VM. Run as USER, not root; authorize sudo first with sudo -v in the human shell. Non-VM and container execution are rejected. Existing Docker/workloads are preserved.')
    parser.add_argument('--docker-user', required=True, metavar='USER')
    parser.add_argument('--worktree-parent', required=True)
    parser.add_argument('--bare-parent', required=True)
    args = parser.parse_args()
    try:
        Provisioner(load_manifest(), args.docker_user, args.worktree_parent, args.bare_parent).run()
    except (ProvisionError, OSError, ValueError, KeyError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(f'provision-agent-vm-guest: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
