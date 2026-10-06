# Local Budget Analyzer TLS Trust

The native workspace tools provide verified trust for the host-managed local
Budget Analyzer ingress. They do not generate certificates, inspect unrelated
CA material at startup or weaken HTTPS verification.

## Ownership And Flow

1. The personal host creates the local ingress certificate and retains the
   mkcert signing key.
2. The human transfers only the approved wildcard leaf, leaf key and public
   root to the guest orchestration checkout.
3. Orchestration validates those files and reconciles the Kubernetes TLS
   Secret; it does not write guest trust.
4. Workspace's human-only installer imports the approved public root into the
   guest system bundle and normal user's Chromium NSS database.
5. `ensure-budget-analyzer-local-ca-trust` and
   `check-budget-analyzer-local-ca-trust` perform read-only diagnosis.

The native environment sets `BUDGET_ANALYZER_WORKTREE_PARENT` to its reviewed
guest working-clone parent. Helpers resolve the orchestration publication under
that parent rather than relying on a fixed checkout location.

Before changing guest trust, the human installer verifies that the publication
is a current CA certificate and validates the orchestration-owned local
wildcard ingress certificate. A mismatched or stale publication fails with
host-side remediation instead of being trusted.

Native Playwright Chromium uses the launching user's NSS database at
`$HOME/.pki/nssdb` for locally added roots. Importing into a root-owned NSS
database would not establish browser trust for agent-run Chromium. Python,
requests and Node use the combined system bundle through the managed native
environment. Public roots are preserved; optional inspection trust remains
separate and process-scoped.

## Commands

Before live work against exactly
`https://app.budgetanalyzer.localhost`, or after a certificate-chain failure
for that origin, run:

```bash
ensure-budget-analyzer-local-ca-trust
```

For read-only diagnosis, run:

```bash
check-budget-analyzer-local-ca-trust
```

The verifier distinguishes publication, system-store, Python-bundle, and
Chromium/NSS failures. Both commands report the trusted SHA-256 fingerprint but
do not print certificate subject or issuer metadata.

The API-test live prerequisite path may invoke the ensure command
automatically only after its resolved configuration identifies a local
environment and the exact origin above. Do not invoke the command for aliases,
arbitrary HTTPS origins, staging, production, or public Internet trust errors.

## Missing Publication And Other Failures

If the publication is missing, invalid or stale, stop. Renew only on the
personal host using the established orchestration workflow, transfer the three
approved files again, validate them, and rerun the human guest import workflow.
Never run mkcert in the guest or copy the mkcert CA signing key.

A DNS failure, connection refusal, gateway readiness failure, or
authentication failure is not a reason to reinstall certificate trust. Fix
the reported prerequisite. Never use HTTP, `--insecure`, `verify=False`,
`ignore_https_errors`, or another certificate-verification bypass.

The commands use these exit statuses:

| Status | Meaning |
| --- | --- |
| `0` | Trust is current. |
| `10` | Host publication is missing. |
| `11` | Host publication is invalid or expired. |
| `12` | Required native tooling is missing. |
| `13` | System trust installation or verification failed. |
| `14` | Python is not configured for the combined system bundle. |
| `15` | Chromium/NSS trust installation or verification failed. |

## Native Development VM

The personal host alone owns the mkcert signing key and browser-certificate
generation. Orchestration validates the three transferred files and reconciles
the local Kubernetes TLS Secret. Workspace alone owns human-operated guest OS
and NSS trust installation plus read-only verification.

The native user environment points Python, requests and Node at the combined
system CA bundle while Chromium uses the same normal user's NSS database.
[Native user tools](native-user-tools.md#establish-exact-ingress-trust) owns the
exact human commands and verified curl/Python/Node/Chromium matrix.

The human runs `scripts/install-agent-vm-local-ca-trust.sh` from the guest OS
with the reviewed worktree/bare parents to import only the approved public
ingress root. It verifies CA validity and the exact local hostname/leaf before
explicit interactive sudo operations. The root signing key stays host-only.
The one workspace-managed system destination is
`/usr/local/share/ca-certificates/budget-analyzer-local-mkcert.crt`. During
convergence, the installer recognizes only the exact legacy
`budget-analyzer-local-ingress-ca.crt` path. Before removing that path it
requires a root-owned, non-symlink regular file with safe permissions and the
same SHA-256 certificate identity as the approved publication, then rechecks
the identity immediately before the exact removal. A different, invalid,
symlinked or unexpectedly owned legacy root stops for explicit private review;
the installer neither deletes it nor mutates another trust entry. Unrelated OS
roots and NSS entries are preserved.

Native `ensure-budget-analyzer-local-ca-trust` and `check-budget-analyzer-local-ca-trust`
are read-only diagnostics; missing/stale system or NSS trust prints the exact
human command. They also reject a remaining legacy duplicate, so success means
the canonical system source is the only workspace/orchestration-managed source
file. Neither invokes `sudo -n` nor generates a CA. Optional guest inspection
trust is separate, process-scoped and never imported system-wide or into NSS by
native installation. Public roots remain intact.

Run trust installation only from mutually reviewed workspace and orchestration
revisions after all affected workers have exited. Repository tests use
disposable paths and mocked system/NSS commands; source validation does not
establish live trust.
