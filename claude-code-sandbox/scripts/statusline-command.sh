#!/bin/bash

input=$(cat)

current_dir=$(echo "$input" | jq -r '.workspace.current_dir')
model_name=$(echo "$input" | jq -r '.model.display_name')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)
max_tokens=$(echo "$input" | jq -r '.context_window.context_window_size // 200000')

# Sum all input token types (matches how used_percentage is calculated)
input_tokens=$(echo "$input" | jq -r '.context_window.current_usage.input_tokens // 0')
cache_create=$(echo "$input" | jq -r '.context_window.current_usage.cache_creation_input_tokens // 0')
cache_read=$(echo "$input" | jq -r '.context_window.current_usage.cache_read_input_tokens // 0')
used_tokens=$((input_tokens + cache_create + cache_read))

# Format as k units
used_k=$((used_tokens / 1000))
max_k=$((max_tokens / 1000))

# Progress bar from used_percentage
bar_width=20
filled=$((used_pct * bar_width / 100))
empty=$((bar_width - filled))
bar=$(printf '%0.s█' $(seq 1 $filled 2>/dev/null))
bar+=$(printf '%0.s░' $(seq 1 $empty 2>/dev/null))

# --- Usage limits (out-of-band API call with caching) ---
CACHE_FILE="/tmp/claude-usage-cache.json"
CACHE_TTL=60
USAGE_STR=""

fetch_usage() {
    local creds_file="/home/vscode/.claude/.credentials.json"
    [ -f "$creds_file" ] || return 1
    local token=$(jq -r '.claudeAiOauth.accessToken // empty' "$creds_file")
    [ -n "$token" ] || return 1
    local version=$(claude --version 2>/dev/null | awk '{print $1}')
    curl -sf --max-time 5 \
        -H "Authorization: Bearer $token" \
        -H "anthropic-beta: oauth-2025-04-20" \
        -H "User-Agent: claude-code/${version:-unknown}" \
        "https://api.anthropic.com/api/oauth/usage" 2>/dev/null
}

# Check cache age
if [ -f "$CACHE_FILE" ]; then
    cache_age=$(( $(date +%s) - $(stat -c %Y "$CACHE_FILE" 2>/dev/null || echo 0) ))
else
    cache_age=$((CACHE_TTL + 1))
fi

if [ "$cache_age" -gt "$CACHE_TTL" ]; then
    usage_data=$(fetch_usage)
    if [ -n "$usage_data" ]; then
        echo "$usage_data" > "$CACHE_FILE"
    elif [ -f "$CACHE_FILE" ]; then
        usage_data=$(cat "$CACHE_FILE")
    fi
else
    usage_data=$(cat "$CACHE_FILE")
fi

if [ -n "$usage_data" ]; then
    h5=$(echo "$usage_data" | jq -r '.five_hour.utilization // empty' | cut -d. -f1)
    d7=$(echo "$usage_data" | jq -r '.seven_day.utilization // empty' | cut -d. -f1)
    [ -n "$h5" ] && [ -n "$d7" ] && USAGE_STR=" | 5h: ${h5}% | 7d: ${d7}%"
fi

printf "%s | %s | %s %sk/%sk%s" \
    "$current_dir" \
    "$model_name" \
    "$bar" \
    "$used_k" \
    "$max_k" \
    "$USAGE_STR"
