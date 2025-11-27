# Budget Analyzer Workspace

Development environment entry point for the Budget Analyzer reference architecture.

## Quick Start

1. Clone this repo alongside all other Budget Analyzer repos:
   ```
   /your-workspace/
   ├── workspace/              # This repo
   ├── orchestration/
   ├── transaction-service/
   └── ...
   ```

2. Open in VS Code with Dev Containers extension

3. "Reopen in Container" when prompted

## What's Here

- `.devcontainer/` - VS Code devcontainer configuration
- `claude-code-sandbox/` - Docker sandbox for AI agent isolation
- `CLAUDE.md` - AI agent context
- `CLAUDE-GATEWAY.md` - Ecosystem navigation for AI agents

## What's Not Here

This repo is intentionally minimal. It's just the front door.

- For system orchestration: see [orchestration](https://github.com/budgetanalyzer/orchestration)
- For architectural discussions: see [architecture-conversations](https://github.com/budgetanalyzer/architecture-conversations)
- For individual services: see the respective repos

## License

MIT
