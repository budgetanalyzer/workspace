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

printf "%s | %s | %s %sk/%sk" \
    "$current_dir" \
    "$model_name" \
    "$bar" \
    "$used_k" \
    "$max_k"
