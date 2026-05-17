# -- Claude Code aliases -----------------------------------------------------
# Opus 4.6 (effort parameter supported, adaptive thinking disabled for fixed budget)
alias dangerous='env CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false claude --verbose --dangerously-skip-permissions'
alias high='env CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false CLAUDE_CODE_EFFORT_LEVEL=high MAX_THINKING_TOKENS=32000 claude --verbose --dangerously-skip-permissions'
alias max='env CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false CLAUDE_CODE_EFFORT_LEVEL=max MAX_THINKING_TOKENS=128000 claude --verbose  --dangerously-skip-permissions'

# Opus 4.6 (effort parameter supported, adaptive thinking disabled for fixed budget)
alias dangerous46='env CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false claude  --model claude-opus-4-6 --verbose --dangerously-skip-permissions'
alias high46='env CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false CLAUDE_CODE_EFFORT_LEVEL=high MAX_THINKING_TOKENS=32000 claude  --model claude-opus-4-6 --verbose --dangerously-skip-permissions'
alias max46='env CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false CLAUDE_CODE_EFFORT_LEVEL=max MAX_THINKING_TOKENS=128000 claude --model claude-opus-4-6 --verbose  --dangerously-skip-permissions'

# Opus 4.5 (no effort parameter, uses MAX_THINKING_TOKENS for fixed budget)
alias dangerous45='env CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false claude --model claude-opus-4-5-20251101 --verbose --dangerously-skip-permissions'
alias high45='env MAX_THINKING_TOKENS=32000 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false claude --model claude-opus-4-5-20251101 --verbose --dangerously-skip-permissions'
alias max45='env MAX_THINKING_TOKENS=128000 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false claude --model claude-opus-4-5-20251101 --verbose --dangerously-skip-permissions'

# -- Codex CLI aliases --------------------------------------------------------
alias codex-dangerous="codex-lean"
alias codex-high="env CODEX_REASONING_EFFORT=high codex-lean"
alias codex-max="env CODEX_REASONING_EFFORT=xhigh codex-lean"
alias codex-proxy="codex-with-proxy"
alias codex-high-proxy="env CODEX_REASONING_EFFORT=high codex-with-proxy"
alias codex-max-proxy="codex-max-with-proxy"
