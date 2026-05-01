#!/usr/bin/env bash
# Launch Codex CLI through mitmproxy with high reasoning effort
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_SCRIPT="$SCRIPT_DIR/codex-with-proxy"
if [ ! -x "$BASE_SCRIPT" ]; then
    BASE_SCRIPT="$SCRIPT_DIR/codex-with-proxy.sh"
fi

exec "$BASE_SCRIPT" -c model_reasoning_effort=high "$@"
