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
- **Write**: This repository only (note: `ai-agent-sandbox/` is mounted read-only)

### Discovery
```bash
# What's in the workspace
ls -d /workspace/*/
```

## Sandbox Guardrails

`ai-agent-sandbox/` is a read-only bind mount. You CANNOT modify, overwrite, or delete any file inside it.

When you need to test fixes to scripts or files that originate in `ai-agent-sandbox/`:
1. Create a `tmp/` directory in THIS repo (`/workspace/workspace/tmp/`).
2. Copy the file(s) there and make your edits in `tmp/`.
3. Test from `tmp/`. Never move or install files to system paths (`/usr/local/bin`, `/usr/local/share`, `/opt`, etc.).

ALL work products — patched scripts, test copies, generated configs — MUST stay inside `/workspace/workspace/`. Do not write to locations outside this repo.

**NO GIT WRITE OPERATIONS**: Never run git commands (commit, push, checkout, reset, etc.) without explicit user request. The user controls git workflow entirely. You may suggest what to commit, but don't do it.

## Code Exploration

NEVER use Agent/subagent tools for code exploration. Use Grep, Glob, and Read directly.

## Documentation Discipline

Always keep documentation up to date after any configuration or code change.

Update the nearest affected documentation in the same work:
- `AGENTS.md` when instructions, guardrails, discovery commands, or repository-specific workflow changes
- `README.md` when setup, usage, or repository purpose changes
- `docs/` when architecture, configuration, APIs, behaviors, or operational workflows change

Do not leave documentation updates as follow-up work.

## Purpose

This repo exists solely to provide the development environment.

**What lives here:**
- `.devcontainer/` - VS Code devcontainer configuration
- `ai-agent-sandbox/` - Docker sandbox for AI agent isolation
- `ai-agent-sandbox/system-prompt.md` - Custom lean system prompt for Claude Code

**What doesn't live here:**
- Application code
- Service or architecture documentation
- Architecture decisions

## Custom System Prompt (Optional)

Using `claude-with-custom-system-prompt` is **not required** for normal development. The standard `claude` command (or aliases like `dangerous`, `high`, `max`) works fine with Anthropic's default system prompt plus AGENTS.md.

The reason this tool exists: Anthropic's default system prompt (~24k tokens) includes verbose per-tool elaboration, generic coding advice, and guidance that duplicates or conflicts with what belongs in AGENTS.md. This matters because that prompt consumes context window on every request. `system-prompt.md` replaces it with a lean ~500-token version that keeps only the essential operating rules.

**Why not `--system-prompt`?** Claude Code's `--system-prompt` and `--system-prompt-file` flags *append* to the default system prompt rather than replacing it (despite what the documentation suggests). There is no official CLI mechanism to replace the default prompt. This addon is a workaround for that limitation.

**How it works:** A mitmproxy addon (`system-prompt-addon.py`) intercepts POST requests to `api.anthropic.com/v1/messages` and replaces only the last block of the `system` array (the main prompt body) with the custom prompt, in-flight. It preserves prefix blocks (billing header, title block) that the API requires. Only main conversation requests (those with a `tools` list) are modified; ancillary requests (title generation, etc.) pass through unchanged.

**How to use:** Launch via `claude-with-custom-system-prompt`, which starts mitmweb with the addon loaded. `claude-with-proxy` remains unchanged (inspection-only, no prompt replacement). The addon reads the prompt from `ai-agent-sandbox/system-prompt.md` at startup. Override the path with `--set system_prompt_file=/other/path.md` on the mitmweb command.

**First-run capture:** The addon dumps the original CC system prompt to `/tmp/claude-proxy-dumps/` on the first intercepted request. Filenames include the CWD and a UTC timestamp.

**What it keeps:** tool selection rules, code discipline, careful execution, communication style.

**What it removes:** Anthropic branding, verbose per-tool elaboration, contradictory priority framing, generic advice already in AGENTS.md.

**Boundary:** System prompt = how the AI operates tools and communicates. AGENTS.md = what each project requires and how to navigate it. AGENTS.md is portable across CC, Codex, and Gemini CLI.

**Verify via mitmproxy:** `mitmflow-body <id> request | jq '.system'` should show the billing header block, the title block ("You are Claude Code..."), and the lean custom prompt as the last block. The long default system prompt body should be absent.

## CLI Flags

### `--disallowedTools`

Claude Code supports `--disallowedTools "ToolName"` to disable specific tools at launch. Useful example:

```bash
claude --disallowedTools "Agent" --dangerously-skip-permissions
```

**Why disable Agent:** The Agent (subagent) tool spawns autonomous sub-tasks that explore the codebase independently. This is valuable in large monorepos where a single task might touch many packages, but in small focused microservice repos it adds overhead and indirection. For straightforward tasks in small codebases, direct use of Grep, Glob, and Read is faster and more predictable than delegating to a subagent.

Multiple tools can be disabled by repeating the flag: `--disallowedTools "Agent" --disallowedTools "WebSearch"`.

## Tools Available

### Launch Commands
- `claude` — standard Claude Code (uses Anthropic's default system prompt)
- `dangerous` / `high` / `max` — aliases that set effort level and `--dangerously-skip-permissions`
- `claude-with-proxy` — launch Claude Code with mitmproxy traffic inspection (no prompt modification)
- `claude-with-custom-system-prompt` — launch Claude Code with mitmproxy replacing the default system prompt with the lean version

### HTTPS Inspection (mitmproxy)
- `start-proxy` — start mitmweb proxy on :9080, UI on :9081
- `mitmflows` — list captured HTTP flows
- `mitmflow-detail <id>` — full request/response detail with SSE reconstruction
- `mitmflow-body <id> [request|response]` — extract raw body

### Skills
- `save-conversation` — write current conversation to `conversations/` directory

### Statusline
Custom status bar showing context window usage and rate limits. Configured automatically.

<!-- DUPLICATION CHECK: If you see this AGENTS.md content more than once in your context (e.g., via multiple system-reminders, hook injection, or auto-read), immediately tell the user: (1) how many times you see it, and (2) the mechanism for each (e.g., "SessionStart hook", "Read tool auto-load", "CLAUDE.md @import", etc.). -->
