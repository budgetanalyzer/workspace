#!/usr/bin/env bash
# Launch Codex lean CLI through mitmproxy with extra high reasoning effort
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_SCRIPT="$SCRIPT_DIR/codex-with-proxy"
if [ ! -x "$BASE_SCRIPT" ]; then
    BASE_SCRIPT="$SCRIPT_DIR/codex-with-proxy.sh"
fi

export CODEX_REASONING_EFFORT="${CODEX_REASONING_EFFORT:-xhigh}"
exec "$BASE_SCRIPT" "$@"
