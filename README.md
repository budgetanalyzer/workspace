# Budget Analyzer Workspace

Development-environment entry point for Budget Analyzer and its AI coding
tools. The supported workflow runs agents directly in the Ubuntu development
VM as its normal development user. The former container workflow is retired
and its tracked launch/build sources have been removed; do not recreate it.

The native migration and human Checkpoints A–D completed on 2026-10-05. See
[Development VM And Guest Agent Runtime](docs/host-isolation.md) for the current
boundary and historical acceptance record. The separate post-migration
security review remains tracked by orchestration.

## Native Daily Workflow

Use the dedicated VS Code Remote SSH profile, open the guest-local working
clones under `/srv/budget-analyzer/worktrees`, and start the application from a
fresh normal-user guest shell:

```bash
cd /srv/budget-analyzer/worktrees/orchestration
./scripts/bootstrap/check-agent-vm-prerequisites.sh --native-runtime
tilt up
```

Then launch `codex`, `claude`, `gemini`, or `ai-run` from the repository where
you want to work. Do not run `setup.sh` for ordinary daily startup; it recreates
Kind. The complete bootstrap, daily-use and troubleshooting procedures live in
[Getting Started](../orchestration/docs/development/getting-started.md#development-vm-native-workflow).

The Remote SSH profile must not forward host credentials, restore ports or
inject Git askpass. Agents use guest-local working clones and bare origins,
the guest's default Docker socket, and the normal guest home. Git publication
remains a personal-host operation.

## What Is Installed

- Claude Code, Codex CLI, Gemini CLI and AI Session Handler, with reviewed
  native launchers described in [AI CLI Launch Options](docs/launch-options.md).
- Optional mitmproxy inspection with a separate, human-initialized guest CA;
  ordinary sessions remain unproxied. See
  [HTTPS Traffic Inspection](docs/traffic-inspection.md).
- Pinned Playwright and Chromium for browser automation.
- Node.js 24, Azul Zulu JDK 25, Maven, Go, Docker/Compose, kubectl, Kind, Tilt,
  Helm, ShellCheck and actionlint.
- VGG Image Annotator 3.0.13 and ImageMagick for human-reviewed image tracing.
- Verified local ingress trust for system, Python, Node and Chromium clients.

Exact versions, checksums, signed repository inputs, package ownership and
capability checks live in [`native/toolchain.json`](native/toolchain.json) and
[Native Tool Migration Inventory](docs/native-tool-inventory.md).

## Repository Layout

- `native/toolchain.json` — reviewed native tool and helper manifest.
- `native/npm/` — locked normal-user npm tool environment.
- `native/helpers/` — canonical portable helpers, settings, prompt and skill
  resources.
- `scripts/native/` — system, user, trust and optional-proxy implementations.
- `scripts/*.sh` — human entry points and read-only native checks.
- `tests/native/` — focused installer-safety, manifest, environment and
  retirement verifiers.
- `AGENTS.md` — agent operating contract.
- `docs/` — native setup, isolation, launch, trust and dependency owner docs.

Application code and active service architecture live in sibling repositories.

## Native Installation And Refresh

Only the human runs native installers, after reviewing source and ending all
affected workers. The repeatable system/user preparation entry point is:

```bash
./scripts/prepare-agent-vm-native.sh
```

It is for first preparation or an explicitly reviewed repair, not daily agent
startup. It rejects containers, Mint, remote Docker endpoints, unsafe
ownership, credential bridges and version collisions while preserving healthy
guest Docker workloads.

Phase 5 changed the canonical helper/settings source and manifest. After these
changes are reviewed and transferred, the human must end workers and rerun the
focused normal-user installer/check sequence in
[Native Guest User Tools](docs/native-user-tools.md#phase-5-native-source-refresh).
This repository change does not claim that live-home refresh has occurred.

## Run An AI Session Handler Plan

From the repository that owns `docs/plans/PLAN_NAME.md`, run:

```bash
ai-run PLAN_NAME
```

For example, `ai-run improve-imports --max-phases 1` runs the plan through the
globally installed high-reasoning Codex wrapper and streams progress. Later
arguments are forwarded to `ai-session-handler run`; use `--quiet` to suppress
live output while retaining the transcript. Set `CODEX_MODEL` only when an
explicit model is required. The editable handler install reflects reviewed
source changes without an image rebuild.

## Local Budget Analyzer HTTPS

Before live work against exactly
`https://app.budgetanalyzer.localhost`, run the read-only native diagnostic:

```bash
check-budget-analyzer-local-ca-trust
```

`ensure-budget-analyzer-local-ca-trust` is also read-only in native execution;
missing established trust reports the exact human installer command. Never use
HTTP or TLS-verification bypasses. Certificate generation remains on the
personal host, orchestration validates transferred files and reconciles the
Kubernetes Secret, and workspace alone owns guest OS/NSS trust installation.
See [Local Budget Analyzer TLS Trust](docs/local-budget-analyzer-tls.md).

## Human-Reviewed Image Tracing

VIA is a human-operated annotation tool. The human selects and orders every
polygon vertex and every two-point line or polyline; automatic edge detection
must not produce authoritative geometry. Verify and launch the native install:

```bash
via-annotator --version
via-annotator --check
via-annotator
```

The launcher serves immutable assets from `/opt/via-annotator`, binds only to
`127.0.0.1`, remains in the foreground and stops with `Ctrl+C`. The default URL
is `http://localhost:8765/via_image_annotator.html`. Private files selected in
the browser are not uploaded to the static server.

## Dependency Automation

Renovate extends the shared Budget Analyzer preset. Native manifest checks own
the checksum- and signing-key-coupled tool inputs; there is no retained
workspace image build/scan job. See
[Dependency Automation](docs/dependency-automation.md).

## What Is Not Here

This repository is the development tooling front door, not an application
monorepo.

- System orchestration: [orchestration](https://github.com/budgetanalyzer/orchestration)
- Individual services: see their sibling repositories

## License

MIT
