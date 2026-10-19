#!/usr/bin/env bash
# Claude Code status line: reads the status line JSON on stdin and prints one
# offline line. No network, credentials, cache or file writes.

input=$(cat)
[ -n "$input" ] || exit 0

sep=$'\x1f'
fields=$(printf '%s' "$input" | jq -r '
  def pct($o): ($o.used_percentage // $o.utilization) | if type == "number" then round else empty end;
  def reset($o): $o.resets_at | if type == "number" then floor elif type == "string" then . else empty end;
  [ (.workspace.current_dir // .cwd // ""),
    (.model.display_name // ""),
    (pct(.context_window // {}) // ""),
    (pct(.rate_limits.five_hour // {}) // ""),
    (reset(.rate_limits.five_hour // {}) // ""),
    (pct(.rate_limits.seven_day // {}) // ""),
    (reset(.rate_limits.seven_day // {}) // "")
  ] | map(tostring) | join("\u001f")' 2>/dev/null) || exit 0
IFS="$sep" read -r dir model ctx five five_reset week week_reset <<<"$fields"

# Relative duration until an epoch (seconds or milliseconds) or ISO-8601 time.
until_reset() {
    local value=$1 epoch now secs
    [ -n "$value" ] || return 0
    if [[ $value =~ ^[0-9]+$ ]]; then
        epoch=$value
        [ "$epoch" -gt 1000000000000 ] && epoch=$((epoch / 1000))
    else
        epoch=$(date -d "$value" +%s 2>/dev/null) || return 0
    fi
    now=$(date +%s)
    secs=$((epoch - now))
    if [ "$secs" -le 0 ]; then
        printf 'now'
    elif [ "$secs" -ge 86400 ]; then
        printf '%dd%dh' $((secs / 86400)) $((secs % 86400 / 3600))
    elif [ "$secs" -ge 3600 ]; then
        printf '%dh%dm' $((secs / 3600)) $((secs % 3600 / 60))
    else
        printf '%dm' $((secs / 60))
    fi
}

usage_segment() {
    local label=$1 percent=$2 reset=$3 duration
    [ -n "$percent" ] || return 0
    duration=$(until_reset "$reset")
    if [ -n "$duration" ]; then
        printf '%s %s%% (%s)' "$label" "$percent" "$duration"
    else
        printf '%s %s%%' "$label" "$percent"
    fi
}

segments=()
if [ -n "$dir" ]; then
    if [ -n "$HOME" ] && [ "$dir" = "$HOME" ]; then
        dir='~'
    elif [ -n "$HOME" ] && [[ $dir == "$HOME"/* ]]; then
        dir="~${dir#"$HOME"}"
    fi
    segments+=("$(printf '\033[01;34m%s\033[00m' "$dir")")
fi
[ -z "$model" ] || segments+=("$model")
[ -z "$ctx" ] || segments+=("ctx $ctx%")
segment=$(usage_segment 5h "$five" "$five_reset")
[ -z "$segment" ] || segments+=("$segment")
segment=$(usage_segment 7d "$week" "$week_reset")
[ -z "$segment" ] || segments+=("$segment")

line=''
for segment in "${segments[@]}"; do
    line+="${line:+ | }$segment"
done
[ -z "$line" ] || printf '%s\n' "$line"
exit 0
