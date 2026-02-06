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

# Ensure .anthropic directory exists with proper permissions
if [ ! -d "/home/vscode/.anthropic" ]; then
    mkdir -p /home/vscode/.anthropic
    chmod 700 /home/vscode/.anthropic
fi

# Verify Claude Code CLI installation
if command -v claude &> /dev/null; then
    echo "✓ Claude Code CLI is installed"
    claude --version 2>/dev/null || true
else
    echo "✗ Warning: Claude Code CLI is not available"
fi

# Verify tool installations
if command -v node &> /dev/null; then
    echo "✓ Node.js $(node --version)"
else
    echo "✗ Warning: Node.js is not available"
fi

if command -v java &> /dev/null; then
    echo "✓ Java $(java --version 2>&1 | head -n 1)"
else
    echo "✗ Warning: Java is not available"
fi

if command -v mvn &> /dev/null; then
    echo "✓ Maven $(mvn --version 2>&1 | head -n 1)"
else
    echo "✗ Warning: Maven is not available"
fi

# =======================================================
# AUDIO TOOLS VERIFICATION
# =======================================================

echo ""
echo "--- Verifying audio processing tools ---"

if command -v ffmpeg &> /dev/null; then
    echo "✓ ffmpeg $(ffmpeg -version 2>&1 | head -n 1)"
else
    echo "✗ Warning: ffmpeg is not available"
fi

if command -v sox &> /dev/null; then
    echo "✓ sox $(sox --version 2>&1 | head -n 1)"
else
    echo "✗ Warning: sox is not available"
fi

if command -v ecasound &> /dev/null; then
    echo "✓ ecasound available"
else
    echo "✗ Warning: ecasound is not available"
fi

if command -v rubberband &> /dev/null; then
    echo "✓ rubberband available"
else
    echo "✗ Warning: rubberband is not available"
fi

if command -v mediainfo &> /dev/null; then
    echo "✓ mediainfo available"
else
    echo "✗ Warning: mediainfo is not available"
fi

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
        # Merge into existing settings
        jq -s '.[0] * .[1]' "$SETTINGS_FILE" <(echo "$STATUSLINE_CONFIG") > "${SETTINGS_FILE}.tmp" \
            && mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
        echo "✓ Statusline config merged into settings.json"
    else
        # Create new settings file
        echo "$STATUSLINE_CONFIG" | jq '.' > "$SETTINGS_FILE"
        echo "✓ Statusline config written to new settings.json"
    fi
else
    echo "  No statusline script found in sandbox"
fi

# =======================================================
# GEMINI CLI SETUP
# =======================================================

echo "--- Configuring NPM for non-root global install ---"
mkdir -p /home/vscode/.npm-global
npm config set prefix '/home/vscode/.npm-global'

# Update PATH in .bashrc only if not already present
if ! grep -q '/home/vscode/.npm-global/bin' /home/vscode/.bashrc; then
    echo 'export PATH="/home/vscode/.npm-global/bin:$PATH"' >> /home/vscode/.bashrc
fi

# Update PATH for current script execution
export PATH="/home/vscode/.npm-global/bin:$PATH"

echo "NPM prefix set to ~/.npm-global and PATH updated."

# Install Gemini CLI globally
echo "--- Installing Gemini CLI globally ---"
if npm install -g @google/gemini-cli; then
    echo "✓ Gemini CLI installed successfully"

    # Verify installation
    if command -v gemini &> /dev/null; then
        echo "✓ Gemini CLI is available: $(gemini --version 2>&1 | head -n 1 || echo 'installed')"
    fi
else
    echo "✗ ERROR: Failed to install Gemini CLI"
fi

# Create .gemini directory for configuration
mkdir -p /home/vscode/.gemini
chmod 700 /home/vscode/.gemini

echo ""
echo "Claude/Gemini Code Sandbox Environment"
echo "======================================"
echo "User: vscode (UID: 1002, GID: 1002)"
echo "Workspace: /workspace (contains all projects)"
echo ""
echo "Audio Tools Available:"
echo "  ffmpeg     - Encoding, format conversion, filters"
echo "  sox        - Effects processing, analysis, batch ops"
echo "  ecasound   - Multitrack CLI processing"
echo "  rubberband - Time-stretching, pitch-shifting"
echo "  mediainfo  - File analysis, metadata"
echo "  LADSPA     - Plugin effects (reverb, compression, EQ)"
echo ""
echo "Gemini CLI Authentication Options:"
echo "1. API Key (Recommended for dev containers):"
echo "   export GEMINI_API_KEY='your-key-here'"
echo "   Get your key from: https://aistudio.google.com/app/apikey"
echo ""
echo "2. Service Account (For team/CI environments):"
echo "   export GOOGLE_APPLICATION_CREDENTIALS='/path/to/service-account.json'"
echo "   export GOOGLE_CLOUD_PROJECT='your-project-id'"
echo "   export GOOGLE_CLOUD_LOCATION='us-central1'"
echo ""
echo "3. OAuth Login (Interactive):"
echo "   Just run 'gemini' and select 'Login with Google'"
echo ""
echo "IMPORTANT: Run 'gemini /ide install' in a new terminal once VS Code is fully loaded."
echo "Open the Claude Code sidebar (Spark icon) or run 'gemini' in the terminal."
echo ""

# Execute the main command
exec "$@"
