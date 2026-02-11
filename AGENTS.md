# Workspace Entry Point

## Honest Discourse

Do not over-validate ideas. The user wants honest pushback, not agreement.

- If something seems wrong, say so directly
- Distinguish "novel" from "obvious in retrospect"
- Push back on vague claims — ask for concrete constraints
- Don't say "great question" or "that's a really interesting point"
- Skip the preamble and caveats — just answer

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

