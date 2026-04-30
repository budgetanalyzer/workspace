#!/usr/bin/env python3
"""Render mitmproxy flows for AI CLI debugging."""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


MITM_API = os.environ.get("MITM_API", "http://localhost:9081").rstrip("/")
MITM_PASS = os.environ.get("MITM_PASS", "mitmlocal")
WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/workspace/workspace")).resolve()
EXPORT_ROOT = WORKSPACE_ROOT / "tmp" / "mitmproxy-flows"
SECRET_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "access_token",
    "refresh_token",
    "cookie",
    "set_cookie",
    "x_api_key",
    "proxy_authorization",
}


class MitmError(RuntimeError):
    pass


def http_get(path: str) -> bytes:
    url = f"{MITM_API}{path}"
    request = Request(url, headers={"Authorization": f"Bearer {MITM_PASS}"})
    try:
        with urlopen(request, timeout=15) as response:
            return response.read()
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise MitmError(f"{exc.code} from {url}: {body or exc.reason}") from exc
    except URLError as exc:
        raise MitmError(f"cannot reach mitmweb at {MITM_API}: {exc.reason}") from exc


def http_get_json(path: str) -> Any:
    try:
        return json.loads(http_get(path).decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise MitmError(f"invalid JSON from {path}: {exc}") from exc


def fatal(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(1)


def to_text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def normalize_key(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def get_section(flow: dict[str, Any], direction: str) -> dict[str, Any]:
    section = flow.get(direction) or {}
    if not section:
        raise MitmError(f"flow {flow.get('id', '<unknown>')} has no {direction} section")
    return section


def headers_as_pairs(section: dict[str, Any]) -> list[list[str]]:
    headers = section.get("headers") or []
    result: list[list[str]] = []
    for item in headers:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            result.append([str(item[0]), str(item[1])])
    return result


def header_value(section: dict[str, Any], name: str) -> str:
    wanted = name.lower()
    for key, value in headers_as_pairs(section):
        if key.lower() == wanted:
            return value
    return ""


def provider_for_flow(flow: dict[str, Any]) -> str:
    request = get_section(flow, "request")
    host = request.get("pretty_host", "").lower()
    path = request.get("path", "").lower()
    if "anthropic" in host or "claude" in host:
        return "anthropic"
    if (
        "openai" in host
        or host.endswith("chatgpt.com")
        or host.endswith("oaistatsig.com")
        or path.startswith("/backend-api/codex/")
    ):
        return "openai"
    return "other"


def looks_like_sse(section: dict[str, Any], body_text: str) -> bool:
    content_type = header_value(section, "content-type").lower()
    if "text/event-stream" in content_type:
        return True
    sample = body_text.lstrip()
    return sample.startswith("event:") or sample.startswith("data:")


def format_timestamp(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def short_timestamp(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%H:%M:%S")


def size_value(section: dict[str, Any], body_bytes: bytes | None = None) -> int:
    for key in ("contentLength", "content_length"):
        value = section.get(key)
        if isinstance(value, int):
            return value
    if body_bytes is not None:
        return len(body_bytes)
    return 0


def safe_json_loads(text: str) -> Any | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def parse_json_body(body_bytes: bytes) -> Any | None:
    return safe_json_loads(to_text(body_bytes))


def secret_key(key: str) -> bool:
    return normalize_key(key) in SECRET_KEYS


def redact_value(name: str, value: Any, enabled: bool) -> Any:
    if enabled and secret_key(name):
        return "[REDACTED]"
    return redact_json_like(value, enabled)


def redact_json_like(value: Any, enabled: bool) -> Any:
    if not enabled:
        return value
    if isinstance(value, dict):
        return {key: redact_value(key, val, enabled) for key, val in value.items()}
    if isinstance(value, list):
        return [redact_json_like(item, enabled) for item in value]
    return value


def redact_headers(headers: list[list[str]], enabled: bool) -> list[list[str]]:
    if not enabled:
        return headers
    result: list[list[str]] = []
    for key, value in headers:
        result.append([key, "[REDACTED]" if secret_key(key) else value])
    return result


def pretty_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=False)


def parse_sse_events(body_text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    event_name = "message"
    data_lines: list[str] = []
    event_id: str | None = None

    def flush() -> None:
        nonlocal event_name, data_lines, event_id
        if not data_lines and event_name == "message":
            return
        data_raw = "\n".join(data_lines)
        payload = safe_json_loads(data_raw)
        events.append(
            {
                "event": event_name,
                "id": event_id,
                "data_raw": data_raw,
                "data": payload if payload is not None else data_raw,
            }
        )
        event_name = "message"
        data_lines = []
        event_id = None

    for raw_line in body_text.splitlines():
        line = raw_line.rstrip("\r")
        if not line:
            flush()
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]
        if field == "event":
            event_name = value or "message"
        elif field == "data":
            data_lines.append(value)
        elif field == "id":
            event_id = value
    flush()
    return events


def parse_partial_json(raw: str) -> Any:
    parsed = safe_json_loads(raw)
    return parsed if parsed is not None else raw


def reconstruct_anthropic(events: list[dict[str, Any]]) -> dict[str, Any]:
    message: dict[str, Any] | None = None
    blocks: dict[int, dict[str, Any]] = {}
    errors: list[Any] = []
    unknown: list[dict[str, Any]] = []
    ping_count = 0

    for event in events:
        payload = event["data"] if isinstance(event["data"], dict) else None
        event_type = payload.get("type") if payload else event["event"]

        if event_type == "message_start" and payload:
            message = copy.deepcopy(payload.get("message") or {})
            message["content"] = []
        elif event_type == "content_block_start" and payload:
            index = int(payload.get("index", 0))
            blocks[index] = copy.deepcopy(payload.get("content_block") or {})
            if blocks[index].get("type") in {"tool_use", "server_tool_use"}:
                blocks[index]["_input_json"] = ""
        elif event_type == "content_block_delta" and payload:
            index = int(payload.get("index", 0))
            block = blocks.setdefault(index, {})
            delta = payload.get("delta") or {}
            delta_type = delta.get("type")
            if delta_type == "text_delta":
                block["text"] = block.get("text", "") + delta.get("text", "")
            elif delta_type == "thinking_delta":
                block["thinking"] = block.get("thinking", "") + delta.get("thinking", "")
            elif delta_type == "signature_delta":
                block["signature"] = delta.get("signature", "")
            elif delta_type == "input_json_delta":
                block["_input_json"] = block.get("_input_json", "") + delta.get("partial_json", "")
            else:
                unknown.append({"event": event_type, "delta_type": delta_type, "payload": payload})
        elif event_type == "content_block_stop" and payload:
            index = int(payload.get("index", 0))
            block = blocks.get(index)
            if block and "_input_json" in block:
                raw = block.pop("_input_json", "")
                block["input"] = parse_partial_json(raw or "{}")
        elif event_type == "message_delta" and payload:
            if message is None:
                message = {"content": []}
            delta = payload.get("delta") or {}
            message.update(delta)
            usage = payload.get("usage")
            if usage:
                merged = copy.deepcopy(message.get("usage") or {})
                merged.update(usage)
                message["usage"] = merged
        elif event_type == "message_stop":
            continue
        elif event_type == "ping":
            ping_count += 1
        elif event_type == "error" and payload:
            errors.append(payload.get("error") or payload)
        else:
            unknown.append({"event": event_type, "payload": payload if payload is not None else event["data_raw"]})

    if message is not None:
        for index in sorted(blocks):
            message["content"].append(blocks[index])

    result: dict[str, Any] = {"provider": "anthropic"}
    if message is not None:
        result["message"] = message
    if errors:
        result["errors"] = errors
    if unknown:
        result["unknown_events"] = unknown
    if ping_count:
        result["ping_count"] = ping_count
    return result


def ensure_output_item(items: dict[str, dict[str, Any]], output_order: list[str], item_id: str, output_index: int | None, item_type: str | None = None) -> dict[str, Any]:
    item = items.get(item_id)
    if item is None:
        item = {"id": item_id}
        if output_index is not None:
            item["output_index"] = output_index
        if item_type:
            item["type"] = item_type
        items[item_id] = item
        output_order.append(item_id)
    else:
        if output_index is not None:
            item.setdefault("output_index", output_index)
        if item_type and "type" not in item:
            item["type"] = item_type
    return item


def ensure_content_part(item: dict[str, Any], content_index: int, part_type: str | None = None) -> dict[str, Any]:
    content = item.setdefault("content", [])
    while len(content) <= content_index:
        content.append({})
    part = content[content_index]
    if part_type and "type" not in part:
        part["type"] = part_type
    return part


def reconstruct_openai(events: list[dict[str, Any]]) -> dict[str, Any]:
    response: dict[str, Any] = {}
    items: dict[str, dict[str, Any]] = {}
    output_order: list[str] = []
    errors: list[Any] = []
    unknown: list[dict[str, Any]] = []

    for event in events:
        payload = event["data"] if isinstance(event["data"], dict) else None
        if payload is None:
            unknown.append({"event": event["event"], "payload": event["data_raw"]})
            continue

        event_type = payload.get("type", event["event"])
        if event_type == "response.created":
            response = copy.deepcopy(payload.get("response") or {})
            for item in response.get("output") or []:
                item_id = item.get("id")
                if not item_id:
                    continue
                items[item_id] = copy.deepcopy(item)
                output_order.append(item_id)
        elif event_type == "response.in_progress":
            response.setdefault("status", "in_progress")
        elif event_type == "response.output_item.added":
            item = copy.deepcopy(payload.get("item") or {})
            item_id = item.get("id") or payload.get("item_id")
            if item_id:
                items[item_id] = item
                if item_id not in output_order:
                    output_order.append(item_id)
        elif event_type == "response.output_item.done":
            item = copy.deepcopy(payload.get("item") or {})
            item_id = item.get("id") or payload.get("item_id")
            if item_id:
                base = ensure_output_item(items, output_order, item_id, payload.get("output_index"), item.get("type"))
                base.update(item)
        elif event_type == "response.content_part.added":
            item_id = payload.get("item_id")
            if item_id:
                item = ensure_output_item(items, output_order, item_id, payload.get("output_index"))
                part = ensure_content_part(item, int(payload.get("content_index", 0)))
                part.update(copy.deepcopy(payload.get("part") or {}))
        elif event_type == "response.content_part.done":
            item_id = payload.get("item_id")
            if item_id:
                item = ensure_output_item(items, output_order, item_id, payload.get("output_index"))
                part = ensure_content_part(item, int(payload.get("content_index", 0)))
                part.update(copy.deepcopy(payload.get("part") or {}))
        elif event_type == "response.output_text.delta":
            item_id = payload.get("item_id")
            if item_id:
                item = ensure_output_item(items, output_order, item_id, payload.get("output_index"), "message")
                part = ensure_content_part(item, int(payload.get("content_index", 0)), "output_text")
                part["text"] = part.get("text", "") + payload.get("delta", "")
        elif event_type == "response.output_text.done":
            item_id = payload.get("item_id")
            if item_id:
                item = ensure_output_item(items, output_order, item_id, payload.get("output_index"), "message")
                part = ensure_content_part(item, int(payload.get("content_index", 0)), "output_text")
                part["text"] = payload.get("text", part.get("text", ""))
        elif event_type == "response.refusal.delta":
            item_id = payload.get("item_id")
            if item_id:
                item = ensure_output_item(items, output_order, item_id, payload.get("output_index"), "message")
                part = ensure_content_part(item, int(payload.get("content_index", 0)), "refusal")
                part["refusal"] = part.get("refusal", "") + payload.get("delta", "")
        elif event_type == "response.refusal.done":
            item_id = payload.get("item_id")
            if item_id:
                item = ensure_output_item(items, output_order, item_id, payload.get("output_index"), "message")
                part = ensure_content_part(item, int(payload.get("content_index", 0)), "refusal")
                part["refusal"] = payload.get("refusal", part.get("refusal", ""))
        elif event_type == "response.function_call_arguments.delta":
            item_id = payload.get("item_id")
            if item_id:
                item = ensure_output_item(items, output_order, item_id, payload.get("output_index"), "function_call")
                item["arguments_delta"] = item.get("arguments_delta", "") + payload.get("delta", "")
        elif event_type == "response.function_call_arguments.done":
            item_id = payload.get("item_id")
            if item_id:
                item = ensure_output_item(items, output_order, item_id, payload.get("output_index"), "function_call")
                raw_arguments = payload.get("arguments", item.get("arguments_delta", ""))
                item["name"] = payload.get("name", item.get("name"))
                item["arguments"] = parse_partial_json(raw_arguments)
        elif event_type == "response.reasoning_summary_part.added":
            item_id = payload.get("item_id")
            if item_id:
                item = ensure_output_item(items, output_order, item_id, payload.get("output_index"), "reasoning")
                summaries = item.setdefault("summary", [])
                summaries.append(copy.deepcopy(payload.get("part") or {}))
        elif event_type == "response.reasoning_summary_text.delta":
            item_id = payload.get("item_id")
            if item_id:
                item = ensure_output_item(items, output_order, item_id, payload.get("output_index"), "reasoning")
                summaries = item.setdefault("summary", [])
                index = int(payload.get("summary_index", 0))
                while len(summaries) <= index:
                    summaries.append({"type": "summary_text", "text": ""})
                summaries[index]["text"] = summaries[index].get("text", "") + payload.get("delta", "")
        elif event_type == "response.reasoning_summary_text.done":
            item_id = payload.get("item_id")
            if item_id:
                item = ensure_output_item(items, output_order, item_id, payload.get("output_index"), "reasoning")
                summaries = item.setdefault("summary", [])
                index = int(payload.get("summary_index", 0))
                while len(summaries) <= index:
                    summaries.append({"type": "summary_text", "text": ""})
                summaries[index]["text"] = payload.get("text", summaries[index].get("text", ""))
        elif event_type == "response.completed":
            completed = payload.get("response") or {}
            response.update(copy.deepcopy(completed))
        elif event_type in {"response.failed", "error"}:
            errors.append(payload.get("error") or payload)
        else:
            unknown.append({"event": event_type, "payload": payload})

    finalized_output: list[dict[str, Any]] = []
    for item_id in output_order:
        item = copy.deepcopy(items[item_id])
        if "arguments" not in item and "arguments_delta" in item:
            item["arguments"] = parse_partial_json(item["arguments_delta"])
        finalized_output.append(item)

    if finalized_output:
        response["output"] = finalized_output

    result: dict[str, Any] = {"provider": "openai"}
    if response:
        result["response"] = response
    if errors:
        result["errors"] = errors
    if unknown:
        result["unknown_events"] = unknown
    return result


def render_event_table(events: list[dict[str, Any]]) -> str:
    rows = []
    for index, event in enumerate(events, start=1):
        payload = event["data"]
        event_type = event["event"]
        payload_type = payload.get("type") if isinstance(payload, dict) else ""
        summary = payload_type or event["data_raw"].splitlines()[0][:80]
        rows.append(f"{index:>3}  {event_type:<36} {summary}")
    return "\n".join(rows)


def decode_body(flow: dict[str, Any], direction: str) -> tuple[dict[str, Any], bytes]:
    section = get_section(flow, direction)
    flow_id = flow["id"]
    data = http_get(f"/flows/{quote(flow_id)}/{direction}/content.data")
    return section, data


def decode_messages(flow: dict[str, Any], content_view: str = "Raw") -> list[dict[str, Any]]:
    flow_id = flow["id"]
    data = http_get_json(f"/flows/{quote(flow_id)}/messages/content/{quote(content_view)}.json")
    if not isinstance(data, list):
        raise MitmError(f"flow {flow_id} returned invalid WebSocket message data")
    return data


def parse_message_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    parsed = safe_json_loads(value)
    return parsed if parsed is not None else value


def message_payload(message: dict[str, Any]) -> dict[str, Any] | None:
    payload = message.get("data")
    return payload if isinstance(payload, dict) else None


def message_event_type(message: dict[str, Any]) -> str:
    payload = message_payload(message)
    if payload is None:
        return ""
    event_type = payload.get("type")
    return event_type if isinstance(event_type, str) else ""


def normalize_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: normalize_json_value(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [normalize_json_value(item) for item in value]
    return value


def normalized_json_text(value: Any) -> str:
    return json.dumps(normalize_json_value(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def normalized_payload_text(value: Any) -> str:
    if isinstance(value, str):
        return normalized_json_text(parse_partial_json(value))
    return normalized_json_text(value)


def response_identity(payload: dict[str, Any]) -> str:
    direct = payload.get("response_id")
    if isinstance(direct, str) and direct:
        return direct
    response = payload.get("response")
    if isinstance(response, dict):
        nested = response.get("id")
        if isinstance(nested, str) and nested:
            return nested
    return ""


def content_index_value(payload: dict[str, Any]) -> int:
    value = payload.get("content_index", 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def plain_output_text_part(part: Any, expected_text: str) -> bool:
    if not isinstance(part, dict):
        return False
    if part.get("type") != "output_text":
        return False
    if part.get("text", "") != expected_text:
        return False
    for key, value in part.items():
        if key in {"type", "text"}:
            continue
        if value not in (None, "", [], {}):
            return False
    return True


def response_key(payload: dict[str, Any], *parts: Any) -> tuple[Any, ...]:
    return (response_identity(payload), *parts)


def dedupe_openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output_text_done: dict[tuple[Any, ...], str] = {}
    function_args_done: dict[tuple[Any, ...], str] = {}
    custom_tool_input_done: dict[tuple[Any, ...], str] = {}

    for message in messages:
        payload = message_payload(message)
        if payload is None:
            continue

        event_type = message_event_type(message)
        if event_type == "response.output_text.done":
            item_id = payload.get("item_id")
            if isinstance(item_id, str) and item_id:
                key = response_key(payload, item_id, content_index_value(payload))
                output_text_done[key] = str(payload.get("text", ""))
        elif event_type == "response.function_call_arguments.done":
            item_id = payload.get("item_id")
            if isinstance(item_id, str) and item_id:
                key = response_key(payload, item_id)
                function_args_done[key] = normalized_payload_text(payload.get("arguments", ""))
        elif event_type == "response.custom_tool_call_input.done":
            item_id = payload.get("item_id")
            if isinstance(item_id, str) and item_id:
                key = response_key(payload, item_id)
                custom_tool_input_done[key] = normalized_payload_text(payload.get("input", payload.get("text", "")))

    deduped: list[dict[str, Any]] = []
    for message in messages:
        payload = message_payload(message)
        if payload is None:
            deduped.append(message)
            continue

        event_type = message_event_type(message)
        if event_type == "response.in_progress":
            continue

        if event_type == "response.output_text.delta":
            item_id = payload.get("item_id")
            if isinstance(item_id, str) and item_id:
                key = response_key(payload, item_id, content_index_value(payload))
                if key in output_text_done:
                    continue
        elif event_type == "response.function_call_arguments.delta":
            item_id = payload.get("item_id")
            if isinstance(item_id, str) and item_id:
                key = response_key(payload, item_id)
                if key in function_args_done:
                    continue
        elif event_type == "response.custom_tool_call_input.delta":
            item_id = payload.get("item_id")
            if isinstance(item_id, str) and item_id:
                key = response_key(payload, item_id)
                if key in custom_tool_input_done:
                    continue
        elif event_type == "response.content_part.done":
            item_id = payload.get("item_id")
            part = payload.get("part")
            if isinstance(item_id, str) and item_id and isinstance(part, dict):
                key = response_key(payload, item_id, content_index_value(payload))
                text = output_text_done.get(key)
                if isinstance(text, str) and plain_output_text_part(part, text):
                    continue
        elif event_type == "response.output_item.done":
            item = payload.get("item")
            if isinstance(item, dict):
                item_id = item.get("id") or payload.get("item_id")
                if isinstance(item_id, str) and item_id:
                    item_type = item.get("type")
                    if item_type == "message":
                        content = item.get("content")
                        if isinstance(content, list) and content:
                            redundant = True
                            for index, part in enumerate(content):
                                key = response_key(payload, item_id, index)
                                text = output_text_done.get(key)
                                if not isinstance(text, str) or not plain_output_text_part(part, text):
                                    redundant = False
                                    break
                            allowed_keys = {"id", "type", "role", "status", "phase", "content"}
                            if redundant and set(item).issubset(allowed_keys):
                                continue
                    elif item_type == "function_call":
                        key = response_key(payload, item_id)
                        arguments = item.get("arguments")
                        if key in function_args_done and normalized_payload_text(arguments) == function_args_done[key]:
                            allowed_keys = {"id", "type", "status", "call_id", "name", "arguments"}
                            if set(item).issubset(allowed_keys):
                                continue
                    elif item_type == "custom_tool_call":
                        key = response_key(payload, item_id)
                        input_payload = item.get("input", item.get("text", ""))
                        if key in custom_tool_input_done and normalized_payload_text(input_payload) == custom_tool_input_done[key]:
                            allowed_keys = {"id", "type", "status", "call_id", "name", "input", "text"}
                            if set(item).issubset(allowed_keys):
                                continue

        deduped.append(message)

    return deduped


def render_messages_output(
    flow: dict[str, Any],
    mode: str,
    redact: bool,
    dedupe: bool = False,
) -> tuple[str | bytes, bool]:
    websocket = flow.get("websocket") or {}
    count = ((websocket.get("messages_meta") or {}).get("count")) or 0
    if count <= 0:
        if mode == "json":
            return "[]\n", False
        return "(no websocket messages)\n", False

    messages = decode_messages(flow, "Raw")
    if mode == "raw":
        payload = "\n\n".join(str(item.get("text", "")) for item in messages)
        if payload:
            payload += "\n"
        return payload, False

    provider = provider_for_flow(flow)
    rendered = []
    for item in messages:
        rendered.append(
            redact_json_like(
                {
                    "from_client": bool(item.get("from_client")),
                    "timestamp": item.get("timestamp"),
                    "data": parse_message_text(item.get("text")),
                },
                redact,
            )
        )

    if dedupe:
        if provider != "openai":
            raise MitmError("--dedupe is only supported for OpenAI websocket messages")
        rendered = dedupe_openai_messages(rendered)

    return pretty_json(rendered) + "\n", False


def resolve_output_path(user_path: str | None, default_name: str) -> Path:
    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
    if not user_path:
        return (EXPORT_ROOT / default_name).resolve()

    candidate = Path(user_path)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (EXPORT_ROOT / candidate).resolve()

    try:
        resolved.relative_to(WORKSPACE_ROOT)
    except ValueError as exc:
        raise MitmError(f"output path must stay under {WORKSPACE_ROOT}") from exc

    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def fetch_flows() -> list[dict[str, Any]]:
    data = http_get_json("/flows")
    if not isinstance(data, list):
        raise MitmError("expected /flows to return a JSON array")
    return data


def resolve_flow(flows: list[dict[str, Any]], flow_id: str) -> dict[str, Any]:
    matches = [flow for flow in flows if flow.get("id") == flow_id]
    if not matches:
        matches = [flow for flow in flows if str(flow.get("id", "")).startswith(flow_id)]
    if not matches:
        raise MitmError(f"no flow matching '{flow_id}'")
    if len(matches) > 1:
        ids = ", ".join(flow["id"][:12] for flow in matches[:5])
        raise MitmError(f"multiple flows match '{flow_id}': {ids}")
    return matches[0]


def summarize_request_payload(provider: str, payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    lines: list[str] = []
    model = payload.get("model")
    if model:
        lines.append(f"model: {model}")
    if "stream" in payload:
        lines.append(f"stream: {payload.get('stream')}")
    if provider == "anthropic":
        messages = payload.get("messages") or []
        tools = payload.get("tools") or []
        if isinstance(messages, list):
            lines.append(f"messages: {len(messages)}")
        if isinstance(tools, list):
            lines.append(f"tools: {len(tools)}")
        if "max_tokens" in payload:
            lines.append(f"max_tokens: {payload.get('max_tokens')}")
        if "thinking" in payload:
            lines.append(f"thinking: {json.dumps(payload.get('thinking'), ensure_ascii=False)}")
    elif provider == "openai":
        input_items = payload.get("input")
        tools = payload.get("tools") or []
        if isinstance(input_items, list):
            lines.append(f"input_items: {len(input_items)}")
        elif input_items is not None:
            lines.append("input_items: 1")
        if isinstance(tools, list):
            lines.append(f"tools: {len(tools)}")
        if "max_output_tokens" in payload:
            lines.append(f"max_output_tokens: {payload.get('max_output_tokens')}")
        if "reasoning" in payload:
            lines.append(f"reasoning: {json.dumps(payload.get('reasoning'), ensure_ascii=False)}")
    return lines


def extract_text_snippets(provider: str, rendered: dict[str, Any]) -> list[str]:
    snippets: list[str] = []
    if provider == "anthropic":
        message = rendered.get("message") or {}
        for block in message.get("content") or []:
            if block.get("type") == "text" and block.get("text"):
                snippets.append(block["text"])
    elif provider == "openai":
        response = rendered.get("response") or {}
        for item in response.get("output") or []:
            for part in item.get("content") or []:
                if part.get("type") == "output_text" and part.get("text"):
                    snippets.append(part["text"])
    return snippets


def extract_tool_summaries(provider: str, rendered: dict[str, Any]) -> list[str]:
    tools: list[str] = []
    if provider == "anthropic":
        message = rendered.get("message") or {}
        for block in message.get("content") or []:
            if block.get("type") in {"tool_use", "server_tool_use"}:
                tools.append(f"{block.get('name', '<unknown>')}: {json.dumps(block.get('input'), ensure_ascii=False)}")
    elif provider == "openai":
        response = rendered.get("response") or {}
        for item in response.get("output") or []:
            if item.get("type") in {"function_call", "custom_tool_call"}:
                tools.append(f"{item.get('name', '<unknown>')}: {json.dumps(item.get('arguments'), ensure_ascii=False)}")
    return tools


def summarize_rendered_response(provider: str, rendered: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if provider == "anthropic":
        message = rendered.get("message") or {}
        if message:
            lines.append(f"stop_reason: {message.get('stop_reason')}")
            if message.get("usage"):
                lines.append(f"usage: {json.dumps(message['usage'], ensure_ascii=False)}")
    elif provider == "openai":
        response = rendered.get("response") or {}
        if response:
            lines.append(f"status: {response.get('status')}")
            if response.get("usage"):
                lines.append(f"usage: {json.dumps(response['usage'], ensure_ascii=False)}")
            if response.get("error"):
                lines.append(f"error: {json.dumps(response['error'], ensure_ascii=False)}")
    for tool in extract_tool_summaries(provider, rendered):
        lines.append(f"tool: {tool}")
    unknown = rendered.get("unknown_events") or []
    if unknown:
        lines.append(f"unknown_events: {len(unknown)}")
    errors = rendered.get("errors") or []
    if errors:
        lines.append(f"errors: {json.dumps(errors, ensure_ascii=False)}")
    return lines


def infer_model(flow: dict[str, Any]) -> str:
    request_section = get_section(flow, "request")
    content_type = header_value(request_section, "content-type").lower()
    if "json" not in content_type:
        return "-"
    try:
        _, body_bytes = decode_body(flow, "request")
    except MitmError:
        return "-"
    payload = parse_json_body(body_bytes)
    if isinstance(payload, dict):
        model = payload.get("model")
        if isinstance(model, str) and model:
            return model
    return "-"


def flow_summary(flow: dict[str, Any], include_model: bool) -> dict[str, Any]:
    request = get_section(flow, "request")
    response = flow.get("response") or {}
    request_ct = header_value(request, "content-type")
    response_ct = header_value(response, "content-type") if response else ""
    provider = provider_for_flow(flow)
    model = infer_model(flow) if include_model else "-"
    stream = "yes" if "text/event-stream" in response_ct.lower() else "no"
    return {
        "id": flow["id"],
        "id_prefix": flow["id"][:8],
        "timestamp": request.get("timestamp_start"),
        "timestamp_text": short_timestamp(request.get("timestamp_start")),
        "method": request.get("method", "-"),
        "status": response.get("status_code") if response else None,
        "provider": provider,
        "model": model,
        "host": request.get("pretty_host", "-"),
        "path": request.get("path", "-"),
        "request_bytes": size_value(request),
        "response_bytes": size_value(response),
        "content_type": response_ct or request_ct or "-",
        "stream": stream,
    }


def filter_flows(flows: list[dict[str, Any]], provider: str, host_filter: str | None, path_filter: str | None) -> list[dict[str, Any]]:
    filtered = []
    for flow in flows:
        request = get_section(flow, "request")
        flow_provider = provider_for_flow(flow)
        if provider != "all" and flow_provider != provider:
            continue
        if host_filter and host_filter.lower() not in request.get("pretty_host", "").lower():
            continue
        if path_filter and path_filter.lower() not in request.get("path", "").lower():
            continue
        filtered.append(flow)
    return filtered


def truncate(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 1:
        return value[:width]
    return value[: width - 1] + "…"


def print_table(rows: list[dict[str, Any]]) -> None:
    headers = [
        ("ID", 8),
        ("TIME", 8),
        ("METH", 4),
        ("ST", 4),
        ("PROVIDER", 10),
        ("MODEL", 18),
        ("HOST", 22),
        ("PATH", 34),
        ("REQ", 8),
        ("RESP", 8),
        ("TYPE", 20),
        ("S", 3),
    ]
    print("  ".join(name.ljust(width) for name, width in headers))
    for row in rows:
        values = [
            row["id_prefix"],
            row["timestamp_text"],
            str(row["method"]),
            str(row["status"] or "-"),
            row["provider"],
            row["model"],
            row["host"],
            row["path"],
            str(row["request_bytes"]),
            str(row["response_bytes"]),
            row["content_type"],
            row["stream"],
        ]
        print("  ".join(truncate(value, width).ljust(width) for value, (_, width) in zip(values, headers)))


def render_body_output(
    flow: dict[str, Any],
    direction: str,
    mode: str,
    redact: bool,
    dedupe: bool = False,
) -> tuple[str | bytes, bool]:
    if direction == "messages":
        if mode == "events":
            raise MitmError("websocket messages do not support --events")
        return render_messages_output(flow, mode, redact, dedupe=dedupe)

    section, body_bytes = decode_body(flow, direction)
    content_type = header_value(section, "content-type").lower()
    body_text = to_text(body_bytes)
    provider = provider_for_flow(flow)

    if mode == "raw":
        return body_bytes, True

    if not body_bytes:
        if mode == "events":
            raise MitmError(f"{direction} body is empty; no SSE events available")
        if mode == "json":
            return "null\n", False
        return "(empty body)\n", False

    if mode == "events":
        if not looks_like_sse(section, body_text):
            raise MitmError(f"{direction} body is not an SSE stream")
        events = parse_sse_events(body_text)
        payload = redact_json_like(events, redact)
        return pretty_json(payload) + "\n", False

    if looks_like_sse(section, body_text):
        events = parse_sse_events(body_text)
        if provider == "anthropic":
            rendered = reconstruct_anthropic(events)
        elif provider == "openai":
            rendered = reconstruct_openai(events)
        else:
            rendered = {"provider": provider, "events": events}
        payload = redact_json_like(rendered, redact)
        if mode == "json":
            return pretty_json(payload) + "\n", False
        if isinstance(payload, dict) and "events" not in payload:
            return pretty_json(payload) + "\n", False
        return render_event_table(events) + "\n", False

    parsed = parse_json_body(body_bytes)
    if parsed is not None:
        payload = redact_json_like(parsed, redact)
        return pretty_json(payload) + "\n", False

    if mode == "json":
        raise MitmError(f"{direction} body is not valid JSON")
    return body_text, False


def write_output(data: str | bytes, binary: bool, path: Path) -> None:
    if binary:
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    else:
        path.write_text(data if isinstance(data, str) else to_text(data), encoding="utf-8")


def emit_output(data: str | bytes, binary: bool) -> None:
    if binary:
        sys.stdout.buffer.write(data if isinstance(data, bytes) else data.encode("utf-8"))
    else:
        sys.stdout.write(data if isinstance(data, str) else to_text(data))


def render_detail(flow: dict[str, Any], full: bool, raw: bool, redact: bool) -> str:
    request = get_section(flow, "request")
    response = flow.get("response") or {}
    req_headers = redact_headers(headers_as_pairs(request), redact)
    resp_headers = redact_headers(headers_as_pairs(response), redact)
    req_ct = header_value(request, "content-type")
    resp_ct = header_value(response, "content-type")
    provider = provider_for_flow(flow)
    method = request.get("method", "-")
    url = f"{request.get('scheme', 'https')}://{request.get('pretty_host', '')}{request.get('path', '')}"
    status = response.get("status_code", "-")
    elapsed = "-"
    if isinstance(request.get("timestamp_start"), (int, float)) and isinstance(response.get("timestamp_end"), (int, float)):
        elapsed = f"{(response['timestamp_end'] - request['timestamp_start']):.3f}s"

    request_body: str | None = None
    response_body: str | None = None
    request_json = None
    response_rendered = None

    try:
        _, req_bytes = decode_body(flow, "request")
        request_json = parse_json_body(req_bytes)
        if raw:
            request_body = to_text(req_bytes)
        elif request_json is not None:
            request_body = pretty_json(redact_json_like(request_json, redact))
        else:
            request_body = to_text(req_bytes)
    except MitmError:
        pass

    try:
        _, resp_bytes = decode_body(flow, "response")
        resp_text = to_text(resp_bytes)
        if raw:
            response_body = resp_text
        elif looks_like_sse(response, resp_text):
            events = parse_sse_events(resp_text)
            if provider == "anthropic":
                response_rendered = reconstruct_anthropic(events)
            elif provider == "openai":
                response_rendered = reconstruct_openai(events)
            else:
                response_rendered = {"provider": provider, "events": events}
            response_body = pretty_json(redact_json_like(response_rendered, redact))
        else:
            parsed = parse_json_body(resp_bytes)
            if parsed is not None:
                response_rendered = redact_json_like(parsed, redact)
                response_body = pretty_json(response_rendered)
            else:
                response_body = resp_text
    except MitmError:
        pass

    model = "-"
    if isinstance(request_json, dict) and isinstance(request_json.get("model"), str):
        model = request_json["model"]

    lines = [
        f"Flow: {flow['id']}",
        f"Provider: {provider}",
        f"Model: {model}",
        f"Request: {method} {url}",
        f"Status: {status}",
        f"Timing: {elapsed}",
        f"Sizes: request={size_value(request)}B response={size_value(response)}B",
        f"Content-Types: request={req_ct or '-'} response={resp_ct or '-'}",
        "",
        "Request Headers:",
    ]
    lines.extend(f"  {key}: {value}" for key, value in req_headers)

    payload_summary = summarize_request_payload(provider, request_json)
    if payload_summary:
        lines.extend(["", "Request Payload Summary:"])
        lines.extend(f"  {line}" for line in payload_summary)

    websocket = flow.get("websocket") or {}
    messages_meta = websocket.get("messages_meta") or {}
    if messages_meta:
        lines.extend(["", "WebSocket Messages:"])
        lines.append(f"  count: {messages_meta.get('count', 0)}")
        lines.append(f"  bytes: {messages_meta.get('contentLength', 0)}")
        lines.append(f"  last_timestamp: {format_timestamp(messages_meta.get('timestamp_last'))}")

    if response_rendered:
        response_summary = summarize_rendered_response(provider, response_rendered)
        if response_summary:
            lines.extend(["", "Response Summary:"])
            lines.extend(f"  {line}" for line in response_summary)
        snippets = extract_text_snippets(provider, response_rendered)
        if snippets:
            lines.extend(["", "Assistant Output:"])
            for snippet in snippets[:3]:
                for line in snippet.splitlines() or [""]:
                    lines.append(f"  {line}")

    lines.extend(["", "Response Headers:"])
    lines.extend(f"  {key}: {value}" for key, value in resp_headers)

    if full or raw:
        if request_body is not None:
            lines.extend(["", "Request Body:", request_body])
        if response_body is not None:
            lines.extend(["", "Response Body:", response_body])

    return "\n".join(lines).rstrip() + "\n"


def render_markdown(flow: dict[str, Any], redact: bool) -> str:
    request = get_section(flow, "request")
    response = flow.get("response") or {}
    provider = provider_for_flow(flow)
    method = request.get("method", "-")
    url = f"{request.get('scheme', 'https')}://{request.get('pretty_host', '')}{request.get('path', '')}"
    req_headers = redact_headers(headers_as_pairs(request), redact)
    resp_headers = redact_headers(headers_as_pairs(response), redact)

    request_json = None
    request_body = None
    response_body = None
    response_rendered = None

    try:
        _, req_bytes = decode_body(flow, "request")
        request_json = parse_json_body(req_bytes)
        request_body = pretty_json(redact_json_like(request_json, redact)) if request_json is not None else to_text(req_bytes)
    except MitmError:
        request_body = None

    try:
        _, resp_bytes = decode_body(flow, "response")
        resp_text = to_text(resp_bytes)
        if looks_like_sse(response, resp_text):
            events = parse_sse_events(resp_text)
            if provider == "anthropic":
                response_rendered = reconstruct_anthropic(events)
            elif provider == "openai":
                response_rendered = reconstruct_openai(events)
            else:
                response_rendered = {"provider": provider, "events": events}
            response_body = pretty_json(redact_json_like(response_rendered, redact))
        else:
            parsed = parse_json_body(resp_bytes)
            response_body = pretty_json(redact_json_like(parsed, redact)) if parsed is not None else resp_text
    except MitmError:
        response_body = None

    model = request_json.get("model") if isinstance(request_json, dict) else "-"
    lines = [
        "---",
        f"flow_id: {flow['id']}",
        f"provider: {provider}",
        f"model: {model}",
        f"timestamp_utc: {format_timestamp(request.get('timestamp_start'))}",
        "---",
        "",
        f"# {method} {url}",
        "",
        f"- Status: {response.get('status_code', '-')}",
        f"- Provider: {provider}",
        f"- Model: {model}",
        f"- Request bytes: {size_value(request)}",
        f"- Response bytes: {size_value(response)}",
        "",
        "## Request Headers",
        "",
        "| Header | Value |",
        "| --- | --- |",
    ]
    lines.extend(f"| {key} | {value} |" for key, value in req_headers)

    payload_summary = summarize_request_payload(provider, request_json)
    if payload_summary:
        lines.extend(["", "## Request Payload Summary", ""])
        lines.extend(f"- {line}" for line in payload_summary)

    websocket = flow.get("websocket") or {}
    messages_meta = websocket.get("messages_meta") or {}
    if messages_meta:
        lines.extend(["", "## WebSocket Messages", ""])
        lines.append(f"- count: {messages_meta.get('count', 0)}")
        lines.append(f"- bytes: {messages_meta.get('contentLength', 0)}")
        lines.append(f"- last_timestamp_utc: {format_timestamp(messages_meta.get('timestamp_last'))}")

    lines.extend(["", "## Response Headers", "", "| Header | Value |", "| --- | --- |"])
    lines.extend(f"| {key} | {value} |" for key, value in resp_headers)

    if response_rendered:
        response_summary = summarize_rendered_response(provider, response_rendered)
        if response_summary:
            lines.extend(["", "## Response Summary", ""])
            lines.extend(f"- {line}" for line in response_summary)

    if request_body is not None:
        lines.extend(["", "## Request Body", "", "```json" if request_json is not None else "```text", request_body, "```"])
    if response_body is not None:
        lines.extend(["", "## Response Body", "", "```json", response_body, "```"])
    return "\n".join(lines).rstrip() + "\n"


def cmd_list(args: argparse.Namespace) -> None:
    flows = fetch_flows()
    filtered = filter_flows(flows, args.provider, args.host, args.path)
    selected = list(reversed(filtered[-args.limit :]))
    if args.full:
        emit_output(pretty_json(selected) + "\n", False)
        return

    summaries = [flow_summary(flow, include_model=True) for flow in selected]
    if args.json:
        emit_output(pretty_json(summaries) + "\n", False)
        return
    print_table(summaries)


def cmd_body(args: argparse.Namespace) -> None:
    if args.raw and args.events:
        raise MitmError("--raw and --events cannot be combined")
    if args.raw and args.json:
        raise MitmError("--raw and --json cannot be combined")
    if args.events and args.json:
        raise MitmError("--events and --json cannot be combined")
    if args.dedupe and args.direction != "messages":
        raise MitmError("--dedupe is only supported for websocket messages")
    if args.dedupe and args.raw:
        raise MitmError("--dedupe cannot be combined with --raw")
    if args.dedupe and args.events:
        raise MitmError("--dedupe cannot be combined with --events")

    flows = fetch_flows()
    flow = resolve_flow(flows, args.flow_id)

    mode = "formatted"
    if args.raw:
        mode = "raw"
    elif args.events:
        mode = "events"
    elif args.json:
        mode = "json"

    payload, binary = render_body_output(
        flow,
        args.direction,
        mode,
        redact=not args.no_redact and mode != "raw",
        dedupe=args.dedupe,
    )
    if args.save:
        default_name = f"flow-{flow['id'][:8]}-{args.direction}.{ 'bin' if binary else 'txt' }"
        path = resolve_output_path(args.save, default_name)
        write_output(payload, binary, path)
        print(f"Wrote: {path}")
        return
    emit_output(payload, binary)


def cmd_detail(args: argparse.Namespace) -> None:
    flows = fetch_flows()
    flow = resolve_flow(flows, args.flow_id)
    if args.full and args.raw:
        raise MitmError("--full and --raw cannot be combined")
    if args.no_redact:
        print("Warning: output redaction disabled", file=sys.stderr)

    text = render_detail(flow, full=args.full, raw=args.raw, redact=not args.no_redact)
    if args.md is not None:
        default_name = f"flow-{flow['id'][:8]}.md"
        md_text = render_markdown(flow, redact=not args.no_redact)
        path = resolve_output_path(args.md, default_name)
        write_output(md_text, False, path)
        print(f"Wrote: {path}")
        return
    emit_output(text, False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render mitmproxy flows for AI CLI traffic.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List captured flows")
    list_parser.add_argument("--limit", type=int, default=50, help="show the last N matching flows")
    list_parser.add_argument("--provider", choices=("anthropic", "openai", "all"), default="all")
    list_parser.add_argument("--host", help="filter by host substring")
    list_parser.add_argument("--path", help="filter by path substring")
    list_parser.add_argument("--json", action="store_true", help="emit summarized JSON")
    list_parser.add_argument("--full", action="store_true", help="emit raw flow JSON")
    list_parser.set_defaults(func=cmd_list)

    body_parser = subparsers.add_parser("body", help="Render a request, response, or WebSocket messages payload")
    body_parser.add_argument("flow_id", help="full or truncated flow ID")
    body_parser.add_argument("direction", nargs="?", choices=("request", "response", "messages"), default="response")
    body_parser.add_argument("--raw", action="store_true", help="emit raw content.data bytes, or raw WebSocket message text")
    body_parser.add_argument("--events", action="store_true", help="emit normalized SSE events as JSON")
    body_parser.add_argument("--json", action="store_true", help="emit parsed JSON or reconstructed stream JSON")
    body_parser.add_argument("--dedupe", action="store_true", help="dedupe redundant OpenAI websocket message events")
    body_parser.add_argument("--save", help="save output under tmp/mitmproxy-flows/ by default")
    body_parser.add_argument("--no-redact", action="store_true", help="disable credential redaction for local debugging")
    body_parser.set_defaults(func=cmd_body)

    detail_parser = subparsers.add_parser("detail", help="Summarize a single flow")
    detail_parser.add_argument("flow_id", help="full or truncated flow ID")
    detail_parser.add_argument("--full", action="store_true", help="include complete formatted request/response bodies")
    detail_parser.add_argument("--raw", action="store_true", help="include raw bodies without formatting")
    detail_parser.add_argument("--md", nargs="?", const="", help="write a Markdown report under tmp/mitmproxy-flows/")
    detail_parser.add_argument("--no-redact", action="store_true", help="disable credential redaction for local debugging")
    detail_parser.set_defaults(func=cmd_detail)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except MitmError as exc:
        fatal(str(exc))


if __name__ == "__main__":
    main()
