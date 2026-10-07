# Dependency Automation

Renovate targets `main` and extends the shared orchestration preset. The shared
[Budget Analyzer dependency-automation policy](https://github.com/budgetanalyzer/orchestration/blob/main/docs/dependency-automation.md)
owns scheduling, update-PR ownership, activation, cost, artifact policy and
failure handling. Renovate is the sole update-PR owner, automerge remains
disabled, and Dependabot remains alert-only.

## Update Discovery

`renovate.json` keeps the standard npm manager for `native/npm/package.json`
and its lockfile. Narrow regex custom managers extract only the owning object
and version field for native declarations with a trustworthy standard
datasource. Every external dependency declaration in `native/toolchain.json`
has exactly one discovery or review owner in this matrix; helpers and
`reviewed_sources` are workspace source mappings, not external dependencies.

| Manifest declaration | Discovery or review owner | Renovate identity / review boundary |
| --- | --- | --- |
| `user_tools` npm entries: Claude Code, Codex CLI, Gemini CLI and Playwright | npm discovery | Package names from `native/npm/package.json`; the npm manager also updates the lockfile |
| `downloads`: kubectl, Helm, Tilt, Kind and actionlint | Custom standard-datasource discovery | `kubernetes/kubernetes`, `helm/helm`, `tilt-dev/tilt`, `kubernetes-sigs/kind` and `rhysd/actionlint` through GitHub Releases |
| `downloads.go` | Custom standard-datasource discovery | `go` through `golang-version` |
| `user_tools.mitmproxy` | Custom standard-datasource discovery | `mitmproxy` through PyPI |
| `repositories.nodesource` Node major | Custom standard-datasource discovery | `node` through `node-version`; the signed NodeSource repository selects the available patch and its key, policy and lifecycle companions remain reviewed together |
| `os`, `apt`, `chromium_apt` and `repositories.azul` | Signed-repository/distribution selection | Ubuntu 24.04 and the declared Zulu major remain human-reviewed repository/lifecycle inputs; installed patches are retained |
| `downloads.via` and `user_tools.ai-session-handler` | Explicit manual review | No suitable complete standard feed or immutable package identity covers the reviewed archive/asset relationship or editable guest checkout |
| `user_tools.chromium` | Explicit manual review | This is a Playwright-derived selection reviewed with the Playwright npm update, not a second Renovate dependency |

Checksums, architecture URLs, validation patterns, versioned destinations and
repository signing-key fingerprints are companion fields of the owning
dependency above, not additional dependency identities. Their explicit review
remains mandatory even when Renovate discovers the version.

The custom managers preserve the Dockerfile-era coverage for Go, Helm, kubectl,
Tilt, Kind, actionlint, mitmproxy and Node against current native declarations.
They do not reopen the retired Ubuntu-container or Docker-in-Docker proposals,
or the deleted workflow-only `setup-trivy` proposal. A Mend run after
publication is expected to create replacement proposals against the current
native declarations when newer releases exist.

## Review Incomplete Proposals

Renovate changes only the extracted version for downloaded tools. Those
kubectl, Helm, Tilt, Kind, actionlint and Go proposals are Dependency Dashboard
approval-gated and labelled `checksum-required`. Before approval and merge,
review and update both architecture URLs and SHA-256 values, ARM64 availability,
the validation pattern, the versioned destination where applicable, lifecycle
compatibility and any orchestration version/checksum contract. Renovate does
not generate or guess checksums, fingerprints, architecture support or
compatibility. The native checks intentionally reject the bot's initial
version-only edit; never weaken them to make that partial proposal pass.

An npm proposal is also discovery rather than a complete reviewed refresh.
Direct versions, every affected lock entry, registry tarball URLs, integrity
values and `native/toolchain.json` must agree before merge. A Playwright change
must additionally refresh the manifest's Chromium package-source and derived
selection records. Ordinary npm proposals remain enabled and major updates
retain the shared Dashboard-approval policy.

A Node-major proposal must keep the NodeSource source, both repository policy
records and native runtime checks aligned. NodeSource and Azul apt patch
selection remains repository-owned, and existing installations are not
implicitly upgraded by the provisioner. VIA's archive, per-architecture
checksum and standalone asset checksum remain manual because upstream does not
provide a suitable standard feed for the complete reviewed relationship.

Run the native checks in
[Native Tool Inventory](native-tool-inventory.md#native-verification) after a
refresh. Do not weaken a checksum, fingerprint, lock-closure or parity check to
make a partial update mergeable.

Production dependency policy, shared Renovate scheduling and vulnerability
alert handling are unchanged. Service-image evidence and release policy remain
owned by their service and orchestration repositories.

## Hosted Native Evidence

`.github/workflows/native-dependency-validation.yml` is the active
repository-input evidence workflow. It runs for relevant pushes to `main`,
same-repository pull requests targeting `main`, a bounded Monday schedule and
manual dispatch. It has only `contents: read`, uses the Node 24 action baseline
and never invokes a provisioner, `sudo`, Docker, Kind, Tilt, trust installation
or a self-hosted runner.

The job runs the strict pinned Renovate validator and the standalone,
workspace-owned offline native validation contract, including committed-source
lock closure. Sibling orchestration contract parity remains part of local
native validation and is intentionally excluded from hosted CI. The job then
downloads every `native/toolchain.json` public release asset for both `amd64`
and `arm64` into temporary storage, verifies each declared SHA-256 and checks
safe archive shape where installation extracts an archive. It never executes
an opposite-architecture artifact or installs a downloaded tool. The verified
runner-native actionlint archive is used only from temporary storage to lint
this workflow.

The one seven-day artifact has an explicit file allowlist:

- overall and source-validation status;
- per-tool/per-architecture release checksum and archive results;
- full and production-only npm audit JSON plus audit classification status;
- tool/input metadata containing the explicit manual-lifecycle inventory,
  including signed-repository companions and the Playwright-derived Chromium
  selection.

The upload runs under `if: always()` with `if-no-files-found: error`. Downloaded
binaries, npm/Renovate caches, repository archives, credentials and arbitrary
workspace paths are not upload inputs. Redirect query strings are removed from
retained release URLs so temporary upstream signatures are not evidence.
Vulnerability findings in a valid npm audit report remain visible and do not
fail the run; malformed JSON, contradictory audit exit status, download or
checksum failure, incomplete architecture coverage and missing evidence do.

This evidence proves checked-in structure, npm lock closure, public release
checksums and completed dependency audits. It does not inspect or mutate the
development VM, attest installed apt patch levels or establish upstream
lifecycle support. Ubuntu, signed-repository package selection, VIA and other
manual-lifecycle inputs remain human review responsibilities.

## Validation

Run these checks after changing workspace dependency discovery:

```bash
NPM_CONFIG_CACHE=tmp/renovate-npm-cache \
  npx --yes --package renovate@44.65.5 renovate-config-validator \
  --strict --no-global renovate.json
NPM_CONFIG_CACHE=tmp/renovate-npm-cache \
RENOVATE_CACHE_DIR=tmp/renovate-cache \
LOG_LEVEL=debug \
  npx --yes --package renovate@44.65.5 renovate \
  --platform=local --dry-run=full
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_install_inputs.py --publication proposed
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_manifest.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest discover -s tests/native -v
PYTHONPYCACHEPREFIX=tmp/pycache python3 scripts/native/verify_release_inputs.py \
  --manifest native/toolchain.json \
  --output tmp/native-release-validation/release-verification.json \
  --download-dir tmp/native-release-validation/downloads
actionlint .github/workflows/native-dependency-validation.yml
git diff --check
```

The dry run must extract the four direct npm packages and exactly these custom
identities: `kubernetes/kubernetes`, `helm/helm`, `tilt-dev/tilt`,
`kubernetes-sigs/kind`, `rhysd/actionlint`, `go`, `mitmproxy` and `node`.
Container-image, Docker feature and retired action records must remain absent.
Keep any redirected debug log and all Renovate/npm caches under `tmp/`.

Run the npm audit equivalents from the committed lock without installing
packages or running lifecycle scripts. npm uses exit 1 for valid reports that
contain findings, so validate the JSON before classifying that result:

```bash
mkdir -p tmp/native-dependency-audit
set +e
(cd native/npm && npm audit --json --package-lock-only --ignore-scripts) \
  > tmp/native-dependency-audit/full.json
full_status=$?
(cd native/npm && npm audit --json --package-lock-only --ignore-scripts --omit=dev) \
  > tmp/native-dependency-audit/production.json
production_status=$?
set -e
for report in \
  tmp/native-dependency-audit/full.json \
  tmp/native-dependency-audit/production.json; do
  jq -e '.auditReportVersion and (.metadata.vulnerabilities.total | type == "number")' \
    "${report}" > /dev/null
done
test "${full_status}" -le 1
test "${production_status}" -le 1
```

For exit 1, require a positive `.metadata.vulnerabilities.total`; otherwise
treat the audit as an operational failure. The workflow additionally bounds
report size and records a separate status for each audit scope.

Use `--publication committed` only after the reviewed native lock and related
inputs exist in `HEAD`; that mode validates a real `git archive HEAD` transfer.
If a GitHub Actions workflow changes, run `actionlint` against it.

Renovate does not establish lifecycle support. Node, Go, Java, Ubuntu,
Kubernetes, Helm, Kind and the other native tools remain subject to the
quarterly human upstream-support review owned by the shared policy.

## Post-Publication Acceptance

These are human-only hosted checks. Perform them after publishing the reviewed
commit; local validation and historical Actions runs do not satisfy them.

1. Trigger or await a Mend Renovate run for the default branch. In the
   Dependency Dashboard, require the four npm identities (`@anthropic-ai/claude-code`,
   `@openai/codex`, `@google/gemini-cli`, and `playwright`) and all eight custom
   identities (`kubernetes/kubernetes`, `helm/helm`, `tilt-dev/tilt`,
   `kubernetes-sigs/kind`, `rhysd/actionlint`, `go`, `mitmproxy`, and `node`) to
   be present without extraction or lookup errors.
2. When updates exist, require new branches and pull requests to modify
   `native/npm/package.json`, its lockfile, or `native/toolchain.json` as
   appropriate. Do not reopen or reuse an autoclosed Dockerfile-era branch, and
   reject a replacement proposal that targets deleted container or workflow
   paths.
3. Confirm checksum-coupled proposals remain Dashboard approval-gated and that
   version-only edits fail the native companion-field checks until both
   architecture URLs/checksums, validation patterns and any versioned
   destination or orchestration contract are reviewed and updated.
4. Trigger or observe `Native Dependency Validation` on the published commit.
   Require the hosted run to complete using no repository secret, then download
   its single seven-day artifact and inspect all seven allowlisted JSON files.
   Require `overall-status.json` and each component status to be complete, all
   fourteen release records to be verified across `amd64` and `arm64`, both npm
   audit reports to be valid, and the complete manual-lifecycle inventory to be
   present.

A failed hosted extraction, a missing Dashboard identity, an incomplete or
missing artifact, or a replacement pull request that bypasses companion-field
checks leaves the rollout incomplete. Correct the owning configuration,
workflow or proposal and repeat acceptance; do not waive the failed control.
