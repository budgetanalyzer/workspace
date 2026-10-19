# HTTPS Traffic Inspection

Native installation includes mitmproxy and the flow helpers, but ordinary
sessions remain unproxied. Installation does not generate, copy or trust an
inspection CA. A human must explicitly initialize the separate guest-owned
inspection identity by following
[Optional Human Inspection Setup](native-user-tools.md#optional-human-inspection-setup).

The wrappers require private CA/token files with safe ownership and modes,
bind proxy and UI listeners only to `127.0.0.1`, reject occupied ports, and keep
upstream TLS verification enabled. Provider wrappers create a temporary
public-plus-inspection bundle under `tmp/mitmproxy-private`, scope proxy and
trust variables to the child process, and remove the bundle on exit. They do
not import the inspection root into system or NSS trust.

Claude remains installed through npm because optional proxy streaming depends
on npm Claude's proxy behavior; see
[anthropics/claude-code#14165](https://github.com/anthropics/claude-code/issues/14165).

## Launch

Start the foreground proxy UI or launch one provider through a child proxy:

```bash
start-proxy
claude-with-proxy
codex-with-proxy
```

`codex-with-proxy` delegates to `codex-lean`, including its explicit
high-authority permission mode. Model and effort selection still forward:

```bash
codex-with-proxy --model MODEL
CODEX_REASONING_EFFORT=xhigh codex-with-proxy
```

`start-proxy` starts only mitmweb; it does not proxy an ordinary provider
session. Stop foreground listeners with `Ctrl+C`.

## Inspect Flows

List recent flows:

```bash
mitmflows --limit 20
mitmflows --provider anthropic
mitmflows --provider openai --json
mitmflows --host openai --path /v1/responses
```

Inspect request, response, SSE or WebSocket payloads:

```bash
mitmflow-body FLOW_ID request --json
mitmflow-body FLOW_ID response
mitmflow-body FLOW_ID response --events
mitmflow-body FLOW_ID response --raw
mitmflow-body FLOW_ID messages --json
mitmflow-body FLOW_ID messages --json --dedupe
```

Use `messages` only for WebSocket-backed flows. `--dedupe` is supported only
for OpenAI message output and cannot be combined with `--raw`.

Render a summary or full diagnostic view:

```bash
mitmflow-detail FLOW_ID
mitmflow-detail FLOW_ID --full
mitmflow-detail FLOW_ID --raw
mitmflow-detail FLOW_ID --md
```

Exports default to `tmp/mitmproxy-flows/`. An explicit export path must remain
inside the workspace. Private proxy bundles use `tmp/mitmproxy-private/`.
Captured requests can contain secrets, so inspect and clean these human-owned
temporary files privately after listeners stop.

## Analyzing The Full System Prompt

Capture one minimal Claude session and read what the model actually receives.
The lean launchers are described in
[Lean Claude Launchers](launch-options.md#lean-claude-launchers); the
settings replacement that keeps `AGENTS.md` to a single copy is in
[Claude Settings Replacement](native-user-tools.md#claude-settings-replacement).

```bash
. "$HOME/.local/share/budget-analyzer-native/aliases.sh"
claude-lean-proxy-medium          # send one trivial prompt, then exit
```

Find the main-model flow. Ancillary flows differ in model and carry few or no
tools:

```bash
mitmflows --provider anthropic --path /v1/messages --limit 20
mitmflows --provider anthropic --path /v1/messages --limit 20 --json
mitmflow-detail FLOW_ID --full
```

Query the request body (`FLOW_ID` may be truncated):

```bash
REQ() { mitmflow-body "$1" request --json; }

# System blocks: index, length, first characters
REQ FLOW_ID | jq -r '.system | if type=="string" then [.] else map(.text) end
  | to_entries[] | "\(.key)\t\(.value|length)\t\(.value[0:60]|gsub("\n";" "))"'

# Tool names, then serialized size per tool
REQ FLOW_ID | jq -r '.tools[].name'
REQ FLOW_ID | jq -r '.tools[] | "\(.name)\t\(tojson|length)"'

# Model, thinking and effort fields
REQ FLOW_ID | jq '{model, thinking, effort: .output_config.effort, max_tokens}'

# Occurrences of AGENTS.md text in the whole request (expected: 1) and where
REQ FLOW_ID | jq '[.. | strings | select(contains("# Workspace Entry Point"))] | length'
REQ FLOW_ID | jq -r 'paths(type=="string" and contains("# Workspace Entry Point"))
  | map(tostring) | join(".")'
```

Captured requests contain secrets and private repository text. Output from
`mitmflow-body` is redacted by default; do not pass `--no-redact` unless you are
debugging privately. Exports under `tmp/` are private, and a human cleans them
after listeners stop.

The full default prompt is what this workflow wants. To compare, pass
`--system-prompt-snapshot off` or `--exclude-dynamic-system-prompt-sections`
through the lean launcher as ordinary trailing Claude arguments; both are
optional comparison knobs, not part of the baseline.

### Human live verification checklist

Live verification and the real settings replacement are human-only and are not
performed by workers.

1. `python3 scripts/native/claude_settings.py check` (expect the legacy `hooks`
   difference), then `apply`, then `check` again (exit 0) and `apply` again
   (`already up to date`).
2. Stop workers and re-run the user installer so `aliases.sh` updates; confirm
   it still verifies against the replaced settings file.
3. `. "$HOME/.local/share/budget-analyzer-native/aliases.sh"`.
4. `claude-lean-proxy-medium`, send a one-line prompt, exit.
5. In the main flow, `.tools[].name` is the whitelist (`Bash`, `Read`, `Edit`,
   `Write`, `WebFetch`, `WebSearch`) and `Agent`, `Grep` and `Glob` are absent.
   Claude Code also injects a `DeferredToolPlaceholder` entry
   (`defer_loading: true`) regardless of `--tools`; it is expected. If `--tools`
   rejects a name, adjust `CLAUDE_LEAN_TOOLS` and record the real names in the
   docs.
6. The `AGENTS.md` text occurs exactly once in the whole request; note whether
   it lands in the system prompt or the first user message.
7. No skills list, MCP tools or memory section appear; review ancillary flows
   for anything unexpectedly still firing. A first lean capture on 2.1.289 still
   showed a Haiku session-title request and a `count_tokens` request despite
   `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`; treat those as known ancillary
   flows when picking the main-model flow.
8. Effort/thinking fields reflect `medium`; repeat with `claude-lean-proxy-high` and
   compare.
9. The git-instructions section is absent from the system prompt with
   `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1`; report it if still present.
10. No `permissions.deny` for `Agent` is needed, because `--tools` already
    excludes it.
11. In the lean session, `/model` and `/effort` open their pickers, and the
    captured main flow still has no `skill_listing` system reminder.

## Development And Validation

Canonical portable flow resources live in `native/helpers/`; lifecycle,
listener and scoped-trust behavior lives in `scripts/native/proxy.py`. Edit
those sources directly and run the offline helper/environment checks in
[Native Guest User Tools](native-user-tools.md#offline-validation).

Do not test changes with real provider traffic unless the human explicitly
requests optional interception and has privately reviewed the inspection
identity and capture scope. Offline fixtures must not initialize a CA, start a
listener, read real credentials or write outside repository `tmp/`.
