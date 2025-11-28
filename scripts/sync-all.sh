#!/bin/bash

# sync-all.sh - Pull latest from main for all git repos in workspace
#
# Usage: ./scripts/sync-all.sh
#
# Discovers all git repositories in the workspace and pulls latest changes.
# Skips repos that are not on main branch or have uncommitted changes.

# Default to parent of script's directory (workspace sits alongside other repos)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="${WORKSPACE_DIR:-$(dirname "$SCRIPT_DIR")/..}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}[INFO]${NC} Syncing all git repos in $WORKSPACE_DIR..."
echo

TOTAL=0
SYNCED=0
SKIPPED=0

# Find all git repos (directories containing .git)
for git_dir in "$WORKSPACE_DIR"/*/.git; do
    [ -d "$git_dir" ] || continue

    REPO_PATH="$(dirname "$git_dir")"
    REPO_NAME="$(basename "$REPO_PATH")"
    TOTAL=$((TOTAL + 1))

    cd "$REPO_PATH" || continue

    # Check if on main branch
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
    if [ "$CURRENT_BRANCH" != "main" ]; then
        echo -e "${YELLOW}[SKIP]${NC} $REPO_NAME - not on main (currently: $CURRENT_BRANCH)"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        echo -e "${YELLOW}[SKIP]${NC} $REPO_NAME - has uncommitted changes"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    # Pull latest
    OUTPUT=$(git pull origin main 2>&1)
    if [ $? -eq 0 ]; then
        if echo "$OUTPUT" | grep -q "Already up to date"; then
            echo -e "${GREEN}[OK]${NC} $REPO_NAME - up to date"
        else
            COMMITS=$(echo "$OUTPUT" | grep -oE '[0-9]+ file' | head -1 || echo "changes")
            echo -e "${GREEN}[OK]${NC} $REPO_NAME - pulled ($COMMITS)"
        fi
        SYNCED=$((SYNCED + 1))
    else
        echo -e "${RED}[ERR]${NC} $REPO_NAME - pull failed"
        echo "     $OUTPUT" | head -2
        SKIPPED=$((SKIPPED + 1))
    fi
done

echo
echo -e "${BLUE}[DONE]${NC} Synced $SYNCED/$TOTAL repos ($SKIPPED skipped)"
