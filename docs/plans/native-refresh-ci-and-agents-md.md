# Native Refresh Cleanup, Hosted Verifiers And AGENTS.md Decision Plan

Close the two native-tooling review gaps and correct the stale design decision:
normal-user refreshes remove retired files only when their recorded digest proves
they are unchanged, hosted CI runs every documented focused verifier, and the
design-decision record reflects Claude Code's native `AGENTS.md` discovery.

Keep all work in this repository. Use only disposable homes and repository
`tmp/` paths for installer tests; do not run the live user installer,
provisioner, preparation runner, settings apply command, provider commands or
trust mutation. Preserve modified retired files and fail safely instead of
deleting user changes. Do not edit historical plans while executing this plan.

## Phase 1: Reconcile Retired Managed User Files

### Workspace

.

### Goal

Make a reviewed normal-user refresh remove files that were managed by the
previous installation but are no longer in the current file plan, without
deleting modified, unmanaged, symlinked or out-of-home paths.

### Scope

- `scripts/native/user_tools.py`
- `tests/native/test_user_tools.py`
- `docs/native-user-tools.md`, only if the owner documentation needs a concise
  clarification of retired-file refresh behavior

### Non-goals

- Reintroducing any retired Claude helper or prompt-replacement addon.
- Deleting directories, provider state, credentials, optional inspection data
  or files that were never recorded in `managed-files.json`.
- Running the installer against the real development-user home.
- Changing system provisioning or trust behavior.

### Required context

- `README.md` ("Native Installation And Refresh")
- `docs/native-user-tools.md` ("Refresh Installed User Resources" and
  "Offline Validation")
- `scripts/native/user_tools.py` (`digest`, `home_path`, `plan_files`, `write`
  and `install`)
- `tests/native/test_user_tools.py` (`UserToolsProbe` and
  `UserInstallerSafetyTests`)
- The prior manifest/source removal in commit `1a3ef5b`, which identifies the
  retired wrappers `claude-45-custom-system-prompt`,
  `claude-46-custom-system-prompt`, `claude-with-custom-system-prompt` and the
  installed helper copy `helpers/system-prompt-addon.py`

### Execution steps

1. Refactor the previous managed-state read so the installer can compare the
   prior `managed-files.json` mapping with the current `plan_files()` paths
   while retaining the existing collision checks for current managed files.
   Validate every candidate through the existing home-boundary, ownership and
   symlink protections before it can be considered for removal.
2. Compute retired paths as prior managed-state keys absent from the current
   file plan. Review all retired candidates before deleting any of them:
   missing paths are already converged; existing regular files are removable
   only when their current SHA-256 equals the prior recorded digest; a modified,
   non-regular, symlinked, malformed or out-of-home candidate aborts the refresh
   with a reviewable collision error.
3. After candidate validation, unlink only digest-matching retired files. Do
   not recursively remove directories. Complete this reconciliation before
   replacing `managed-files.json`, then write the new state with current
   managed files only.
4. Add an upgrade fixture that seeds the four files retired by `1a3ef5b` and a
   previous state file containing their real digests, runs the mocked
   installer, and proves the retired files disappear while current wrappers,
   credentials, settings and unrelated files remain intact. Assert that the
   rewritten state omits every retired path.
5. Add negative safety coverage proving a modified retired file causes the
   refresh to fail before cleanup/state replacement and keeps its bytes. Cover
   a previous-state path outside the disposable home (and a symlink case if it
   is not already covered by the same path guard) to prove the cleanup cannot
   escape the managed home. Include a missing-retired-file case to prove an
   interrupted or partially cleaned prior refresh converges on rerun.
6. If implementation details expose a durable user-visible rule not already
   clear in `docs/native-user-tools.md`, state briefly that refresh removes
   unchanged retired managed files and refuses modified collisions. Do not
   duplicate implementation details in `README.md`.

### Implementation notes

- Determine and validate the full retirement set before the first unlink so
  one bad candidate cannot produce partial cleanup.
- Use the digest from the previous state as deletion authority; do not compare
  retired files to deleted repository sources or hardcode the four historical
  paths in production code.
- Keep `plan_files()` free of filesystem mutation. A small helper that parses
  prior state or reconciles retired paths is preferable to hiding deletion in
  planning/collision discovery.
- State replacement must happen only after successful retirement cleanup. A
  failure must not silently drop a modified retired path from bookkeeping.

### Validation

```bash
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile scripts/native/user_tools.py tests/native/test_user_tools.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest tests.native.test_user_tools -v
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest discover -s tests/native -v
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_install_inputs.py --publication proposed
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_user_environment.py
git diff --check
```

### Completion criteria

- A mocked upgrade from the pre-`1a3ef5b` managed state removes all three
  retired command wrappers and the installed `system-prompt-addon.py` copy.
- The new state contains only current managed files.
- Modified, unsafe and out-of-home retired candidates are never deleted and
  prevent state replacement; unmanaged files and provider data are preserved.
- Repeat/missing-file refresh behavior is idempotent, and the focused plus full
  native unit suites pass.

## Phase 2: Execute Focused Native Verifiers In Hosted CI

### Workspace

.

### Goal

Make the hosted native dependency workflow execute and record the three
documented behavioral verifiers and syntax-check every newly introduced Python
source involved in those behaviors.

### Scope

- `.github/workflows/native-dependency-validation.yml`
- `docs/dependency-automation.md`
- `docs/native-tool-inventory.md` and `docs/native-user-tools.md`, only where
  their validation command lists must stay aligned with the workflow

### Non-goals

- Converting the focused verifier scripts to `unittest` discovery.
- Changing verifier behavior, native dependency pins, Renovate configuration,
  release checksums or artifact retention.
- Running a hosted workflow or publishing a commit from the worker session.

### Required context

- `.github/workflows/native-dependency-validation.yml` (path filters and
  "Validate committed native sources")
- `docs/native-user-tools.md` ("Offline Validation")
- `docs/native-tool-inventory.md` ("Native Verification")
- `docs/dependency-automation.md` ("Hosted Native Evidence" and
  "Validation")
- `tests/native/check_claude_settings.py`
- `tests/native/check_lean_launchers.py`
- `tests/native/check_statusline.py`
- `scripts/native/claude_settings.py`

### Execution steps

1. In the workflow's `record_check` block, add separate, clearly named checks
   that invoke `check_claude_settings.py`, `check_lean_launchers.py` and
   `check_statusline.py` with `PYTHONPYCACHEPREFIX=tmp/pycache`. Keep them
   separate from `native-unit-tests` because their filenames intentionally do
   not match `unittest discover`'s `test_*.py` pattern and each result should
   be visible in source-validation evidence.
2. Extend the workflow's `python-syntax` input list with
   `scripts/native/claude_settings.py` and all three focused verifier files.
   Preserve the existing aggregate failure handling so every check runs and
   the final source status fails if any result is nonzero.
3. Update the hosted-evidence description in `docs/dependency-automation.md`
   to make the focused settings, lean-launcher and status-line behavior part of
   the explicit hosted source contract. Align the Python syntax command lists
   in `docs/native-tool-inventory.md` and `docs/native-user-tools.md` with the
   sources now checked in CI, without removing existing checks.
4. Run each newly wired verifier directly, then run the complete offline native
   unit/static set. Lint the workflow with `actionlint`.
5. Run the local dependency-evidence commands required by
   `docs/dependency-automation.md`, keeping caches, reports and public downloads
   under `tmp/`. Report unavailable network/tool prerequisites explicitly; do
   not substitute a partial run for full verification.

### Implementation notes

- Use the existing `record_check` function rather than a new workflow step so
  the checks remain represented in `source-validation-status.json` and share
  the job's bounded failure collection.
- These scripts are executable behavioral checks, not import-only syntax
  checks; adding them only to `py_compile` would not close the review gap.
- Do not invoke `claude_settings.py apply`; `check_claude_settings.py` uses only
  disposable paths under repository `tmp/`.

### Validation

```bash
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_claude_settings.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_lean_launchers.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_statusline.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile scripts/native/claude_settings.py tests/native/check_claude_settings.py tests/native/check_lean_launchers.py tests/native/check_statusline.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest discover -s tests/native -v
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_manifest.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_install_inputs.py --publication proposed
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_user_environment.py
actionlint .github/workflows/native-dependency-validation.yml
PYTHONPYCACHEPREFIX=tmp/pycache python3 scripts/native/verify_release_inputs.py \
  --manifest native/toolchain.json \
  --output tmp/native-release-validation/release-verification.json \
  --download-dir tmp/native-release-validation/downloads
NPM_CONFIG_CACHE=tmp/renovate-npm-cache \
  npx --yes --package renovate@44.167.1 renovate-config-validator \
  --strict --no-global renovate.json
NPM_CONFIG_CACHE=tmp/renovate-npm-cache \
RENOVATE_CACHE_DIR=tmp/renovate-cache \
LOG_LEVEL=debug \
  npx --yes --package renovate@44.167.1 renovate \
  --platform=local --dry-run=full
git diff --check
```

### Completion criteria

- Hosted source validation records independent passing/failing results for
  Claude settings, lean launchers and status line behavior.
- `python-syntax` covers `claude_settings.py` and all three focused verifier
  scripts.
- Workflow and owner-document validation lists agree, `actionlint` passes, and
  all locally available offline/evidence checks pass with any unavailable
  external prerequisite called out explicitly.

## Phase 3: Correct The Claude AGENTS.md Design Decision

### Workspace

.

### Goal

Replace the obsolete statement that Claude Code does not natively read
`AGENTS.md` with the current design basis: native project-instruction discovery
loads it, and the retired settings hook is intentionally absent to avoid a
duplicate copy.

### Scope

- `docs/design-decisions.md`

### Non-goals

- Changing `AGENTS.md`, Claude settings, launcher flags or runtime behavior.
- Editing historical plans or research records that already describe the
  chronology accurately.
- Adding a new SessionStart hook or `CLAUDE.md` shim.

### Required context

- `docs/design-decisions.md` ("AGENTS.md over CLAUDE.md")
- `docs/launch-options.md` (native project-instruction discovery and excluded
  `--bare`/`--safe-mode` behavior)
- `docs/native-user-tools.md` ("Claude Settings Replacement")
- `docs/research/claude-code-barebones-launch.md` (current native-loading
  conclusion)

### Execution steps

1. Rewrite the short decision rationale to state that the repository uses
   `AGENTS.md` as the multi-tool instruction source and current Claude Code
   loads it natively through normal project-instruction discovery.
2. Retain the reason the settings replacement removes the legacy
   `SessionStart` injection: native loading should provide exactly one copy.
   Keep issue `#6235` only as historical context, label it as the earlier
   support request/gap, and remove the present-tense claim that Claude Code
   does not read `AGENTS.md`. Keep issue `#18560` only to the extent it still
   explains why a `CLAUDE.md`-based workaround was rejected.
3. Search active documentation for equivalent stale claims. If another active
   owner document contradicts native loading, correct it in the nearest owner
   document and record the scope expansion; do not rewrite `docs/plans/` as
   current authority.
4. Review the final diff for a design-decision-only documentation change and
   run whitespace/link-oriented static checks available in the repository.

### Implementation notes

- Describe current behavior directly and distinguish historical issue context
  from the accepted design.
- Keep the section concise; launch/settings procedures belong in their existing
  owner documents.

### Validation

```bash
rg -n -i "does(n't| not) (natively )?(read|support).*AGENTS\.md|Claude Code doesn't natively read AGENTS\.md" \
  --glob '!docs/plans/**' --glob '!tmp/**' .
rg -n "AGENTS\.md" docs/design-decisions.md docs/launch-options.md docs/native-user-tools.md docs/research/claude-code-barebones-launch.md
git diff --check
```

The first search must return no active stale claim. The second is a manual
consistency review and is expected to return the current native-loading
references.

### Completion criteria

- `docs/design-decisions.md` says Claude Code natively discovers `AGENTS.md`
  and explains why duplicate hook injection remains removed.
- Issue `#6235` is framed as historical context, not current product behavior.
- Active documentation contains no contradictory claim, runtime files remain
  unchanged in this phase, and `git diff --check` passes.
