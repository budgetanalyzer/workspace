#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

CURRENT_UID=$(id -u)
CURRENT_GID=$(id -g)

cat > "$ENV_FILE" << EOF
# Auto-generated - do not commit
USER_UID=$CURRENT_UID
USER_GID=$CURRENT_GID
CLI_CACHE_BUST=$(date +%s)
EOF

echo "✓ Generated .env in workspace/claude-code-sandbox/"
echo "  USER_UID=$CURRENT_UID"
echo "  USER_GID=$CURRENT_GID"
