#!/usr/bin/env bash
# Human Checkpoint B only; agents use the read-only installed ensure/check commands.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$script_dir/native/local_ca.py" human-install "$@"
