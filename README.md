# Budget Analyzer Workspace

Development-environment entry point for Budget Analyzer and its AI coding
tools. The supported workflow runs agents directly in the Ubuntu development
VM as its normal development user. See
[Development VM And Native Agent Runtime](docs/host-isolation.md) for the
current host/guest boundary, repository transport and SSH-client requirements.

Workspace owns native VM identity, the normal user and home, guest-local
repository topology, rejection of forwarded authority, guest Docker selection,
native tool versions, guest trust readiness, personal-host-to-VM host tunnels
and reusable personal-host isolation audit tooling. Orchestration owns
application bootstrap, the exact local Kind target, Tilt, ingress-file
validation and Kubernetes Secret reconciliation.

## Native Daily Workflow

Connect to the VM with your preferred SSH client or editor and open the
guest-local working clones under `/srv/budget-analyzer/worktrees`. VS Code
Remote SSH with the dedicated profile is the tested editor workflow, but it is
optional. Start the application from a fresh normal-user guest shell:

```bash
cd /srv/budget-analyzer/worktrees/orchestration
./scripts/bootstrap/check-agent-vm-prerequisites.sh --native-runtime
tilt up
```

Then launch `codex`, `claude`, `gemini`, or `ai-run` from the repository where
you want to work. Do not run `setup.sh` for ordinary daily startup; it recreates
Kind. The complete bootstrap, daily-use and troubleshooting procedures live in
[Getting Started](https://github.com/budgetanalyzer/orchestration/blob/main/docs/development/getting-started.md#development-vm-native-workflow).

For personal-host browser access after the guest application is running, start
the documented foreground host tunnel for application HTTPS and the Tilt UI.
The one-time narrow host authorization, daily command, checks, and separate
optional observability path live in
[Personal-Host Access](docs/host-isolation.md#personal-host-access).

Every SSH client must preserve the documented host boundary: do not forward
host credentials or an SSH agent, restore or create automatic port forwards,
or inject Git askpass. The validated VS Code profile applies these controls for
Remote SSH. Agents use guest-local working clones and bare origins, the guest's
default Docker socket, and the normal guest home. Git publication remains a
personal-host operation.

## Canonical Native Runtime Contract

The single read-only native runtime verifier is:

```bash
./scripts/check-agent-vm-tools.sh \
  --worktree-parent "$BUDGET_ANALYZER_WORKTREE_PARENT" \
  --bare-parent "$BUDGET_ANALYZER_BARE_PARENT"
```

Run it from the reviewed workspace checkout after native preparation and local
ingress trust are complete. Sibling orchestration calls this same interface for
both first application bootstrap and daily startup; both parent arguments are
required canonical absolute directories. The verifier checks Ubuntu 24.04
QEMU/KVM identity, the normal user/home, absent credential, Git, proxy and
endpoint bridges, guest-local working/bare repositories, the default guest
Unix Docker socket and data root, manifest-owned native and user tool versions,
managed user resources, Chromium and established OS/NSS ingress trust.

The command does not use sudo, install packages, mutate trust, authenticate,
repair repositories or change Docker/Kind state. A failure requires the
documented human preparation or trust workflow; callers must not substitute a
partial check. Exact versions and capabilities remain solely in
[`native/toolchain.json`](native/toolchain.json).

## Docker Sandboxes

Docker Sandboxes (`sbx`) is being monitored as a possible future replacement
for some of this repository's native VM and agent-runtime machinery. It offers
promising microVM isolation, private Docker daemons and policy-controlled host
integrations, but the product and those integration surfaces are still
maturing. For now, the dedicated development VM remains the supported boundary:
it relies on mature, inspectable virtualization components and deliberately
exposes fewer filesystem, credential and host-service paths, making its
security boundary less fragile for this environment.

## Personal-Host Isolation Audit

Workspace owns the reusable human-only audit runbook, read-only evidence
collector, bounded protocol fixture and configurable binary go/no-go verifier.
Concrete host topology, policy source and evidence remain private operator
material outside Git and guest-accessible storage. Agents may run only the
offline fixtures; they must not access or administer the personal host. Read
[Personal-Host Isolation Audit](docs/host-isolation-audit.md) before collecting,
reviewing or testing host-isolation evidence.

To add one host repository after initial VM setup, run this from the personal
host's common repository parent:

```bash
./workspace/scripts/add-agent-vm-repository.sh ./repository-name
```

The command shows the exact repository and branch before asking for
confirmation. The conventional organization repository basename `.github` is
supported. See [Development VM And Native Agent Runtime](docs/host-isolation.md#adding-one-repository-later)
for the transfer contract and prerequisites.

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
[Native Tool Inventory](docs/native-tool-inventory.md).

## Repository Layout

- `native/toolchain.json` — reviewed native tool and helper manifest.
- `native/npm/` — locked normal-user npm tool environment.
- `native/helpers/` — canonical portable helpers, settings, prompt and skill
  resources.
- `scripts/native/` — system, user, trust and optional-proxy implementations.
- `scripts/host-isolation/` — human-only host audit tools, safe template and
  strict configuration parser.
- `scripts/*.sh` — human entry points and read-only native checks.
- `tests/native/` — focused installer-safety, manifest and environment
  verifiers.
- `tests/host-isolation-audit/` — offline collector, protocol, configuration
  and verifier-contract fixtures.
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
startup. It rejects unsupported operating systems, containers, remote Docker
endpoints, unsafe ownership, credential bridges and version collisions while
preserving healthy guest Docker workloads.

After reviewed helper, settings or manifest changes are transferred, the human
must end affected workers and rerun the focused normal-user installer/check
sequence in
[Native Guest User Tools](docs/native-user-tools.md#refresh-installed-user-resources).

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
source changes immediately; dependency or entry-point changes require an
explicit reinstall.

## Local Budget Analyzer HTTPS

Before live work against exactly
`https://app.budgetanalyzer.localhost`, run the read-only native diagnostic:

```bash
check-budget-analyzer-local-ca-trust
```

`ensure-budget-analyzer-local-ca-trust` is also read-only in native execution;
missing established trust reports the exact human installer command. Never use
HTTP or TLS-verification bypasses. Certificate generation remains on the
personal host without a host Kind cluster, orchestration validates transferred
files and reconciles the VM's Kubernetes Secret, and workspace owns the
three-file transfer plus guest OS/NSS trust installation.
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
the checksum- and signing-key-coupled tool inputs. See
[Dependency Automation](docs/dependency-automation.md).

## What Is Not Here

This repository is the development tooling front door, not an application
monorepo.

- System orchestration: [orchestration](https://github.com/budgetanalyzer/orchestration)
- Individual services: see their sibling repositories

## License

MIT
