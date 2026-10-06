# Dependency Automation

Renovate targets `main` and extends the shared orchestration preset. The shared
[Budget Analyzer dependency-automation policy](https://github.com/budgetanalyzer/orchestration/blob/main/docs/dependency-automation.md)
owns scheduling, update-PR ownership, activation, cost, artifact policy and
failure handling. Renovate is the sole update-PR owner, automerge remains
disabled, and Dependabot remains alert-only.

## Update Discovery

`renovate.json` uses the shared preset without repository-specific managers.
Renovate's standard managers may discover the tracked native npm manifest and
lock. A generated proposal does not replace the native review contract: direct
versions, registry tarball URLs and integrity values must agree across
`native/npm/package.json`, `native/npm/package-lock.json` and
`native/toolchain.json` before the proposal can pass.

The native toolchain manifest is the reviewed source for system packages,
signed repositories, exact release downloads, architecture checksums and
normal-user tools. Renovate does not understand its arbitrary checksum and
signing-key relationships. Refresh those inputs deliberately and run the
native checks in
[Native Tool Inventory](native-tool-inventory.md#native-verification).
Do not weaken a checksum, fingerprint or parity check to make a partial update
mergeable.

Ubuntu, NodeSource and Azul apt patch selection remains
repository/distribution owned. Existing installations are not implicitly
upgraded by the native provisioner. VIA's reviewed archive and standalone asset
remain explicit manual inputs because upstream does not expose a suitable
release feed for the two required checksum records.

Production dependency policy, shared Renovate scheduling and vulnerability
alert handling are unchanged. Service-image evidence and release policy remain
owned by their service and orchestration repositories.

## Validation

Run these checks after changing workspace dependency discovery:

```bash
NPM_CONFIG_CACHE=tmp/renovate-npm-cache \
  npx --yes --package renovate@44.65.5 renovate-config-validator --strict renovate.json
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_install_inputs.py --publication proposed
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_manifest.py
git diff --check
```

Use `--publication committed` only after the reviewed native lock and related
inputs exist in `HEAD`; that mode validates a real `git archive HEAD` transfer.
If a GitHub Actions workflow changes, run `actionlint` against it.

Renovate does not establish lifecycle support. Node, Go, Java, Ubuntu,
Kubernetes, Helm, Kind and the other native tools remain subject to the
quarterly human upstream-support review owned by the shared policy.
