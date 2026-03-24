"""mitmproxy addon: replace Claude Code's system prompt in-flight.

Intercepts POST requests to api.anthropic.com/v1/messages and replaces
the `system` field with a custom prompt loaded from disk.

Usage:
    mitmweb -s /workspace/workspace/system-prompt-addon.py
    mitmweb -s /workspace/workspace/system-prompt-addon.py \
        --set system_prompt_file=/path/to/custom.md
"""

import json
import logging
import os

from mitmproxy import ctx, http

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_PATH = "/workspace/workspace/ai-agent-sandbox/system-prompt.md"
DUMP_DIR = "/workspace/workspace/tmp"


class SystemPromptReplacer:
    def __init__(self):
        self.custom_prompt: str = ""
        self.request_count: int = 0
        self.original_dumped: bool = False

    def load(self, loader):
        loader.add_option(
            name="system_prompt_file",
            typespec=str,
            default=DEFAULT_PROMPT_PATH,
            help="Path to custom system prompt file.",
        )

    def configure(self, updated):
        if "system_prompt_file" in updated:
            path = ctx.options.system_prompt_file
            with open(path, "r") as f:
                self.custom_prompt = f.read().strip()
            logger.info(
                "Loaded custom system prompt from %s (%d chars)",
                path,
                len(self.custom_prompt),
            )

    def request(self, flow: http.HTTPFlow) -> None:
        if flow.request.method != "POST":
            return
        if flow.request.pretty_host != "api.anthropic.com":
            return
        if not flow.request.path.startswith("/v1/messages"):
            return
        if not self.custom_prompt:
            logger.warning("No custom prompt loaded, passing through")
            return

        try:
            data = json.loads(flow.request.get_content())
        except (json.JSONDecodeError, TypeError):
            logger.error("Failed to parse request body, passing through")
            return

        if "system" not in data:
            return

        # Skip ancillary requests (title generation, etc.) — only replace
        # the main conversation request which carries a non-empty tools list.
        tools = data.get("tools")
        if not tools:
            model = data.get("model", "unknown")
            logger.info(
                "Skipping ancillary request (model=%s, no tools), passing through",
                model,
            )
            return

        original_system = data["system"]
        original_size = len(json.dumps(original_system))

        if not self.original_dumped:
            self._dump_original(original_system)
            self.original_dumped = True

        # Replace, preserving format (array-of-blocks vs plain string)
        if isinstance(original_system, list):
            # Keep all blocks except the last (the main prompt body).
            # This preserves the billing header, title block, etc.
            prefix_blocks = original_system[:-1]
            data["system"] = prefix_blocks + [
                {
                    "type": "text",
                    "text": self.custom_prompt,
                    "cache_control": {"type": "ephemeral", "ttl": "1h"},
                }
            ]
        else:
            data["system"] = self.custom_prompt

        new_size = len(json.dumps(data["system"]))
        self.request_count += 1

        # Dump full request body to tmp for debugging before sending
        self._dump_request(data)

        # Setting .content auto-updates content-length header
        flow.request.content = json.dumps(data, ensure_ascii=False).encode("utf-8")

        logger.info(
            "[#%d] Replaced system prompt: %d -> %d chars",
            self.request_count,
            original_size,
            new_size,
        )

    def _dump_request(self, data):
        """Dump the full modified request body for debugging."""
        try:
            os.makedirs(DUMP_DIR, exist_ok=True)
            dump_path = os.path.join(
                DUMP_DIR, f"request-{self.request_count:04d}.json"
            )
            with open(dump_path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("Dumped request #%d to %s", self.request_count, dump_path)
        except OSError as e:
            logger.warning("Could not dump request: %s", e)

    def _dump_original(self, original_system):
        """Save the original system prompt once for reference."""
        try:
            os.makedirs(DUMP_DIR, exist_ok=True)
            dump_path = os.path.join(DUMP_DIR, "original-system-prompt.json")
            with open(dump_path, "w") as f:
                json.dump(original_system, f, indent=2, ensure_ascii=False)
            logger.info("Saved original system prompt to %s", dump_path)
        except OSError as e:
            logger.warning("Could not dump original prompt: %s", e)


addons = [SystemPromptReplacer()]
