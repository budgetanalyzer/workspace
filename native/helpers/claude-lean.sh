#!/usr/bin/env bash
# Launch Claude Code with the workspace's lean defaults and custom system prompt.
# Usage: claude-lean EFFORT [claude args...]
set -euo pipefail

effort="${1:-}"
case "$effort" in
    low | medium | high | xhigh | max) shift ;;
    *)
        echo "claude-lean: effort must be one of low|medium|high|xhigh|max" >&2
        exit 2
        ;;
esac

prompt_file="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/system-prompt.md"
if [ ! -r "$prompt_file" ]; then
    echo "claude-lean: system prompt missing: $prompt_file" >&2
    exit 1
fi

export CLAUDE_CODE_DISABLE_AUTO_MEMORY=1
export CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1
export CLAUDE_CODE_DISABLE_AGENT_VIEW=1
export CLAUDE_CODE_DISABLE_CRON=1
export CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1
export CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false
# claude-lean-proxy receives these from claude-with-proxy (scripts/native/proxy.py).
export CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1
export ENABLE_CLAUDEAI_MCP_SERVERS=false
export CLAUDE_CODE_DISABLE_1M_CONTEXT=1

exec claude \
    --dangerously-skip-permissions \
    --effort "$effort" \
    --tools "${CLAUDE_LEAN_TOOLS:-Bash,Read,Edit,Write,WebFetch,WebSearch}" \
    --strict-mcp-config \
    --system-prompt-file "$prompt_file" \
    "$@"
