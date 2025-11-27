#!/bin/bash
set -e

# Ensure proper ownership of workspace
sudo chown -R vscode:vscode /workspace 2>/dev/null || true

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
