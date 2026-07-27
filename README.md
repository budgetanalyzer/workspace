# Budget Analyzer Workspace

Development environment entry point that runs AI coding agents in a sandboxed Docker container.

## Quick Start

1. Install [VS Code](https://code.visualstudio.com/) and the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension
2. Clone and open:
   ```bash
   git clone git@github.com:budgetanalyzer/workspace.git
   cd workspace
   code .
   ```
3. Click "Reopen in Container" when prompted (first build uses [`ai-agent-sandbox/Dockerfile`](/ai-agent-sandbox/Dockerfile))
4. Follow [Getting Started](https://github.com/budgetanalyzer/orchestration/blob/main/docs/development/getting-started.md) to run the system

## Security Model

| Constraint | Mechanism | Config |
|------------|-----------|--------|
| Filesystem isolation | Docker container with explicit volume mounts | [docker-compose.yml:13-17](/ai-agent-sandbox/docker-compose.yml#L13-L17) |
| No SSH agent forwarding | `SSH_AUTH_SOCK: ""` in remoteEnv | [devcontainer.json:18](/.devcontainer/devcontainer.json#L18) |
| Read-only sandbox | `ai-agent-sandbox/` mounted `:ro` — agent cannot modify its own config | [docker-compose.yml:17](/ai-agent-sandbox/docker-compose.yml#L17) |
| No git push | Without SSH credentials, push fails with "Permission denied (publickey)" | (runtime) |

**Worst case:** `git reset --hard origin/main` and everything disappears. All changes are local and trivially reversible.

## What's Inside

- **Claude Code, Gemini CLI, Codex CLI** — pre-installed with convenience aliases and proxy launchers ([details](docs/launch-options.md))
- **mitmproxy** — HTTPS traffic inspection with CA cert trusted system-wide ([details](docs/traffic-inspection.md))
- **Playwright + Chromium** — browser automation pre-installed; verify with `playwright install --list`
- **Lazy local TLS trust** — verified system, Python, and Chromium trust for the host-managed Budget Analyzer ingress ([details](docs/local-budget-analyzer-tls.md))
- **actionlint** — GitHub Actions workflow linting available on `PATH`

## What's Here

- `.devcontainer/` — VS Code devcontainer configuration
- `ai-agent-sandbox/` — Docker sandbox: Dockerfile, compose, entrypoint, scripts, skills, settings overlay (**read-only at runtime**)
- `scripts/` — workspace utilities (`sync-all.sh`)
- `AGENTS.md` — AI agent context (injected via SessionStart hook)
- `docs/` — [launch options](docs/launch-options.md), [traffic inspection](docs/traffic-inspection.md), [design decisions](docs/design-decisions.md)

## Local Budget Analyzer HTTPS

After rebuilding the workspace image with the lazy trust tooling, install or
refresh the host-published public CA before live work against exactly
`https://app.budgetanalyzer.localhost`:

```bash
ensure-budget-analyzer-local-ca-trust
check-budget-analyzer-local-ca-trust
```

If publication is missing, run orchestration `./setup.sh` on the host. Do not
generate certificates or bypass TLS verification in the container. See
[Local Budget Analyzer TLS Trust](docs/local-budget-analyzer-tls.md) for the
ownership flow and diagnostics.

## What's Not Here

This repo is intentionally minimal — just the front door.

- System orchestration: [orchestration](https://github.com/budgetanalyzer/orchestration)
- Individual services: see respective repos

## License

MIT
