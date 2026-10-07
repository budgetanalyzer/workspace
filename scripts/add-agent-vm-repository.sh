#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage: add-agent-vm-repository.sh PATH

Add one host Git repository to the Budget Analyzer development VM. PATH must
identify the repository root. The repository is added through the standard
budget-agent-vm SSH profile under /srv/budget-analyzer.
EOF
}

die() {
    printf 'add-agent-vm-repository: %s\n' "$*" >&2
    exit 1
}

if (($# == 1)) && [[ "$1" == --help || "$1" == -h ]]; then
    usage
    exit 0
fi

(($# == 1)) || die 'provide exactly one repository path'

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
exec "$script_dir/setup-agent-vm-repositories.sh" \
    --repository "$1" \
    --ssh-host budget-agent-vm \
    --guest-root /srv/budget-analyzer
