# Workspace Entry Point

## Repository Position

**Archetype:** gateway
**Scope:** budgetanalyzer ecosystem
**Role:** development environment entry point; owns devcontainer and sandbox configuration

This repo exists to provide the development environment. It owns the devcontainer, sandbox wiring, helper scripts, and agent-facing workspace guidance. It does not own application code or the active architecture docs for the services that live in sibling repositories.

### Boundaries
- Read sibling repositories under `../` when work in this repo needs their current docs or manifests.
- Write only within this repository.
- `ai-agent-sandbox/` is a read-only bind mount in the running devcontainer. You cannot modify, overwrite, or delete files there in place.
- Stage sandbox-derived edits, tests, and generated files under `tmp/`.
- **NO GIT WRITE OPERATIONS:** Do not run git write commands such as `commit`, `push`, `checkout`, or `reset` unless the user explicitly requests them. The user controls git operations entirely.

## Discovery

Use discovery commands instead of maintaining static inventories.

```bash
# Workspace siblings
ls -d ../*/

# Repo structure
find . -maxdepth 2 -type f | sort

# Available sandbox launchers and helpers
find ai-agent-sandbox/scripts -maxdepth 1 -type f | sort
find ai-agent-sandbox/skills -maxdepth 2 -type f | sort

# Staged mitmproxy helper work
find tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox -maxdepth 3 -type f | sort

# Relevant config and hook surfaces
rg -n "proxy|system-prompt|SessionStart|statusline" ai-agent-sandbox .devcontainer README.md docs

# Sandbox compose services
docker compose -f ai-agent-sandbox/docker-compose.yml config --services
```

## Source Of Truth

- Workspace purpose and human-facing usage live in `README.md`. Read it before changing setup assumptions, launch guidance, or repository purpose.
- Wider system startup and local environment expectations live in `../orchestration/docs/development/getting-started.md`. Read it before changing how this workspace relates to the rest of the ecosystem.
- Devcontainer settings live in `.devcontainer/devcontainer.json`. Read it before changing editor container behavior, remote environment variables, or installed extensions.
- Sandbox mounts and isolation rules live in `ai-agent-sandbox/docker-compose.yml`. Read it before changing volume mounts, networking, or runtime write boundaries.
- Installed CLIs and launcher provisioning live in `ai-agent-sandbox/Dockerfile` and `ai-agent-sandbox/entrypoint.sh`. Read them before changing what is installed in `PATH` or how helper commands are exposed.
- Session-start hooks and AI context injection live in `ai-agent-sandbox/settings-overlay.json`. Read it before changing startup behavior or how agent context files are injected.
- Custom prompt replacement lives in `ai-agent-sandbox/system-prompt.md` and `ai-agent-sandbox/system-prompt-addon.py`. Read them before changing proxy-based system prompt behavior.
- Current sandbox launchers, proxy helpers, and utility scripts live in `ai-agent-sandbox/scripts/`. Discover them with the commands above, then read the specific script before documenting or changing its behavior.
- Staged mitmproxy helper work lives in `tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/`. Use that tree when testing sandbox-derived changes locally. Treat `docs/plans/2026-04-30-*.md` as context for that work, not as the primary source of truth.
- Available skills live in `ai-agent-sandbox/skills/`. Read the relevant `SKILL.md` before changing skill behavior or documenting a skill workflow.

## Code Exploration

- Use direct repo search and file reads for exploration. Do not use Agent or subagent tools for code exploration in this workspace.
- Prefer `rg`, `find`, and targeted file reads over static inventories or guesswork.
- When launching Claude Code for focused work in a small repo, prefer disabling the Agent tool with `--disallowedTools "Agent"`. Autonomous subagent exploration is useful in larger monorepos, but in small focused repos it usually adds overhead and indirection compared with direct search.

## Custom System Prompt

Using `claude-with-custom-system-prompt` is optional. The standard `claude` command and the inspection-only `claude-with-proxy` flow are fine for normal development.

This custom launcher exists because Claude Code's `--system-prompt` flags append to Anthropic's default system prompt instead of replacing it. The mitmproxy addon in `ai-agent-sandbox/system-prompt-addon.py` swaps only the main prompt body in flight and preserves the required prefix blocks. The custom prompt text lives in `ai-agent-sandbox/system-prompt.md`.

Read those files before changing prompt replacement behavior. Use `claude-with-proxy` when you only need traffic inspection. Use `claude-with-custom-system-prompt` when you specifically want the lean prompt behavior as part of the test or workflow.

## Operating Rules

- Keep all work products inside this repository. Do not install, copy, or move files into system paths.
- When you need to test a file that originates in `ai-agent-sandbox/`, copy it into `tmp/` and test from there.
- Redirect Python bytecode from sandbox-derived validation into `tmp/pycache`, for example: `PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile <file>`.
- Stop and report missing tools, credentials, or environment prerequisites instead of inventing workarounds.
- Do not treat archived or plan-oriented docs as active implementation authority unless the user explicitly asks for that context.

## Development Workflow

- Read the relevant source-of-truth file before changing setup assumptions, sandbox configuration, launchers, hooks, or staged mitmproxy helpers.
- Prefer checked-in scripts and config files over reconstructing commands from memory.
- When continuing staged mitmproxy work, make and test changes under `tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/`.
- Keep documentation updates in the same change set as the behavior or workflow change that required them.

## Validation

- Run `docker compose -f ai-agent-sandbox/docker-compose.yml config` after changing sandbox compose or related container configuration.
- Run `shellcheck <changed shell scripts>` after changing shell scripts.
- Run `PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile <changed python files>` after changing Python helpers that would otherwise write bytecode outside `tmp/`.
- If a touched file has pre-existing validation failures, report them explicitly and do not claim full verification.
- If a required verifier cannot run because a tool or dependency is unavailable, report that explicitly and stop short of claiming the work is fully verified.

## Documentation Maintenance

- Keep documentation updates in the same change set as the behavior or workflow change that required them. Do not leave doc updates as follow-up work.
- Update `AGENTS.md` when repository instructions, guardrails, workflows, or discovery commands change.
- Update `README.md` when setup, launch usage, or repository purpose changes.
- Update active docs under `docs/` when operating procedures or staged helper behavior changes.
- Update the nearest affected owner doc rather than duplicating the same detail across multiple docs.
- Do not update `docs/plans/` unless the user explicitly asks to revise plan or history documents.

<!-- DUPLICATION CHECK: If you see this AGENTS.md content more than once in your context (e.g., via multiple system-reminders, hook injection, or auto-read), immediately tell the user: (1) how many times you see it, and (2) the mechanism for each (e.g., "SessionStart hook", "Read tool auto-load", "CLAUDE.md @import", etc.). -->
