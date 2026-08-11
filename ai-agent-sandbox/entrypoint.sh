#!/bin/bash
set -e

# Ensure proper ownership of workspace
sudo chown -R vscode:vscode /workspace 2>/dev/null || true

# =======================================================
# CLONE BUDGET ANALYZER REPOS
# =======================================================

echo "--- Checking Budget Analyzer repositories ---"

REPOS=(
  "orchestration"
  "service-common"
  "transaction-service"
  "currency-service"
  "permission-service"
  "session-gateway"
  "budget-analyzer-web"
  "checkstyle-config"
  "budget-analyzer-api-tests"
  "ai-session-handler"
)

for repo in "${REPOS[@]}"; do
  if [ ! -d "/workspace/$repo" ]; then
    echo "Cloning $repo..."
    if git clone "https://github.com/budgetanalyzer/$repo.git" "/workspace/$repo" 2>/dev/null; then
      echo "✓ Cloned $repo"
    else
      echo "✗ Failed to clone $repo"
    fi
  else
    echo "✓ $repo already exists"
  fi
done

# =======================================================
# CONVERT ORIGINS TO SSH
# =======================================================

echo "--- Converting origins to SSH ---"

for repo in "workspace" "${REPOS[@]}"; do
  if [ -d "/workspace/$repo" ]; then
    current_origin=$(git -C "/workspace/$repo" remote get-url origin 2>/dev/null || echo "")
    if [[ "$current_origin" == https://github.com/* ]]; then
      ssh_origin=${current_origin/https:\/\/github.com\//git@github.com:}
      git -C "/workspace/$repo" remote set-url origin "$ssh_origin"
      echo "✓ $repo: converted to SSH"
    elif [[ "$current_origin" == git@github.com:* ]]; then
      echo "✓ $repo: already SSH"
    fi
  fi
done

echo ""

# =======================================================
# AI SESSION HANDLER
# =======================================================

echo "--- Installing AI Session Handler ---"

AI_SESSION_HANDLER_DIR="/workspace/ai-session-handler"
AI_SESSION_HANDLER_PROJECT="$AI_SESSION_HANDLER_DIR/pyproject.toml"
AI_SESSION_HANDLER_SOURCE="$AI_SESSION_HANDLER_DIR/src/ai_session_handler"

if [ ! -d "$AI_SESSION_HANDLER_DIR" ]; then
    echo "✗ AI Session Handler checkout missing at $AI_SESSION_HANDLER_DIR" >&2
    exit 1
elif [ ! -f "$AI_SESSION_HANDLER_PROJECT" ]; then
    echo "✗ AI Session Handler package metadata missing at $AI_SESSION_HANDLER_PROJECT" >&2
    exit 1
elif ! command -v pipx &> /dev/null; then
    echo "✗ pipx is required to install AI Session Handler" >&2
    exit 1
elif ! pipx install --force --editable "$AI_SESSION_HANDLER_DIR"; then
    echo "✗ Failed to install AI Session Handler with: pipx install --force --editable $AI_SESSION_HANDLER_DIR" >&2
    exit 1
fi

if ! command -v ai-session-handler &> /dev/null; then
    echo "✗ pipx installed AI Session Handler, but ai-session-handler is not available on PATH" >&2
    exit 1
elif ! command -v ai-session-handler-codex-high &> /dev/null; then
    echo "✗ pipx installed AI Session Handler, but ai-session-handler-codex-high is not available on PATH" >&2
    exit 1
elif ! ai-session-handler --version &> /dev/null; then
    echo "✗ The installed ai-session-handler command is unusable" >&2
    exit 1
elif ! ai-session-handler-codex-high --help &> /dev/null; then
    echo "✗ The installed ai-session-handler-codex-high command is unusable" >&2
    exit 1
fi

if ! pipx_local_venvs=$(pipx environment --value PIPX_LOCAL_VENVS) || [ -z "$pipx_local_venvs" ]; then
    echo "✗ Could not locate the pipx virtual environment for AI Session Handler" >&2
    exit 1
fi

ai_session_handler_python="$pipx_local_venvs/ai-session-handler/bin/python"
if [ ! -x "$ai_session_handler_python" ]; then
    echo "✗ AI Session Handler pipx Python is missing at $ai_session_handler_python" >&2
    exit 1
elif ! ai_session_handler_module=$(
    "$ai_session_handler_python" -c \
        'from pathlib import Path; import ai_session_handler; print(Path(ai_session_handler.__file__).resolve())'
); then
    echo "✗ The pipx environment cannot import ai_session_handler" >&2
    exit 1
fi

case "$ai_session_handler_module" in
    "$AI_SESSION_HANDLER_SOURCE"/*)
        echo "✓ AI Session Handler installed editably from $AI_SESSION_HANDLER_DIR"
        ;;
    *)
        echo "✗ AI Session Handler import is not linked to $AI_SESSION_HANDLER_SOURCE: $ai_session_handler_module" >&2
        exit 1
        ;;
esac

echo ""

# =======================================================
# VERIFY AI CODING CLIs
# =======================================================

echo "--- AI Coding CLIs ---"

if command -v claude &> /dev/null; then
    echo "✓ Claude Code $(claude --version 2>/dev/null || echo 'installed')"
else
    echo "✗ Claude Code not available"
fi

if command -v codex &> /dev/null; then
    echo "✓ Codex CLI installed"
else
    echo "✗ Codex CLI not available"
fi

if command -v codex-lean &> /dev/null; then
    echo "✓ Codex lean launcher installed"
else
    echo "✗ Codex lean launcher not available"
fi

if command -v gemini &> /dev/null; then
    echo "✓ Gemini CLI $(gemini --version 2>&1 | head -n 1 || echo 'installed')"
else
    echo "✗ Gemini CLI not available"
fi

echo "✓ $(ai-session-handler --version)"
echo "✓ AI Session Handler Codex high launcher installed"

# =======================================================
# VERIFY DEV TOOLS
# =======================================================

echo ""
echo "--- Dev tools ---"

if command -v node &> /dev/null; then
    echo "✓ Node.js $(node --version)"
else
    echo "✗ Node.js not available"
fi

if command -v java &> /dev/null; then
    echo "✓ Java $(java --version 2>&1 | head -n 1)"
else
    echo "✗ Java not available"
fi

if command -v mvn &> /dev/null; then
    echo "✓ Maven $(mvn --version 2>&1 | head -n 1)"
else
    echo "✗ Maven not available"
fi

if command -v actionlint &> /dev/null; then
    echo "✓ actionlint $(actionlint --version)"
else
    echo "✗ actionlint not available"
fi

# =======================================================
# CLAUDE CODE SKILLS
# =======================================================

echo ""
echo "--- Installing Claude Code skills ---"
if [ -d "/workspace/workspace/ai-agent-sandbox/skills" ]; then
    mkdir -p /home/vscode/.claude/skills
    cp -r /workspace/workspace/ai-agent-sandbox/skills/* /home/vscode/.claude/skills/
    echo "✓ Skills installed: $(ls /home/vscode/.claude/skills/)"
else
    echo "  No skills directory found"
fi

# =======================================================
# CLAUDE CODE SETTINGS
# =======================================================

echo ""
echo "--- Applying Claude Code settings ---"

CLAUDE_DIR="/home/vscode/.claude"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
OVERLAY_FILE="/workspace/workspace/ai-agent-sandbox/settings-overlay.json"
if [ -f "$OVERLAY_FILE" ]; then
    if [ -f "$SETTINGS_FILE" ]; then
        jq -s '.[0] * .[1]' "$SETTINGS_FILE" "$OVERLAY_FILE" > "${SETTINGS_FILE}.tmp" \
            && mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
        echo "✓ Settings overlay merged"
    else
        cp "$OVERLAY_FILE" "$SETTINGS_FILE"
        echo "✓ Settings overlay written as new settings.json"
    fi
else
    echo "  No settings overlay found"
fi

# =======================================================
# BANNER
# =======================================================

echo ""
echo "AI Coding Sandbox"
echo "======================================"
echo ""
echo "CLIs:     claude | codex | gemini | ai-session-handler | ai-run"
echo "Context:  Claude/Gemini read repo instructions. Codex aliases load AGENTS.md via project docs."
echo "Plans:    cd /workspace/REPOSITORY && ai-run PLAN_NAME"
echo ""
echo "Auth:"
echo "  Claude — run 'claude auth login'"
echo "  Codex  — export OPENAI_API_KEY or run 'codex login' (use codex for upstream defaults, codex-lean for lean defaults)"
echo "  Gemini — export GEMINI_API_KEY or run 'gemini' to sign in"
echo ""

# Execute the main command
exec "$@"
