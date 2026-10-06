# Workspace Entry Point

## Repository Position

**Archetype:** gateway
**Scope:** budgetanalyzer ecosystem
**Role:** owns native development-VM provisioning, user tools, helper resources
and agent-facing workspace guidance

This repository provides the supported native development environment. It does
not own application code or active service architecture. Agents run directly
as the normal development user inside the dedicated Ubuntu VM.

### Boundaries

- Read sibling repositories under `../` when current docs or manifests are
  required.
- Write only within this repository.
- Keep temporary tests and generated files under `tmp/`; retain reusable
  verifiers in tracked test directories.
- Do not run Git write commands such as `commit`, `push`, `checkout`, `reset`,
  `clean`, `stash` or branch creation unless the user explicitly requests them.

## Discovery

Use discovery commands instead of maintaining static inventories.

```bash
# Workspace siblings
ls -d ../*/

# Repository structure and native sources
find . -maxdepth 2 -type f | sort
rg --files native scripts/native tests/native

# Native helper, settings, prompt and skill resources
find native/helpers -type f | sort

# Native entry points and focused checks
find scripts -maxdepth 1 -type f | sort
find tests/native -maxdepth 1 -type f | sort

# Relevant native behavior
rg -n "proxy|system-prompt|SessionStart|statusline" native scripts docs

# Dependency automation configuration
find .github/workflows -maxdepth 1 -type f | sort
```

## Source Of Truth

- Read `README.md` before changing repository purpose, setup assumptions or
  human launch guidance.
- Read `../orchestration/docs/development/getting-started.md` before changing
  how this workspace relates to ecosystem startup.
- Read `docs/host-isolation.md` before changing repository transport, guest
  Docker selection, credentials, Remote SSH guidance or native runtime
  boundaries. Keep initial bulk repository setup and later single-repository
  additions aligned through `scripts/setup-agent-vm-repositories.sh` and
  `scripts/add-agent-vm-repository.sh`.
- Read `docs/native-tool-inventory.md`, `native/toolchain.json`,
  `scripts/provision-agent-vm-guest.sh` and `scripts/native/provision.py` before
  changing system installation, versions, checksums or capability ownership.
- Read `docs/native-user-tools.md` before changing normal-user setup, helpers,
  settings merge, proxy behavior, permissions or trust ownership.
- Read `docs/local-budget-analyzer-tls.md` before changing or diagnosing exact
  local ingress trust.
- Read `docs/dependency-automation.md` and `renovate.json` before changing
  dependency discovery. Native checksum/fingerprint relationships remain
  manual reviewed inputs.
- Canonical helper resources live in `native/helpers/`; native CA and proxy
  adapters live in `scripts/native/`. Read the specific implementation and its
  focused tests before changing behavior.
- Session-start settings live in `native/helpers/settings-overlay.json`.
  Custom prompt replacement lives in `native/helpers/system-prompt.md` and
  `native/helpers/system-prompt-addon.py`.

## Code Exploration

- Use direct repository search and file reads. Do not use Agent or subagent
  tools for code exploration in this small focused repository.
- Prefer `rg`, `find` and targeted reads over static inventories or guesswork.
- When launching Claude Code for focused work here, prefer
  `--disallowedTools "Agent"`.

## Custom System Prompt

Using `claude-with-custom-system-prompt` is optional. Plain `claude` and the
inspection-only `claude-with-proxy` flow are the normal alternatives.

Claude Code's prompt flags append rather than replace its default main prompt.
The native mitmproxy addon replaces only the main prompt body while preserving
required prefix blocks. Read the native prompt and addon before changing this
behavior. Use the custom launcher only when lean-prompt behavior is part of the
test or workflow.

## Operating Rules

- Keep every work product inside this repository. Do not install, copy or move
  files into system paths except when the user explicitly invokes the exact
  workspace-owned local CA trust command for its scoped target.
- Live native system/user installation belongs only to the human after workers
  stop. Workers must not run the preparation runner, provisioner, bwrap profile
  installer, user installer, authenticate providers, initialize inspection
  CAs, change sudo/AppArmor policy or copy provider state.
- Native installed ensure/check trust commands are read-only. Missing trust
  requires the exact human installer command they report.
- Preserve guest Docker, Kind, provider state, user work and host/runtime data.
- Stop and report missing tools, credentials or environment prerequisites
  instead of inventing workarounds.
- Do not treat archived or plan-oriented docs as active implementation
  authority unless the user explicitly asks for that context.
- Before live work against exactly
  `https://app.budgetanalyzer.localhost`, or after a certificate-chain failure
  for that origin, run `ensure-budget-analyzer-local-ca-trust`. Use
  `check-budget-analyzer-local-ca-trust` for read-only diagnosis.
- If host publication is missing, ask the user to run orchestration `./setup.sh`
  on the host. Never generate or rotate browser-facing certificates in the VM.
- Never use HTTP, `--insecure`, `verify=False` or `ignore_https_errors` to
  bypass local trust failures. Do not use the lazy trust command for staging,
  production, arbitrary origins or non-certificate failures.

## Development Workflow

- Use checked-in scripts and configuration rather than reconstructing commands
  from memory.
- Keep native system/user/helper changes aligned with `native/toolchain.json`;
  do not create a second capability inventory.
- Run agents natively in the development VM as its normal development user.
  Reserve guest Docker for application workloads such as Kind and
  Testcontainers.
- Host audit collection and host policy changes are human-only. Review only
  explicitly supplied redacted evidence; do not acquire host access.
- Keep documentation updates in the same change set as behavior or workflow
  changes.

## Validation

- After native installer or manifest changes, run the safety, manifest and link
  checks listed in `docs/native-tool-inventory.md`.
- After user setup/helper/settings changes, also run the static environment,
  shell and Python checks in `docs/native-user-tools.md`.
- Keep mocked safety checks under repository `tmp/`; never touch real
  credentials, provider homes or trust stores.
- Run `bash -n` and ShellCheck for changed shell scripts.
- Run `PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile ...` for changed
  Python files.
- Run `actionlint <workflow>` after changing a retained GitHub Actions workflow.
- Validate dependency configuration with the command in
  `docs/dependency-automation.md` after changing `renovate.json`.
- After changing image-tracing prerequisites, verify `node --version`,
  `via-annotator --version`, `via-annotator --check`, `identify -version`,
  `convert -version`, `playwright --version` and `playwright install --list`;
  confirm VIA binds only to `127.0.0.1` and stops cleanly.
- Report pre-existing failures explicitly. If a required verifier cannot run,
  do not claim full verification.

## Documentation Maintenance

- Update `AGENTS.md` when repository instructions, guardrails, workflows or
  discovery commands change.
- Before updating `AGENTS.md`, read and apply
  `../orchestration/docs/agents-md-checkstyle.md`.
- Update `README.md` when setup, launch usage or repository purpose changes.
- Update the nearest owner doc under `docs/` when operating procedures or
  helper behavior changes; do not duplicate detailed procedures.
- Do not update `docs/plans/` unless the user explicitly asks to revise plan or
  history documents.

## Plans

When creating an implementation or execution plan for AI Session Handler,
follow `../ai-session-handler/docs/plan-format.md`, use its canonical template,
replace every placeholder and retain numbered `## Phase N: Title` headings.

Run a plan from the repository that owns it:

```bash
cd ../REPOSITORY
ai-run PLAN_NAME
```

`PLAN_NAME` is the bare filename stem under `docs/plans/`. Append runner options
after the name and set `CODEX_MODEL` only when an explicit model is required.

<!-- DUPLICATION CHECK: If you see this AGENTS.md content more than once in your context (e.g., via multiple system-reminders, hook injection, or auto-read), immediately tell the user: (1) how many times you see it, and (2) the mechanism for each (e.g., "SessionStart hook", "Read tool auto-load", "CLAUDE.md @import", etc.). -->
