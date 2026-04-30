# Budget Analyzer Workspace

> "Archetype: gateway. Role: Development environment entry point; owns sandbox configuration."
>
> — [AGENTS.md](AGENTS.md#tree-position)

## Why This Exists

This workspace runs AI coding agents (Claude Code, Codex, Gemini CLI) in a **sandboxed Docker container** with intentional security constraints:

1. **No access to your filesystem** — only the mounted `/workspace` directory is visible
2. **No SSH credentials** — `SSH_AUTH_SOCK` is explicitly cleared ([devcontainer.json:18](/.devcontainer/devcontainer.json#L18))
3. **No git push capability** — without SSH credentials, the agent cannot push to GitHub
4. **Read-only sandbox config** — `ai-agent-sandbox/` is mounted `:ro` ([docker-compose.yml:17](/ai-agent-sandbox/docker-compose.yml#L17)), so the agent cannot modify its own Dockerfile, entrypoint, or settings to subvert these rules

**Worst case scenario:** If an agent does something unexpected, run `git reset --hard origin/main` and everything disappears — uncommitted changes *and* any local commits the agent made. All changes are local to the workspace directory and trivially reversible.

This is the point. The agent can explore, refactor, break things, and experiment freely — but it can never escape the sandbox, push broken code, or cause damage outside this directory.

## Quick Start

### Prerequisites

1. Install [VS Code](https://code.visualstudio.com/)
2. Install the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension

### Setup

```bash
git clone git@github.com:budgetanalyzer/workspace.git
cd workspace
code .
```

With the Dev Containers extension installed, VS Code will prompt "Reopen in Container" — click it. The container builds on first run (defined in [`ai-agent-sandbox/Dockerfile`](/ai-agent-sandbox/Dockerfile)).

**After the container starts:**
- All repos are available at `/workspace/{repo-name}/`
- Claude Code, Gemini CLI, and Codex CLI are pre-installed
- Follow [Getting Started](https://github.com/budgetanalyzer/orchestration/blob/main/docs/development/getting-started.md) to run the system

## Security Model

| Constraint | Mechanism | Config Reference |
|------------|-----------|------------------|
| Filesystem isolation | Docker container with explicit volume mounts | [docker-compose.yml:13-17](/ai-agent-sandbox/docker-compose.yml#L13-L17) |
| No SSH agent forwarding | `SSH_AUTH_SOCK: ""` in remoteEnv | [devcontainer.json:18](/.devcontainer/devcontainer.json#L18) |
| Read-only sandbox | `.:/workspace/workspace/ai-agent-sandbox:ro` mount | [docker-compose.yml:17](/ai-agent-sandbox/docker-compose.yml#L17) |
| No git credential helper | Agent's git push fails with "Permission denied (publickey)" | (verified at runtime) |

The read-only sandbox mount is critical: even if an agent running with `--dangerously-skip-permissions` tries to modify `docker-compose.yml` or `Dockerfile` to grant itself SSH access, the write will fail. The agent cannot escalate its own privileges.

## What's Inside

### AI Coding CLIs

Claude Code, Gemini CLI, and Codex CLI are pre-installed in the image build defined by `ai-agent-sandbox/Dockerfile`.

Add extra system packages there as well rather than in `.devcontainer/devcontainer.json`. For example, `pdftotext` comes from the `poppler-utils` package.

Playwright is also pre-installed, along with the Chromium browser binary and its system dependencies. The browser cache lives at `/opt/playwright-browsers`. A built container can verify that Chromium is present with `playwright install --list`.

**Auth:**
- **Claude** — already authenticated via `~/.anthropic` volume mount
- **Codex** — `export OPENAI_API_KEY` or run `codex` to sign in
- **Gemini** — `export GEMINI_API_KEY` or run `gemini` to sign in

### Claude Code Launch Options

**Standard usage** — just run `claude` or use the convenience aliases:

| Command | What it does |
|---------|-------------|
| `claude` | Standard launch with Anthropic's default system prompt |
| `dangerous` | Alias: `--dangerously-skip-permissions` |
| `high` | Alias: above + `CLAUDE_CODE_EFFORT_LEVEL=high` |
| `max` | Alias: above + `CLAUDE_CODE_EFFORT_LEVEL=max` |

All aliases also set `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true` and `ENABLE_CLAUDEAI_MCP_SERVERS=false`.

**With traffic inspection:**

| Command | What it does |
|---------|-------------|
| `claude-with-proxy` | Launch Claude Code with mitmproxy intercepting all API traffic. Inspection only — no prompt modification. |
| `claude-with-custom-system-prompt` | Same as above, plus replaces Anthropic's ~24k-token default system prompt with a lean ~500-token version via a mitmproxy addon. |

Request dumps (modified request bodies) are written to `/tmp/claude-proxy-dumps/` with CWD and timestamp in filenames for debugging.

Using `claude-with-custom-system-prompt` is **not required** for normal development. It exists because Anthropic's default system prompt includes verbose per-tool elaboration and generic advice that duplicates what belongs in AGENTS.md, consuming context window on every request. Claude Code's `--system-prompt` and `--system-prompt-file` flags *append* to the default prompt rather than replacing it, so a mitmproxy addon is used to swap the prompt in-flight as a workaround. See [AGENTS.md](AGENTS.md#custom-system-prompt-optional) for details.

**Disabling specific tools:**

```bash
claude --disallowedTools "Agent" --dangerously-skip-permissions
```

The `--disallowedTools` flag disables tools at launch. Disabling the Agent (subagent) tool is useful in small microservice repos where direct Grep/Glob/Read is faster and more predictable than autonomous subagent exploration. The Agent tool is designed for large monorepos — in small focused codebases it adds unnecessary overhead.

### HTTPS Traffic Inspection

mitmproxy is pre-installed with its CA cert trusted system-wide and by Node.js (`NODE_EXTRA_CA_CERTS`). Scripts available in PATH:

- `start-proxy` — start mitmweb (proxy :9080, UI :9081)
- `mitmflows` — list captured flows as a table
- `mitmflow-detail <id>` — full request/response with SSE reconstruction
- `mitmflow-body <id> [request|response|messages]` — render request or response bodies, or WebSocket messages

Note: Claude Code is installed via npm (not the native binary) because the native Bun binary ignores `HTTP_PROXY` for streaming — see [anthropics/claude-code#14165](https://github.com/anthropics/claude-code/issues/14165).

### Staged Mitmproxy Improvements

Because `ai-agent-sandbox/` is mounted read-only inside the devcontainer, mitmproxy helper changes are staged under [`tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/`](/workspace/workspace/tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/) until a human copies them into `ai-agent-sandbox/` from a writable context and rebuilds the container.

That staged replacement set adds:

- `scripts/mitmflow-render.py` — shared Python renderer used by thin `mitmflows`, `mitmflow-body`, and `mitmflow-detail` wrappers
- `mitmflows --provider anthropic|openai|all --host <substring> --path <substring> --json`
- `mitmflow-body <id> [request|response|messages]` modes: default formatted output, `--raw`, `--events`, `--json`, `--dedupe` for OpenAI WebSocket messages, and `--save`
- `mitmflow-detail <id>` summary-first output plus `--full`, `--raw`, `--md [file]`, and `--no-redact`
- default export/report output under [`tmp/mitmproxy-flows/`](/workspace/workspace/tmp/mitmproxy-flows/)
- inspection-only Codex proxy launchers: `codex-with-proxy`, `codex-high-with-proxy`, and `codex-max-with-proxy`
- GPT-5.4-pinned Codex proxy launchers: `codex-54-with-proxy` (`gpt-5.4`) and `codex-54-mini-with-proxy` (`gpt-5.4-mini`)
- model-pinned Codex proxy launchers: `codex-53-with-proxy` (`gpt-5.3-codex`) and `codex-mini-with-proxy` (`codex-mini-latest`)

The staged `Dockerfile` pins mitmproxy to `12.2.2` and fixes the helper script install list so rebuilt images are deterministic once those replacements are applied.

When validating staged Python helpers from `tmp/`, direct bytecode into the workspace instead of `ai-agent-sandbox/__pycache__`, for example:

```bash
PYTHONPYCACHEPREFIX=/workspace/workspace/tmp/pycache python3 -m py_compile \
  tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflow-render.py
```

#### Usage

Until those staged files are copied into `ai-agent-sandbox/` and the devcontainer is rebuilt, run the staged commands directly from:

[`tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/`](/workspace/workspace/tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/)

After rollout and rebuild, the same commands are available in `PATH` without the `tmp/...` prefix.

**Typical workflow**

1. Start mitmproxy or launch a CLI through the proxy.
2. Make one Claude or Codex request.
3. List recent flows to get the short ID.
4. Inspect the request body, streamed events, WebSocket messages, or summary view.
5. Export a Markdown report when you need something shareable.

**Examples**

Start the proxy directly:

```bash
start-proxy
```

Launch Claude or Codex through the proxy:

```bash
claude-with-proxy
codex-with-proxy
codex-high-with-proxy
codex-max-with-proxy
codex-54-with-proxy
codex-54-mini-with-proxy
codex-53-with-proxy
codex-mini-with-proxy
```

Codex model selection is available directly on the CLI with `-m/--model`, so you can also run commands like:

```bash
codex-with-proxy --model gpt-5.4
codex-with-proxy --model gpt-5.4-mini
codex-with-proxy --model gpt-5.3-codex
codex-high-with-proxy -m codex-mini-latest
CODEX_MODEL=gpt-5.3-codex codex-with-proxy
```

As of April 30, 2026, OpenAI's official models guide recommends `gpt-5.5` as the default starting point, with `gpt-5.4` and `gpt-5.4-mini` as cheaper pinned alternatives.

List recent flows:

```bash
mitmflows --limit 20
mitmflows --provider anthropic
mitmflows --provider openai --json
mitmflows --host openai --path /v1/responses
```

Inspect a request, response, or WebSocket message payload:

```bash
mitmflow-body <id> request --json
mitmflow-body <id> response
mitmflow-body <id> response --events
mitmflow-body <id> response --raw
mitmflow-body <id> messages --json
mitmflow-body <id> messages --json --dedupe
```

`--dedupe` is only supported for OpenAI `messages` output and is rejected with `--raw` so the transport-faithful view remains lossless.

Render a summary or full diagnostic view:

```bash
mitmflow-detail <id>
mitmflow-detail <id> --full
mitmflow-detail <id> --raw
mitmflow-detail <id> --md
```

Exports default to:

[`tmp/mitmproxy-flows/`](/workspace/workspace/tmp/mitmproxy-flows/)

So, for example:

```bash
mitmflow-body <id> request --json --save anthropic-request.json
mitmflow-detail <id> --md
```

will write files under `tmp/mitmproxy-flows/` unless you pass an absolute path inside the workspace.

### Save Conversation Skill

`/save-conversation` captures the current conversation to a `conversations/` directory. Files are numbered with kebab-case titles, organized with INDEX shards.

## What's Here

- `.devcontainer/` — VS Code devcontainer configuration (points to `ai-agent-sandbox/docker-compose.yml`)
- `ai-agent-sandbox/` — Docker sandbox definition: Dockerfile, docker-compose.yml, entrypoint, mitmproxy scripts, skills, settings overlay. **Mounted read-only at runtime** — the agent cannot modify its own configuration.
- `scripts/` — workspace utilities (`sync-all.sh`)
- `AGENTS.md` — AI agent context (injected via SessionStart hook)

## What's Not Here

This repo is intentionally minimal. It's just the front door.

- For system orchestration: see [orchestration](https://github.com/budgetanalyzer/orchestration)
- For individual services: see the respective repos

## Design Decisions

### AGENTS.md over CLAUDE.md

We use AGENTS.md (the emerging multi-tool standard) instead of CLAUDE.md, injected via a SessionStart hook. This works around two open issues:

- [#18560](https://github.com/anthropics/claude-code/issues/18560) — system-reminder appended to CLAUDE.md contents undermines user instructions with a contradictory "may or may not be relevant" caveat
- [#6235](https://github.com/anthropics/claude-code/issues/6235) — Claude Code doesn't natively read AGENTS.md

The hook in `settings-overlay.json` cats AGENTS.md at session start, which arrives as a system-reminder without the subversive suffix.

### CLAUDE_CODE_DISABLE_AUTO_MEMORY

Set in `devcontainer.json` remoteEnv. Disables Claude Code's automatic memory feature, which lets the agent decide on its own what to remember across sessions. This is a personal preference for 100% control over what goes into AI context — if you prefer the memory feature (many users do), remove this env var.

## License

MIT
