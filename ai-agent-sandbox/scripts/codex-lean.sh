#!/usr/bin/env bash
# Launch Codex with the sandbox's lean defaults.
set -euo pipefail

REAL_CODEX="${CODEX_REAL_BIN:-/usr/local/bin/codex}"
if [ ! -x "$REAL_CODEX" ]; then
    REAL_CODEX="$(command -v codex)"
fi

reasoning_effort="${CODEX_REASONING_EFFORT:-high}"

args=(
    --dangerously-bypass-approvals-and-sandbox
    -c 'approval_policy="never"'
    -c 'sandbox_mode="danger-full-access"'
    -c 'web_search="disabled"'
    -c 'project_doc_max_bytes=0'
    -c 'hide_agent_reasoning=false'
    -c 'include_environment_context=false'
    -c 'include_permissions_instructions=false'
    -c 'include_apps_instructions=false'
    -c 'include_apply_patch_tool=true'
    -c 'features.apps=false'
    -c 'features.browser_use=false'
    -c 'features.browser_use_external=false'
    -c 'features.computer_use=false'
    -c 'features.enable_fanout=false'
    -c 'features.enable_mcp_apps=false'
    -c 'features.hooks=false'
    -c 'features.image_generation=false'
    -c 'features.in_app_browser=false'
    -c 'features.memories=false'
    -c 'features.multi_agent=false'
    -c 'features.multi_agent_v2=false'
    -c 'features.plugin_hooks=false'
    -c 'features.plugins=false'
    -c 'features.shell_snapshot=false'
    -c 'features.skill_mcp_dependency_install=false'
    -c 'features.tool_call_mcp_elicitation=false'
    -c 'features.tool_search=false'
    -c 'features.tool_suggest=false'
    -c 'features.workspace_dependencies=false'
    -c 'apps._default.enabled=false'
    -c 'apps._default.destructive_enabled=false'
    -c 'apps._default.open_world_enabled=false'
    -c 'history.persistence="none"'
    -c 'tui.notifications=false'
    -c 'tui.animations=false'
    -c 'tui.show_tooltips=false'
    -c 'tui.status_line=[]'
    -c 'tui.terminal_title=[]'
    -c "model_reasoning_effort=\"${reasoning_effort}\""
)

if [ -n "${CODEX_MODEL:-}" ]; then
    args+=(--model "$CODEX_MODEL")
fi

exec "$REAL_CODEX" "${args[@]}" "$@"
