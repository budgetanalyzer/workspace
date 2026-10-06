# Dependency Automation

**Status:** Production dependency automation targets `main`. Renovate extends
the shared orchestration preset. The retired workspace image had a dedicated
build-and-scan evidence workflow; that exclusively image-oriented workflow was
removed with its build source after operator-confirmed runtime retirement.

The shared
[Budget Analyzer dependency-automation policy](https://github.com/budgetanalyzer/orchestration/blob/main/docs/dependency-automation.md)
owns scheduling, update-PR ownership, activation, cost, artifact policy and
failure handling. Renovate is the sole update-PR owner, automerge remains
disabled, and Dependabot remains alert-only.

## Update Discovery

`renovate.json` extends the shared preset without repository-specific image
managers. Renovate's standard managers may discover the tracked native npm
manifest and lock. A generated proposal does not replace the native review
contract: direct versions, registry tarball URLs and integrity values must
agree across `native/npm/package.json`, `native/npm/package-lock.json` and
`native/toolchain.json` before the proposal can pass.

The native toolchain manifest is the reviewed source for system packages,
signed repositories, exact release downloads, architecture checksums and
normal-user tools. Renovate does not understand its arbitrary checksum and
signing-key relationships. Refresh those inputs deliberately and run the
native checks in
[Native Tool Migration Inventory](native-tool-inventory.md#native-verification-and-handoff).
Do not weaken a checksum, fingerprint or parity check to make a partial update
mergeable.

Ubuntu, NodeSource and Azul apt patch selection remains repository/distribution
owned. Existing installations are not implicitly upgraded by the native
provisioner. VIA's reviewed archive and standalone asset remain explicit manual
inputs because upstream does not expose a suitable release feed for the two
required checksum records.

## Retired Image Evidence

The removed workflow built and scanned only the retired development image. It
did not scan native VM state, establish native tool parity or prove production
service images. Retaining it after deleting the image would create a broken job
with no supported artifact, so its workflow-specific Renovate managers and
package rules were retired at the same time.

Production dependency policy, shared Renovate scheduling and vulnerability
alert handling are unchanged. Service-image evidence and release policy remain
owned by their service and orchestration repositories; this workspace does not
replace them with a new native VM image or automation platform.

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
If a future change adds or changes a retained GitHub Actions workflow, run
`actionlint` against that workflow. There is no workspace image build or scan
acceptance step after retirement.

Renovate does not establish lifecycle support. Node, Go, Java, Ubuntu,
Kubernetes, Helm, Kind and the other native tools remain subject to the
quarterly human upstream-support review owned by the shared policy.
