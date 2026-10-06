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

The `dangerous`, `high`, `max` and version-selected Claude aliases use
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
are visible without an image rebuild or reinstall. Dependency or entry-point
changes still require an explicit human reinstall after review.

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
GitHub, forward host agents or import retired runtime credentials.
