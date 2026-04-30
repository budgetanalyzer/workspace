#!/usr/bin/env bash
# Start mitmweb with browser UI, proxy on :9080, UI on :9081
# Usage: start-proxy [port]
set -euo pipefail

PORT="${1:-${PROXY_PORT:-9080}}"
WEB_PORT=$((PORT + 1))

echo "mitmweb proxy on :${PORT} | UI on :${WEB_PORT}"
exec mitmweb \
    --listen-port "$PORT" \
    --web-port "$WEB_PORT" \
    --set console_eventlog_verbosity=info \
    --set web_password="${MITM_PASS:-mitmlocal}"
