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

The `claude-dangerous`, `claude-high`, `claude-max` and version-selected
(`claude-*45`, `claude-*46`) Claude aliases use
`--dangerously-skip-permissions`. The `codex-dangerous`, `codex-high` and
`codex-max` aliases delegate to `codex-lean`.

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

Run a plan from the repository that owns it:

```bash
ai-run PLAN_NAME
```

`PLAN_NAME` is a bare filename stem for `./docs/plans/PLAN_NAME.md`; do not pass
a path or `.md` suffix. Later arguments are forwarded unchanged:

```bash
ai-run improve-imports --max-phases 1
ai-run improve-imports --quiet
ai-run improve-imports --retry-stopped
```

The launcher selects the globally installed high-reasoning Codex wrapper and
streams progress by default. `--quiet` suppresses live output while retaining
the transcript. Use `ai-run --help` for the command summary.

## Optional Proxy Launchers

- `claude-with-proxy` provides inspection without prompt replacement.
- `codex-with-proxy` and `codex-max-with-proxy` delegate to `codex-lean`.

These launchers require the separate human-created inspection identity
described in [HTTPS Traffic Inspection](traffic-inspection.md). They bind only
to loopback, keep upstream TLS verification enabled and scope proxy/trust
variables to the launched provider process.

Canonical launcher implementations and resources live under `native/helpers/`
and `scripts/native/proxy.py`; command mappings live in
[`native/toolchain.json`](../native/toolchain.json).

## Lean Claude Launchers

Both lean launchers run Claude with a minimal tool surface at a chosen effort
level and always bypass permissions:

```bash
claude-lean medium                  # workspace system prompt, no proxy
claude-lean-proxy medium            # default system prompt, captured in mitmweb
```

Both take `EFFORT [claude args...]`; trailing arguments forward to Claude.
`claude-lean` is an installed command. `claude-lean-proxy` and the
`claude-lean-LEVEL` and `claude-lean-proxy-LEVEL` shortcuts (`low`, `medium`,
`high`, `xhigh`, `max`) come from the opt-in aliases (above). Plain `claude`,
plain `claude-with-proxy` and the other aliases are unchanged.

`claude-lean` (`native/helpers/claude-lean.sh`) passes
`--system-prompt-file` with the installed copy of
[`native/helpers/system-prompt.md`](../native/helpers/system-prompt.md).
That flag replaces Claude Code's default main prompt; only
`--append-system-prompt[-file]` appends. Keep the prompt's tool guidance
consistent with the lean tool list.

`claude-lean-proxy` keeps the default prompt so the full system prompt, tool
definitions and injected context can be captured. It needs the inspection
identity from [HTTPS Traffic Inspection](traffic-inspection.md); the capture and
analysis workflow lives in
[Analyzing The Full System Prompt](traffic-inspection.md#analyzing-the-full-system-prompt).

| Setting | Purpose |
| --- | --- |
| `--dangerously-skip-permissions` | Always on for lean sessions; same guest-root-equivalent authority as the other high-authority launchers |
| `--effort LEVEL` | Per-launch effort as a flag, because `CLAUDE_CODE_EFFORT_LEVEL` would override `/effort` mid-session |
| `--tools "Bash,Read,Edit,Write,WebFetch,WebSearch"` | Whitelist; omits `Agent`, `Grep`, `Glob`, `Skill` and task tools |
| `--strict-mcp-config` | Ignores all MCP servers |
| (no `--disable-slash-commands`) | Deliberately not used: it empties the whole command list, including built-ins such as `/model` and `/effort`. The skill list is already absent because `Skill` is not in `--tools`, and `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1` drops bundled skills |
| `CLAUDE_CODE_DISABLE_AUTO_MEMORY`, `_BACKGROUND_TASKS`, `_AGENT_VIEW`, `_CRON`, `_BUNDLED_SKILLS`, `_FEEDBACK_SURVEY`, `_NONESSENTIAL_TRAFFIC` = `1` | Remove memory, background features and ancillary requests so flows are easier to read |
| `CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false` | No prompt-suggestion requests |
| `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1`, `ENABLE_CLAUDEAI_MCP_SERVERS=false`, `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` | Set by `claude-lean` directly and by `claude-with-proxy` itself (`scripts/native/proxy.py`) for `claude-lean-proxy` |
| `--system-prompt-file` | `claude-lean` only; replaces the default main prompt with the workspace prompt |

The variables are scoped to the launched process.

Override the tool list with `CLAUDE_LEAN_TOOLS`, for example
`CLAUDE_LEAN_TOOLS="Bash,Read,Edit,Write,WebFetch,WebSearch,Grep" claude-lean-medium`. Exact
accepted tool names are confirmed in the live checklist in
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
