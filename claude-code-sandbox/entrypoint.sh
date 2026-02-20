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
  "token-validation-service"
  "session-gateway"
  "budget-analyzer-web"
  "architecture-conversations"
  "checkstyle-config"
  "claude-discovery"
)

for repo in "${REPOS[@]}"; do
  if [ ! -d "/workspace/$repo" ]; then
    echo "Cloning $repo..."
    if git clone "https://github.com/budgetanalyzerllc/$repo.git" "/workspace/$repo" 2>/dev/null; then
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
      ssh_origin=$(echo "$current_origin" | sed 's|https://github.com/|git@github.com:|')
      git -C "/workspace/$repo" remote set-url origin "$ssh_origin"
      echo "✓ $repo: converted to SSH"
    elif [[ "$current_origin" == git@github.com:* ]]; then
      echo "✓ $repo: already SSH"
    fi
  fi
done

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

if command -v gemini &> /dev/null; then
    echo "✓ Gemini CLI $(gemini --version 2>&1 | head -n 1 || echo 'installed')"
else
    echo "✗ Gemini CLI not available"
fi

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

# =======================================================
# VERIFY AUDIO TOOLS
# =======================================================

echo ""
echo "--- Audio tools ---"

for tool in ffmpeg sox ecasound rubberband mediainfo; do
    if command -v $tool &> /dev/null; then
        echo "✓ $tool"
    else
        echo "✗ $tool not available"
    fi
done

# =======================================================
# CLAUDE CODE SKILLS
# =======================================================

echo ""
echo "--- Installing Claude Code skills ---"
if [ -d "/workspace/workspace/claude-code-sandbox/skills" ]; then
    mkdir -p /home/vscode/.claude/skills
    cp -r /workspace/workspace/claude-code-sandbox/skills/* /home/vscode/.claude/skills/
    echo "✓ Skills installed: $(ls /home/vscode/.claude/skills/)"
else
    echo "  No skills directory found"
fi

# =======================================================
# CLAUDE CODE STATUSLINE
# =======================================================

echo ""
echo "--- Installing Claude Code statusline ---"
SANDBOX_SCRIPTS="/workspace/workspace/claude-code-sandbox/scripts"
CLAUDE_DIR="/home/vscode/.claude"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"

if [ -f "$SANDBOX_SCRIPTS/statusline-command.sh" ]; then
    cp "$SANDBOX_SCRIPTS/statusline-command.sh" "$CLAUDE_DIR/statusline-command.sh"
    chmod +x "$CLAUDE_DIR/statusline-command.sh"
    echo "✓ Statusline script installed"

    # Merge statusLine config into settings.json without clobbering other settings
    STATUSLINE_CONFIG='{"statusLine":{"type":"command","command":"/home/vscode/.claude/statusline-command.sh"}}'
    if [ -f "$SETTINGS_FILE" ]; then
        jq -s '.[0] * .[1]' "$SETTINGS_FILE" <(echo "$STATUSLINE_CONFIG") > "${SETTINGS_FILE}.tmp" \
            && mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
        echo "✓ Statusline config merged into settings.json"
    else
        echo "$STATUSLINE_CONFIG" | jq '.' > "$SETTINGS_FILE"
        echo "✓ Statusline config written to new settings.json"
    fi
else
    echo "  No statusline script found in sandbox"
fi

# =======================================================
# CLAUDE CODE SETTINGS
# =======================================================

echo ""
echo "--- Applying Claude Code settings ---"

OVERLAY_FILE="/workspace/workspace/claude-code-sandbox/settings-overlay.json"
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
echo "CLIs:     claude | codex | gemini"
echo "Context:  All three read AGENTS.md. Claude Code also reads CLAUDE.md."
echo ""
echo "Auth:"
echo "  Claude — already authenticated via ~/.anthropic volume"
echo "  Codex  — export OPENAI_API_KEY or run 'codex' to sign in"
echo "  Gemini — export GEMINI_API_KEY or run 'gemini' to sign in"
echo ""

# Execute the main command
exec "$@"
