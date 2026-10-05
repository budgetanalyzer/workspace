"""Focused shell-runner checks using only disposable command stubs."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[2]


class PreparationRunnerTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / 'tmp/native-installer-safety'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(
            prefix='runner path with spaces ', dir=scratch)
        self.root = Path(self.temp.name)
        self.worktrees = self.root / 'work trees'
        self.workspace = self.worktrees / 'workspace'
        self.scripts = self.workspace / 'scripts'
        self.scripts.mkdir(parents=True)
        self.bares = self.root / 'bare repos'
        self.bares.mkdir()
        self.home = self.root / 'disposable home'
        self.home.mkdir()
        self.commands = self.root / 'command shim'
        self.commands.mkdir()
        self.calls = self.root / 'calls.log'
        shutil.copyfile(
            REPO / 'scripts/prepare-agent-vm-native.sh',
            self.scripts / 'prepare-agent-vm-native.sh',
        )
        self.env = dict(
            os.environ,
            HOME=str(self.home),
            PATH=f'{self.commands}:/usr/bin:/bin',
            FIXTURE_CALLS=str(self.calls),
        )
        self.stub(self.commands / 'sudo',
                  'printf "sudo %s\\n" "$*" >> "$FIXTURE_CALLS"\n')
        self.stub(self.scripts / 'provision-agent-vm-guest.sh',
                  'printf "system %s\\n" "$*" >> "$FIXTURE_CALLS"\n')
        self.stub(self.scripts / 'install-agent-vm-bwrap-profile.sh',
                  'printf "profile %s\\n" "$*" >> "$FIXTURE_CALLS"\n')
        self.stub(self.scripts / 'install-agent-vm-user-tools.sh', '''
printf 'user %s\n' "$*" >> "$FIXTURE_CALLS"
mkdir -p "$HOME/.config/budget-analyzer-native"
printf 'export FIXTURE_FRAGMENT_LOADED=1\n' > "$HOME/.config/budget-analyzer-native/env.sh"
if [[ ${FIXTURE_FRAGMENT_LOADED:-0} == 1 ]]; then
    printf 'fragment loaded\n' >> "$FIXTURE_CALLS"
fi
''')

    def tearDown(self):
        self.temp.cleanup()

    def stub(self, path, body):
        path.write_text('#!/usr/bin/env bash\nset -euo pipefail\n' + body)
        path.chmod(0o755)

    def run_script(self, *args):
        return subprocess.run(
            ['bash', str(self.scripts / 'prepare-agent-vm-native.sh'), *args],
            text=True,
            capture_output=True,
            env=self.env,
        )

    def test_forwards_spaced_paths_repeats_user_install_and_keeps_private_log(self):
        result = self.run_script('--bare-parent', str(self.bares))
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        lines = self.calls.read_text().splitlines()
        self.assertEqual(
            ['sudo', 'system', 'profile', 'user', 'user', 'fragment'],
            [line.split()[0] for line in lines],
        )
        self.assertIn(str(self.worktrees), lines[3])
        self.assertIn(str(self.bares), lines[3])
        logs = list((self.workspace / 'tmp/native-preparation').glob(
            'prepare-*.log'))
        self.assertEqual(1, len(logs))
        self.assertEqual(0o600, logs[0].stat().st_mode & 0o777)

    def test_failure_short_circuits_later_installers(self):
        self.stub(self.scripts / 'install-agent-vm-bwrap-profile.sh',
                  'printf "profile failed\\n" >> "$FIXTURE_CALLS"\nexit 7\n')
        result = self.run_script('--bare-parent', str(self.bares))
        self.assertEqual(7, result.returncode)
        self.assertFalse(any(
            line.startswith('user ') for line in self.calls.read_text().splitlines()))
        self.assertIn('Preparation stopped (exit 7)', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
