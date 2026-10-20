#!/usr/bin/env bash
# Launch Claude Code with the workspace's lean defaults and custom system prompt.
# Usage: claude-lean [--proxy] [claude args...]
set -euo pipefail

use_proxy=false
if [ "${1:-}" = "--proxy" ]; then
    use_proxy=true
    shift
fi

export CLAUDE_CODE_DISABLE_AUTO_MEMORY=1
export CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1
export CLAUDE_CODE_DISABLE_AGENT_VIEW=1
export CLAUDE_CODE_DISABLE_CRON=1
export CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1
export CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false
export CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1
export ENABLE_CLAUDEAI_MCP_SERVERS=false
export CLAUDE_CODE_DISABLE_1M_CONTEXT=1

claude_args=(
    --dangerously-skip-permissions
    --tools "Bash,Read,Edit,Write,WebFetch,WebSearch"
    --strict-mcp-config
)

if [ "$use_proxy" = true ]; then
    exec claude-with-proxy "${claude_args[@]}" "$@"
fi

prompt_file="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/system-prompt.md"
if [ ! -r "$prompt_file" ]; then
    echo "claude-lean: system prompt missing: $prompt_file" >&2
    exit 1
fi

exec claude "${claude_args[@]}" --system-prompt-file "$prompt_file" "$@"
