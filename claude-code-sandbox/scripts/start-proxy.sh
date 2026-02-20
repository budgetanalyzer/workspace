#!/bin/bash
# Start mitmweb with browser UI on :8081, proxy on :8080
# Usage: start-proxy [port]
#   Then in another terminal: export HTTPS_PROXY=http://127.0.0.1:8080 HTTP_PROXY=http://127.0.0.1:8080
PORT=${1:-8080}
echo "mitmweb proxy on :${PORT} | UI on :$((PORT + 1))"
mitmweb --listen-port "$PORT" --set console_eventlog_verbosity=info --set web_password=mitmlocal
