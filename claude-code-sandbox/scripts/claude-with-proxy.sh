#!/bin/bash
# Launch mitmproxy + Claude Code in one shot
# All Claude API traffic visible at http://localhost:8081
#
# Usage: claude-with-proxy [claude args...]

export HTTPS_PROXY=http://127.0.0.1:8080
export HTTP_PROXY=http://127.0.0.1:8080
export NODE_EXTRA_CA_CERTS=$HOME/.mitmproxy/mitmproxy-ca-cert.pem

mitmweb --listen-port 8080 --set console_eventlog_verbosity=info --set web_password=mitmlocal >/dev/null 2>&1 &
PROXY_PID=$!
sleep 2

if ! kill -0 "$PROXY_PID" 2>/dev/null; then
    echo "ERROR: mitmproxy failed to start"
    exit 1
fi

echo "Proxy PID $PROXY_PID | mitmweb UI: http://localhost:8081"
echo "---"

claude "$@"
EXIT_CODE=$?

kill "$PROXY_PID" 2>/dev/null
exit $EXIT_CODE
