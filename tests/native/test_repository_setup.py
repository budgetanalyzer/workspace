"""Focused checks for host-to-development-VM repository setup."""
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


REPO = Path(__file__).resolve().parents[2]
SETUP = REPO / 'scripts/setup-agent-vm-repositories.sh'
ADD_ONE = REPO / 'scripts/add-agent-vm-repository.sh'


class RepositorySetupTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / 'tmp/repository-setup-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='setup-', dir=scratch)
        self.root = Path(self.temp.name)
        self.host_parent = self.root / 'host'
        self.host_parent.mkdir()
        self.repository = self.host_parent / 'new-service'
        self.repository.mkdir()
        self.guest_root = self.root / 'guest'
        self.guest_root.mkdir()
        self.commands = self.root / 'commands'
        self.commands.mkdir()
        self.env = dict(
            os.environ,
            PATH=f'{self.commands}:/usr/bin:/bin',
        )
        self._write_fake_ssh()
        self._git(self.repository, 'init', '--initial-branch=main')
        self._git(self.repository, 'config', 'user.name', 'Repository Test')
        self._git(self.repository, 'config', 'user.email', 'repository@example.test')
        (self.repository / 'README.md').write_text('main\n')
        self._git(self.repository, 'add', 'README.md')
        self._git(self.repository, 'commit', '-m', 'main')
        self.main_oid = self._git(self.repository, 'rev-parse', 'HEAD').stdout.strip()
        self._git(self.repository, 'switch', '-c', 'feature/add')
        (self.repository / 'feature.txt').write_text('feature\n')
        self._git(self.repository, 'add', 'feature.txt')
        self._git(self.repository, 'commit', '-m', 'feature')
        self.feature_oid = self._git(self.repository, 'rev-parse', 'HEAD').stdout.strip()

        self.ignored = self.host_parent / 'ignored-service'
        self.ignored.mkdir()
        self._git(self.ignored, 'init', '--initial-branch=other')

    def tearDown(self):
        self.temp.cleanup()

    def _git(self, path, *args):
        return subprocess.run(
            ['git', '-C', str(path), *args],
            check=True,
            text=True,
            capture_output=True,
        )

    def _write_fake_ssh(self):
        ssh = self.commands / 'ssh'
        ssh.write_text(textwrap.dedent('''\
            #!/usr/bin/env bash
            set -Eeuo pipefail
            if [[ ${1:-} == -G ]]; then
                exit 1
            fi
            while [[ ${1:-} == -o ]]; do
                shift 2
            done
            (($# >= 1)) || exit 2
            shift
            (($# >= 1)) || exit 2
            if (($# == 1)); then
                exec bash -c "$1"
            fi
            exec "$@"
        '''))
        ssh.chmod(0o755)

    def test_adds_only_the_selected_repository(self):
        result = subprocess.run(
            [
                'bash', str(SETUP),
                '--repository', str(self.repository),
                '--ssh-host', 'fixture-vm',
                '--guest-root', str(self.guest_root),
            ],
            input='yes\n',
            text=True,
            capture_output=True,
            env=self.env,
        )
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        self.assertIn('Repository setup complete for 1 repositories.', result.stdout)
        self.assertEqual(
            f'fixture-vm:{self.guest_root}/bare/new-service.git',
            self._git(self.repository, 'remote', 'get-url', 'vm').stdout.strip(),
        )
        self.assertEqual(
            self.main_oid,
            self._git(
                self.guest_root / 'bare/new-service.git',
                'rev-parse', 'refs/heads/main',
            ).stdout.strip(),
        )
        worktree = self.guest_root / 'worktrees/new-service'
        self.assertEqual(
            'feature/add',
            self._git(worktree, 'branch', '--show-current').stdout.strip(),
        )
        self.assertEqual(
            self.feature_oid,
            self._git(worktree, 'rev-parse', 'HEAD').stdout.strip(),
        )
        self.assertEqual(
            'origin',
            self._git(worktree, 'remote').stdout.strip(),
        )
        self.assertFalse((self.guest_root / 'bare/ignored-service.git').exists())

    def test_adds_dot_github_as_selected_repository(self):
        dot_github = self.host_parent / '.github'
        self.repository.rename(dot_github)

        result = subprocess.run(
            [
                'bash', str(SETUP),
                '--repository', str(dot_github),
                '--ssh-host', 'fixture-vm',
                '--guest-root', str(self.guest_root),
            ],
            input='yes\n',
            text=True,
            capture_output=True,
            env=self.env,
        )

        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        self.assertEqual(
            f'fixture-vm:{self.guest_root}/bare/.github.git',
            self._git(dot_github, 'remote', 'get-url', 'vm').stdout.strip(),
        )
        self.assertEqual(
            self.feature_oid,
            self._git(
                self.guest_root / 'worktrees/.github', 'rev-parse', 'HEAD',
            ).stdout.strip(),
        )

    def test_discovers_dot_github_under_host_parent(self):
        dot_github = self.host_parent / '.github'
        self.repository.rename(dot_github)
        self.ignored.rename(self.root / 'ignored-service')

        result = subprocess.run(
            [
                'bash', str(SETUP),
                '--host-parent', str(self.host_parent),
                '--ssh-host', 'fixture-vm',
                '--guest-root', str(self.guest_root),
            ],
            input='yes\n',
            text=True,
            capture_output=True,
            env=self.env,
        )

        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        self.assertIn('  .github (main; selected branch: feature/add)', result.stdout)
        self.assertTrue((self.guest_root / 'bare/.github.git').is_dir())
        self.assertTrue((self.guest_root / 'worktrees/.github').is_dir())

    def test_simple_entry_point_requires_one_path(self):
        result = subprocess.run(
            ['bash', str(ADD_ONE)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(1, result.returncode)
        self.assertIn('provide exactly one repository path', result.stderr)


if __name__ == '__main__':
    unittest.main()
