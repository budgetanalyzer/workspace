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
4. Workspace's human-only installer receives the public root and current leaf
   as explicit `--ca-file` and `--leaf-file` inputs, imports the root into the
   guest system bundle and normal user's Chromium NSS database, and then
   records it as the approved root under the native root.
5. `ensure-budget-analyzer-local-ca-trust` and
   `check-budget-analyzer-local-ca-trust` perform read-only store diagnosis
   against that record.
6. The human opens exactly `https://app.budgetanalyzer.localhost` in the
   normal Workspace Chromium as the browser acceptance check.

Certificate creation, artifact transfer, guest trust, and browser transport
are distinct concerns. This document owns the first three; the explicit
personal-host-to-VM SSH transport is owned by
[Personal-Host Access](host-isolation.md#personal-host-access). Establishing a
host tunnel neither creates nor repairs certificate trust.

There is no personal-host Kind cluster or "host container" in this flow. Kind,
Tilt, the ingress listener and the Kubernetes TLS Secret all live in the
development VM. The personal host retains the mkcert CA signing key because it
also owns browser trust. The VM receives only these three ignored files:

| Artifact | Personal host | Development VM |
| --- | --- | --- |
| mkcert CA signing key | Retained in the host mkcert store | Never copied |
| Public CA | Trusted by the host browser and staged for transfer | Checkout publication, OS/NSS trust and workspace approved-root record |
| Wildcard leaf | Staged for transfer | Checkout publication and Kubernetes TLS Secret |
| Wildcard leaf key | Staged for transfer | Mode `0600` checkout publication and Kubernetes TLS Secret |

### Transfer The Three Published Files

Git intentionally does not carry these files. After workspace repository setup
has established the reviewed `budget-agent-vm` SSH alias, the human may stage
the exact three files from the personal-host orchestration checkout:

```bash
ssh budget-agent-vm 'install -d -m 0700 "$HOME/.cache/budget-analyzer-tls-transfer"'
scp \
  nginx/certs/k8s/_wildcard.budgetanalyzer.localhost.pem \
  nginx/certs/k8s/_wildcard.budgetanalyzer.localhost-key.pem \
  nginx/certs/k8s/_mkcert-rootCA.pem \
  budget-agent-vm:.cache/budget-analyzer-tls-transfer/
```

Then, from the normal-user guest shell with the managed environment loaded:

```bash
transfer_dir="$HOME/.cache/budget-analyzer-tls-transfer"
cert_dir="$BUDGET_ANALYZER_WORKTREE_PARENT/orchestration/nginx/certs/k8s"
install -m 0644 "$transfer_dir/_wildcard.budgetanalyzer.localhost.pem" "$cert_dir/"
install -m 0600 "$transfer_dir/_wildcard.budgetanalyzer.localhost-key.pem" "$cert_dir/"
install -m 0644 "$transfer_dir/_mkcert-rootCA.pem" "$cert_dir/"
rm -f \
  "$transfer_dir/_wildcard.budgetanalyzer.localhost.pem" \
  "$transfer_dir/_wildcard.budgetanalyzer.localhost-key.pem" \
  "$transfer_dir/_mkcert-rootCA.pem"
```

The existing pre-migration files are valid migration inputs when
orchestration's `install-imported-ingress-tls.sh --validate-only` accepts them.
Do not rotate a working CA merely because Kind moved into the VM. For a fresh
or stale host publication, the human runs orchestration
`scripts/bootstrap/setup-k8s-tls.sh` on the personal host; that command prepares
browser trust and transfer files without accessing Kubernetes.

Workspace trust code never reads an application checkout. The human passes
the published files explicitly; the documented command uses orchestration's
published locations under `$BUDGET_ANALYZER_WORKTREE_PARENT`, described in
orchestration's
[host-published local ingress CA](../../orchestration/docs/development/local-environment.md#host-published-local-ingress-ca)
guide.

Before changing guest trust, the human installer verifies that the supplied
root contains no private key, is a current CA certificate and verifies the
supplied unexpired leaf for exactly `app.budgetanalyzer.localhost`. The leaf
must contain no private key either. A mismatched or stale publication fails
with host-side remediation instead of being trusted. Only after the system and
NSS imports and the post-import store checks succeed does the installer write
the approved public root to
`$HOME/.local/share/budget-analyzer-native/trust/approved-local-root.pem`
(mode `0600` in a mode `0700` directory, like other native-root state). A
failed installation leaves any earlier record unchanged and never writes a
first one.

## Installation And Renewal Sequence

Run this sequence after the first transfer and again after every certificate
renewal; a renewed root is not trusted until the human reruns the installer.

1. Transfer the three files and validate them with orchestration
   `install-imported-ingress-tls.sh --validate-only`.
2. Run the human installer with explicit inputs, as documented in
   [Establish Exact Ingress Trust](native-user-tools.md#establish-exact-ingress-trust).
3. Store check: `check-budget-analyzer-local-ca-trust` verifies that the OS
   source, combined bundle and NSS database trust the recorded root and that
   the record has not expired. It reports store state only. It does not read
   the current leaf and cannot tell whether the running application serves a
   certificate from that root.
4. Supplied-leaf/system-trust check: orchestration
   `scripts/bootstrap/check-tilt-prerequisites.sh` verifies the supplied
   current ingress leaf against the system bundle. It neither proves browser
   trust nor inspects the certificate actually served by ingress.
5. Browser acceptance: with the application running, open exactly
   `https://app.budgetanalyzer.localhost` in the normal Workspace
   Chromium/Playwright browser, which uses `$HOME/.pki/nssdb`. A successful
   HTTPS load with no certificate exception, `ignoreHTTPSErrors` or other
   verification bypass is required. Use the Chromium probe in
   [native user tools](native-user-tools.md#browser-acceptance-check).

Only step 5 is browser acceptance. Successful store or supplied-leaf checks
alone are not. For example, if the system bundle trusts roots A and B, NSS
trusts only A, and the application serves a leaf from root B, curl, Python and
the supplied-leaf check can pass while Chromium rejects the site. That state is
not browser-ready, and only the browser check exposes it.

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

The verifier distinguishes approved-root record, system-store, Python-bundle,
and Chromium/NSS failures. Both commands report the recorded SHA-256
fingerprint but do not print certificate subject or issuer metadata. They take
no certificate paths, read no application checkout and report store state, not
browser acceptance.

The API-test live prerequisite path may invoke the ensure command
automatically only after its resolved configuration identifies a local
environment and the exact origin above. Do not invoke the command for aliases,
arbitrary HTTPS origins, staging, production, or public Internet trust errors.

## Missing Publication And Other Failures

A missing approved-root record fails closed and prints the human installer
command with `CA_PEM` and `LEAF_PEM` placeholders. If the publication is
missing, invalid or stale, or the recorded root has expired, stop. Prepare or renew it only
on the personal host using the established orchestration workflow, transfer the
three approved files again, validate them, and rerun the human guest import
workflow.
Never run mkcert in the guest or copy the mkcert CA signing key.

A DNS failure, connection refusal, gateway readiness failure, or
authentication failure is not a reason to reinstall certificate trust. Fix
the reported prerequisite. Never use HTTP, `--insecure`, `verify=False`,
`ignore_https_errors`, or another certificate-verification bypass.

The commands use these exit statuses:

| Status | Meaning |
| --- | --- |
| `0` | Trust is current. |
| `10` | Supplied publication file or approved-root record is missing. |
| `11` | Supplied publication or recorded root is invalid or expired. |
| `12` | Required native tooling is missing. |
| `13` | System trust installation or verification failed. |
| `14` | Python is not configured for the combined system bundle. |
| `15` | Chromium/NSS trust installation or verification failed. |
| `16` | Approved-root record path is a symlink or has unsafe ownership/permissions. |

## Native Development VM

The personal host alone owns the mkcert signing key and browser-certificate
generation. Host certificate preparation does not require Kind. Orchestration
validates the three transferred files and reconciles the local Kubernetes TLS
Secret. Workspace alone owns human-operated guest OS
and NSS trust installation plus read-only verification.

The native user environment points Python, requests and Node at the combined
system CA bundle while Chromium uses the same normal user's NSS database.
[Native user tools](native-user-tools.md#establish-exact-ingress-trust) owns the
exact human commands and verified curl/Python/Node/Chromium matrix.

The human runs `scripts/install-agent-vm-local-ca-trust.sh` from the guest OS
with the reviewed worktree/bare parents and explicit `--ca-file` and
`--leaf-file` inputs to import only the approved public ingress root. The
hostname is fixed at `app.budgetanalyzer.localhost`. It verifies CA validity
and the exact local hostname/leaf, anchored only at the supplied root, before
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
are read-only diagnostics against the recorded approved root; a missing
record or missing/stale system or NSS trust prints the human command. They also reject a remaining legacy duplicate, so success means
the canonical system source is the only workspace/orchestration-managed source
file. Neither invokes `sudo -n` nor generates a CA. Optional guest inspection
trust is separate, process-scoped and never imported system-wide or into NSS by
native installation. Public roots remain intact.

The canonical `scripts/check-agent-vm-tools.sh` native runtime verifier invokes
the installed read-only trust check as part of its `extras` component. It does
not import or repair trust. Installing the trust helpers does not require trust
to be established yet. Its stable invocation and complete scope are documented in
[Native Guest User Tools](native-user-tools.md#canonical-read-only-native-runtime-contract).
Orchestration remains responsible for validating imported ingress files and
reconciling the Kubernetes TLS Secret.

Run trust installation only from a reviewed workspace revision, with
reviewed supplied files, after all affected workers have exited. Repository tests use
disposable paths and mocked system/NSS commands; source validation does not
establish live trust.
