# Lazy Local CA Trust Installation Plan

Provide an on-demand, idempotent workspace command that installs the
host-published Budget Analyzer mkcert root CA into the agent container's normal
system, Python, and Chromium trust paths. The devcontainer will include the
required tooling and stable trust-bundle configuration, but it will not require
the CA at startup. Agents working in `orchestration` or
`budget-analyzer-api-tests` will invoke the command only before exact-local live
HTTPS work or when diagnosing a certificate trust failure.

This workspace-owned plan implements Phase 2 of
[`verified-local-tls-agent-runner-prerequisite-plan.md`](../../../orchestration/docs/plans/verified-local-tls-agent-runner-prerequisite-plan.md).
The orchestration repository remains responsible for publishing only the
host's public `rootCA.pem`, and the API-test repository remains responsible for
calling this command from its local live-run prerequisite path.

Status: Phases 1 and 2 staged for host application under
`tmp/local-ca-trust-installation/proposed/`; Phase 3 requires applying the
sandbox patch, rebuilding the devcontainer image, and running live acceptance.

## Phase 1: Add The Lazy Trust Installer And Verifier

### Goal

Install the image-level dependencies and workspace-owned commands needed to
add or refresh the host-published public CA only when local Budget Analyzer
HTTPS access requires it.

### Scope

- Add `libnss3-tools` to `ai-agent-sandbox/Dockerfile` so `certutil` is
  available for the container user's Chromium/NSS trust database.
- Set `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt` in the image so
  Python/httpx uses the combined system bundle without requiring a caller to
  mutate its parent shell.
- Add `ai-agent-sandbox/scripts/ensure-budget-analyzer-local-ca-trust.sh` and
  install it on `PATH` as `ensure-budget-analyzer-local-ca-trust`.
- On explicit invocation, have the ensure command:
  - locate the deterministic publication at
    `/workspace/orchestration/nginx/certs/k8s/_mkcert-rootCA.pem`
  - fail with host-side remediation when the publication is missing
  - validate that the publication is a parseable CA certificate
  - install or refresh it under a stable filename in the container system
    trust store
  - run `update-ca-certificates` only when the installed CA changed
  - create or reuse the `vscode` user's applicable Chromium/NSS database
  - import or replace a fixed certificate nickname when the fingerprint
    changes
  - finish by verifying system, Python-bundle, and NSS trust state
- Add a read-only
  `ai-agent-sandbox/scripts/check-budget-analyzer-local-ca-trust.sh` command and
  install it on `PATH` as `check-budget-analyzer-local-ca-trust`.
- Keep both commands idempotent and return documented nonzero statuses for a
  missing publication, invalid CA, missing image dependency, failed system
  installation, or stale/failed NSS import.

### Non-goals

- Do not run either command automatically from the devcontainer entrypoint,
  startup hooks, shell initialization, or generic AI launchers.
- Do not generate, rotate, copy, mount, inspect, or name `rootCA-key.pem`.
- Do not run mkcert or orchestration certificate-generation scripts from the
  container.
- Do not replace the combined system bundle with an mkcert-only bundle.
- Do not add TLS bypass flags or Budget Analyzer behavior to unrelated proxy
  launchers.
- Do not modify the host-published CA file.

### Required context

- `AGENTS.md`
- `.devcontainer/devcontainer.json`
- `ai-agent-sandbox/docker-compose.yml`
- `ai-agent-sandbox/Dockerfile`
- `ai-agent-sandbox/entrypoint.sh`
- existing mitmproxy CA installation and environment behavior
- the orchestration publication contract in the cross-repository prerequisite
  plan

### Implementation notes

- Run system-store operations through narrow `sudo` calls while running NSS
  operations as the `vscode` user; importing into root's NSS database does not
  satisfy Playwright Chromium.
- Compare SHA-256 certificate fingerprints without printing subject or issuer
  metadata.
- Use temporary files and atomic replacement for container-local system trust
  updates.
- Preserve existing public roots and the mitmproxy CA.
- The ensure command may be called by the API-test prerequisite process, so
  keep stdout concise, never read unrelated environment variables, and never
  require an interactive prompt.
- Absence of the publication is an expected prerequisite stop. Its remediation
  must tell the user to run `./setup.sh` from the host orchestration checkout.

### Validation

```bash
docker compose -f ai-agent-sandbox/docker-compose.yml config
shellcheck ai-agent-sandbox/scripts/ensure-budget-analyzer-local-ca-trust.sh
shellcheck ai-agent-sandbox/scripts/check-budget-analyzer-local-ca-trust.sh
rg -n "ensure-budget-analyzer-local-ca-trust|check-budget-analyzer-local-ca-trust|SSL_CERT_FILE|libnss3-tools" \
  ai-agent-sandbox/Dockerfile ai-agent-sandbox/scripts
```

Build a fresh devcontainer image and confirm both commands are on `PATH`,
`certutil` is available, and `SSL_CERT_FILE` resolves to the combined system
bundle. With the orchestration publication temporarily unavailable, confirm
the ensure command fails with the documented host remediation and makes no
trust-store changes.

### Completion criteria

- A rebuilt agent image contains `certutil`, the stable Python trust-bundle
  environment, the lazy ensure command, and the read-only verifier.
- The commands are safe to run repeatedly and refresh stale trust after host CA
  rotation.
- Missing or invalid publication fails clearly without an insecure fallback.
- Container startup and unrelated offline agent work do not require the local
  CA or a running Budget Analyzer stack.
- No private CA material enters the image, container trust stores, output, or
  repository.

## Phase 2: Document The Agent-Invoked Trust Workflow

### Goal

Make the lazy command discoverable to agents working on the two repositories
that currently require verified access to the local Budget Analyzer ingress.

### Scope

- Update workspace `AGENTS.md` with a narrow local-TLS workflow:
  - before live work against exactly
    `https://app.budgetanalyzer.localhost`, or after a trust-chain failure for
    that origin, run `ensure-budget-analyzer-local-ca-trust`
  - if publication is missing, stop and ask the user to run orchestration
    `./setup.sh` on the host
  - use `check-budget-analyzer-local-ca-trust` for read-only diagnosis
  - never use `verify=False`, `--insecure`, `ignore_https_errors`, HTTP, or
    in-container certificate generation
- Update `README.md` or the nearest workspace trust documentation with the
  host-publication to lazy-container-install flow and command examples.
- Document that the API-test prerequisite path may invoke the ensure command
  automatically for the exact local target.
- Keep detailed command behavior in one workspace-owned document and link to
  it from sibling plans or repository instructions rather than duplicating the
  implementation contract.

### Non-goals

- Do not instruct agents to run the ensure command for arbitrary HTTPS,
  staging, production, or public Internet certificate failures.
- Do not make startup dependent on the orchestration checkout or published CA.
- Do not claim that environment variables or local trust material are hidden
  from the trusted agent container.
- Do not update sibling repository implementation code from this phase.

### Required context

- completed Phase 1
- `AGENTS.md`
- `README.md`
- `docs/traffic-inspection.md`
- orchestration and API-test repository agent instructions concerning TLS

### Implementation notes

- Keep `AGENTS.md` guidance short and pattern-based. Link to the workspace
  trust documentation for command behavior and troubleshooting.
- Distinguish a certificate trust failure from DNS failure, connection refusal,
  gateway readiness, and authentication failures.
- State explicitly that host certificate setup remains host-only even though
  installing its public root into container-local trust is permitted.

### Validation

```bash
rg -n "ensure-budget-analyzer-local-ca-trust|check-budget-analyzer-local-ca-trust" \
  AGENTS.md README.md docs ai-agent-sandbox
rg -n "verify=False|ignore_https_errors|--insecure" AGENTS.md README.md docs
```

Review the rendered workflow and confirm an agent can distinguish:

1. missing host publication requiring user action on the host;
2. present publication requiring the lazy container ensure command; and
3. a non-certificate prerequisite that must not trigger TLS workarounds.

### Completion criteria

- Workspace guidance names the lazy ensure and read-only verifier commands.
- Guidance limits automatic or agent-invoked installation to the exact local
  Budget Analyzer origin.
- Host-only generation and container-local public trust installation have
  distinct ownership and remediation.
- Documentation contains no restart requirement after ordinary CA publication
  or rotation.

## Phase 3: Prove Lazy Trust Against The Host-Managed Local Stack

### Goal

Verify that a running agent container can consume a newly published or rotated
host CA without a container restart and can then reach the local ingress using
normal verification paths.

### Scope

- Confirm the host-published CA and wildcard ingress certificate are present
  through the existing shared workspace mount.
- Run the ensure command in an already-running container.
- Prove system/curl, Python/httpx, and Playwright Chromium trust without bypass
  options.
- Run the ensure command and verifier again to prove idempotency.
- Rotate or replace the public CA only through the host-owned orchestration
  workflow when rotation testing is explicitly authorized, then prove lazy
  refresh without rebuilding or restarting the container.
- Record missing credentials or application assertion failures separately from
  certificate trust acceptance.

### Non-goals

- Do not run host certificate generation, Kind recreation, or Tilt startup
  from the agent container.
- Do not require authenticated API-test credentials for the public TLS proof.
- Do not mutate staging or production or supply their credentials to the
  container.
- Do not bypass TLS while diagnosing an acceptance failure.

### Required context

- completed Phases 1 and 2
- completed orchestration CA publication phase
- healthy host-managed Tilt/Kind local stack
- exact local origin `https://app.budgetanalyzer.localhost`

### Implementation notes

- Host-side acceptance must first prove the active context is `kind-kind` and
  the expected Kind cluster is named `kind`.
- In-container acceptance must use the existing local-target safety checks
  before any authorized cluster inspection.
- Compare fingerprints rather than printing certificate subject or issuer
  fields.

### Validation

In the already-running agent container:

```bash
ensure-budget-analyzer-local-ca-trust
check-budget-analyzer-local-ca-trust
openssl verify \
  -CAfile /etc/ssl/certs/ca-certificates.crt \
  ../orchestration/nginx/certs/k8s/_wildcard.budgetanalyzer.localhost.pem
curl --fail-with-body https://app.budgetanalyzer.localhost/
python -c 'import httpx; print(httpx.get("https://app.budgetanalyzer.localhost/api/v1/currencies").status_code)'
```

Run an uncredentialed Playwright navigation to the exact local origin without
`ignore_https_errors`, then rerun both workspace commands. Confirm public
Internet HTTPS still validates through curl and Python.

### Completion criteria

- The public CA becomes trusted in an already-running container through one
  explicit, idempotent ensure invocation.
- Curl, Python/httpx, and Playwright Chromium validate the local ingress.
- Public Internet certificates remain trusted.
- Repeated ensures make no unnecessary changes, and an authorized host CA
  rotation can be refreshed without a container rebuild or restart.
- The result is ready for the API-test local preflight/bootstrap path to invoke
  automatically.
