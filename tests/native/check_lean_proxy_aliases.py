#!/usr/bin/env python3
"""Offline proof of the arguments and environment claude-lean-proxy hands to claude-with-proxy."""
from pathlib import Path
import os
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[2]
ALIASES = REPO / 'native/helpers/bash_aliases.sh'
ENV_ONE = ('CLAUDE_CODE_DISABLE_AUTO_MEMORY', 'CLAUDE_CODE_DISABLE_BACKGROUND_TASKS',
           'CLAUDE_CODE_DISABLE_AGENT_VIEW', 'CLAUDE_CODE_DISABLE_CRON',
           'CLAUDE_CODE_DISABLE_BUNDLED_SKILLS', 'CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY',
           'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC')
ENV_ALL = ENV_ONE + ('CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION',)
FORBIDDEN = ('--bare', '--safe-mode', '--restricted', '--setting-sources')

STUB = f'''#!/usr/bin/env bash
{{
  printf 'ARGS'; printf ' [%s]' "$@"; printf '\\n'
  for v in {' '.join(ENV_ALL)}; do printf 'ENV %s=%s\\n' "$v" "${{!v-<unset>}}"; done
}} >> "$STUB_LOG"
'''

(REPO / 'tmp').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=REPO / 'tmp') as scratch_name:
    scratch = Path(scratch_name)
    bin_dir = scratch / 'bin'
    bin_dir.mkdir()
    stub = bin_dir / 'claude-with-proxy'
    stub.write_text(STUB)
    stub.chmod(0o755)
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

    # function with a forwarded argument
    result, text = run('claude-lean-proxy medium extra-arg\n'
                       'for v in ' + ' '.join(ENV_ALL) + '; do echo "${!v-<unset>}"; done')
    assert result.returncode == 0, result.stderr
    (args,) = args_of(text)
    for want in ('[--dangerously-skip-permissions]', '[--effort] [medium]',
                 '[--tools] [Bash,Read,Edit,Write,WebFetch,WebSearch]', '[--strict-mcp-config]',
                 '[--disable-slash-commands]', '[extra-arg]'):
        assert want in args, f'{want} missing from {args}'
    assert args.rstrip().endswith('[extra-arg]')
    for flag in FORBIDDEN:
        assert flag not in args, flag
    tools = args.split('[--tools] [')[1].split(']')[0].split(',')
    assert not {'Agent', 'Grep', 'Glob'} & set(tools)
    for name in ENV_ONE:
        assert f'ENV {name}=1' in text, name
    assert 'ENV CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false' in text
    assert 'CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS' not in text
    # nothing leaks into the parent shell
    assert result.stdout.split() == ['<unset>'] * len(ENV_ALL), result.stdout

    # alias form forwards trailing arguments
    result, text = run('claude-lean-proxy-medium extra-arg')
    assert result.returncode == 0, result.stderr
    (args,) = args_of(text)
    assert '[--effort] [medium]' in args and args.rstrip().endswith('[extra-arg]')
    for level in ('low', 'high', 'xhigh', 'max'):
        result, text = run(f'claude-lean-proxy-{level}')
        assert result.returncode == 0 and f'[--effort] [{level}]' in args_of(text)[0], level

    # tool override
    result, text = run('claude-lean-proxy high', {'CLAUDE_LEAN_TOOLS': 'Bash,Read'})
    assert '[--tools] [Bash,Read] ' in args_of(text)[0] + ' '

    # invalid or missing effort never reaches the stub
    for script in ('claude-lean-proxy', 'claude-lean-proxy bogus', 'claude-lean-proxy --effort high'):
        result, text = run(script)
        assert result.returncode == 2 and text == '' and result.stderr.strip(), script

proxy = (REPO / 'scripts/native/proxy.py').read_text()
assert "CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS='1'" in proxy
assert "CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS='true'" not in proxy
print('lean proxy alias checks passed')
