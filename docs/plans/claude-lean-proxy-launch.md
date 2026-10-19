# Claude Lean Proxy Launch Plan

Make it easy to run `claude-with-proxy` with a minimal tool surface at a chosen
effort level (primarily `medium`) so the full Claude Code system prompt, tool
definitions and injected context can be captured and analyzed in mitmweb. This
is the tooling step only. Reusing or rewriting `claude-with-custom-system-prompt`
is a later, separate decision.

Requirements, from the owner:

- `claude-with-proxy` stays the launcher; effort is selectable per launch.
- Exactly one copy of `AGENTS.md` in context. Claude Code now loads `AGENTS.md`
  natively as project instructions, so no `SessionStart` hook is wanted.
- Only the bare-minimum tools plus web access. Omit `Grep` and `Glob`. No
  subagents.
- Lean sessions always run with `--dangerously-skip-permissions`.
- `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS` is set to `1` (not `true`).
- Settings setup must be idempotent: one human-run script that makes
  `~/.claude/settings.json` match a reviewed repository file, replacing the
  current one, safe to run any number of times.
- Simplest mechanism: shell aliases/functions over existing launchers. No new
  installed command.

Grounding: [Barebones launch research](../research/claude-code-barebones-launch.md),
[Launch options](../launch-options.md), [HTTPS Traffic Inspection](../traffic-inspection.md)
and [Native Guest User Tools](../native-user-tools.md).

## Design decisions (settled; do not re-litigate)

- **Mechanism:** one shell function plus thin aliases in
  `native/helpers/bash_aliases.sh`. That file is already installed verbatim as
  `~/.local/share/budget-analyzer-native/aliases.sh` and is opt-in, so plain
  `claude`, `claude-with-proxy` and every other launcher keep upstream behavior.
- **AGENTS.md (native, no hook):** the hook is not restored. The repository
  overlay `native/helpers/settings-overlay.json`, `merge_settings`/`verify` in
  `scripts/native/user_tools.py`, the checkers and the existing docs stay exactly
  as they are (commit `e777f87` already removed the managed hook). The user's
  live `~/.claude/settings.json` still contains the old `SessionStart` hook,
  which now injects a second copy; the settings script below removes it.
  Because `AGENTS.md` is loaded by Claude Code's own project-instruction
  discovery, the lean launcher must not use `--bare`, `--safe-mode` or
  `--restricted` (the research doc shows they disable instruction discovery
  and/or change authentication). The handoff verifies exactly one copy.
- **Settings script (idempotent replace):**
  - Canonical desired state: new reviewed file `native/helpers/claude-settings.json`.
  - Tool: new `scripts/native/claude_settings.py`, run by the human as
    `python3 scripts/native/claude_settings.py {check|apply} [--settings-path PATH]`.
    Default path is `~/.claude/settings.json`; tests always pass a path under
    repository `tmp/`.
  - `check`: read-only; exit 0 if the target JSON equals the canonical file,
    exit 1 with a short key-level difference otherwise; exit 2 on unreadable or
    invalid input.
  - `apply`: if already equal, print "already up to date" and change nothing
    (no backup, no rewrite). Otherwise copy the existing file to
    `settings.json.bak-YYYYmmddTHHMMSS` beside it (mode `0600`), write the
    canonical content to a temp file in the same directory (mode `0600`), and
    `os.replace` it into place. Missing target is created with no backup.
    Refuse a symlink or non-regular target. Never read or write any other file
    under `~/.claude` (credentials, skills, history).
  - Because it fully replaces the file, every desired key lives in the
    canonical file. Seed it from the current live file minus the hook:

    ```json
    {
      "model": "sonnet",
      "promptSuggestionEnabled": false,
      "skipDangerousModePermissionPrompt": true,
      "theme": "dark",
      "autoCompactEnabled": false,
      "statusLine": {
        "type": "command",
        "command": "printf '\\033[01;32m%s@%s\\033[00m:\\033[01;34m%s\\033[00m' \"$(whoami)\" \"$(hostname -s)\" \"$(pwd)\""
      }
    }
    ```

    It must contain `promptSuggestionEnabled` and `autoCompactEnabled` with the
    same values as the overlay (a test enforces this) and must not contain
    `hooks`. The user installer's overlay merge keeps working unchanged on the
    replaced file, so the two never fight.
  - Not an installed command and not a `toolchain.json` entry: it is a
    human-run repository script.
- **Why not other overlay or settings keys for lean behavior:** lean controls
  are CLI flags and environment variables scoped to the launched process so
  plain `claude` is unaffected.
- **Git instructions:** change `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS='true'` to
  `'1'` in `scripts/native/proxy.py`. That is the only `proxy.py` change; it
  applies to every Claude proxy action. Leave `ENABLE_CLAUDEAI_MCP_SERVERS` and
  `CLAUDE_CODE_DISABLE_1M_CONTEXT` alone. The lean function does not repeat the
  variable. The existing alias lines that still say `true` are out of scope
  (follow-up).
- **Tools:** `--tools "Bash,Read,Edit,Write,WebFetch,WebSearch"`, overridable through
  `CLAUDE_LEAN_TOOLS`. `--tools` is a whitelist, so `Agent`, `Grep`, `Glob`,
  `Skill` and task tools are all absent. `WebFetch` and `WebSearch` are included
  because without them the agent cannot search the web. Claude Code also injects
  a `DeferredToolPlaceholder` tool regardless of `--tools`. Exact accepted tool
  names are verified live in the human handoff, not guessed.
- **Permissions:** the lean function always passes
  `--dangerously-skip-permissions`. `proxy.py` is not changed for this, so plain
  `claude-with-proxy` keeps its documented plain-permission behavior; the bypass
  belongs to the lean function only.
- **Other flags:** `--strict-mcp-config` and `--disable-slash-commands`.
- **Effort:** `--effort LEVEL` as a CLI flag, not `CLAUDE_CODE_EFFORT_LEVEL`,
  because the variable overrides `/effort` mid-session.
- **Environment (value `1`, never `true`):** `CLAUDE_CODE_DISABLE_AUTO_MEMORY`,
  `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`, `CLAUDE_CODE_DISABLE_AGENT_VIEW`,
  `CLAUDE_CODE_DISABLE_CRON`, `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS`,
  `CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`.
  Also `CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false`. Fewer ancillary requests
  make captured flows easier to read.
- **Names:** function `claude-lean-proxy EFFORT [claude args...]`; aliases
  `claude-lean-proxy-low`, `claude-lean-proxy-medium`, `claude-lean-proxy-high`, `claude-lean-proxy-xhigh`
  and `claude-lean-proxy-max`.

## Safety and scope

- Workers write only inside this repository and use `tmp/` for scratch.
- Workers must not run the user installer, provisioner, preparation runner or
  CA initialization, start `mitmweb`/`claude-with-proxy`, generate provider
  traffic, or run the settings script against the real `~/.claude`. All live
  verification and the real settings replacement are a human handoff.
- Allowed edits: new `native/helpers/claude-settings.json`; new
  `scripts/native/claude_settings.py`; `native/helpers/bash_aliases.sh`; the one
  value in `scripts/native/proxy.py`; new verifiers under `tests/native/`; and
  the documents `docs/native-user-tools.md`, `docs/launch-options.md`,
  `docs/traffic-inspection.md` and
  `docs/research/claude-code-barebones-launch.md`. Workers do not edit this plan
  file.
- Do not touch `native/helpers/settings-overlay.json`, `scripts/native/user_tools.py`,
  `native/toolchain.json`, installer shell scripts, `AGENTS.md`, `~/.claude`,
  credentials or provider state, including in tests. If an existing checker
  rejects the new helper file, report it instead of widening scope.
- Do not run Git write commands.

## Phase 1: Idempotent settings script

### Workspace

.

### Goal

A human-run script can check and apply the canonical Claude user settings
(without the `SessionStart` hook) idempotently, proven by an offline test against
files under repository `tmp/`.

### Scope

- Add `native/helpers/claude-settings.json` (content from the design decisions).
- Add `scripts/native/claude_settings.py`.
- Add `tests/native/check_claude_settings.py`.

### Non-goals

- No change to the overlay, `user_tools.py`, the manifest or `AGENTS.md`.
- Never read or write the real `~/.claude`.

### Required context

- Design decisions in this plan (the settings script section is the spec)
- `native/helpers/settings-overlay.json` and `merge_settings` in
  `scripts/native/user_tools.py` (read only)
- `tests/native/check_user_environment.py` for verifier style
- `scripts/native/proxy.py` for the repository's private-file mode and
  `require()` conventions

### Execution steps

1. Create `native/helpers/claude-settings.json` with the exact JSON from the
   design decisions.
2. Implement `scripts/native/claude_settings.py` with `check` and `apply`
   subcommands and `--settings-path`, following the spec: JSON equality (not
   byte equality) decides "up to date"; backup only when replacing an existing
   different file; temp file plus `os.replace` in the target directory; mode
   `0600`; refuse symlink or non-regular targets; short stderr messages and the
   exit codes above; stdlib only; no network; no other file access.
3. Add `tests/native/check_claude_settings.py`, a standalone verifier that,
   under a temporary directory beneath repository `tmp/`, proves:
   - `check` exits 0 on an identical file and 1 on a different one, with the
     differing key named; exit 2 on invalid JSON;
   - `apply` on a file containing the old `SessionStart` hook plus extra keys
     replaces it with exactly the canonical content, creates exactly one
     `settings.json.bak-*` holding the original, and the result has no `hooks`;
   - a second `apply` prints "already up to date", changes neither the file's
     bytes and mtime nor the backup count;
   - a missing target is created without a backup;
   - a symlink target is refused and its destination is untouched;
   - file modes are `0600`;
   - the canonical file has no `hooks` and carries the same
     `promptSuggestionEnabled` and `autoCompactEnabled` as
     `native/helpers/settings-overlay.json`;
   - `merge_settings(canonical, overlay) == canonical` using the real function
     (import it read-only), proving the installer merge leaves the replaced
     file unchanged.
4. Confirm `git status --short` lists only the three new files for this phase.

### Implementation notes

- Compare parsed JSON so key order or whitespace never causes a rewrite.
- Write canonical output with `indent=2`, sorted keys off (preserve the file's
  order) and a trailing newline.
- The default path is only a default; nothing in tests may rely on `HOME`.

### Validation

```bash
python3 -c "import json; json.load(open('native/helpers/claude-settings.json'))"
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile scripts/native/claude_settings.py tests/native/check_claude_settings.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_claude_settings.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest discover -s tests/native -v
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_manifest.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_user_environment.py
git diff --check
```

### Completion criteria

- The verifier passes and covers every assertion above.
- No file outside the three new files changed.
- Pre-existing failures, if any, are reported separately.

## Phase 2: Lean launcher function, aliases and git-instructions value

### Workspace

.

### Goal

`native/helpers/bash_aliases.sh` defines `claude-lean-proxy` and the five
`claude-lean-proxy-*` aliases, `proxy.py` uses `1` for git instructions, and an offline
test proves the exact arguments and environment handed to `claude-with-proxy`.

### Scope

- Edit `native/helpers/bash_aliases.sh`.
- Edit the one value in `scripts/native/proxy.py`.
- Add one new offline verifier under `tests/native/`.

### Non-goals

- No change to existing `dangerous`, `high`, `max`, `*45` or `*46` aliases.
- No other `proxy.py`, manifest or installer change.
- No documentation yet (Phase 3).

### Required context

- `native/helpers/bash_aliases.sh`
- `scripts/native/proxy.py` (`provider_arguments`, `launch`) to confirm user
  arguments and environment pass through unchanged
- `tests/native/check_user_environment.py` and `tests/native/check_manifest.py`
  for the style and discovery of existing verifiers
- Any existing test that pins `proxy.py` environment values (search `tests/`
  for `DISABLE_GIT_INSTRUCTIONS`)
- The design decisions section above

### Execution steps

1. In `scripts/native/proxy.py`, change
   `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS='true'` to `'1'`. Update any test or
   doc that pins the old value.
2. Add a clearly commented "Lean proxy inspection" section to
   `native/helpers/bash_aliases.sh` (separate from the existing Claude and
   Codex sections) containing the function `claude-lean-proxy`:
   - First argument is the effort level; reject anything outside
     `low|medium|high|xhigh|max` with a one-line stderr message and status 2,
     and reject a missing level the same way.
   - Run `claude-with-proxy` as a single command with the design-decision
     environment set inline for that command only, then
     `--dangerously-skip-permissions --effort "$effort"
     --tools "${CLAUDE_LEAN_TOOLS:-Bash,Read,Edit,Write,WebFetch,WebSearch}" --strict-mcp-config
     --disable-slash-commands "$@"`.
   - Quote every expansion; keep the file valid for `bash -n` and ShellCheck
     (aliases referencing functions are acceptable).
3. Add aliases `claude-lean-proxy-low|medium|high|xhigh|max`, each
   `claude-lean-proxy <level>`, so trailing arguments forward to Claude.
4. Add `tests/native/check_lean_proxy_aliases.py`, a standalone verifier in the
   style of the existing `check_*.py` files. It must, under a temporary
   directory beneath repository `tmp/`:
   - create a stub `claude-with-proxy` that records `"$@"` and the relevant
     environment variables to a file, and put it first on `PATH`;
   - source `native/helpers/bash_aliases.sh` in `bash` with `HOME` pointing at
     the temporary directory, and run `claude-lean-proxy medium extra-arg`
     plus the `claude-lean-proxy-medium` alias via `bash -ic` or an equivalent that
     enables alias expansion;
   - assert the recorded arguments contain `--dangerously-skip-permissions`,
     `--effort medium`, the default tool list, `--strict-mcp-config`,
     `--disable-slash-commands` and the forwarded `extra-arg`, and contain none
     of `--bare`, `--safe-mode`, `--restricted` or `--setting-sources`;
   - assert `CLAUDE_LEAN_TOOLS` overrides the tool list;
   - assert each environment variable from the design decisions is exactly `1`
     (or `false` for prompt suggestion) and is absent from the parent shell
     afterwards;
   - assert an invalid or missing effort exits non-zero without invoking the
     stub;
   - assert the tool list never contains `Agent`, `Grep` or `Glob` by default;
   - separately assert `proxy.py` contains `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS='1'`
     and no `'true'` value for it.
5. Confirm the existing alias lines are byte-identical to `HEAD` apart from
   the appended section (`git diff` shows additions only to that file).

### Implementation notes

- A function-plus-alias form keeps one source of truth; do not copy the flag
  list into each alias.
- The stub must not rely on any real credential, CA or listener.
- If alias expansion under a non-interactive shell is awkward, enable it with
  `shopt -s expand_aliases` inside the test script; do not weaken the assertion.

### Validation

```bash
bash -n native/helpers/bash_aliases.sh
shellcheck native/helpers/bash_aliases.sh
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile scripts/native/proxy.py tests/native/check_lean_proxy_aliases.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_lean_proxy_aliases.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_user_environment.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest discover -s tests/native -v
git diff --check
```

If ShellCheck already reports pre-existing findings in `bash_aliases.sh`, record
them separately and show that the new section adds none.

### Completion criteria

- The new verifier passes and covers every assertion listed above.
- `proxy.py` differs from `HEAD` by exactly the `'true'` → `'1'` change.
- Existing native tests still pass, or any pre-existing failure is reported
  with its output.

## Phase 3: Documentation and capture workflow

### Workspace

.

### Goal

A human can read one place to apply the settings, install the aliases, launch a
lean session at any effort level, capture it, and extract the system prompt, tool
definitions and injected context from the flow.

### Scope

- Edit `docs/launch-options.md`, `docs/traffic-inspection.md`,
  `docs/native-user-tools.md` and `docs/research/claude-code-barebones-launch.md`.

### Non-goals

- No new helper command, `mitmflow-*` change or toolchain entry.
- No `AGENTS.md` or `docs/design-decisions.md` change.
- No `docs/plans/` edits.

### Required context

- Phase 1 and Phase 2 output
- `docs/launch-options.md`, `docs/traffic-inspection.md`,
  `docs/native-user-tools.md` (the Claude configuration paragraph and the
  permission table near "Authentication, Permissions And Verification")
- `docs/research/claude-code-barebones-launch.md`
- `native/helpers/mitmflow-render.py` and `mitmflow-body` for the exact flags
  referenced in recipes

### Execution steps

1. In `docs/native-user-tools.md`, add a "Claude Settings Replacement" subsection
   next to the Claude configuration paragraph: the command, `check` versus
   `apply`, idempotence, the backup naming, that it fully replaces
   `~/.claude/settings.json` from `native/helpers/claude-settings.json` (so
   unlisted keys are dropped; edit the canonical file to keep new ones), that it
   removes the legacy `SessionStart` hook so `AGENTS.md` appears once, and its
   relationship to the installer's overlay merge. Add the permission-table row
   for the lean launchers: explicit `--dangerously-skip-permissions` through
   `claude-with-proxy`, scoped flags and environment, opt-in through
   `aliases.sh`; keep the `claude-with-proxy` row as plain permissions.
2. In `docs/launch-options.md`, add a "Lean Inspection Launchers" section: how
   to opt in to the aliases, the function and alias names, what each flag and
   variable does and why (short table), the `CLAUDE_LEAN_TOOLS` override, and
   that every lean launch uses `--dangerously-skip-permissions` (same
   guest-root-equivalent authority note as the other high-authority launchers).
   State that `--bare`, `--safe-mode` and `--restricted` are not used because
   `AGENTS.md` must load through normal project-instruction discovery.
3. In `docs/traffic-inspection.md`, add a "Analyzing The Full System Prompt"
   section with a copy-paste workflow:
   - launch `claude-lean-proxy-medium`, send one trivial prompt, exit;
   - `mitmflows --provider anthropic --path /v1/messages --limit 20` to find the
     main-model flow versus ancillary flows (differing model, tool count);
   - `mitmflow-detail FLOW_ID --full` for the summary;
   - `jq` recipes over `mitmflow-body FLOW_ID request --json` for:
     `.system` (each block with index and length), `.tools[].name`,
     per-tool schema size, `.thinking`/effort fields, and a count of how many
     times the `AGENTS.md` text occurs in the whole request (expected: 1);
   - a note that captured requests contain secrets and that exports under
     `tmp/` are private and human-cleaned;
   - a note on `--system-prompt-snapshot off` and
     `--exclude-dynamic-system-prompt-sections` as optional comparison knobs
     (default is the full prompt this workflow wants).
4. In `docs/research/claude-code-barebones-launch.md`, update the status line
   to point at this plan and the implemented launcher, record that git
   instructions now use `1` in `proxy.py`, correct the statements that say the
   `AGENTS.md` loading depends on a hook (it is native), and note that the open
   questions on tool names, `AGENTS.md` retention and `Agent` removal are
   answered by the human handoff checklist (without inventing answers).
5. Add a "Human live verification checklist" subsection to
   `docs/traffic-inspection.md` covering exactly the items in Phase 4's handoff
   list so the checklist survives after this plan is archived.
6. Check that no doc claims plain `claude`, plain `claude-with-proxy`,
   `toolchain.json`, the overlay or the existing aliases changed.

### Implementation notes

- Keep detailed procedure in one owner doc and link from the others; do not
  duplicate the recipes.
- Use repository-relative paths only; never hardcode checkout locations.
- Recipes must use flags that exist in `mitmflows`, `mitmflow-detail` and
  `mitmflow-body` as implemented; run each `--help` to confirm.

### Validation

```bash
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_manifest.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_user_environment.py
mitmflows --help && mitmflow-body --help && mitmflow-detail --help
git diff --check
```

Run the documented link check from `docs/native-tool-inventory.md` if it lists
one for these docs. Run the `jq` recipes against a small hand-written fixture
JSON under `tmp/` shaped like an Anthropic messages request to prove the filters
parse; do not use real captured traffic.

### Completion criteria

- All four documents are updated, consistent, and link to each other without
  duplicating procedures.
- Every `jq` recipe was exercised against a local fixture.
- No statement contradicts native `AGENTS.md` loading, the always-bypass lean
  launcher or the `1` git-instructions value.

## Phase 4: Review and human handoff

### Workspace

.

### Goal

An independent consistency review of Phases 1 to 3, the full offline
validation suite, and a precise handoff list for the human-only settings
replacement, installation and live capture.

### Scope

- Read-only review plus fixes to defects found in earlier phases' files.
- Run the offline validation suite from `docs/native-user-tools.md`.

### Non-goals

- Do not run the user installer, the settings script against the real
  `~/.claude`, `claude-with-proxy`, `mitmweb`, or any provider traffic. Do not
  authenticate or initialize CAs.
- Do not add features beyond fixing defects.

### Required context

- `git diff` of Phases 1 to 3
- `docs/native-user-tools.md` "Offline Validation"
- `docs/native-tool-inventory.md` validation list
- Design decisions in this plan

### Execution steps

1. Review the diff against each design decision above; fix any deviation.
   Specifically confirm: no hook anywhere in the canonical settings file; the
   overlay, `user_tools.py`, `AGENTS.md` and `toolchain.json` are untouched;
   `proxy.py` changed only by `'true'` → `'1'`; no `true` values for variables
   documented as `1` in the lean function; `--dangerously-skip-permissions`
   always present; `Grep`, `Glob` and `Agent` absent; existing aliases untouched.
2. Run the complete offline suite from `docs/native-user-tools.md` and the
   manifest/link checks in `docs/native-tool-inventory.md`; record results.
3. Confirm `scripts/native/user_tools.py` installs `bash_aliases.sh` verbatim, so
   the new aliases only appear after the human re-runs the user installer, and
   that the settings script is independent of the installer.
4. Produce the human handoff in the final report, in this order:
   1. `python3 scripts/native/claude_settings.py check` (expected: reports the
      legacy `hooks` difference), then `... apply`, then `... check` again
      (expected: exit 0) and `... apply` again (expected: "already up to date").
   2. Stop workers; re-run the user installer (the human-only command in
      `docs/native-user-tools.md`) so `aliases.sh` updates; confirm it still
      verifies against the replaced settings file.
   3. `. "$HOME/.local/share/budget-analyzer-native/aliases.sh"`.
   4. `claude-lean-proxy-medium`, send a one-line prompt, exit.
   5. Verify in the captured main flow: `.tools[].name` is the whitelist
      (plus the injected `DeferredToolPlaceholder`) and `Agent`, `Grep`, `Glob` are absent (this answers the open question on
      accepted tool names; if `--tools` rejects a name, adjust
      `CLAUDE_LEAN_TOOLS` and record the real names in the docs).
   6. Verify the `AGENTS.md` text occurs exactly once in the whole request, and
      note where it lands (system prompt or first user message).
   7. Verify no skills list, MCP tools or memory section appear, and review
      ancillary flows for anything unexpectedly still firing.
   8. Verify the effort/thinking fields reflect `medium`; repeat with
      `claude-lean-proxy-high` and compare.
   9. Verify the git-instructions section is absent from the system prompt now
      that `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1`; if it is still present,
      report it.
   10. Confirm no `permissions.deny` for `Agent` is needed (expected: none,
       because `--tools` already excludes it).
5. List follow-ups, not done here: reusing `claude-with-custom-system-prompt`
   with the lean flags; normalizing `true` values in the older aliases;
   collapsing the existing eight repeated aliases into a shared base; whether
   the installer should adopt the canonical settings file.

### Implementation notes

- Prefer reporting an issue that is outside the allowed scope over widening
  scope to fix it.
- Findings already documented as pre-existing must be labeled as such.

### Validation

```bash
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest discover -s tests/native -v
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_manifest.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_install_inputs.py --publication proposed
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_user_environment.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_claude_settings.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_lean_proxy_aliases.py
bash -n native/helpers/bash_aliases.sh
shellcheck native/helpers/*.sh native/helpers/mitmflows native/helpers/mitmflow-detail native/helpers/mitmflow-body
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile scripts/native/proxy.py scripts/native/claude_settings.py tests/native/check_claude_settings.py tests/native/check_lean_proxy_aliases.py
git diff --check
git status --short
```

### Completion criteria

- All commands pass, or each pre-existing failure is reported with output and
  clearly separated from this change.
- `git status --short` shows changes only to the files named in "Safety and
  scope".
- The final report contains the numbered human handoff above and states plainly
  that live verification and the real settings replacement have not been
  performed.
