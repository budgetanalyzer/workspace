#!/usr/bin/env bash
# Launch Codex CLI through mitmproxy pinned to GPT-5.4
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CODEX_MODEL="${CODEX_MODEL:-gpt-5.4}"
BASE_SCRIPT="$SCRIPT_DIR/codex-with-proxy"
if [ ! -x "$BASE_SCRIPT" ]; then
    BASE_SCRIPT="$SCRIPT_DIR/codex-with-proxy.sh"
fi

exec "$BASE_SCRIPT" "$@"
