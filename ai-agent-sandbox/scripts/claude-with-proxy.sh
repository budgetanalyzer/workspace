#!/bin/bash
# Launch mitmproxy + Claude Code in one shot
# All Claude API traffic visible at http://localhost:9081
#
# Usage: claude-with-proxy [claude args...]

export HTTPS_PROXY=http://127.0.0.1:9080
export HTTP_PROXY=http://127.0.0.1:9080
export NODE_EXTRA_CA_CERTS=$HOME/.mitmproxy/mitmproxy-ca-cert.pem
export CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true
export ENABLE_CLAUDEAI_MCP_SERVERS=false
export CLAUDE_CODE_EFFORT_LEVEL=max

mitmweb --listen-port 9080 --web-port 9081 --set console_eventlog_verbosity=info --set web_password=mitmlocal >/dev/null 2>&1 &
PROXY_PID=$!
sleep 2

if ! kill -0 "$PROXY_PID" 2>/dev/null; then
    echo "ERROR: mitmproxy failed to start"
    exit 1
fi

echo "Proxy PID $PROXY_PID | mitmweb UI: http://localhost:9081"
echo "---"

command claude "$@"

EXIT_CODE=$?

kill "$PROXY_PID" 2>/dev/null
exit $EXIT_CODE
