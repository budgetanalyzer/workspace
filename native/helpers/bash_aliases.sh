#!/usr/bin/env bash
# -- Claude Code aliases -----------------------------------------------------
# Opus 4.6 (effort parameter supported, adaptive thinking disabled for fixed budget)
alias claude-dangerous='env CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false claude --verbose --dangerously-skip-permissions'
alias claude-high='env CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false CLAUDE_CODE_EFFORT_LEVEL=high MAX_THINKING_TOKENS=32000 claude --verbose --dangerously-skip-permissions'
alias claude-max='env CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false CLAUDE_CODE_EFFORT_LEVEL=max MAX_THINKING_TOKENS=128000 claude --verbose  --dangerously-skip-permissions'

# Opus 4.6 (effort parameter supported, adaptive thinking disabled for fixed budget)
alias claude-dangerous46='env CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false claude  --model claude-opus-4-6 --verbose --dangerously-skip-permissions'
alias claude-high46='env CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false CLAUDE_CODE_EFFORT_LEVEL=high MAX_THINKING_TOKENS=32000 claude  --model claude-opus-4-6 --verbose --dangerously-skip-permissions'
alias claude-max46='env CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false CLAUDE_CODE_EFFORT_LEVEL=max MAX_THINKING_TOKENS=128000 claude --model claude-opus-4-6 --verbose  --dangerously-skip-permissions'

# Opus 4.5 (no effort parameter, uses MAX_THINKING_TOKENS for fixed budget)
alias claude-dangerous45='env CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false claude --model claude-opus-4-5-20251101 --verbose --dangerously-skip-permissions'
alias claude-high45='env MAX_THINKING_TOKENS=32000 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false claude --model claude-opus-4-5-20251101 --verbose --dangerously-skip-permissions'
alias claude-max45='env MAX_THINKING_TOKENS=128000 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false claude --model claude-opus-4-5-20251101 --verbose --dangerously-skip-permissions'

# -- Codex CLI aliases --------------------------------------------------------
alias codex-dangerous="codex-lean"
alias codex-high="env CODEX_REASONING_EFFORT=high codex-lean"
alias codex-max="env CODEX_REASONING_EFFORT=xhigh codex-lean"
alias codex-proxy="codex-with-proxy"
alias codex-high-proxy="env CODEX_REASONING_EFFORT=high codex-with-proxy"
alias codex-max-proxy="codex-max-with-proxy"

# -- Lean proxy inspection ----------------------------------------------------
# claude-with-proxy with a minimal tool surface at a chosen effort level, for
# capturing the full system prompt in mitmweb. Always bypasses permissions.
# Usage: claude-lean-proxy EFFORT [claude args...]
claude-lean-proxy() {
  local effort="${1:-}"
  case "$effort" in
    low | medium | high | xhigh | max) shift ;;
    *)
      echo "claude-lean-proxy: effort must be one of low|medium|high|xhigh|max" >&2
      return 2
      ;;
  esac
  CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 \
    CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1 \
    CLAUDE_CODE_DISABLE_AGENT_VIEW=1 \
    CLAUDE_CODE_DISABLE_CRON=1 \
    CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1 \
    CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1 \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false \
    claude-with-proxy \
    --dangerously-skip-permissions \
    --effort "$effort" \
    --tools "${CLAUDE_LEAN_TOOLS:-Bash,Read,Edit,Write,WebFetch,WebSearch}" \
    --strict-mcp-config \
    "$@"
}
alias claude-lean-proxy-low='claude-lean-proxy low'
alias claude-lean-proxy-medium='claude-lean-proxy medium'
alias claude-lean-proxy-high='claude-lean-proxy high'
alias claude-lean-proxy-xhigh='claude-lean-proxy xhigh'
alias claude-lean-proxy-max='claude-lean-proxy max'

# -- Lean sessions ------------------------------------------------------------
# claude-lean: the lean settings above without the proxy, plus the workspace
# system prompt through --system-prompt-file.
alias claude-lean-low='claude-lean low'
alias claude-lean-medium='claude-lean medium'
alias claude-lean-high='claude-lean high'
alias claude-lean-xhigh='claude-lean xhigh'
alias claude-lean-max='claude-lean max'
