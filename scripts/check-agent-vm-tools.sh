#!/usr/bin/env bash
# Read-only verifier. With no --component it is the full check; repeatable
# --component NAME checks only those components. Boundary runs first.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$script_dir/native/user_tools.py" check "$@"
