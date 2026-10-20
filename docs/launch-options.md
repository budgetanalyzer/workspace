# AI CLI Launch Options

The native installer exposes commands through the normal guest user's
`.local/bin`. Plain `claude`, `codex` and `gemini` retain their upstream
defaults. Optional aliases are installed in
`~/.local/share/budget-analyzer-native/aliases.sh` but are not sourced
automatically; opt in explicitly when needed:

```bash
. "$HOME/.local/share/budget-analyzer-native/aliases.sh"
```

## Explicit High-Authority Launchers

The Claude high-authority aliases are the lean aliases described below. They
delegate to `claude-lean`, which uses `--dangerously-skip-permissions`. The
`codex-dangerous`, `codex-high` and `codex-max` aliases delegate to
`codex-lean`.

`codex-lean` keeps project instruction loading enabled and disables web search,
apps/connectors, MCP apps, subagents, browser/computer/image tools, hooks,
plugins, memories, shell snapshots and history persistence. It also selects
`--dangerously-bypass-approvals-and-sandbox`, `approval_policy="never"` and
`sandbox_mode="danger-full-access"`. It is not an OS sandbox. Docker-group
membership gives native agent processes guest-root-equivalent authority; the
VM and host policy are the external boundary.

`CODEX_REASONING_EFFORT` selects effort and `CODEX_MODEL` supplies a model only
when the command line did not already select one. Plain `codex` is not aliased
and uses upstream behavior plus the user's configuration.

## AI Session Handler Plans

The native user installer exposes the sibling AI Session Handler checkout
through an editable pipx environment. Current reviewed Python source changes
are visible without reinstalling. Dependency or entry-point changes still
require an explicit human reinstall after review.

Run a plan from the repository that owns it. Codex is the default provider;
place `--claude` before `PLAN_NAME` to select Claude:

```bash
ai-run PLAN_NAME
ai-run --claude PLAN_NAME
```

`PLAN_NAME` is a bare filename stem for `./docs/plans/PLAN_NAME.md`; do not pass
a path or `.md` suffix. Later arguments are forwarded unchanged:

```bash
ai-run improve-imports --max-phases 1
ai-run --claude improve-imports --max-phases 1
ai-run improve-imports --quiet
ai-run improve-imports --retry-stopped
```

The `ai-run-claude` opt-in alias is equivalent to `ai-run --claude`. The
launcher selects either the globally installed high-reasoning Codex wrapper or
the high-effort Claude wrapper and streams progress by default. Handler Claude
runs fix effort at `high` because a non-interactive run cannot use `/effort`.
Set `CODEX_MODEL` or `ANTHROPIC_MODEL` to select the corresponding model. The
human-applied `native/helpers/claude-settings.json` replacement defaults Claude
Code to the `opus` alias. `--quiet` suppresses live output while retaining the
transcript. Use `ai-run --help` for the command summary.

## Optional Proxy Launchers

- `claude-with-proxy` runs upstream Claude through the proxy without adding
  Claude environment settings or replacing its prompt.
- `codex-with-proxy` and `codex-max-with-proxy` delegate to `codex-lean`.

These launchers require the separate human-created inspection identity
described in [HTTPS Traffic Inspection](traffic-inspection.md). They bind only
to loopback, keep upstream TLS verification enabled and scope proxy/trust
variables to the launched provider process.

Canonical launcher implementations and resources live under `native/helpers/`
and `scripts/native/proxy.py`; command mappings live in
[`native/toolchain.json`](../native/toolchain.json).

## Lean Claude Launchers

One launcher owns the lean option set and always bypasses permissions:

```bash
claude-lean [--proxy] [claude args...]
```

Without `--proxy`, it launches Claude with the workspace system prompt. With
`--proxy` as the first argument, it launches `claude-with-proxy` and keeps the
default prompt for capture. All remaining arguments forward to Claude. The
installed command uses Claude Code's default effort unless the caller supplies
an ordinary `--effort LEVEL` flag. Effort is a launch-time starting value;
`/effort` can change it during an interactive session.

The opt-in aliases are exactly:

```bash
alias claude-lean-high='claude-lean --effort high'
alias claude-lean-proxy='claude-lean --proxy'
alias claude-lean-proxy-high='claude-lean --proxy --effort high'
```

Plain `claude` and plain `claude-with-proxy` retain upstream behavior. The
human-applied `native/helpers/claude-settings.json` replacement sets Claude
Code's default model to `opus`.

`claude-lean` (`native/helpers/claude-lean.sh`) passes
`--system-prompt-file` with the installed copy of
[`native/helpers/system-prompt.md`](../native/helpers/system-prompt.md).
That flag replaces Claude Code's default main prompt; only
`--append-system-prompt[-file]` appends. Keep the prompt's tool guidance
consistent with the lean tool list.

`claude-lean --proxy` keeps the default prompt so the full system prompt, tool
definitions and injected context can be captured. A trailing
`--system-prompt-file PATH` still forwards when a custom-prompt capture is
wanted. Proxy mode needs the inspection identity from
[HTTPS Traffic Inspection](traffic-inspection.md); the capture and analysis
workflow lives in
[Analyzing The Full System Prompt](traffic-inspection.md#analyzing-the-full-system-prompt).

| Setting | Purpose |
| --- | --- |
| `--dangerously-skip-permissions` | Always on for lean sessions; same guest-root-equivalent authority as the other high-authority launchers |
| `-high` aliases | Add `--effort high` as the starting effort; vanilla launchers leave effort at Claude Code's default, and `/effort` remains available interactively |
| `--tools "Bash,Read,Edit,Write,WebFetch,WebSearch"` | Whitelist; omits `Agent`, `Grep`, `Glob`, `Skill` and task tools |
| `--strict-mcp-config` | Ignores all MCP servers |
| (no `--disable-slash-commands`) | Deliberately not used: it empties the whole command list, including built-ins such as `/model` and `/effort`. The skill list is already absent because `Skill` is not in `--tools`, and `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1` drops bundled skills |
| `CLAUDE_CODE_DISABLE_AUTO_MEMORY`, `_BACKGROUND_TASKS`, `_AGENT_VIEW`, `_CRON`, `_BUNDLED_SKILLS`, `_FEEDBACK_SURVEY`, `_NONESSENTIAL_TRAFFIC` = `1` | Set only by `claude-lean`; remove memory, background features and ancillary requests so flows are easier to read |
| `CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false` | Set only by `claude-lean`; no prompt-suggestion requests |
| `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1`, `ENABLE_CLAUDEAI_MCP_SERVERS=false`, `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` | Set only by `claude-lean`; suppress Git instructions, Claude.ai MCP servers and 1M context |
| `--system-prompt-file` | Added by `claude-lean` only in non-proxy mode; replaces the default main prompt with the workspace prompt |

The variables are scoped to the launched process.

To change the fixed tool list, edit `native/helpers/claude-lean.sh` and keep the
prompt's tool guidance consistent. Confirm exact accepted tool names with the
live checklist in
[traffic-inspection.md](traffic-inspection.md#human-live-verification-checklist).

`--bare`, `--safe-mode` and `--restricted` are deliberately not used: Claude
Code loads `AGENTS.md` through normal project-instruction discovery, and those
flags disable it and/or change authentication. The old `SessionStart` hook that
also injected `AGENTS.md` is removed by the
[settings replacement](native-user-tools.md#claude-settings-replacement), so one
copy appears.

## Disabling Claude Subagents

For focused work in a small repository:

```bash
claude --disallowedTools "Agent"
```

Direct search and reads are usually clearer than autonomous exploration in
small repositories. Choose permissions separately; disabling one tool does not
require bypassing all permission checks.

## Authentication

- Claude: `claude auth login`
- Codex: `codex login`
- Gemini: run `gemini` interactively

Authenticate only the selected provider in the guest. Do not authenticate
GitHub or forward host agents or credentials.
