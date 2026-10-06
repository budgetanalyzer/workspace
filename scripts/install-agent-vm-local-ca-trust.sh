#!/usr/bin/env bash
# Human-only trust installation; agents use the read-only ensure/check commands.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$script_dir/native/local_ca.py" human-install "$@"
