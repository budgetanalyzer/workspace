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
- `claude-with-custom-system-prompt` adds prompt replacement.
- `claude-45-custom-system-prompt` and
  `claude-46-custom-system-prompt` add explicit model selection.
- `codex-with-proxy` and `codex-max-with-proxy` delegate to `codex-lean`.

These launchers require the separate human-created inspection identity
described in [HTTPS Traffic Inspection](traffic-inspection.md). They bind only
to loopback, keep upstream TLS verification enabled and scope proxy/trust
variables to the launched provider process.

Canonical launcher implementations and resources live under `native/helpers/`
and `scripts/native/proxy.py`; command mappings live in
[`native/toolchain.json`](../native/toolchain.json).

### Why the custom system prompt launcher exists

Claude Code's `--system-prompt` flags append to its default main prompt. The
optional native mitmproxy addon replaces that main prompt in flight while
preserving required prefix blocks and passing ancillary requests through.
The prompt and addon are canonical resources in `native/helpers/`.

## Lean Inspection Launchers

For capturing the full Claude system prompt, tool definitions and injected
context with a minimal tool surface, opt in to the aliases (above) and run:

```bash
claude-lean-proxy-medium            # also claude-lean-proxy-low|high|xhigh|max
claude-lean-proxy medium     # the underlying function: EFFORT [claude args...]
```

Trailing arguments forward to Claude. Plain `claude`, plain `claude-with-proxy`
and the existing aliases are unchanged. These launchers need the inspection
identity from [HTTPS Traffic Inspection](traffic-inspection.md); the capture and
analysis workflow lives in
[Analyzing The Full System Prompt](traffic-inspection.md#analyzing-the-full-system-prompt).

| Setting | Purpose |
| --- | --- |
| `--dangerously-skip-permissions` | Always on for lean sessions; same guest-root-equivalent authority as the other high-authority launchers |
| `--effort LEVEL` | Per-launch effort as a flag, because `CLAUDE_CODE_EFFORT_LEVEL` would override `/effort` mid-session |
| `--tools "Bash,Read,Edit,Write,WebFetch,WebSearch"` | Whitelist; omits `Agent`, `Grep`, `Glob`, `Skill` and task tools |
| `--strict-mcp-config` | Ignores all MCP servers |
| `--disable-slash-commands` | Removes skills and their list from context |
| `CLAUDE_CODE_DISABLE_AUTO_MEMORY`, `_BACKGROUND_TASKS`, `_AGENT_VIEW`, `_CRON`, `_BUNDLED_SKILLS`, `_FEEDBACK_SURVEY`, `_NONESSENTIAL_TRAFFIC` = `1` | Remove memory, background features and ancillary requests so flows are easier to read |
| `CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false` | No prompt-suggestion requests |

The variables are scoped to the launched process. `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1`
comes from `claude-with-proxy` itself (`scripts/native/proxy.py`).

Override the tool list with `CLAUDE_LEAN_TOOLS`, for example
`CLAUDE_LEAN_TOOLS="Bash,Read,Edit,Write,WebFetch,WebSearch,Grep" claude-lean-proxy-medium`. Exact
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
