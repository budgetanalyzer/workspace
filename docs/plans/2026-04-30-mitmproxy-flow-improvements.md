# Mitmproxy Flow Improvements Plan

## Context

The current `mitmflows`, `mitmflow-body`, and `mitmflow-detail` helpers live under `ai-agent-sandbox/`, which is mounted read-only inside the devcontainer. Any implementation work must therefore be authored as full replacement files under `/workspace/workspace/tmp/` and tested there before a human applies the changes to `ai-agent-sandbox/` from outside the read-only mount.

Current source snapshots for this plan were copied to:

```text
tmp/mitmproxy-flow-improvements/current/ai-agent-sandbox/
```

As of April 30, 2026, the latest stable mitmproxy release verified from PyPI and GitHub is `12.2.2`, released April 12, 2026. The running container already reports `Mitmproxy: 12.2.2`, but the Dockerfile currently uses an unpinned `pipx install mitmproxy`, so rebuilds are not reproducible.

## Clarifying Questions

1. Should the new Codex proxy launchers be limited to parity with the existing Codex aliases (`codex-dangerous`, `codex-high`, `codex-max`), or should they also include model-specific variants once preferred Codex models are chosen?
2. Should full flow exports default to staying inside `/workspace/workspace/tmp/mitmproxy-flows/`, even when the user passes a relative `--out` path, to preserve the workspace guardrail?
3. Should request and response body renderers redact only transport secrets by default, or also redact likely prompt/user content when producing Markdown summaries for sharing?

If unanswered, use these defaults: implement only alias-parity Codex launchers, keep generated exports under `tmp/mitmproxy-flows/` by default, and redact credentials while preserving prompt/message content because the primary use case is debugging AI CLI traffic.

## Goals

- Make flow inspection useful for AI CLI traffic instead of dumping hard-to-read raw streams.
- Keep raw extraction available for exact debugging while adding readable summaries and reconstructed views.
- Support both Anthropic Claude and OpenAI Codex traffic.
- Keep all generated artifacts and test copies inside `/workspace/workspace/`.
- Pin mitmproxy to the current stable version so future rebuilds are deterministic.

## Non-Goals

- Do not override the Codex system prompt. There is no current need for a Codex prompt-replacement addon.
- Do not replace mitmweb. The browser UI remains useful; the scripts should make common terminal inspection faster.
- Do not add git operations to the workflow. Implementation sessions should leave commit control to the user.

## Proposed Design

Replace the fragile Bash-heavy formatting path with a small Python renderer and keep the shell commands as thin entrypoints.

Proposed files to author as full files under `tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/`:

```text
Dockerfile
bash_aliases.sh
scripts/start-proxy.sh
scripts/mitmflows
scripts/mitmflow-body
scripts/mitmflow-detail
scripts/mitmflow-render.py
scripts/codex-with-proxy.sh
scripts/codex-high-with-proxy.sh
scripts/codex-max-with-proxy.sh
scripts/codex-54-with-proxy.sh
scripts/codex-54-mini-with-proxy.sh
scripts/codex-53-with-proxy.sh
scripts/codex-mini-with-proxy.sh
```

### Shared Flow Renderer

Add `scripts/mitmflow-render.py` as the canonical implementation for listing, body extraction, detail rendering, and export. The existing shell scripts should call this helper rather than duplicate parsing logic.

The renderer should:

- Resolve truncated flow IDs and fail clearly on zero or multiple matches.
- Fetch flow metadata and request/response content from the mitmweb REST API using `MITM_API` and `MITM_PASS`.
- Decode bodies by content type and content encoding where mitmproxy exposes decoded content, while preserving a raw mode for byte-exact output.
- Pretty-print JSON request and response bodies.
- Parse Server-Sent Events into structured events rather than concatenated text.
- Reconstruct Anthropic streaming responses into final `message` JSON, including text, thinking blocks, tool uses, input JSON deltas, stop reason, and usage.
- Reconstruct OpenAI Responses API streams into a readable final response, including output text, reasoning summaries when present, function/tool calls, tool-call arguments, errors, and usage.
- Fall back to raw event tables for unknown SSE event types.
- Redact credentials in headers and common JSON fields such as `api_key`, `authorization`, `access_token`, `refresh_token`, `cookie`, and `set-cookie`.

### `mitmflows`

Keep the command simple, but make the table more useful:

- Show ID prefix, timestamp, method, status, provider, model, host, path, request bytes, response bytes, content type, and stream indicator.
- Add `--provider anthropic|openai|all`.
- Add `--host <substring>` and `--path <substring>` filters.
- Add `--json` for machine-readable output.
- Keep `--full` as a compatibility alias for raw flow JSON.

### `mitmflow-body`

Change this from "raw bytes only" to a body extraction command with explicit modes:

- Default: formatted body, provider-aware SSE reconstruction when applicable.
- `--raw`: byte-ish raw content from the current mitmweb `content.data` endpoint.
- `--events`: normalized SSE event list.
- `--json`: parsed JSON body or reconstructed stream JSON.
- `--save <file>`: write to a file under `tmp/mitmproxy-flows/` by default.
- Preserve current positional form: `mitmflow-body <flow-id> [request|response]`.

### `mitmflow-detail`

Make the default terminal output a summary, not a wall of text:

- Top section: flow ID, provider, model, method, URL, status, timing, size, content types.
- Request section: redacted headers plus compact API payload summary.
- Response section: reconstructed assistant output, tool calls, stop reason, usage, and errors.
- Add `--full` for complete formatted bodies.
- Add `--raw` for exact current behavior.
- Add `--md [file]` for a Markdown diagnostic report written under `tmp/mitmproxy-flows/` by default.
- Add `--no-redact` only for local debugging, with a warning on stderr.

## Codex Proxy Launchers

Add Codex proxy scripts parallel to the Claude scripts, but without a prompt-replacement addon:

```text
codex-with-proxy
codex-high-with-proxy
codex-max-with-proxy
codex-54-with-proxy
codex-54-mini-with-proxy
codex-53-with-proxy
codex-mini-with-proxy
```

Each script should:

- Start or reuse mitmweb on `PROXY_PORT` with `WEB_PORT=PROXY_PORT+1`.
- Export `HTTPS_PROXY`, `HTTP_PROXY`, and `NODE_EXTRA_CA_CERTS`.
- Set `CODEX_DISABLE_PROJECT_DOC=1`, matching `bash_aliases.sh`.
- Pass `--dangerously-bypass-approvals-and-sandbox`.
- For high: add `-c model_reasoning_effort=high`.
- For max: add `-c model_reasoning_effort=xhigh`.
- For model-pinned wrappers: set `CODEX_MODEL` before delegating to `codex-with-proxy`, while still allowing an explicit `--model` flag to override it at invocation time.
- Avoid any Codex system prompt override.

Update `Dockerfile` to copy these scripts into `/usr/local/bin` and chmod them with the existing proxy helpers.

Update `bash_aliases.sh` to include short aliases if desired:

```bash
alias codex-proxy="codex-with-proxy"
alias codex-high-proxy="codex-high-with-proxy"
alias codex-max-proxy="codex-max-with-proxy"
```

## Dockerfile Changes

Make mitmproxy installation reproducible and add only dependencies that materially improve the scripts:

- Add `ARG MITMPROXY_VERSION=12.2.2`.
- Replace `pipx install mitmproxy` with `pipx install "mitmproxy==${MITMPROXY_VERSION}"`.
- Consider installing Python packages used by `mitmflow-render.py` with system Python, not inside the mitmproxy pipx venv, so helper scripts can import them reliably.
- Prefer Python standard library for HTTP, JSON, SSE, and Markdown generation. Add `rich` only if terminal formatting uses it directly; otherwise avoid the extra dependency.
- Fix the existing chmod list to include `claude-46-custom-system-prompt`; it is copied but not currently included in the chmod command.

## Documentation Updates

Update `README.md` and `AGENTS.md` in the same implementation work:

- Document the new Codex proxy launchers.
- Document the improved `mitmflows`, `mitmflow-body`, and `mitmflow-detail` options.
- Document the default export directory under `tmp/mitmproxy-flows/`.
- Document that Codex proxying is inspection-only and does not override prompts.
- Note that mitmproxy is pinned to `12.2.2` until explicitly upgraded.

## Test Plan

All tests should run from files under `tmp/mitmproxy-flow-improvements/proposed/`.

1. Shell lint the entrypoints:

```bash
shellcheck tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflows
shellcheck tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflow-body
shellcheck tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflow-detail
shellcheck tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/codex-with-proxy.sh
shellcheck tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/codex-high-with-proxy.sh
shellcheck tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/codex-max-with-proxy.sh
```

2. Run Python static checks:

```bash
PYTHONPYCACHEPREFIX=/workspace/workspace/tmp/pycache python3 -m py_compile \
  tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflow-render.py
```

3. Start a proxy from `tmp/` on a non-default port:

```bash
PROXY_PORT=9180 tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/codex-with-proxy.sh --help
```

4. Capture one Claude request and one Codex request through mitmproxy.

5. Verify listing:

```bash
tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflows --limit 20
tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflows --provider openai --json
tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflows --provider anthropic --json
```

6. Verify body rendering:

```bash
tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflow-body <id> request --json
tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflow-body <id> response --events
tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflow-body <id> response --raw
```

7. Verify diagnostic reports:

```bash
tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflow-detail <id>
tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflow-detail <id> --full
tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflow-detail <id> --md
```

8. Verify generated files remain inside `/workspace/workspace/tmp/`.

## Rollout

1. Implement and test full replacement files under `tmp/mitmproxy-flow-improvements/proposed/`.
2. Review diffs between `current/` and `proposed/`.
3. From a context with write access to the sandbox source, copy the proposed files into `ai-agent-sandbox/`.
4. Rebuild the devcontainer.
5. Re-run the test plan against installed commands from `/usr/local/bin`.

## Risks

- Codex may not honor proxy environment variables in the same way as the npm Claude Code package. The first implementation should validate actual captured OpenAI API flows before declaring Codex proxy support complete.
- OpenAI and Anthropic streaming event schemas can change. The renderer should preserve unknown events in output instead of silently dropping them.
- Over-redaction can make debugging prompts impossible; under-redaction can leak credentials into Markdown exports. Default redaction should target secrets, not normal message content.
