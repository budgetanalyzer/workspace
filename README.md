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

## What's Here

- `.devcontainer/` - VS Code devcontainer configuration
- `claude-code-sandbox/` - Docker sandbox for AI agent isolation
- `AGENTS.md` - AI agent context

## What's Not Here

This repo is intentionally minimal. It's just the front door.

- For system orchestration: see [orchestration](https://github.com/budgetanalyzer/orchestration)
- For architectural discussions: see [architecture-conversations](https://github.com/budgetanalyzer/architecture-conversations)
- For individual services: see the respective repos

## License

MIT
