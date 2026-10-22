#!/usr/bin/env python3
"""Read-only development-VM boundary check that precedes agent work.

Proves the Ubuntu QEMU/KVM guest identity, canonical normal user and home,
guest-local repositories with bare origins, Git configuration, absent
credential/proxy/endpoint bridges and the guest Docker endpoint. It does not
require provider CLIs, agent helpers, AI Session Handler, platform binaries or
any sibling checkout other than this workspace.

The checkout entry point must run from the selected workspace clone. The copy
installed in the native root is the provider launch guard: it requires the
selected workspace checkout to exist, prints nothing on success and reports
failures only on stderr.
"""
import argparse
import grp
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
ENTRY = Path(__file__).resolve().parent
NATIVE_ROOT = '.local/share/budget-analyzer-native'
SHELLS = ('/bin/bash', '/usr/bin/bash', '/bin/sh', '/bin/zsh', '/usr/bin/zsh')
DENIED_ENV = ('SSH_AUTH_SOCK', 'GITHUB_TOKEN', 'GH_TOKEN', 'GIT_ASKPASS', 'SSH_ASKPASS',
              'GPG_AGENT_INFO', 'DOCKER_HOST', 'DOCKER_CONTEXT', 'TESTCONTAINERS_HOST_OVERRIDE',
              'GIT_CONFIG', 'GIT_CONFIG_GLOBAL', 'GIT_CONFIG_SYSTEM', 'GIT_CONFIG_COUNT',
              'GIT_SSH', 'GIT_SSH_COMMAND', 'GIT_CONFIG_PARAMETERS', 'HTTP_PROXY', 'HTTPS_PROXY',
              'ALL_PROXY', 'NODE_TLS_REJECT_UNAUTHORIZED', 'PYTHONHTTPSVERIFY', 'PIP_TRUSTED_HOST', 'NPM_TOKEN', 'NODE_AUTH_TOKEN', 'http_proxy', 'https_proxy', 'all_proxy')
DOCKER_SOCKET = '/var/run/docker.sock'


class BoundaryError(RuntimeError):
    pass


def is_private_primary_group(user, primary_gid, path_gid):
    if path_gid != primary_gid:
        return False
    try:
        group = grp.getgrgid(path_gid)
    except KeyError:
        return False
    primary_users = {entry.pw_name for entry in pwd.getpwall() if entry.pw_gid == path_gid}
    return (group.gr_name == user and primary_users == {user} and
            not set(group.gr_mem) - {user})


def installed_entry(home):
    """True for the base component's copy in the account's native root."""
    return ENTRY == Path(home) / NATIVE_ROOT


class VmBoundary:
    """Shared boundary rules; fixtures substitute observations, never gates."""
    error = BoundaryError

    def __init__(self, worktrees, bares):
        self.worktrees, self.bares = Path(worktrees), Path(bares)
        self.env = dict(os.environ)

    def require(self, condition, message):
        if not condition:
            raise self.error(message)

    def command(self, args, *, check=True):
        # Never print Git config, credentials or a full environment.
        result = subprocess.run([str(a) for a in args], text=True, capture_output=True, env=self.env)
        self.require(not check or result.returncode == 0,
                     f'{Path(str(args[0])).name}: command failed (exit {result.returncode}); inspect privately')
        return result

    def probe(self, args, **options):
        """Boundary observation: no subclass surfaces probe output on failure."""
        result = self.command(args, check=False, **options)
        self.require(result.returncode == 0,
                     f'{Path(str(args[0])).name}: boundary probe failed (exit {result.returncode}); inspect privately')
        return result

    def which(self, name):
        return shutil.which(name)

    def account(self):
        return pwd.getpwuid(self.current_uid())

    def current_uid(self):
        return os.getuid()

    def system_path(self, path):
        return Path(path)

    def private_primary_group(self, gid):
        return is_private_primary_group(self.user, self.gid, gid)

    def installed(self, package):
        result = self.command(['dpkg-query', '-W', '-f=${Status}', package], check=False)
        return result.returncode == 0 and result.stdout.strip() == 'install ok installed'

    def docker_root(self):
        return self.probe(['docker', 'info', '--format', '{{.DockerRootDir}}']).stdout.strip()

    def owned(self, path, *, directory=False, private=True):
        self.require(path.exists() and not path.is_symlink(), f'missing or symlinked path: {path}')
        status = path.stat()
        self.require(status.st_uid == self.uid, f'wrong owner: {path}')
        unsafe_group_write = (private and status.st_mode & 0o020 and
                              not self.private_primary_group(status.st_gid))
        self.require(not status.st_mode & 0o002 and not unsafe_group_write,
                     f'unsafe writable path: {path}')
        if directory:
            self.require(path.is_dir(), f'expected directory: {path}')

    def git_config(self, repo):
        result = self.probe(['git', '-C', repo, 'config', '--null', '--list', '--includes'])
        for record in result.stdout.split('\0'):
            key = record.split('\n', 1)[0].lower()
            self.require(not re.search(r'^(credential\.|include\.|includeif\.|url\.|http\..*extraheader|core\.sshcommand|core\.askpass|gpg\.)', key),
                         'Git credential/include/rewrite/forwarding configuration rejected; inspect privately')

    def check_boundary(self, *, installable=False):
        """Read-only boundary. installable=True is first provisioning: missing
        Docker or Git may be installed later, but unsafe existing state fails."""
        self.check_identity()
        self.check_authority()
        self.check_repositories(installable)
        self.check_docker(installable)

    def check_identity(self):
        account = self.account()
        self.uid, self.gid = account.pw_uid, account.pw_gid
        self.home, self.user = Path(account.pw_dir), account.pw_name
        self.shell = account.pw_shell
        self.require(self.shell in SHELLS, 'requires a supported normal-user login shell')
        self.require(self.uid >= 1000 and self.user != 'root' and self.current_uid() == self.uid,
                     'run as the normal development user, without sudo')
        self.require(self.env.get('HOME') == str(self.home) and self.home.resolve() == self.home,
                     'HOME must match the canonical account home')
        self.owned(self.home, directory=True)
        release = self.system_path('/etc/os-release').read_text()
        self.require(re.search(r'^ID=ubuntu$', release, re.M) and
                     re.search(r'^VERSION_ID="?24\.04"?$', release, re.M),
                     'requires Ubuntu 24.04 guest OS; other distributions and personal hosts are rejected')
        self.require(not self.system_path('/.dockerenv').exists() and
                     not self.system_path('/run/.containerenv').exists(),
                     'container execution rejected; run from the guest OS shell')
        self.require(self.which('systemd-detect-virt'), 'systemd-detect-virt is required for VM detection')
        container = self.command(['systemd-detect-virt', '--container'], check=False)
        vm = self.command(['systemd-detect-virt', '--vm'], check=False)
        self.require(container.returncode == 1 and container.stdout.strip() == 'none',
                     'container execution rejected; requires native QEMU/KVM execution')
        self.require(vm.returncode == 0 and vm.stdout.strip() in ('kvm', 'qemu'),
                     'requires native QEMU/KVM execution; a marker is insufficient')

    def check_authority(self):
        for key in DENIED_ENV:
            self.require(key not in self.env, f'{key} must be absent; remove credential/endpoint/proxy bridges privately')
        self.require(not any(k.startswith('GIT_CONFIG_KEY_') or k.startswith('GIT_CONFIG_VALUE_') for k in self.env),
                     'injected Git configuration rejected')
        for path in (self.home / '.git-credentials', self.home / '.netrc'):
            self.require(not path.exists(), 'Git/network credential store rejected; inspect privately')
        for path in (self.home / '.ssh', self.home / '.gnupg'):
            if path.exists():
                self.require(not any(p.is_socket() for p in path.rglob('*')),
                             'agent/forwarded credential socket rejected')

    def check_repositories(self, installable):
        for path in (self.worktrees, self.bares):
            self.require(path.is_absolute() and path.resolve() == path,
                         'repository parents must be canonical absolute paths')
            self.owned(path, directory=True, private=False)
        # The installed copy lives in the native root, so only the checkout
        # entry point can prove it runs from the selected workspace clone.
        self.require(installed_entry(self.home) or (self.worktrees / 'workspace').resolve() == REPO,
                     'entry point must come from the selected workspace clone')
        self.repos = sorted(p for p in self.worktrees.iterdir() if (p / '.git').exists())
        self.require(self.worktrees / 'workspace' in self.repos, 'missing local checkout: workspace')
        # A fresh guest may receive Git from provisioning; filesystem
        # ownership still applies and the Git rules run once it exists.
        git = bool(self.which('git'))
        self.require(git or installable, 'git is required for repository boundary checks')
        for repo in self.repos:
            self.owned(repo, directory=True, private=False)
            self.owned(repo / '.git', directory=True, private=False)
            bare = self.bares / (repo.name + '.git')
            self.owned(bare, directory=True, private=False)
            self.owned(bare / 'config', private=False)
            if not git:
                continue
            self.require(self.probe(['git', '-C', bare, 'rev-parse', '--is-bare-repository']).stdout.strip() == 'true',
                         'matching guest-local bare origin is absent')
            self.require(self.probe(['git', '-C', bare, 'remote']).stdout.strip() == '', 'bare origin has an external remote')
            self.git_config(repo)
            self.git_config(bare)
            self.require(self.probe(['git', '-C', repo, 'rev-parse', '--show-toplevel']).stdout.strip() == str(repo),
                         'checkout is not a standalone local clone')
            self.require(self.probe(['git', '-C', repo, 'remote']).stdout.strip() == 'origin', 'extra or missing Git remote')
            for push in (False, True):
                argv = ['git', '-C', repo, 'remote', 'get-url', '--all']
                if push:
                    argv.append('--push')
                self.require(self.probe([*argv, 'origin']).stdout.strip() == str(bare),
                             'wrong origin/push URL; human must inspect, no automatic Git repair')

    def check_docker(self, installable):
        config = self.home / '.docker/config.json'
        if config.exists():
            self.require(json.loads(config.read_text()).get('currentContext', 'default') in ('', 'default'),
                         'user Docker configuration selects a non-default context')
        socket = self.system_path(DOCKER_SOCKET)
        self.existing_docker = bool(self.which('docker'))
        if not self.existing_docker:
            self.require(installable, 'guest Docker is missing; human: ./scripts/provision-agent-vm-guest.sh')
            self.require(not socket.exists() and not self.installed('docker.io') and
                         not self.installed('docker-ce'), 'partial Docker installation needs human repair')
            return
        self.require(self.probe(['docker', 'context', 'show']).stdout.strip() == 'default',
                     'requires default guest Docker context')
        endpoint = self.probe(['docker', 'context', 'inspect', 'default', '--format', '{{.Endpoints.docker.Host}}'])
        self.require(endpoint.stdout.strip() == 'unix://' + DOCKER_SOCKET,
                     'rejecting remote/custom Docker endpoint; requires guest Unix Docker socket')
        self.require(socket.is_socket(), 'guest Docker socket missing')
        self.require(self.docker_root() == '/var/lib/docker',
                     'guest Docker data root mismatch; existing Docker must be healthy with /var/lib/docker')


def main():
    parser = argparse.ArgumentParser(
        prog='check-agent-vm-boundary.sh',
        description='Read-only pre-agent development-VM boundary check. Requires healthy guest '
                    'Docker; does not require provider CLIs, agent helpers or sibling checkouts.')
    parser.add_argument('--worktree-parent', required=True)
    parser.add_argument('--bare-parent', required=True)
    args = parser.parse_args()
    guard = False
    try:
        guard = installed_entry(pwd.getpwuid(os.getuid()).pw_dir)
        boundary = VmBoundary(args.worktree_parent, args.bare_parent)
        boundary.check_boundary()
    except (BoundaryError, OSError, ValueError, KeyError) as exc:
        if guard:
            print(f'agent launch blocked by VM boundary: {exc}; provider not started. '
                  'Diagnose with scripts/check-agent-vm-boundary.sh', file=sys.stderr)
        else:
            print(f'check-agent-vm-boundary: {exc}', file=sys.stderr)
        return 1
    if guard:
        # Provider output consumers parse stdout; success stays silent.
        return 0
    print(f'VM boundary PASS: user={boundary.user}; home={boundary.home}; '
          f'local repositories={len(boundary.repos)}; guest Docker default context')
    return 0


if __name__ == '__main__':
    sys.exit(main())
