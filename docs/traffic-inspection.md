# HTTPS Traffic Inspection

mitmproxy is pre-installed with its CA cert trusted system-wide and by Node.js (`NODE_EXTRA_CA_CERTS`).

> **Note:** Claude Code is installed via npm (not the native binary) because the native Bun binary ignores `HTTP_PROXY` for streaming — see [anthropics/claude-code#14165](https://github.com/anthropics/claude-code/issues/14165).

## Quick Reference

Start the proxy or launch a CLI through it:

```bash
start-proxy
claude-with-proxy
codex-with-proxy
```

`codex-with-proxy` starts mitmproxy and then delegates to `codex-lean`, so it keeps the same web-search, MCP, subagent, connector, and UI defaults as direct `codex-lean` launches. Project instruction loading remains enabled, including applicable `AGENTS.md` files.

Codex model selection still works directly on the CLI:

```bash
codex-with-proxy --model gpt-5.4
codex-with-proxy --model gpt-5.4-mini
CODEX_REASONING_EFFORT=xhigh codex-with-proxy
```

## Inspecting Flows

List recent flows:

```bash
mitmflows --limit 20
mitmflows --provider anthropic
mitmflows --provider openai --json
mitmflows --host openai --path /v1/responses
```

Inspect request, response, or WebSocket payloads:

```bash
mitmflow-body <id> request --json
mitmflow-body <id> response
mitmflow-body <id> response --events
mitmflow-body <id> response --raw
mitmflow-body <id> messages --json
mitmflow-body <id> messages --json --dedupe
```

- Use `request` and `response` for normal HTTP and SSE inspection.
- Use `messages` only for WebSocket-backed flows (currently most useful for OpenAI traffic).
- `--dedupe` is only supported for OpenAI `messages` output and is rejected with `--raw`.

Render a summary or full diagnostic view:

```bash
mitmflow-detail <id>
mitmflow-detail <id> --full
mitmflow-detail <id> --raw
mitmflow-detail <id> --md
```

## Exports

Exports default to [`tmp/mitmproxy-flows/`](/workspace/workspace/tmp/mitmproxy-flows/):

```bash
mitmflow-body <id> request --json --save anthropic-request.json
mitmflow-detail <id> --md
```

Pass an absolute path inside the workspace to override the default location.

## Staged Improvements

Because `ai-agent-sandbox/` is mounted read-only inside the devcontainer, mitmproxy helper changes are staged under [`tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/`](/workspace/workspace/tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/) until a human copies them into `ai-agent-sandbox/` and rebuilds the container.

The staged helpers add provider filtering, richer body/detail rendering, export support, and Codex proxy launcher wrappers.

When validating staged Python helpers, direct bytecode into the workspace:

```bash
PYTHONPYCACHEPREFIX=/workspace/workspace/tmp/pycache python3 -m py_compile \
  tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflow-render.py
```

After rollout and rebuild, the same commands are available in `PATH` without the `tmp/...` prefix.
