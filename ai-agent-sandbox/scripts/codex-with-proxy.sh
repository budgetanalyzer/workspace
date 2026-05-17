#!/usr/bin/env bash
# Launch mitmproxy + Codex lean CLI in one shot
set -euo pipefail

PROXY_PORT="${PROXY_PORT:-9080}"
WEB_PORT=$((PROXY_PORT + 1))

export HTTPS_PROXY="http://127.0.0.1:${PROXY_PORT}"
export HTTP_PROXY="http://127.0.0.1:${PROXY_PORT}"
export NODE_EXTRA_CA_CERTS="${NODE_EXTRA_CA_CERTS:-$HOME/.mitmproxy/mitmproxy-ca-cert.pem}"

PROXY_OWNED=false

cleanup() {
    if [ "$PROXY_OWNED" = true ]; then
        kill "$PROXY_PID" 2>/dev/null || true
        wait "$PROXY_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

if nc -z 127.0.0.1 "$PROXY_PORT" 2>/dev/null; then
    echo "Reusing existing mitmproxy on :$PROXY_PORT"
else
    mitmweb \
        --listen-port "$PROXY_PORT" \
        --web-port "$WEB_PORT" \
        --set console_eventlog_verbosity=info \
        --set web_password="${MITM_PASS:-mitmlocal}" \
        >/dev/null 2>&1 &
    PROXY_PID=$!
    sleep 2

    if ! kill -0 "$PROXY_PID" 2>/dev/null; then
        echo "ERROR: mitmproxy failed to start" >&2
        exit 1
    fi

    echo "Proxy PID $PROXY_PID | mitmweb UI: http://localhost:$WEB_PORT"
    PROXY_OWNED=true
fi

echo "---"

command codex-lean "$@"
