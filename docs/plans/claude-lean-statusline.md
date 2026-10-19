# Claude Lean Slash Commands And Status Line Plan

Two related fixes to the minimal Claude Code setup:

1. **Restore slash commands in the lean launcher.** `claude-lean-proxy` passes
   `--disable-slash-commands`. `claude --help` on 2.1.289 says it "Disable[s] all
   skills", but in the binary the session command list becomes empty whenever
   the flag is set (`commands = disableSlashCommands ? noCommands : …`), so
   built-ins such as `/model`, `/effort`, `/clear` and `/compact` are gone too.
   The flag is not needed for a lean context: the `skill_listing` attachment
   returns nothing unless the `Skill` tool is loaded
   (`if (!tools.some(t => t is "Skill")) return []`), and the lean `--tools`
   whitelist omits `Skill`. Dropping the flag brings back user-typed commands
   without adding a skill list to the prompt.
2. **Replace the PS1-style status line** (`user@host:cwd`) with a small,
   offline helper that shows the directory, model, context percentage and the
   5-hour and weekly plan-usage percentages with relative reset times.

Requirements, from the owner:

- One plan for both fixes.
- Status line: no `user@host` (single-user VM). Show model, context used as a
  percentage only (no token counts or window size), and 5-hour and weekly usage
  percentages with reset time as a relative duration. Keep the data simple.

Grounding: [Launch options](../launch-options.md),
[HTTPS Traffic Inspection](../traffic-inspection.md),
[Native Guest User Tools](../native-user-tools.md),
[Native tool inventory](../native-tool-inventory.md) and
[Barebones launch research](../research/claude-code-barebones-launch.md).

## Design decisions (settled; do not re-litigate)

- **Lean launcher:** remove only `--disable-slash-commands` from the
  `claude-lean-proxy` function in `native/helpers/bash_aliases.sh`. Every other
  flag, variable, alias and the `--tools` default stay exactly as they are.
  `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1` and `--strict-mcp-config` remain, so
  bundled skills and MCP prompts stay out. User skills and custom commands
  become typeable again; that is intended.
- **Status line helper:** restore `native/helpers/statusline-command.sh` (same
  path as the helper removed in `e777f87`; the dependency workflow
  `.github/workflows/native-dependency-validation.yml` still lists that path for
  ShellCheck, so the workflow needs no edit). It is a **new, simpler script**,
  not the old one: it reads only the JSON Claude Code writes to stdin. No
  network, no `curl`, no credential reads, no cache, no file writes.
- **Language:** Bash plus `jq` (already in the provisioned apt list) and GNU
  `date`. Prefer one `jq` call to extract all fields.
- **Input fields** (Claude Code 2.1.289 status line stdin):

  | Segment | Field | Fallback |
  | --- | --- | --- |
  | Directory | `.workspace.current_dir` | `.cwd` |
  | Model | `.model.display_name` | none |
  | Context | `.context_window.used_percentage` | none |
  | 5-hour | `.rate_limits.five_hour.used_percentage` | `.rate_limits.five_hour.utilization` |
  | 5-hour reset | `.rate_limits.five_hour.resets_at` | none |
  | Weekly | `.rate_limits.seven_day.used_percentage` | `.rate_limits.seven_day.utilization` |
  | Weekly reset | `.rate_limits.seven_day.resets_at` | none |

  `resets_at` may be epoch seconds (number), epoch milliseconds (number above
  `1e12`) or an ISO-8601 string; accept all three. `rate_limits` is null on API
  keys, Bedrock and Vertex.
- **Output** — one line, segments joined by ` | `, in this order:

  ```text
  ~/worktrees/workspace | Opus 5.5 | ctx 42% | 5h 31% (2h13m) | 7d 12% (3d4h)
  ```

  - Directory: `$HOME` prefix shown as `~`; bold blue (`\033[01;34m` …
    `\033[00m`), the same color as the current PS1 directory. No other colors.
  - Percentages: rounded to the nearest integer, followed by `%`.
  - Reset duration from now: at least one day → `XdYh`; at least one hour →
    `XhYm`; otherwise `Ym`; zero or past → `now`. If the reset time is missing
    or unparsable, show the percentage without the parenthesized duration.
  - A segment whose value is null or missing is omitted entirely, with no
    placeholder (for example before the first response, or without plan rate
    limits).
  - Empty or invalid stdin prints nothing. Always exit 0 and write nothing to
    stderr.
  - No per-model weekly buckets, extra usage, effort, git or token counts.
- **Installation:** an ordinary reviewed helper. Add a `statusline-command`
  entry to `native/toolchain.json` `helpers` and map it in `helper_sources` in
  `scripts/native/user_tools.py`, exactly like `via-annotator`. The installer
  then writes the `~/.local/bin/statusline-command` wrapper. It is not added to
  the installer's post-install `--help` verification loop (it reads stdin and
  has no `--help`).
- **Settings:** in `native/helpers/claude-settings.json`, set
  `statusLine.command` to `statusline-command` (keep `"type": "command"`). No
  other key changes. The human applies it with
  `scripts/native/claude_settings.py` after re-running the installer.
- **Out of scope:** `docs/plans/claude-lean-proxy-launch.md` (history),
  `AGENTS.md`, `native/helpers/settings-overlay.json`, `scripts/native/proxy.py`,
  the older `claude-*` aliases, the custom-system-prompt launcher.

## Safety and scope

- Write only inside this repository; scratch files go under `tmp/`.
- Workers must not run the user installer, provisioner, preparation runner,
  `claude_settings.py apply` against the real `~/.claude`, `mitmweb`,
  `claude-with-proxy` or any provider traffic, and must not read credentials.
  Live checks are a human handoff (Phase 4).
- Allowed edits: `native/helpers/bash_aliases.sh`,
  `native/helpers/statusline-command.sh` (new),
  `native/helpers/claude-settings.json`, `native/toolchain.json` (one helper
  entry), `scripts/native/user_tools.py` (one `helper_sources` entry),
  `tests/native/check_lean_proxy_aliases.py`, `tests/native/check_statusline.py`
  (new), any existing `tests/native/` file that pins helper lists or the
  status line command, and the documents `docs/launch-options.md`,
  `docs/traffic-inspection.md`, `docs/native-user-tools.md`,
  `docs/native-tool-inventory.md` and
  `docs/research/claude-code-barebones-launch.md`.
- Do not run Git write commands.

## Phase 1: Restore slash commands in the lean launcher

### Workspace

.

### Goal

`claude-lean-proxy` no longer passes `--disable-slash-commands`, the offline
alias verifier enforces that, and the docs explain why the skill list stays out
of context without it.

### Scope

- Edit `native/helpers/bash_aliases.sh` (remove one line).
- Edit `tests/native/check_lean_proxy_aliases.py`.
- Edit `docs/launch-options.md`, `docs/traffic-inspection.md` and
  `docs/research/claude-code-barebones-launch.md`.

### Non-goals

- No other flag, variable, alias or tool-list change.
- No `docs/plans/` edits.
- No status line work (Phases 2 and 3).

### Required context

- Preamble and design decisions in this plan
- `native/helpers/bash_aliases.sh` ("Lean proxy inspection" section)
- `tests/native/check_lean_proxy_aliases.py`
- `docs/launch-options.md` ("Lean Inspection Launchers")
- `docs/traffic-inspection.md` ("Human live verification checklist")
- `docs/research/claude-code-barebones-launch.md` (CLI options table,
  Recommendation)

### Execution steps

1. Delete the `--disable-slash-commands \` line from `claude-lean-proxy`.
   Confirm `git diff native/helpers/bash_aliases.sh` shows exactly that one
   removed line.
2. In `tests/native/check_lean_proxy_aliases.py`, remove
   `'[--disable-slash-commands]'` from the expected arguments and add
   `--disable-slash-commands` to `FORBIDDEN` so the verifier fails if it
   returns.
3. In `docs/launch-options.md`, replace the `--disable-slash-commands` table
   row: the flag is deliberately not used because it empties the whole command
   list (built-ins such as `/model` and `/effort` included); the skill list is
   already absent because `Skill` is not in `--tools`, and
   `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1` drops bundled skills. Keep the table
   short.
4. In `docs/research/claude-code-barebones-launch.md`, correct the CLI options
   row for `--disable-slash-commands` (the help text says skills only, but it
   also removes built-in commands), drop the flag from Recommendation item 2
   and from the `_claude_lean` example, and note that the `Skill` tool's absence
   is what keeps the skill listing out.
5. In `docs/traffic-inspection.md`, extend the human checklist: in a lean
   session, `/model` and `/effort` open their pickers, and the captured main
   flow still has no `skill_listing` system reminder. Keep item numbering
   consistent.
6. Search for any remaining `disable-slash-commands` outside `docs/plans/`
   and resolve it (`rg -n "disable-slash-commands" -g '!docs/plans/**'`).

### Implementation notes

- Describe the binary behavior in plain terms; do not paste minified code into
  docs.
- Do not claim live verification; the checklist item is the human proof.

### Validation

```bash
bash -n native/helpers/bash_aliases.sh
shellcheck native/helpers/bash_aliases.sh
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile tests/native/check_lean_proxy_aliases.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_lean_proxy_aliases.py
rg -n "disable-slash-commands" -g '!docs/plans/**' .
git diff --check
```

The `rg` output may list only the test's `FORBIDDEN` entry and doc text that
says the flag is deliberately not used.

### Completion criteria

- The alias verifier passes and rejects `--disable-slash-commands`.
- `bash_aliases.sh` differs from `HEAD` by exactly one removed line.
- The three docs agree with each other and with the launcher.

## Phase 2: Offline status line helper

### Workspace

.

### Goal

`native/helpers/statusline-command.sh` renders the specified line from
status line JSON on stdin, proven by an offline verifier over fixture inputs.

### Scope

- Add `native/helpers/statusline-command.sh`.
- Add `tests/native/check_statusline.py`.

### Non-goals

- No installer, manifest, settings or doc changes (Phase 3).
- No network, credentials, cache or file writes in the helper.

### Required context

- Design decisions in this plan (input fields and output are the spec)
- `git show e777f87^:native/helpers/statusline-command.sh` for the old
  helper's shape only; do not carry over its API call, cache or credential use
- `native/helpers/via-annotator.sh` and `native/helpers/codex-lean.sh` for
  repository shell style
- `tests/native/check_lean_proxy_aliases.py` for standalone verifier style

### Execution steps

1. Write `native/helpers/statusline-command.sh` (`#!/usr/bin/env bash`,
   executable) implementing the design decisions: read all of stdin, extract
   fields with `jq` (one call preferred, all errors suppressed), format each
   segment, omit missing segments, join with ` | `, print one line, exit 0.
2. Implement the reset-duration rule with GNU `date -d` for ISO strings and
   integer arithmetic for epoch values; treat numbers above `1e12` as
   milliseconds.
3. Add `tests/native/check_statusline.py`, a standalone verifier that runs the
   script with fixture JSON on stdin (`HOME` set to a temporary directory under
   repository `tmp/`) and asserts:
   - a full input produces exactly
     `<blue>~/dir<reset> | Opus 5.5 | ctx 42% | 5h 31% (2h13m) | 7d 12% (3d4h)`,
     using reset times computed from the current time plus a margin of about
     30 seconds so the expected minutes are stable;
   - `used_percentage` rounds (for example `41.6` → `42%`) and the
     `utilization` fallback works;
   - `resets_at` as epoch seconds, epoch milliseconds and ISO-8601 (with and
     without fractional seconds, `Z` and `+00:00`) give the same duration;
   - a past reset prints `now`; durations under one hour print `Ym`;
   - a null `rate_limits` omits both usage segments; a null
     `context_window.used_percentage` omits `ctx`; a missing reset time keeps
     the percentage without parentheses;
   - a directory outside `HOME` prints unchanged; `.cwd` is used when
     `.workspace.current_dir` is absent;
   - empty input and invalid JSON print nothing, exit 0 and write no stderr;
   - the output contains no `@`-style user/host segment and only the directory
     color sequence;
   - the script text contains none of `curl`, `wget`, `.credentials`,
     `mktemp` or redirections to files.

### Implementation notes

- Use `printf '%s'` for user-controlled values so `%` or backslashes in a
  directory name are printed literally.
- Keep the script short and readable; this is a display helper, not a
  library.

### Validation

```bash
bash -n native/helpers/statusline-command.sh
shellcheck native/helpers/statusline-command.sh
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile tests/native/check_statusline.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_statusline.py
git diff --check
git status --short
```

### Completion criteria

- The verifier passes and covers every assertion above.
- Only the two new files changed in this phase.

## Phase 3: Install wiring, settings and documentation

### Workspace

.

### Goal

The installer would install `statusline-command`, the canonical Claude
settings use it, and the owner docs describe the helper and the new status
line, with the native offline suite passing.

### Scope

- `native/toolchain.json`: add the `statusline-command` helper entry.
- `scripts/native/user_tools.py`: add it to `helper_sources`.
- `native/helpers/claude-settings.json`: change `statusLine.command`.
- Existing `tests/native/` files only where they pin helper lists or the
  status line command.
- `docs/native-tool-inventory.md` and `docs/native-user-tools.md`.

### Non-goals

- No change to the overlay, `merge_settings`, `AGENTS.md`, `proxy.py` or the
  dependency workflow.
- Do not run the installer or `claude_settings.py apply` against the real
  home.

### Required context

- Phase 2 output
- `git show e777f87 -- native/toolchain.json scripts/native/user_tools.py docs/native-tool-inventory.md docs/native-user-tools.md`
  (how the previous helper was wired, in reverse)
- `native/toolchain.json` `helpers` (the `via-annotator` entry)
- `scripts/native/user_tools.py` `plan_files` and the post-install verify loop
- `tests/native/check_user_environment.py`, `tests/native/check_manifest.py`,
  `tests/native/test_user_tools.py`, `tests/native/check_claude_settings.py`
- `docs/native-user-tools.md` ("Install User Tools And Environment", "Claude
  Settings Replacement", "Offline Validation")
- `docs/native-tool-inventory.md` ("Every Helper, Skill And Hook")

### Execution steps

1. Add to `native/toolchain.json` `helpers`, in alphabetical position:

   ```json
   "statusline-command": {
     "owner": "normal-user",
     "method": "reviewed-native-user-helper-install",
     "policy": "workspace-revision",
     "check": "offline fixture tests/native/check_statusline.py; reads stdin only, no network, credentials or files",
     "native_source": "native/helpers/statusline-command.sh"
   }
   ```

2. Add `'statusline-command': 'statusline-command.sh'` to `helper_sources` in
   `scripts/native/user_tools.py`. Do not add it to the post-install `--help`
   loop.
3. Set `statusLine.command` in `native/helpers/claude-settings.json` to
   `statusline-command`, leaving every other key unchanged.
4. Run the native tests; update only tests that pin the helper set or the old
   `printf` command. Do not weaken unrelated assertions.
5. `docs/native-tool-inventory.md`: add a helper-table row for
   `statusline-command` (source path; stdin-only, offline, no credentials or
   cache).
6. `docs/native-user-tools.md`: in "Claude Settings Replacement", state that
   the canonical file points `statusLine` at the installed
   `statusline-command`, list what it shows and when segments are omitted, and
   that the installer must run before `apply` so the command exists. Add
   `tests/native/check_statusline.py` and
   `tests/native/check_lean_proxy_aliases.py` to "Offline Validation" if they
   are not already listed.

### Implementation notes

- Keep detail in one owner doc (`native-user-tools.md`); the inventory row
  stays one line.
- If an existing checker rejects the new helper for a reason outside the
  allowed files, report it instead of widening scope.

### Validation

```bash
python3 -c "import json; json.load(open('native/toolchain.json')); json.load(open('native/helpers/claude-settings.json'))"
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile scripts/native/user_tools.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest discover -s tests/native -v
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_manifest.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_install_inputs.py --publication proposed
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_user_environment.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_claude_settings.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_statusline.py
git diff --check
```

Run the manifest and link checks listed in `docs/native-tool-inventory.md`.

### Completion criteria

- All commands pass, or each pre-existing failure is reported with output.
- The rendered wrapper `bin/statusline-command` appears in
  `check_user_environment.py`'s rendered files and passes ShellCheck.
- `claude-settings.json` differs from `HEAD` only in `statusLine.command`.

## Phase 4: Review and human handoff

### Workspace

.

### Goal

An independent consistency review of Phases 1 to 3, the full offline suite,
and a precise handoff for the human-only install, settings apply and live
checks.

### Scope

- Read-only review plus fixes to defects in files changed by earlier phases.
- Run the offline validation suite.

### Non-goals

- Do not run the installer, `claude_settings.py apply` on the real home,
  `claude-with-proxy`, `mitmweb` or provider traffic.
- No new features.

### Required context

- `git diff` of Phases 1 to 3
- Design decisions and safety scope in this plan
- `docs/native-user-tools.md` "Offline Validation"
- `docs/native-tool-inventory.md` validation list

### Execution steps

1. Review the diff against every design decision. Confirm specifically:
   `bash_aliases.sh` lost exactly one line; the helper has no network,
   credential, cache or file-write code; the output order and format match the
   spec; `claude-settings.json` changed only `statusLine.command`; the overlay,
   `AGENTS.md`, `proxy.py` and the workflow are untouched; `git status --short`
   lists only allowed files.
2. Run the complete offline suite below and record results.
3. Produce the human handoff in the final report, in this order:
   1. Stop workers; re-run the user installer (the human-only command in
      `docs/native-user-tools.md`) so `statusline-command` and `aliases.sh`
      update.
   2. `command -v statusline-command`, then
      `echo '{"model":{"display_name":"Opus 5.5"},"context_window":{"used_percentage":12}}' | statusline-command`
      (expected: `Opus 5.5 | ctx 12%`).
   3. `python3 scripts/native/claude_settings.py check` (expected: reports
      `statusLine: differs`), then `apply`, then `check` (exit 0).
   4. Start plain `claude`: the status line shows directory, model and, after
      the first response, `ctx`, `5h` and `7d` with reset durations. No
      `user@host`.
   5. If `5h`/`7d` never appear on a claude.ai plan, capture one stdin sample
      privately (temporarily set the command to
      `tee "$BUDGET_ANALYZER_WORKTREE_PARENT/workspace/tmp/statusline-input.json" | statusline-command`),
      check the `rate_limits` field names, then restore the command with
      `claude_settings.py apply`.
   6. `. "$HOME/.local/share/budget-analyzer-native/aliases.sh"`, then
      `claude-lean-proxy-medium`: `/model` and `/effort` open their pickers.
   7. In that capture, the main flow has no `skill_listing` system reminder
      and `.tools[].name` is still the whitelist.
4. List follow-ups not done here (for example per-model weekly buckets or
   usage colors) only if the review found a concrete need.

### Implementation notes

- Prefer reporting an out-of-scope issue over widening scope.
- Label pre-existing failures as such.

### Validation

```bash
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest discover -s tests/native -v
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_manifest.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_install_inputs.py --publication proposed
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_user_environment.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_claude_settings.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_lean_proxy_aliases.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_statusline.py
bash -n native/helpers/bash_aliases.sh native/helpers/statusline-command.sh
shellcheck native/helpers/*.sh native/helpers/mitmflows native/helpers/mitmflow-detail native/helpers/mitmflow-body
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile scripts/native/user_tools.py tests/native/check_lean_proxy_aliases.py tests/native/check_statusline.py
git diff --check
git status --short
```

### Completion criteria

- All commands pass, or each pre-existing failure is reported with output and
  separated from this change.
- `git status --short` shows changes only to files allowed in "Safety and
  scope".
- The handoff list is in the final report.
