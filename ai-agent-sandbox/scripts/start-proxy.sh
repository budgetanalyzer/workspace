#!/bin/bash
# Start mitmweb with browser UI, proxy on :9080, UI on :9081
# Usage: start-proxy [port]
#   Then in another terminal: export HTTPS_PROXY=http://127.0.0.1:9080 HTTP_PROXY=http://127.0.0.1:9080
PORT=${1:-9080}
WEB_PORT=$((PORT + 1))
echo "mitmweb proxy on :${PORT} | UI on :${WEB_PORT}"
mitmweb --listen-port "$PORT" --web-port "$WEB_PORT" --set console_eventlog_verbosity=info --set web_password=mitmlocal
