#!/bin/bash

input=$(cat)

current_dir=$(echo "$input" | jq -r '.workspace.current_dir')
model_name=$(echo "$input" | jq -r '.model.display_name')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)


# --- Usage limits (out-of-band API call with caching) ---
CACHE_FILE="/tmp/claude-usage-cache.json"
CACHE_META="/tmp/claude-usage-cache.meta"
BASE_TTL=60
MAX_STALE=600  # 10 minutes: beyond this, show ?%
USAGE_STR=""

fetch_usage() {
    local creds_file="/home/vscode/.claude/.credentials.json"
    [ -f "$creds_file" ] || return 1
    local token=$(jq -r '.claudeAiOauth.accessToken // empty' "$creds_file")
    [ -n "$token" ] || return 1
    local version=$(claude --version 2>/dev/null | awk '{print $1}')
    local http_code
    local body
    local tmpfile=$(mktemp)
    http_code=$(curl -s --max-time 5 -o "$tmpfile" -w '%{http_code}' \
        -H "Authorization: Bearer $token" \
        -H "anthropic-beta: oauth-2025-04-20" \
        -H "User-Agent: claude-code/${version:-unknown}" \
        "https://api.anthropic.com/api/oauth/usage" 2>/dev/null)
    body=$(cat "$tmpfile")
    rm -f "$tmpfile"

    if [ "$http_code" = "200" ] && [ -n "$body" ]; then
        echo "$body"
        # Record success: reset backoff
        echo "ok $http_code $(date +%s)" > "$CACHE_META"
        return 0
    else
        # Record failure with status code
        echo "fail $http_code $(date +%s)" > "$CACHE_META"
        return 1
    fi
}

# Determine effective TTL (backoff on failures)
effective_ttl() {
    if [ ! -f "$CACHE_META" ]; then
        echo "$BASE_TTL"
        return
    fi
    local status=$(awk '{print $1}' "$CACHE_META")
    if [ "$status" = "ok" ]; then
        echo "$BASE_TTL"
        return
    fi
    # Count consecutive failures by checking time since last success
    # Simple backoff: 60 → 120 → 300, capped at 300
    local fail_time=$(awk '{print $3}' "$CACHE_META")
    local now=$(date +%s)
    local since_fail=$(( now - fail_time ))
    if [ "$since_fail" -lt 120 ]; then
        echo 120
    else
        echo 300
    fi
}

# Format seconds into human-readable delta
format_delta() {
    local secs=$1
    if [ "$secs" -le 0 ]; then
        echo "now"
        return
    fi
    local days=$((secs / 86400))
    local hours=$(( (secs % 86400) / 3600 ))
    local mins=$(( (secs % 3600) / 60 ))
    if [ "$days" -gt 0 ]; then
        echo "${days}d ${hours}h"
    elif [ "$hours" -gt 0 ]; then
        echo "${hours}h ${mins}m"
    else
        echo "${mins}m"
    fi
}

# Check cache age
if [ -f "$CACHE_FILE" ]; then
    cache_age=$(( $(date +%s) - $(stat -c %Y "$CACHE_FILE" 2>/dev/null || echo 0) ))
else
    cache_age=$((BASE_TTL + 1))
fi

CACHE_TTL=$(effective_ttl)
is_stale=false

if [ "$cache_age" -gt "$CACHE_TTL" ]; then
    usage_data=$(fetch_usage)
    if [ -n "$usage_data" ]; then
        echo "$usage_data" > "$CACHE_FILE"
        is_stale=false
    elif [ -f "$CACHE_FILE" ]; then
        usage_data=$(cat "$CACHE_FILE")
        is_stale=true
        # Recalculate cache_age for the fallback data
        cache_age=$(( $(date +%s) - $(stat -c %Y "$CACHE_FILE" 2>/dev/null || echo 0) ))
    fi
else
    usage_data=$(cat "$CACHE_FILE")
fi

if [ -n "$usage_data" ]; then
    now=$(date +%s)

    # Age-gate: if cache is older than MAX_STALE, show ?% instead
    if [ "$cache_age" -gt "$MAX_STALE" ] && [ "$is_stale" = true ]; then
        USAGE_STR=" | 5h: ?% | 7d: ?%"
    else
        stale_marker=""
        [ "$is_stale" = true ] && stale_marker="~"

        h5=$(echo "$usage_data" | jq -r '.five_hour.utilization // empty' | cut -d. -f1)
        h5_reset=$(echo "$usage_data" | jq -r '.five_hour.resets_at // empty')
        h5_delta=""
        if [ -n "$h5_reset" ] && [ "$h5_reset" != "null" ]; then
            h5_epoch=$(date -d "$h5_reset" +%s 2>/dev/null)
            [ -n "$h5_epoch" ] && h5_delta=" $(format_delta $((h5_epoch - now)))"
        fi

        d7=$(echo "$usage_data" | jq -r '.seven_day.utilization // empty' | cut -d. -f1)
        d7_reset=$(echo "$usage_data" | jq -r '.seven_day.resets_at // empty')
        d7_delta=""
        if [ -n "$d7_reset" ] && [ "$d7_reset" != "null" ]; then
            d7_epoch=$(date -d "$d7_reset" +%s 2>/dev/null)
            [ -n "$d7_epoch" ] && d7_delta=" $(format_delta $((d7_epoch - now)))"
        fi

        # Model-specific 7-day limits
        model_lower=$(echo "$model_name" | tr '[:upper:]' '[:lower:]')
        d7_model=""
        d7_model_key=""
        case "$model_lower" in
            *opus*)   d7_model_key="seven_day_opus" ;;
            *sonnet*) d7_model_key="seven_day_sonnet" ;;
        esac
        if [ -n "$d7_model_key" ]; then
            d7_model_val=$(echo "$usage_data" | jq -r ".${d7_model_key}.utilization // empty" | cut -d. -f1)
            if [ -n "$d7_model_val" ]; then
                d7_model_reset=$(echo "$usage_data" | jq -r ".${d7_model_key}.resets_at // empty")
                d7_model_delta=""
                if [ -n "$d7_model_reset" ] && [ "$d7_model_reset" != "null" ]; then
                    d7_model_epoch=$(date -d "$d7_model_reset" +%s 2>/dev/null)
                    [ -n "$d7_model_epoch" ] && d7_model_delta=" $(format_delta $((d7_model_epoch - now)))"
                fi
                d7_model=" ${d7_model_key##seven_day_}: ${d7_model_val}%${stale_marker}${d7_model_delta}"
            fi
        fi

        if [ -n "$h5" ] && [ -n "$d7" ]; then
            USAGE_STR=" | 5h: ${h5}%${stale_marker}${h5_delta} | 7d: ${d7}%${stale_marker}${d7_delta}${d7_model}"
        fi
    fi
fi

printf "%s | %s | ctx: %s%%%s" \
    "$current_dir" \
    "$model_name" \
    "$used_pct" \
    "$USAGE_STR"
