alias dangerous="env CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false claude --dangerously-skip-permissions"
alias high="env CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false CLAUDE_CODE_EFFORT_LEVEL=high claude --dangerously-skip-permissions"
alias max="env CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true ENABLE_CLAUDEAI_MCP_SERVERS=false CLAUDE_CODE_EFFORT_LEVEL=max claude --dangerously-skip-permissions"

alias codex-dangerous="codex --dangerously-bypass-approvals-and-sandbox"
alias codex-high="codex --dangerously-bypass-approvals-and-sandbox -c model_reasoning_effort=high"
alias codex-max="codex --dangerously-bypass-approvals-and-sandbox -c model_reasoning_effort=xhigh"