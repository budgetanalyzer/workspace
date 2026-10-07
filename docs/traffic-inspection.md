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
inside the workspace. Addon dumps use `tmp/claude-proxy-dumps/`; private proxy
bundles use `tmp/mitmproxy-private/`. Captured requests can contain secrets, so
inspect and clean these human-owned temporary files privately after listeners
stop.

## Development And Validation

Canonical portable flow/prompt resources live in `native/helpers/`; lifecycle,
listener and scoped-trust behavior lives in `scripts/native/proxy.py`. Edit
those sources directly and run the offline helper/environment checks in
[Native Guest User Tools](native-user-tools.md#offline-validation).

Do not test changes with real provider traffic unless the human explicitly
requests optional interception and has privately reviewed the inspection
identity and capture scope. Offline fixtures must not initialize a CA, start a
listener, read real credentials or write outside repository `tmp/`.
