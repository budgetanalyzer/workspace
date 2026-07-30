# Local Budget Analyzer TLS Trust

The workspace image provides lazy, verified trust for the host-managed local
Budget Analyzer ingress. It does not generate certificates, inspect local CA
material at startup, or weaken HTTPS verification.

## Ownership And Flow

1. The user runs orchestration `./setup.sh` on the host.
2. Orchestration publishes only its public mkcert root at
   `../orchestration/nginx/certs/k8s/_mkcert-rootCA.pem` in the shared workspace.
3. A rebuilt workspace image provides
   `ensure-budget-analyzer-local-ca-trust` and
   `check-budget-analyzer-local-ca-trust` on `PATH`.
4. The ensure command installs or refreshes that public root in the combined
   system bundle and the `vscode` user's Chromium NSS database only when the
   command is explicitly invoked.

Before changing container trust, the command verifies that the publication is
a current CA certificate and that it validates the orchestration-owned local
wildcard ingress certificate. A mismatched or stale publication fails with
host-side remediation instead of being trusted.

The Linux Playwright Chromium bundled in this image uses the launching user's
NSS database at `$HOME/.pki/nssdb` for locally added roots. Importing into a
root-owned NSS database would not establish browser trust for agent-run
Chromium. Python clients use the existing combined system bundle through the
image-level `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt` setting. These
additions preserve public roots and the existing mitmproxy CA.

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

If the publication is missing, invalid, or stale, stop and ask the user to run
orchestration `./setup.sh` on the host. Do not run mkcert or orchestration
certificate setup from the container. After the image has been rebuilt once
to add the commands and NSS tooling, ordinary host CA publication or rotation
requires only another ensure invocation, not a container restart.

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
| `12` | Required image tooling is missing. |
| `13` | System trust installation or verification failed. |
| `14` | Python is not configured for the combined system bundle. |
| `15` | Chromium/NSS trust installation or verification failed. |
