#!/usr/bin/env bash
# -- Lean Claude aliases ------------------------------------------------------
alias claude-lean-high='claude-lean --effort high'
alias claude-lean-proxy='claude-lean --proxy'
alias claude-lean-proxy-high='claude-lean --proxy --effort high'
alias ai-run-claude='ai-run --claude'

# -- Codex CLI aliases --------------------------------------------------------
alias codex-dangerous="codex-lean"
alias codex-high="env CODEX_REASONING_EFFORT=high codex-lean"
alias codex-max="env CODEX_REASONING_EFFORT=xhigh codex-lean"
alias codex-proxy="codex-with-proxy"
alias codex-high-proxy="env CODEX_REASONING_EFFORT=high codex-with-proxy"
alias codex-max-proxy="codex-max-with-proxy"
