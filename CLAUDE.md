# Workspace Entry Point

## Tree Position

**Archetype**: gateway
**Scope**: budgetanalyzer ecosystem
**Role**: Development environment entry point; owns sandbox configuration

### Relationships
- **Provides environment for**: All repos in /workspace
- **Defers to**: orchestration/ for runtime coordination

### Permissions
- **Read**: All of /workspace
- **Write**: This repository only

### Discovery
```bash
# What's in the workspace
ls -d /workspace/*/
```

## Purpose

This repo exists solely to provide the development environment.

**What lives here:**
- `.devcontainer/` - VS Code devcontainer configuration
- `claude-code-sandbox/` - Docker sandbox for AI agent isolation
- `CLAUDE-GATEWAY.md` - Ecosystem navigation map

**What doesn't live here:**
- Code
- Documentation (beyond navigation)
- Architecture decisions

For ecosystem navigation, see [CLAUDE-GATEWAY.md](CLAUDE-GATEWAY.md).
