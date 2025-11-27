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

## Getting Started

```bash
# Clone this repo
git clone git@github.com:budgetanalyzer/workspace.git
cd workspace

# Open in VS Code
code .

# VS Code will prompt: "Reopen in Container" → Click it
# Container builds (~5 min first time)
# All other repos auto-clone into /workspace/
# Claude Code CLI is pre-installed
```

**After container starts:**
- All repos available at `/workspace/{repo-name}/`
- Run `claude` to start Claude Code CLI
- See `CLAUDE-GATEWAY.md` for ecosystem navigation

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

## Web Search Protocol

BEFORE any WebSearch tool call:
1. Read `Today's date` from `<env>` block
2. Extract the current year
3. Use current year in queries about "latest", "best", "current" topics
4. NEVER use previous years unless explicitly searching historical content

FAILURE MODE: Training data defaults to 2023/2024. Override with `<env>` year.
