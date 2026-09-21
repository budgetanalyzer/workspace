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

- **Claude Code, Gemini CLI, Codex CLI, and AI Session Handler** — globally available with convenience launchers ([details](docs/launch-options.md))
- **mitmproxy** — HTTPS traffic inspection with CA cert trusted system-wide ([details](docs/traffic-inspection.md))
- **Playwright + Chromium** — browser automation pre-installed; verify with `playwright install --list`
- **Node.js 24** — the latest LTS major line from the signed NodeSource repository, compatible with Site Modeler's `>=22` engine requirement
- **VGG Image Annotator 3.0.13** — pinned standalone human annotation UI with a localhost-only foreground launcher
- **ImageMagick** — deterministic image metadata, crop, and review-overlay tools (`identify` and `convert`)
- **Lazy local TLS trust** — verified system, Python, and Chromium trust for the host-managed Budget Analyzer ingress ([details](docs/local-budget-analyzer-tls.md))
- **actionlint** — GitHub Actions workflow linting available on `PATH`

## What's Here

- `.devcontainer/` — VS Code devcontainer configuration
- `ai-agent-sandbox/` — Docker sandbox: Dockerfile, compose, entrypoint, scripts, skills, settings overlay (**read-only at runtime**)
- `scripts/` — workspace utilities (`sync-all.sh`)
- `AGENTS.md` — AI agent context (injected via SessionStart hook)
- `docs/` — [launch options](docs/launch-options.md), [traffic inspection](docs/traffic-inspection.md), [design decisions](docs/design-decisions.md), and [dependency automation](docs/dependency-automation.md)

## Dependency Automation

Renovate extends the shared Budget Analyzer preset on `main`. The workspace
image security workflow runs for pushes to `main`, trusted same-repository pull
requests targeting `main`, a weekly schedule, and manual dispatches. It rebuilds
the image without cache, starting, or pushing it; scans the exact local image;
and retains the declared evidence paths in one artifact for seven days. See
[Dependency Automation](docs/dependency-automation.md) for extraction boundaries,
image-scan limits, and validation commands.

After applying the Docker-in-Docker feature rollback, follow the
[host recovery and rebuild sequence](docs/dependency-automation.md#applying-the-docker-feature-rollback)
before resuming the local stack. The configuration change does not repair
already damaged host firewall rules.

## Run An AI Session Handler Plan

A fresh container installs `/workspace/ai-session-handler` globally through an editable pipx
environment. From any repository root, run a plan in that repository's `docs/plans/` directory by
its filename stem:

```bash
cd /workspace/REPOSITORY
ai-run PLAN_NAME
```

For example, `ai-run improve-imports --max-phases 1` runs
`./docs/plans/improve-imports.md` with `ai-session-handler-codex-high`, streams the worker's
progress, and forwards the phase limit unchanged. Pass `--quiet` explicitly to suppress live worker
output while retaining the transcript. Set `CODEX_MODEL` when an explicit Codex model is needed.
Ordinary Python source changes under `/workspace/ai-session-handler/src/` are visible to the global
commands without a reinstall or image rebuild.

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

## Human-Reviewed Image Tracing

A rebuilt sandbox image provides [VGG Image Annotator (VIA) 3.0.13](https://www.robots.ox.ac.uk/~vgg/software/via/), an open-source BSD-2-Clause standalone application with ordered polygon, line, and polyline annotations. The build downloads VGG's [official versioned archive](https://www.robots.ox.ac.uk/~vgg/software/via/downloads/via3/via-3.0.13.zip), verifies archive SHA-256 `d16fac5ac83507587845c04644bdbe81896865f2cb963d570bf0f52d48e7d793`, verifies the standalone image annotator SHA-256 `44de1edcee45a0c442dcd028316cdce1647b4fb1a3ca3669b07cd77f39e5fc98`, and preserves the upstream license under `/opt/via-annotator`.

VIA is a human-operated annotation tool. The human selects and orders every polygon vertex and every two-point line or polyline. ImageMagick may produce deterministic metadata, crops, and review overlays, but automatic edge detection or other automated tracing must never produce authoritative geometry.

After changing the sandbox image, use **Dev Containers: Rebuild and Reopen in Container** from the VS Code Command Palette. Do not use a normal window reload: the Node.js, VIA, ImageMagick, and browser prerequisites are image contents and are available only after the rebuild completes.

Verify the rebuilt environment:

```bash
node --version
via-annotator --version
via-annotator --check
identify -version
convert -version
playwright --version
playwright install --list
```

`node --version` must report major version 24, `via-annotator --check` must report a valid 3.0.13 installation without starting a server, and Playwright's list must include Chromium under `/opt/playwright-browsers`.

Start VIA in a terminal:

```bash
via-annotator
# Or choose another local port:
via-annotator --port 8766
```

The default local URL is `http://localhost:8765/via_image_annotator.html`. The launcher remains in the foreground; press `Ctrl+C` in that terminal to stop it cleanly. VIA never starts as a service or background process.

For private source images, choose **Add Local Files** in VIA and select the original image with the browser file picker. Create the ordered polygon and the required two-point line or polyline annotations manually, then save the VIA project and export its JSON for the reviewed import workflow. The launcher binds strictly to `127.0.0.1` and serves only immutable files in `/opt/via-annotator`; it neither serves `/workspace` nor provides a file-upload endpoint. Selected local files are read in the browser and are not sent to the static server. Do not use remote-file or project-sharing features for private images.

## What's Not Here

This repo is intentionally minimal — just the front door.

- System orchestration: [orchestration](https://github.com/budgetanalyzer/orchestration)
- Individual services: see respective repos

## License

MIT
