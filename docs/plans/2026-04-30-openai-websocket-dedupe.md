# OpenAI WebSocket Dedupe Plan

## Context

The staged `mitmflow-render.py` helper now exposes Codex/OpenAI WebSocket frames through:

```bash
mitmflow-body <id> messages --json
```

That output is transport-faithful, but noisy. A single logical action can appear multiple times across OpenAI event types such as:

- `response.function_call_arguments.delta`
- `response.function_call_arguments.done`
- `response.output_text.done`
- `response.content_part.done`
- `response.output_item.done`

This is not a mitmproxy bug. It is actual OpenAI protocol traffic carried inside WebSocket message payloads. The helper currently emits every frame losslessly, which is correct for low-level debugging but poor for human inspection and substring search.

## Goal

Add an OpenAI-specific `--dedupe` option to the staged mitmproxy body renderer so `messages` output can collapse protocol-level repetition into one logical record per meaningful payload.

## Non-Goals

- Do not change raw transport inspection. The existing lossless view must remain available.
- Do not apply dedupe to HTTP `request` or `response` bodies.
- Do not make substring-based or fuzzy-content-based decisions that could hide genuinely distinct events.
- Do not add Anthropic-specific dedupe behavior in this change unless real duplication patterns are later demonstrated there.

## Scope

Implement `--dedupe` only for:

```bash
mitmflow-body <id> messages
```

and only when the flow provider is OpenAI.

For non-OpenAI flows, either:

- ignore `--dedupe` and emit the normal output unchanged, or
- fail clearly with a message such as `--dedupe is only supported for OpenAI websocket messages`

The latter is preferable because it keeps the flag semantics explicit.

## Proposed CLI Behavior

Examples:

```bash
mitmflow-body <id> messages --json --dedupe
mitmflow-body <id> messages --dedupe
mitmflow-body <id> messages --raw
```

Rules:

- `--dedupe` is valid only when `direction=messages`.
- `--dedupe` works with formatted and `--json` output.
- `--dedupe` should be rejected with `--raw`, because raw mode is explicitly transport-faithful.
- `--dedupe` should be rejected with `--events`, which is already invalid for `messages`.

## Semantics

`--dedupe` should dedupe by event meaning, not by repeated substrings.

The guiding principle:

- Keep the most complete final representation of a logical payload.
- Drop intermediate or wrapper events that restate the same payload without adding meaning.

### Keep

- `response.create`
  - This is the best approximation of the outbound request envelope.
- `response.created`
  - Keep only if it provides status or metadata not represented elsewhere in the selected view.
- `response.completed`
  - Keep as lifecycle metadata if the output mode intends to preserve turn boundaries.
- `response.output_text.done`
  - Preferred final assistant text record.
- `response.function_call_arguments.done`
  - Preferred final tool-call argument record.
- `response.custom_tool_call_input.done`
  - Preferred final custom-tool input record.

### Drop When Final Form Exists

- `response.output_text.delta`
  - Drop if a corresponding `response.output_text.done` exists for the same `item_id` and `content_index`.
- `response.function_call_arguments.delta`
  - Drop if a corresponding `response.function_call_arguments.done` exists for the same `item_id`.
- `response.custom_tool_call_input.delta`
  - Drop if a corresponding `response.custom_tool_call_input.done` exists for the same `item_id`.
- `response.content_part.done`
  - Drop if it duplicates `response.output_text.done` for the same `item_id` and same text payload.
- `response.output_item.done`
  - Drop if it only wraps data already preserved in a more specific event for the same `item.id`.
- `response.in_progress`
  - Drop by default in deduped output unless later debugging shows it carries unique information worth keeping.

### Preserve Distinct Events

`--dedupe` must not collapse:

- separate `response.create` events from different turns
- different tool calls with different `item_id` values
- different final texts for different items
- repeated text that happens to be identical across different turns

Identity should be derived from event type plus stable fields such as:

- `item_id`
- `content_index`
- `output_index`
- `response.id`
- normalized payload text or parsed arguments

## Output Strategy

For `--json`, emit a filtered list of the same message-wrapper objects currently returned by `messages --json`:

- preserve `from_client`
- preserve `timestamp`
- preserve parsed `data`

The difference is only which records remain in the list.

For formatted output, use the same filtered message list and render it normally.

This keeps `--dedupe` composable with future flags such as:

- `--client-only`
- `--first-create`
- `--conversation-only`

## Implementation Notes

Suggested implementation points in the staged helper:

- Parse WebSocket messages exactly as today.
- Add a provider-aware post-processing phase after message parsing and before final rendering.
- Create a helper such as:

```python
dedupe_openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]
```

- Normalize the inner `data` payload before comparisons so logically equivalent objects compare cleanly.
- Prefer explicit event-family rules over a generic "drop duplicates by JSON hash" approach.

## Edge Cases

- Some turns may end before a `.done` event is seen. In that case keep the available delta records rather than dropping everything.
- Some wrapper events may include fields that the specific event omits. If so, only drop the wrapper when it is truly redundant.
- If parsing fails for a message payload, keep that message rather than dropping it.
- If OpenAI changes event names, unknown events should pass through unchanged.

## Test Plan

Validate against a real captured Codex WebSocket flow with many repeated event forms.

1. Confirm the current non-deduped baseline still shows all events.
2. Run:

```bash
tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflow-body <id> messages --json
```

3. Run:

```bash
tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflow-body <id> messages --json --dedupe
```

4. Verify that:
   - `response.output_text.delta` records disappear when matching `.done` records exist.
   - `response.function_call_arguments.delta` records disappear when matching `.done` records exist.
   - duplicated text from `response.output_text.done`, `response.content_part.done`, and `response.output_item.done` is reduced to one logical record.
   - `response.create` remains visible.
   - repeated but distinct turns are still present.

5. Verify argument validation:

```bash
tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflow-body <id> messages --raw --dedupe
tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflow-body <id> request --dedupe
```

Both should fail clearly.

6. Re-run Python validation:

```bash
PYTHONPYCACHEPREFIX=/workspace/workspace/tmp/pycache python3 -m py_compile \
  tmp/mitmproxy-flow-improvements/proposed/ai-agent-sandbox/scripts/mitmflow-render.py
```

## Rollout

1. Implement the flag in the staged helper under `tmp/mitmproxy-flow-improvements/proposed/`.
2. Validate on a real OpenAI WebSocket flow captured through Codex.
3. Update `README.md` usage text if the flag is accepted.
4. After review, copy the staged helper into `ai-agent-sandbox/` from a writable context and rebuild the devcontainer.

## Current Implementation Decisions

1. `response.completed` remains in deduped output so turn boundaries and lifecycle metadata stay visible.
2. `codex.rate_limits` and other unknown OpenAI events pass through unchanged; this change only removes explicitly redundant event families.
3. `response.output_item.done` is currently preserved for reasoning items, and for any other wrapper that still carries non-redundant fields not represented by a more specific final event.
4. A future `--conversation-only` mode should build on top of `--dedupe` rather than replacing it, because `--dedupe` preserves a still-debuggable event stream.
