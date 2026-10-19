#!/usr/bin/env python3
"""Offline proof of the arguments and environment the lean Claude launchers hand to Claude."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[2]
ALIASES = REPO / 'native/helpers/bash_aliases.sh'
CLAUDE_LEAN = REPO / 'native/helpers/claude-lean.sh'
PROMPT = REPO / 'native/helpers/system-prompt.md'
LEAN_TOOLS = ('Bash', 'Read', 'Edit', 'Write', 'WebFetch', 'WebSearch')
ENV_ONE = ('CLAUDE_CODE_DISABLE_AUTO_MEMORY', 'CLAUDE_CODE_DISABLE_BACKGROUND_TASKS',
           'CLAUDE_CODE_DISABLE_AGENT_VIEW', 'CLAUDE_CODE_DISABLE_CRON',
           'CLAUDE_CODE_DISABLE_BUNDLED_SKILLS', 'CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY',
           'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC')
ENV_ALL = ENV_ONE + ('CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION',)
# claude-with-proxy sets these itself; claude-lean sets them directly.
ENV_PROXY = {'CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS': '1', 'ENABLE_CLAUDEAI_MCP_SERVERS': 'false',
             'CLAUDE_CODE_DISABLE_1M_CONTEXT': '1'}
FORBIDDEN = ('--bare', '--safe-mode', '--restricted', '--setting-sources',
             '--disable-slash-commands', '--append-system-prompt')

STUB = f'''#!/usr/bin/env bash
{{
  printf 'ARGS'; printf ' [%s]' "$@"; printf '\\n'
  for v in {' '.join(ENV_ALL + tuple(ENV_PROXY))}; do printf 'ENV %s=%s\\n' "$v" "${{!v-<unset>}}"; done
}} >> "$STUB_LOG"
'''

(REPO / 'tmp').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=REPO / 'tmp') as scratch_name:
    scratch = Path(scratch_name)
    bin_dir = scratch / 'bin'
    bin_dir.mkdir()
    for name in ('claude-with-proxy', 'claude'):
        stub = bin_dir / name
        stub.write_text(STUB)
        stub.chmod(0o755)
    (bin_dir / 'claude-lean').symlink_to(CLAUDE_LEAN)
    log = scratch / 'log'

    def run(script, extra_env=None):
        log.write_text('')
        env = {'PATH': f'{bin_dir}:{os.environ["PATH"]}', 'HOME': str(scratch), 'STUB_LOG': str(log)}
        env.update(extra_env or {})
        result = subprocess.run(['bash', '-c', f'shopt -s expand_aliases\n. "{ALIASES}"\n{script}'],
                                env=env, text=True, capture_output=True)
        return result, log.read_text()

    def args_of(text):
        return [line[5:] for line in text.splitlines() if line.startswith('ARGS')]

    def assert_lean(args, text, effort):
        for want in ('[--dangerously-skip-permissions]', f'[--effort] [{effort}]',
                     f'[--tools] [{",".join(LEAN_TOOLS)}]', '[--strict-mcp-config]'):
            assert want in args, f'{want} missing from {args}'
        for flag in FORBIDDEN:
            assert flag not in args, flag
        for name in ENV_ONE:
            assert f'ENV {name}=1' in text, name
        assert 'ENV CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false' in text

    # claude-lean-proxy: function with a forwarded argument
    result, text = run('claude-lean-proxy medium extra-arg\n'
                       'for v in ' + ' '.join(ENV_ALL) + '; do echo "${!v-<unset>}"; done')
    assert result.returncode == 0, result.stderr
    (args,) = args_of(text)
    assert_lean(args, text, 'medium')
    assert args.rstrip().endswith('[extra-arg]')
    assert '--system-prompt' not in args
    for name in ENV_PROXY:
        assert f'ENV {name}=<unset>' in text, name
    # nothing leaks into the parent shell
    assert result.stdout.split() == ['<unset>'] * len(ENV_ALL), result.stdout

    # claude-lean: the same lean settings plus the workspace system prompt
    result, text = run('claude-lean medium extra-arg')
    assert result.returncode == 0, result.stderr
    (args,) = args_of(text)
    assert_lean(args, text, 'medium')
    assert f'[--system-prompt-file] [{PROMPT}]' in args, args
    assert args.rstrip().endswith('[extra-arg]')
    for name, value in ENV_PROXY.items():
        assert f'ENV {name}={value}' in text, name

    # installed layout: the prompt resolves next to the helper copy
    installed = scratch / 'installed/helpers'
    installed.mkdir(parents=True)
    shutil.copy2(CLAUDE_LEAN, installed / 'claude-lean.sh')
    result, text = run(f'"{installed / "claude-lean.sh"}" high')
    assert result.returncode == 1 and text == '' and 'system prompt missing' in result.stderr, result.stderr
    shutil.copy2(PROMPT, installed / 'system-prompt.md')
    result, text = run(f'"{installed / "claude-lean.sh"}" high')
    assert result.returncode == 0, result.stderr
    assert f'[--system-prompt-file] [{installed / "system-prompt.md"}]' in args_of(text)[0]

    # alias forms forward trailing arguments
    for launcher in ('claude-lean-proxy', 'claude-lean'):
        result, text = run(f'{launcher}-medium extra-arg')
        assert result.returncode == 0, result.stderr
        (args,) = args_of(text)
        assert '[--effort] [medium]' in args and args.rstrip().endswith('[extra-arg]'), launcher
        for level in ('low', 'high', 'xhigh', 'max'):
            result, text = run(f'{launcher}-{level}')
            assert result.returncode == 0 and f'[--effort] [{level}]' in args_of(text)[0], (launcher, level)

        # tool override
        result, text = run(f'{launcher} high', {'CLAUDE_LEAN_TOOLS': 'Bash,Read'})
        assert '[--tools] [Bash,Read] ' in args_of(text)[0] + ' ', launcher

        # invalid or missing effort never reaches the stub
        for script in (launcher, f'{launcher} bogus', f'{launcher} --effort high'):
            result, text = run(script)
            assert result.returncode == 2 and text == '' and result.stderr.strip(), script

# The prompt must not direct the model to tools outside the lean tool list.
prompt = PROMPT.read_text()
for name in ('Glob', 'Grep', 'Agent', 'Skill', 'Task', 'TodoWrite', 'NotebookEdit'):
    assert not re.search(rf'\b{name}\b', prompt), f'system prompt names unavailable tool {name}'

proxy = (REPO / 'scripts/native/proxy.py').read_text()
assert "CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS='1'" in proxy
assert "CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS='true'" not in proxy
print('lean launcher checks passed')
