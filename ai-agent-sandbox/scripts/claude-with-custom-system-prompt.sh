#!/bin/bash
# Launch mitmproxy + Claude Code with system prompt replacement
# The mitmproxy addon intercepts API requests and replaces CC's default
# ~24k-token system prompt with the lean version from system-prompt.md
#
# Usage: claude-with-custom-system-prompt [claude args...]

PROXY_PORT=${PROXY_PORT:-9080}
WEB_PORT=$((PROXY_PORT + 1))

export HTTPS_PROXY=http://127.0.0.1:$PROXY_PORT
export HTTP_PROXY=http://127.0.0.1:$PROXY_PORT
export NODE_EXTRA_CA_CERTS=$HOME/.mitmproxy/mitmproxy-ca-cert.pem

export CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true
export ENABLE_CLAUDEAI_MCP_SERVERS=false
export CLAUDE_CODE_EFFORT_LEVEL=max
export CLAUDE_CODE_DISABLE_1M_CONTEXT=1
export CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1

PROXY_OWNED=false

cleanup() {
    if [ "$PROXY_OWNED" = true ]; then
        kill "$PROXY_PID" 2>/dev/null
        wait "$PROXY_PID" 2>/dev/null
    fi
}
trap cleanup EXIT

# Check if proxy is already running on the target port
if nc -z 127.0.0.1 "$PROXY_PORT" 2>/dev/null; then
    echo "Reusing existing mitmproxy on :$PROXY_PORT"
else
    mitmweb --listen-port "$PROXY_PORT" --web-port "$WEB_PORT" \
        --set console_eventlog_verbosity=info \
        --set web_password=mitmlocal \
        -s /workspace/workspace/ai-agent-sandbox/system-prompt-addon.py \
        >/dev/null 2>&1 &
    PROXY_PID=$!
    sleep 2

    if ! kill -0 "$PROXY_PID" 2>/dev/null; then
        echo "ERROR: mitmproxy failed to start"
        exit 1
    fi

    echo "Proxy PID $PROXY_PID | mitmweb UI: http://localhost:$WEB_PORT"
    PROXY_OWNED=true
fi

echo "System prompt replacement active via proxy addon"
echo "---"

command claude --verbose --dangerously-skip-permissions "$@"
