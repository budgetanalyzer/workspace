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
PROXY = REPO / 'scripts/native/proxy.py'
LEAN_TOOLS = 'Bash,Read,Edit,Write,WebFetch,WebSearch'
ENV_EXPECTED = {
    'CLAUDE_CODE_DISABLE_AUTO_MEMORY': '1',
    'CLAUDE_CODE_DISABLE_BACKGROUND_TASKS': '1',
    'CLAUDE_CODE_DISABLE_AGENT_VIEW': '1',
    'CLAUDE_CODE_DISABLE_CRON': '1',
    'CLAUDE_CODE_DISABLE_BUNDLED_SKILLS': '1',
    'CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY': '1',
    'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1',
    'CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION': 'false',
    'CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS': '1',
    'ENABLE_CLAUDEAI_MCP_SERVERS': 'false',
    'CLAUDE_CODE_DISABLE_1M_CONTEXT': '1',
}
FORBIDDEN = ('--bare', '--safe-mode', '--restricted', '--setting-sources',
             '--disable-slash-commands', '--append-system-prompt')

STUB = f'''#!/usr/bin/env bash
{{
  printf 'BIN [%s]\\n' "${{0##*/}}"
  printf 'ARGS'; printf ' [%s]' "$@"; printf '\\n'
  for v in {' '.join(ENV_EXPECTED)}; do printf 'ENV %s=%s\\n' "$v" "${{!v-<unset>}}"; done
}} >> "$STUB_LOG"
'''


def arguments(text):
    lines = [line[5:] for line in text.splitlines() if line.startswith('ARGS')]
    assert len(lines) == 1, text
    return lines[0]


def assert_common(text, expected_bin):
    args = arguments(text)
    assert f'BIN [{expected_bin}]' in text, text
    for want in ('[--dangerously-skip-permissions]', f'[--tools] [{LEAN_TOOLS}]',
                 '[--strict-mcp-config]'):
        assert want in args, f'{want} missing from {args}'
    for flag in FORBIDDEN:
        assert flag not in args, flag
    for name, value in ENV_EXPECTED.items():
        assert f'ENV {name}={value}' in text, name
    return args


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
        env = {'PATH': f'{bin_dir}:{os.environ["PATH"]}', 'HOME': str(scratch),
               'STUB_LOG': str(log)}
        env.update(extra_env or {})
        result = subprocess.run(['bash', '-c', f'shopt -s expand_aliases\n. "{ALIASES}"\n{script}'],
                                env=env, text=True, capture_output=True)
        return result, log.read_text()

    # Vanilla modes apply the shared contract without selecting an effort.
    for command, expected_bin in (('claude-lean direct-tail', 'claude'),
                                  ('claude-lean --proxy proxy-tail', 'claude-with-proxy')):
        result, text = run(command)
        assert result.returncode == 0, result.stderr
        args = assert_common(text, expected_bin)
        assert '[--effort]' not in args, args
        assert args.rstrip().endswith(f'[{command.split()[-1]}]'), args
        if expected_bin == 'claude':
            assert f'[--system-prompt-file] [{PROMPT}]' in args, args
        else:
            assert '--system-prompt' not in args, args

    # The effort aliases select their effort exactly once, and all four aliases forward arguments.
    aliases = {
        'claude-lean-medium': 'claude',
        'claude-lean-high': 'claude',
        'claude-lean-proxy': 'claude-with-proxy',
        'claude-lean-proxy-high': 'claude-with-proxy',
    }
    for alias, expected_bin in aliases.items():
        result, text = run(f'{alias} {alias}-tail')
        assert result.returncode == 0, result.stderr
        args = assert_common(text, expected_bin)
        assert args.rstrip().endswith(f'[{alias}-tail]'), args
        effort = alias.rsplit('-', 1)[-1]
        if effort in ('medium', 'high'):
            assert args.count('[--effort]') == 1 and f'[--effort] [{effort}]' in args, args
        else:
            assert '[--effort]' not in args, args

    # Proxy mode accepts an explicit trailing custom prompt for capture.
    result, text = run('claude-lean --proxy --system-prompt-file custom.md')
    assert result.returncode == 0, result.stderr
    args = assert_common(text, 'claude-with-proxy')
    assert args.rstrip().endswith('[--system-prompt-file] [custom.md]'), args

    # Only a leading --proxy selects proxy mode; later occurrences pass through unchanged.
    for command, forwarded in (
            ('claude-lean before --proxy', '[before] [--proxy]'),
            ('claude-lean one two --proxy after', '[one] [two] [--proxy] [after]')):
        result, text = run(command)
        assert result.returncode == 0, result.stderr
        args = assert_common(text, 'claude')
        assert args.rstrip().endswith(forwarded), args
        assert f'[--system-prompt-file] [{PROMPT}]' in args, args

    # The historical tool override has no effect in either mode.
    for command, expected_bin in (('claude-lean', 'claude'),
                                  ('claude-lean --proxy', 'claude-with-proxy')):
        result, text = run(command, {'CLAUDE_' + 'LEAN_TOOLS': 'Bash,Read'})
        assert result.returncode == 0, result.stderr
        args = assert_common(text, expected_bin)
        assert f'[--tools] [{LEAN_TOOLS}]' in args and '[--tools] [Bash,Read]' not in args, args

    # The prompt is required only for direct launches in an installed layout.
    installed = scratch / 'installed/helpers'
    installed.mkdir(parents=True)
    shutil.copy2(CLAUDE_LEAN, installed / 'claude-lean.sh')
    result, text = run(f'"{installed / "claude-lean.sh"}"')
    assert result.returncode == 1 and text == '' and 'system prompt missing' in result.stderr, result.stderr
    result, text = run(f'"{installed / "claude-lean.sh"}" --proxy installed-tail')
    assert result.returncode == 0, result.stderr
    args = assert_common(text, 'claude-with-proxy')
    assert '--system-prompt' not in args and args.rstrip().endswith('[installed-tail]'), args
    shutil.copy2(PROMPT, installed / 'system-prompt.md')
    result, text = run(f'"{installed / "claude-lean.sh"}" installed-tail')
    assert result.returncode == 0, result.stderr
    args = assert_common(text, 'claude')
    assert f'[--system-prompt-file] [{installed / "system-prompt.md"}]' in args, args

# The aliases file contains only the four Claude lean aliases and unchanged Codex aliases.
aliases_text = ALIASES.read_text()
alias_names = re.findall(r'^alias\s+([\w-]+)=', aliases_text, re.MULTILINE)
assert [name for name in alias_names if name.startswith('claude')] == [
    'claude-lean-medium', 'claude-lean-high', 'claude-lean-proxy', 'claude-lean-proxy-high'
]
assert [name for name in alias_names if name.startswith('codex')] == [
    'codex-dangerous', 'codex-high', 'codex-max', 'codex-proxy',
    'codex-high-proxy', 'codex-max-proxy'
]
for forbidden_text in ('CLAUDE_CODE_', 'ENABLE_CLAUDEAI', 'MAX_THINKING_TOKENS',
                       '--dangerously-skip-permissions'):
    assert forbidden_text not in aliases_text, forbidden_text
assert not re.search(r'^\s*[A-Za-z_][\w-]*\s*\(\)\s*\{', aliases_text, re.MULTILINE)
retired = re.compile(
    r'^alias\s+(?:claude-(?:dangerous|high|max)\w*|'
    r'claude-lean-(?:low|xhigh|max)|claude-lean-proxy-(?:low|medium|xhigh|max))=', re.MULTILINE)
assert not retired.search(aliases_text), retired.pattern

# The proxy adapter contributes no Claude-specific environment.
proxy_text = PROXY.read_text()
assert 'CLAUDE_CODE_' not in proxy_text
assert 'ENABLE_CLAUDEAI' not in proxy_text

# The prompt must not direct the model to tools outside the lean tool list.
prompt = PROMPT.read_text()
for name in ('Glob', 'Grep', 'Agent', 'Skill', 'Task', 'TodoWrite', 'NotebookEdit'):
    assert not re.search(rf'\b{name}\b', prompt), f'system prompt names unavailable tool {name}'
for prohibition in ('cat/head/tail', 'sed/awk'):
    assert prohibition not in prompt, f'system prompt contradicts bypass mode: {prohibition}'

print('lean launcher checks passed')
