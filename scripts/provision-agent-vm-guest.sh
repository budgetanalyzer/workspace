#!/usr/bin/env bash
set -Eeuo pipefail

# The stdlib engine and manifest are tested without privileged commands or
# environment-based preflight bypasses.
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
command -v python3 >/dev/null 2>&1 || {
    printf 'provision-agent-vm-guest: python3 is required\n' >&2
    exit 1
}
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$script_dir/native/provision.py" "$@"
