#!/usr/bin/env bash
# Human Checkpoint B.1; workers must not invoke live installers.
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage: prepare-agent-vm-native.sh [--worktree-parent PATH] [--bare-parent PATH]

Human-only Ubuntu development-VM preparation after all authoring workers exit.
Runs system provisioning, scoped bwrap profile setup, and user installation
twice. Existing installers enforce VM/user/repository/Docker boundaries.
Defaults worktree parent to this workspace's parent; prompts for bare parent
when omitted. Logs stay under workspace tmp/native-preparation/.
No reboot, trust import, provider login or full B.2 verification runs.
EOF
}

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
workspace_dir=$(cd -- "$script_dir/.." && pwd)
native_worktree_parent=$(cd -- "$workspace_dir/.." && pwd -P)
native_bare_parent=
while (($#)); do
    case "$1" in
        --worktree-parent|--bare-parent)
            if (($# < 2)) || [[ -z $2 || $2 == --* ]]; then
                printf 'Missing path for %s\n' "$1" >&2
                exit 2
            fi
            if [[ $1 == --worktree-parent ]]; then
                native_worktree_parent=$2
            else
                native_bare_parent=$2
            fi
            shift 2
            ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ -z $native_bare_parent ]]; then
    read -r -p 'Existing guest bare-repository parent: ' native_bare_parent
fi
for parent in "$native_worktree_parent" "$native_bare_parent"; do
    if [[ $parent != /* || ! -d $parent || $(cd -- "$parent" && pwd -P) != "$parent" ]]; then
        printf 'Repository parents must be existing canonical absolute directories.\n' >&2
        exit 2
    fi
done
if [[ $native_worktree_parent/workspace != "$workspace_dir" ]]; then
    printf 'Worktree parent must contain this workspace checkout.\n' >&2
    exit 2
fi

cd -- "$workspace_dir"
umask 077
mkdir -p tmp/native-preparation
log_file=$(mktemp "$workspace_dir/tmp/native-preparation/prepare-XXXXXXXX.log")
exec > >(tee "$log_file") 2>&1
report_exit() {
    local preparation_exit_code=$?
    if ((preparation_exit_code)); then
        printf 'Preparation stopped (exit %s). Log: %s\n' "$preparation_exit_code" "$log_file" >&2
    fi
}
trap report_exit EXIT
printf 'Preparation log: %s\n' "$log_file"
sudo -v
"$script_dir/provision-agent-vm-guest.sh" --docker-user "$(id -un)"
"$script_dir/install-agent-vm-bwrap-profile.sh" --docker-user "$(id -un)"
"$script_dir/install-agent-vm-user-tools.sh" \
    --worktree-parent "$native_worktree_parent" --bare-parent "$native_bare_parent"
# shellcheck disable=SC1091
. "$HOME/.config/budget-analyzer-native/env.sh"
"$script_dir/install-agent-vm-user-tools.sh" \
    --worktree-parent "$native_worktree_parent" --bare-parent "$native_bare_parent"
printf '\nB.1 preparation completed. Open a fresh guest terminal for the installed environment.\n'
printf 'Continue B.2 trust and provider setup in docs/native-user-tools.md, then run check-agent-vm-tools.sh.\n'
printf 'Preparation log: %s\n' "$log_file"
