#!/usr/bin/env bash
# Human-only user installation; repeatable --component NAME selects
# base, claude, codex, gemini or extras (default: all). Boundary runs first.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$script_dir/native/user_tools.py" install "$@"
