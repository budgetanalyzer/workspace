#!/usr/bin/env python3
"""Human-only installation of the scoped Ubuntu bubblewrap AppArmor profile."""
import argparse
import os
from pathlib import Path
import pwd
import sys

from provision import MANIFEST, REPO, ProvisionError, Provisioner, load_manifest, require


class BwrapProfileInstaller(Provisioner):
    def preflight(self):
        # Reuse the system installer's native VM, user, ownership and Docker
        # gates. No downloads or system installation run from this helper.
        super().preflight()
        require(self.existing_docker, 'complete system provisioning before bwrap profile setup')
        for command in ('bwrap', 'aa-status', 'apparmor_parser'):
            require(self.which(command), f'required bootstrap command missing: {command}')
        binary = self.path('/usr/bin/bwrap')
        require(binary.is_file() and Path(self.which('bwrap')).resolve() == binary,
                'bwrap must resolve to the system /usr/bin/bwrap executable')
        self.root_owned(binary)
        restriction = self.path('/proc/sys/kernel/apparmor_restrict_unprivileged_userns')
        require(restriction.is_file(), 'Ubuntu namespace restriction setting is missing')
        self.restricted = restriction.read_text().strip()
        require(self.restricted in ('0', '1'), 'unexpected Ubuntu namespace restriction setting')
        self.profile = self.path('/etc/apparmor.d/bwrap')
        self.source = REPO / 'native/apparmor/bwrap'
        require(self.source.is_file() and not self.source.is_symlink(), 'workspace bwrap profile is missing or symlinked')
        self.managed = False
        if self.restricted == '1':
            require(self.profile.parent.is_dir(), 'AppArmor profile directory is missing')
            self.root_owned(self.profile.parent)
            require(not self.profile.is_symlink(), 'bwrap profile symlink collision; inspect manually')
            if self.profile.exists():
                require(self.profile.is_file(), 'bwrap profile is not a regular file; inspect manually')
                self.root_owned(self.profile)
                self.managed = self.profile.read_bytes() == self.source.read_bytes()
            self.command(['aa-status', '--enabled'], privileged=True)

    def smoke(self):
        return self.command([str(self.path('/usr/bin/bwrap')), '--unshare-user',
                             '--ro-bind', '/', '/', '--', '/bin/true'], check=False)

    def run(self):
        self.preflight()
        created = False
        if self.restricted == '1' and not self.profile.exists():
            print('Installing workspace profile for /usr/bin/bwrap:\n' + self.source.read_text(), flush=True)
            self.copy_file(self.source, '/etc/apparmor.d/bwrap', '0644')
            self.command(['apparmor_parser', '-r', str(self.profile)], privileged=True)
            created = True
        elif self.restricted == '1':
            print('Preserving existing bwrap profile: ' + str(self.profile), flush=True)
        result = self.smoke()
        if result.returncode and self.restricted == '1' and self.managed:
            # Recover an interrupted prior load only for identical reviewed
            # workspace bytes. Never reload an unrelated distro/user profile.
            self.command(['apparmor_parser', '-r', str(self.profile)], privileged=True)
            result = self.smoke()
        require(result.returncode == 0,
                'bwrap namespace check failed; existing profiles are preserved; inspect docs/native-user-tools.md: '
                + (result.stderr.strip() or result.stdout.strip()))
        if self.restricted == '1':
            status = self.command(['aa-status'], privileged=True)
            print(status.stdout.strip())
        require(self.workloads() == self.before, 'running workload set/start times changed; stop and inspect')
        print('Bubblewrap namespace check passed. ' +
              ('Scoped profile installed and loaded.' if created else 'Existing system policy retained.'))


def main():
    parser = argparse.ArgumentParser(description='Human-only setup for the scoped /usr/bin/bwrap AppArmor profile in the Ubuntu 24.04 QEMU/KVM guest. Run sudo -v first. Existing profiles are preserved; no sysctl, sudoers, reboot or Docker changes.')
    parser.add_argument('--docker-user', default=pwd.getpwuid(os.getuid()).pw_name)
    args = parser.parse_args()
    try:
        BwrapProfileInstaller(load_manifest(MANIFEST), args.docker_user).run()
    except (ProvisionError, OSError, ValueError, KeyError) as exc:
        print(f'install-agent-vm-bwrap-profile: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
