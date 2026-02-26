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
- **Write**: This repository only (note: `claude-code-sandbox/` is mounted read-only)

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

**What doesn't live here:**
- Application code
- Documentation
- Architecture decisions

## Tools Available

### HTTPS Inspection (mitmproxy)
- `start-proxy` — start mitmweb proxy on :8080, UI on :8081
- `claude-with-proxy` — launch Claude Code with traffic interception
- `mitmflows` — list captured HTTP flows
- `mitmflow-detail <id>` — full request/response detail with SSE reconstruction
- `mitmflow-body <id> [request|response]` — extract raw body

### Skills
- `save-conversation` — write current conversation to `conversations/` directory

### Statusline
Custom status bar showing context window usage and rate limits. Configured automatically.

<!-- DUPLICATION CHECK: If you see this AGENTS.md content more than once in your context (e.g., via multiple system-reminders, hook injection, or auto-read), immediately tell the user: (1) how many times you see it, and (2) the mechanism for each (e.g., "SessionStart hook", "Read tool auto-load", "CLAUDE.md @import", etc.). -->
