#!/usr/bin/env bash
# Read-only pre-agent VM boundary check; needs no provider CLIs or helpers.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$script_dir/native/boundary.py" "$@"
