# Research: Barebones Claude Code Launch Options

Status: research, now partly implemented. The lean inspection launcher
(`claude-lean-proxy`, `lean-proxy-*`) and the settings replacement script follow
[the launch plan](../plans/claude-lean-proxy-launch.md); see
[Lean Inspection Launchers](../launch-options.md#lean-inspection-launchers).
`proxy.py` now sets `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1`. The older aliases
still use `true` (follow-up). The open questions on tool names, `AGENTS.md`
retention and `Agent` removal are answered by the
[human live verification checklist](../traffic-inspection.md#human-live-verification-checklist);
no answers are recorded here until that checklist is run.

Sources: `claude --help` on Claude Code 2.1.289, the Claude Code environment
variable and settings reference pages (fetched 2026-10-19 through a summarizing
fetch, so confirm exact values before relying on them), and
`native/helpers/bash_aliases.sh`, `scripts/native/proxy.py` and
`docs/launch-options.md` in this repository.

## Goal

Run Claude Code with the leanest practical feature set: no subagents, no
unused tools, no background services, minimal injected context and minimal
non-essential traffic.

## Audit of the current aliases

`native/helpers/bash_aliases.sh` sets these variables on every Claude alias.

| Variable | Verdict | Notes |
|---|---|---|
| `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1` | Valid, mostly no-op | Only affects Opus 4.6 and Sonnet 4.6. No effect on Fable, Sonnet 5+, Haiku 5.5 or Opus 4.7+, which always use adaptive reasoning. Effective only in the `*46` aliases. |
| `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` | Valid | Removes `[1m]` variants and holds models to a 200K window. |
| `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true` | Valid, value unverified | Documented value is `1`. Whether `true` is accepted was not confirmed. `proxy.py` now uses `1`; the aliases still use `true`. |
| `ENABLE_CLAUDEAI_MCP_SERVERS=false` | Undocumented | Not in the env-var reference. May be inert. Verify with `/mcp` in a session. Prefer `--strict-mcp-config`. |
| `CLAUDE_CODE_EFFORT_LEVEL` | Valid | Accepts `low`, `medium`, `high`, `xhigh`, `max`, `auto`. Overrides `--effort` and `/effort`. |
| `MAX_THINKING_TOKENS` | Mostly stale | Fixed budget, used only on Opus 4.6 and Sonnet 4.6 when adaptive thinking is disabled. The docs state no maximum. |

Other findings:

- The comments in the file describe Opus 4.6 and 4.5, but the unsuffixed
  aliases (`dangerous`, `high`, `max`) run the current default model, for which
  the thinking-budget variables do nothing. Only `CLAUDE_CODE_EFFORT_LEVEL` is
  an effective thinking control there.
- `scripts/native/proxy.py` carries its own copy of these variables and only
  loosely matches the aliases. It sets `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING`
  and `MAX_THINKING_TOKENS=128000` only for the custom-system-prompt launcher.
- The aliases repeat the same env and flags eight times.

## Disabling subagents

No single environment variable disables the Agent tool.

| Mechanism | Effect |
|---|---|
| `--tools "<list>"` | Whitelists built-in tools. Anything not named, including the Agent tool, is removed. Strongest option. |
| `--disallowedTools "Agent"` | Blacklists the Agent tool. Already documented in `docs/launch-options.md` and `AGENTS.md`. |
| `permissions.deny: ["Agent"]` in settings | Same as the flag, applied to every session. Deny rules should still apply under `--dangerously-skip-permissions`, but that was not tested on this build. |
| `CLAUDE_CODE_DISABLE_EXPLORE_PLAN_AGENTS=1` | Removes only the built-in Explore and Plan agents. `general-purpose` remains. |
| `CLAUDE_CODE_DISABLE_AGENT_VIEW=1` | Disables background agents (`claude agents`, `--bg`, `/background`). Does not disable the Agent tool. |
| `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` | Disables `run_in_background` and Ctrl+B. Subagents remain available. |
| `CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS=1` | Non-interactive `-p` mode only. |

## CLI options considered

| Flag | Effect | Caveat |
|---|---|---|
| `--tools "..."` | Restricts the built-in tool set. | Tool names such as `Glob` and `Grep` were not verified on this build. Check the tool list in one session. |
| `--strict-mcp-config` | Ignores all MCP servers except those in `--mcp-config`. | None. |
| `--disable-slash-commands` | Disables all skills. | Removes the skill list from context. |
| `--setting-sources user` | Skips project and local settings. | Drops repository `.claude` settings. |
| `--bare` | No hooks, LSP, plugin sync, attribution, auto-memory, keychain reads or CLAUDE.md discovery. Sets `CLAUDE_CODE_SIMPLE=1`. | OAuth and keychain are never read. Requires `ANTHROPIC_API_KEY` or `apiKeyHelper`. Drops `AGENTS.md` instructions. |
| `--safe-mode` | Disables CLAUDE.md, skills, plugins, hooks, MCP, agents, styles and keybindings. | Drops `AGENTS.md` instructions this repository depends on (loaded natively). |
| `--restricted` | Removes command-running tools and WebFetch, ignores user, project and local settings, confines file tools to the working directories and refuses `bypassPermissions`. | Incompatible with `--dangerously-skip-permissions` and with an agent that must run commands. |
| `--exclude-dynamic-system-prompt-sections` | Moves cwd, env and git status out of the system prompt. | Cache-reuse optimization, not a reduction. |
| `--autocompact <auto\|tokens>` | Sets the auto-compact window. | Not needed for barebones. |

## Environment variables considered

```bash
CLAUDE_CODE_DISABLE_AUTO_MEMORY=1
CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1
CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1
CLAUDE_CODE_DISABLE_AGENT_VIEW=1
CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1
CLAUDE_CODE_DISABLE_CRON=1
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1
CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false
CLAUDE_CODE_DISABLE_FILE_CHECKPOINTING=1   # optional: disables /rewind
CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1       # optional: also skips session title generation
```

Notes:

- `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` covers auto-updates, telemetry,
  error reporting, `/feedback`, PR badges, plugin background commands and
  feature-flag fetching. Per the docs summary, setting it to `0` or `false`
  still disables those. Disabling auto-updates makes updates manual.
- Other variables found but not recommended for the baseline:
  `CLAUDE_CODE_DISABLE_WEB_FETCH`, `CLAUDE_CODE_DISABLE_ATTACHMENTS`,
  `CLAUDE_CODE_DISABLE_FILE_MENTIONS`, `CLAUDE_CODE_DISABLE_ARTIFACT`
  (irreversible once set), `CLAUDE_CODE_DISABLE_THINKING`,
  `CLAUDE_CODE_DISABLE_FAST_MODE`, `CLAUDE_CODE_DISABLE_WORKFLOWS`,
  `CLAUDE_CODE_DISABLE_CFC_PROMPT`, `CLAUDE_CODE_ATTRIBUTION_HEADER=0`,
  `DISABLE_TELEMETRY`, `DISABLE_ERROR_REPORTING`.

## Settings keys considered

Candidate overlay for `native/helpers/settings-overlay.json`:

```json
{
  "autoMemoryEnabled": false,
  "includeGitInstructions": false,
  "promptSuggestionEnabled": false,
  "spinnerTipsEnabled": false,
  "disableBundledSkills": true,
  "disableRemoteControl": true,
  "disableAgentView": true,
  "syncClaudeAiPlugins": false,
  "syncClaudeAiSkills": false,
  "disableDeepLinkRegistration": true
}
```

`disableAllHooks` is deliberately omitted because it also disables custom
status lines. `AGENTS.md` loading is native to Claude Code and no longer uses a
hook; the legacy `SessionStart` hook in a live settings file is removed by the
[settings replacement](../native-user-tools.md#claude-settings-replacement).
Merge any edit against the current content of
`native/helpers/settings-overlay.json`.

## Recommendation

1. Add `--tools` with a short whitelist (for example
   `"Bash,Read,Edit,Write,Glob,Grep"`) to remove subagents and all unused
   tools. Add `WebFetch,WebSearch` only if needed.
2. Add `--strict-mcp-config` and `--disable-slash-commands`.
3. Add the env var block above, using `1` rather than `true`.
4. Move durable settings into `settings-overlay.json` where they fit.
5. Drop `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING` and `MAX_THINKING_TOKENS` from
   aliases that run models they do not affect, and drop
   `ENABLE_CLAUDEAI_MCP_SERVERS`.
6. Skip `--bare` and `--safe-mode` unless losing `AGENTS.md` instructions and,
   for `--bare`, OAuth login is acceptable.
7. Collapse the repeated alias bodies into one shared base:

   ```bash
   _claude_lean() { env <vars> claude --verbose --dangerously-skip-permissions --tools "..." --strict-mcp-config --disable-slash-commands "$@"; }
   alias dangerous='_claude_lean'
   alias high='CLAUDE_CODE_EFFORT_LEVEL=high _claude_lean'
   ```

## Open questions

The tool-name, `AGENTS.md` retention and `Agent` removal questions are answered
by the live checklist once a human runs it; the rest remain open.

- Is `true` accepted for `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS`?
- Does `ENABLE_CLAUDEAI_MCP_SERVERS` have any effect on 2.1.289?
- Do `permissions.deny: ["Agent"]` rules apply under
  `--dangerously-skip-permissions`?
- What are the exact built-in tool names accepted by `--tools` on this build?
- Which of the aliases, `proxy.py`, `native/toolchain.json` and the docs must
  change together, and which tests (`tests/native`) pin the current values?
- Should skills and WebFetch/WebSearch stay available?
