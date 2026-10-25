# Playwright 1.64.1 Reviewed Companion Refresh

Complete Renovate PR #51 (`renovate/playwright-monorepo`, Playwright 1.63.0 -> 1.64.1) as a
review-complete refresh so `Native Dependency Validation` passes without weakening any check.

Diagnosis (2026-10-25):

- The PR's only CI run (Actions run #30) failed two steps. `Validate committed native sources`
  fails by design: `tests/native/check_install_inputs.py` and `scripts/native/user_tools.py`
  require `chromium_apt_source` in `native/toolchain.json` to name the locked `playwright-core`
  version, and it still says `playwright-core 1.63.0`. `Verify both architecture release inputs`
  fails because the branch is based on an old `main` that still declares Go 1.24.1. `main` has
  passed since `pin ubuntu 24.04 (#56)` and now declares Go 1.27.3.
- Upstream `packages/playwright-core/src/server/registry/nativeDeps.ts` is byte-identical at
  `v1.63.0` and `v1.64.1`. Its `ubuntu24.04-x64` `tools` + `chromium` lists (33 packages) exactly
  match the current `chromium_apt`, and `ubuntu24.04-arm64` copies the x64 lists. The package list
  is expected to stay unchanged; only the reviewed provenance text needs the new version.
- The lock change also invalidates reviewed literals: the lock SHA-256 pinned in
  `tests/native/test_install_inputs.py` and `docs/native-user-tools.md`, and version-specific
  fixtures in `tests/native/test_install_inputs.py` and `tests/native/test_user_tools.py`.
- `renovate.json` deliberately leaves ordinary Playwright npm proposals ungated and adds review
  notes; `docs/dependency-automation.md` documents that policy. Changing Dashboard approval is out
  of scope for this plan.

Human prerequisite before Phase 1 (personal host; agents must not do this): rebase PR #51 onto
current `main` (Renovate rebase checkbox), fetch it, push it to the VM remote and switch the guest
`workspace` clone to `renovate/playwright-monorepo` per `docs/host-isolation.md#branch-transfer`.

Safety and scope: write only inside this repository and keep downloads and scratch files under
`tmp/`. Run no Git write commands; the human commits, transfers and pushes the result. Do not run
the provisioner, user installer or `npm install` against `native/npm`. Do not touch provider homes
or trust stores. Never weaken the provenance, lock-closure, integrity or checksum checks. Follow
`docs/dependency-automation.md` and `docs/native-user-tools.md`.

## Phase 1: Review And Apply Playwright 1.64.1 Companion Inputs

### Workspace

.

### Goal

Verify the Renovate lock and upstream Chromium native dependencies for 1.64.1. Then update
`chromium_apt_source`, the reviewed lock hash and the version-specific test fixtures so focused
native checks pass.

### Scope

- `native/toolchain.json` (`chromium_apt_source`; `chromium_apt` only if upstream differs)
- `tests/native/test_install_inputs.py`
- `tests/native/test_user_tools.py`
- `docs/native-user-tools.md` (reviewed lock SHA-256)

### Non-goals

- Editing `native/npm/package.json` or `native/npm/package-lock.json`; Renovate owns those and they
  are verified, not regenerated.
- Changing `renovate.json`, Dashboard approval policy or any validator logic.
- Refactoring tests to derive versions dynamically.
- Running full suites, which belong to Phase 2.

### Required context

- `docs/dependency-automation.md#review-incomplete-proposals`
- `docs/native-user-tools.md` (Installed Capabilities)
- `docs/native-tool-inventory.md`
- `tests/native/check_install_inputs.py`, `scripts/native/user_tools.py` (provenance checks)

### Execution steps

1. Read-only state check. Confirm `git merge-base --is-ancestor origin/main HEAD` succeeds, both
   npm files declare `1.64.1`, and `native/toolchain.json` declares Go `1.27.3`. If any of these
   fails, stop and report that the human prerequisite rebase or transfer is incomplete.
2. Verify the lock against the registry. Compare `npm view playwright@1.64.1 dist.integrity
   dist.tarball dependencies --json` and `npm view playwright-core@1.64.1 dist.integrity
   dist.tarball --json` with the lock's `resolved` and `integrity` entries. Use
   `NPM_CONFIG_CACHE=tmp/npm-cache`. Expected: `playwright` depends on exactly
   `playwright-core 1.64.1`, the lock has exactly those two packages, and both integrity values
   match. Stop on any mismatch.
3. Download upstream `packages/playwright-core/src/server/registry/nativeDeps.ts` for tags
   `v1.63.0` and `v1.64.1` into a new, empty `tmp/playwright-native-deps/`. Treat them as data. In a
   separate `tmp/` script run with `python3 -I`, compare `ubuntu24.04-x64` `tools` + `chromium`
   against `chromium_apt`, and confirm `ubuntu24.04-arm64` still copies the x64 lists. If upstream
   changed, set `chromium_apt` to the exact upstream union in upstream order and record the delta
   for the final report.
4. In `native/toolchain.json`, change `chromium_apt_source` from `playwright-core 1.63.0` to
   `playwright-core 1.64.1` and leave the rest of the text unchanged.
5. Compute `sha256sum native/npm/package-lock.json` (expected
   `b9a22b8f4376aba7d70c792a9ac2c98ed28545fc32e62d4376fc10c88923dd05`). Replace the old
   `a9a9e5ba...` value in `tests/native/test_install_inputs.py`
   (`test_reviewed_source_is_complete`) and in `docs/native-user-tools.md`.
6. Update version fixtures in `tests/native/test_install_inputs.py` so each test still exercises
   its intended failure:
   - `test_lockfile_only_playwright_upgrade_fails_on_stale_apt_provenance`: simulate an upgrade to
     `1.65.0` by replacing `1.64.1` in `resolved`. With the current `replace('1.63.0', ...)` the
     replace silently does nothing, and the test hits the tarball-mismatch error instead.
   - `test_stale_apt_provenance_is_rejected`: replace `playwright-core 1.64.1` with
     `playwright-core 1.63.0`. With the current string the replace silently does nothing.
   - `test_package_and_lock_disagreement_is_rejected`: keep its disagreeing value distinct from
     `1.64.1` (the existing `1.64.0` already is).
   - `test_non_registry_transitive_tarball_is_rejected`: use the `1.64.1` URL for consistency.
7. In `tests/native/test_user_tools.py`, update the fixture `playwright --version` output to
   `Version 1.64.1`.

### Implementation notes

The provenance check is intentionally independent of the lock. Fix it by editing the reviewed
input, never by deriving it from the lock or relaxing the `require`. The lock-hash test and doc
record a deliberately reviewed pin, so update their literals rather than removing them.

### Validation

```bash
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_install_inputs.py --publication proposed
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile tests/native/test_install_inputs.py tests/native/test_user_tools.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest -v tests.native.test_install_inputs tests.native.test_user_tools
rg -n "1\.63\.0|a9a9e5ba" --glob '!docs/plans/**' .
git diff --check
```

### Completion criteria

- Lock integrity matches the registry, and the upstream Chromium list comparison is recorded
  (expected: unchanged).
- `chromium_apt_source` names `playwright-core 1.64.1`, and test and doc hashes equal the computed
  lock SHA-256.
- The focused checker and both focused test modules pass, and each provenance test still fails for
  its intended reason.
- `rg` finds no `1.63.0` or old hash outside `docs/plans/`, and `git diff --check` is clean.
- Changes remain uncommitted for human review.

## Phase 2: Full Native Source And Release Validation

### Workspace

.

### Goal

Prove the complete refresh passes the full source-validation contract CI runs, plus release-input
and dependency-discovery validation, so the human can commit and publish it.

### Scope

Validation only. Fix a failure only if it comes from Phase 1 edits and is within Phase 1 scope.

### Non-goals

- Weakening or skipping any check.
- Changing workflows, `renovate.json` or validator code.
- Running `--publication committed`, which needs the human's commit in `HEAD`.

### Required context

- `docs/dependency-automation.md#validation`
- `docs/native-tool-inventory.md` (native verification)
- `tests/native/run-source-validation.sh`

### Execution steps

1. Run the full validation list below and capture each result.
2. If a failure is caused by Phase 1 edits, correct it within Phase 1 scope and rerun. Report any
   failure that also reproduces on unmodified `main` as pre-existing; do not fix it here.
3. Write a final report covering: lock and registry agreement, upstream Chromium comparison
   result, files changed, per-command results and the human next steps.

### Implementation notes

Keep all caches, downloads and logs under `tmp/`. The Renovate dry run must still extract only
`playwright` plus the four custom identities named in `docs/dependency-automation.md`.

### Validation

```bash
NPM_CONFIG_CACHE=tmp/renovate-npm-cache \
  npx --yes --package renovate@44.167.1 renovate-config-validator --strict --no-global renovate.json
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_manifest.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest discover -s tests/native -v
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_claude_settings.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_lean_launchers.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_statusline.py
NPM_CONFIG_CACHE=tmp/renovate-npm-cache \
  tests/native/check-source-validation-without-orchestration.sh --publication proposed
PYTHONPYCACHEPREFIX=tmp/pycache python3 scripts/native/verify_release_inputs.py \
  --manifest native/toolchain.json \
  --output tmp/native-release-validation/release-verification.json \
  --download-dir tmp/native-release-validation/downloads
git diff --check
```

Also run the npm audit commands from `docs/dependency-automation.md#validation` and classify them
as that section describes.

### Completion criteria

- Every command passes, or every failure is shown to be pre-existing on `main` and reported.
- The final report gives the human next steps: commit on `renovate/playwright-monorepo`, transfer
  it to the personal host, push it to PR #51 (no force-push needed), and run
  `tests/native/check_install_inputs.py --publication committed` after the commit. Renovate stops
  auto-rebasing the branch once it has a human commit.
