# Budget Analyzer Workspace

> "Archetype: gateway. Role: Development environment entry point; owns sandbox configuration."
>
> — [AGENTS.md](AGENTS.md#tree-position)

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

With the Dev Containers extension installed, VS Code will prompt "Reopen in Container" — click it. The container builds on first run.

**After the container starts:**
- All repos are available at `/workspace/{repo-name}/`
- Claude Code, Gemini CLI, and Codex CLI are pre-installed
- Follow [Getting Started](https://github.com/budgetanalyzer/orchestration/blob/main/docs/development/getting-started.md) to run the system

## What's Inside

### AI Coding CLIs

Claude Code, Gemini CLI, and Codex CLI are pre-installed. The directory is named `claude-code-sandbox` but the environment is client-agnostic.

**Auth:**
- **Claude** — already authenticated via `~/.anthropic` volume mount
- **Codex** — `export OPENAI_API_KEY` or run `codex` to sign in
- **Gemini** — `export GEMINI_API_KEY` or run `gemini` to sign in

### HTTPS Traffic Inspection

mitmproxy is pre-installed with its CA cert trusted system-wide and by Node.js (`NODE_EXTRA_CA_CERTS`). Scripts available in PATH:

- `start-proxy` — start mitmweb (proxy :8080, UI :8081)
- `claude-with-proxy` — launch Claude Code with proxy in one shot
- `mitmflows` — list captured flows as a table
- `mitmflow-detail <id>` — full request/response with SSE reconstruction
- `mitmflow-body <id> [request|response]` — raw body extraction

Note: Claude Code is installed via npm (not the native binary) because the native Bun binary ignores `HTTP_PROXY` for streaming — see [anthropics/claude-code#14165](https://github.com/anthropics/claude-code/issues/14165).

### Save Conversation Skill

`/save-conversation` captures the current conversation to a `conversations/` directory. Files are numbered with kebab-case titles, organized with INDEX shards.

## What's Here

- `.devcontainer/` — VS Code devcontainer configuration
- `claude-code-sandbox/` — Docker sandbox: Dockerfile, entrypoint, mitmproxy scripts, skills, settings overlay (mounted read-only at runtime)
- `scripts/` — workspace utilities (`sync-all.sh`)
- `AGENTS.md` — AI agent context (injected via SessionStart hook)

## What's Not Here

This repo is intentionally minimal. It's just the front door.

- For system orchestration: see [orchestration](https://github.com/budgetanalyzer/orchestration)
- For architectural discussions: see [architecture-conversations](https://github.com/budgetanalyzer/architecture-conversations)
- For individual services: see the respective repos

## Design Decisions

### AGENTS.md over CLAUDE.md

We use AGENTS.md (the emerging multi-tool standard) instead of CLAUDE.md, injected via a SessionStart hook. This works around two open issues:

- [#18560](https://github.com/anthropics/claude-code/issues/18560) — system-reminder appended to CLAUDE.md contents undermines user instructions with a contradictory "may or may not be relevant" caveat
- [#6235](https://github.com/anthropics/claude-code/issues/6235) — Claude Code doesn't natively read AGENTS.md

The hook in `settings-overlay.json` cats AGENTS.md at session start, which arrives as a system-reminder without the subversive suffix.

### Read-Only Sandbox Mount

`claude-code-sandbox/` is mounted `:ro` in docker-compose.yml. The AI agent cannot modify its own Dockerfile, entrypoint, settings, or skills. Changes to sandbox configuration require a human editing the source files and rebuilding.

### CLAUDE_CODE_DISABLE_AUTO_MEMORY

Set in `devcontainer.json` remoteEnv. Disables Claude Code's automatic memory feature, which lets the agent decide on its own what to remember across sessions. This is a personal preference for 100% control over what goes into AI context — if you prefer the memory feature (many users do), remove this env var.

## License

MIT
