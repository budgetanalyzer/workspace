"""Offline checks for the native ai-run provider selection wrapper."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[2]
AI_RUN = REPO / 'native/helpers/ai-run.sh'
ALIASES = REPO / 'native/helpers/bash_aliases.sh'
SCRATCH = REPO / 'tmp/ai-run-tests'
SCRATCH.mkdir(parents=True, exist_ok=True)


class AiRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        (self.root / 'docs/plans').mkdir(parents=True)
        (self.root / 'docs/plans/example.md').write_text('# Fixture plan\n')
        (self.bin / 'ai-run').symlink_to(AI_RUN)
        handler = self.bin / 'ai-session-handler'
        handler.write_text(
            '#!/usr/bin/env bash\n'
            'printf "[%s]" "$@"\n'
            'printf "\\n"\n'
        )
        handler.chmod(0o755)
        self.env = {
            'HOME': str(self.root),
            'PATH': f'{self.bin}:{os.environ["PATH"]}',
        }

    def tearDown(self):
        self.temp.cleanup()

    def run_ai(self, *args):
        return subprocess.run(
            [self.bin / 'ai-run', *args], cwd=self.root, env=self.env,
            text=True, capture_output=True, check=False,
        )

    def expected(self, agent, *options):
        plan = self.root / 'docs/plans/example.md'
        return f'[run][--plan][{plan}][--agent-cmd][{agent}]' + ''.join(
            f'[{option}]' for option in options
        ) + '\n'

    def test_default_selects_codex_and_forwards_options(self):
        result = self.run_ai('example', '--max-phases', '1')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            self.expected('ai-session-handler-codex-high', '--max-phases', '1'),
            result.stdout,
        )

    def test_leading_claude_selects_claude(self):
        result = self.run_ai('--claude', 'example', '--quiet')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            self.expected('ai-session-handler-claude-high', '--quiet'),
            result.stdout,
        )

    def test_claude_after_plan_is_forwarded_without_changing_provider(self):
        result = self.run_ai('example', '--claude')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            self.expected('ai-session-handler-codex-high', '--claude'),
            result.stdout,
        )

    def test_ai_run_claude_alias_selects_claude(self):
        command = (
            'shopt -s expand_aliases\n'
            f'. "{ALIASES}"\n'
            'ai-run-claude example --retry-stopped\n'
        )
        result = subprocess.run(
            ['bash', '-c', command], cwd=self.root, env=self.env,
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            self.expected('ai-session-handler-claude-high', '--retry-stopped'),
            result.stdout,
        )

    def test_help_describes_provider_selection(self):
        result = self.run_ai('--help')
        self.assertEqual(0, result.returncode, result.stderr)
        for expected in ('ai-run [--claude] PLAN_NAME', 'CODEX_MODEL',
                         'ANTHROPIC_MODEL'):
            self.assertIn(expected, result.stdout)

    def test_invalid_plan_names_remain_rejected(self):
        cases = (
            ((), 'missing PLAN_NAME'),
            (('--claude',), 'missing PLAN_NAME'),
            (('nested/example',), 'must not contain path separators'),
            ((r'nested\\example',), 'must not contain path separators'),
            (('example.md',), 'must omit the .md suffix'),
            (('.',), 'must be a bare filename stem'),
            (('..',), 'must be a bare filename stem'),
            (('--unknown',), 'must be a bare filename stem'),
            (('missing',), 'plan file not found'),
        )
        for arguments, message in cases:
            with self.subTest(arguments=arguments):
                result = self.run_ai(*arguments)
                self.assertEqual(2, result.returncode)
                self.assertIn(message, result.stderr)


if __name__ == '__main__':
    unittest.main()
