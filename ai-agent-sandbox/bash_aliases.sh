# -- Claude Code aliases -----------------------------------------------------
alias dangerous='env CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false claude  --verbose --dangerously-skip-permissions'
alias high='env CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false CLAUDE_CODE_EFFORT_LEVEL=high claude  --verbose --dangerously-skip-permissions'
alias max='env CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 CLAUDE_CODE_DISABLE_1M_CONTEXT=1 CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false CLAUDE_CODE_EFFORT_LEVEL=max claude --verbose  --dangerously-skip-permissions'

# -- Codex CLI aliases (no --system-prompt support) ---------------------------
alias codex-dangerous="env CODEX_DISABLE_PROJECT_DOC=1 codex --dangerously-bypass-approvals-and-sandbox"
alias codex-high="env CODEX_DISABLE_PROJECT_DOC=1 codex --dangerously-bypass-approvals-and-sandbox -c model_reasoning_effort=high"
alias codex-max="env CODEX_DISABLE_PROJECT_DOC=1 codex --dangerously-bypass-approvals-and-sandbox -c model_reasoning_effort=xhigh"
