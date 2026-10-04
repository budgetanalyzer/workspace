#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage: agent-vm-container-lifecycle.sh OPERATION [--bootstrap-only]

Internal shared implementation for the installed agent-vm-container-* helpers.
OPERATION is start, stop, restart, status, or shell.

Normal operation requires the post-Kind kubeconfig and uses both reviewed
Compose files. --bootstrap-only visibly selects the base Compose file for the
pre-Kind bootstrap window. These commands manage only the agent container.
EOF
}

die() {
    printf 'agent-vm-container: %s\n' "$*" >&2
    exit 1
}

read_env_value() {
    local key=$1
    local -a matches=()

    mapfile -t matches < <(sed -n "/^${key}=/p" "$env_file")
    ((${#matches[@]} == 1)) \
        || die "$key must occur exactly once in agent-vm.env"
    REPLY=${matches[0]#*=}
    [[ -n "$REPLY" ]] || die "$key must not be empty in agent-vm.env"
}

validate_absolute_directory() {
    local key=$1
    local path=$2

    [[ "$path" == /* && "$path" != / ]] \
        || die "$key must be an absolute non-root path"
    [[ -d "$path" ]] || die "$key directory is missing"
    [[ ! -L "$path" ]] || die "$key must not be a symbolic link"
    [[ "$(realpath -e -- "$path")" == "$path" ]] \
        || die "$key must be an exact canonical path"
}

(($# >= 1 && $# <= 2)) || {
    usage >&2
    exit 2
}

operation=$1
case "$operation" in
    start|stop|restart|status|shell) ;;
    --help|-h)
        (($# == 1)) || die '--help does not accept other arguments'
        usage
        exit 0
        ;;
    *) die "unsupported operation: $operation" ;;
esac

mode=daily
if (($# == 2)); then
    if [[ "$2" == --help || "$2" == -h ]]; then
        usage
        exit 0
    fi
    [[ "$2" == --bootstrap-only ]] \
        || die "unsupported option for $operation: $2"
    mode=bootstrap-only
fi

for command_name in docker realpath sed; do
    command -v "$command_name" >/dev/null 2>&1 \
        || die "$command_name is required"
done

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
workspace_root=$(realpath -e -- "$script_dir/..") \
    || die 'could not resolve the installed workspace root'
sandbox_dir=$workspace_root/ai-agent-sandbox
env_file=$sandbox_dir/agent-vm.env
base_compose=$sandbox_dir/docker-compose.agent-vm.yml
kube_compose=$sandbox_dir/docker-compose.agent-vm-kubeconfig.yml

[[ -r "$env_file" ]] || die 'missing readable ai-agent-sandbox/agent-vm.env'
[[ -r "$base_compose" ]] \
    || die 'missing readable ai-agent-sandbox/docker-compose.agent-vm.yml'
if [[ "$mode" == daily ]]; then
    [[ -r "$kube_compose" ]] \
        || die 'missing readable ai-agent-sandbox/docker-compose.agent-vm-kubeconfig.yml'
fi

for variable_name in DOCKER_HOST DOCKER_CONTEXT TESTCONTAINERS_HOST_OVERRIDE; do
    [[ ! -v "$variable_name" ]] \
        || die "$variable_name must be unset for the guest-local Docker endpoint"
done
[[ -S /var/run/docker.sock ]] \
    || die 'the guest Docker socket is missing at /var/run/docker.sock'
[[ "$(docker context show)" == default ]] \
    || die 'the Docker context must be default'
[[ "$(docker context inspect default --format '{{.Endpoints.docker.Host}}')" \
    == unix:///var/run/docker.sock ]] \
    || die 'the default Docker context must use unix:///var/run/docker.sock'
[[ "$(docker info --format '{{.DockerRootDir}}')" == /var/lib/docker ]] \
    || die 'the Docker daemon data root must be /var/lib/docker'

read_env_value AGENT_VM_WORKTREES
worktrees=$REPLY
validate_absolute_directory AGENT_VM_WORKTREES "$worktrees"
read_env_value AGENT_VM_BARE
bare=$REPLY
validate_absolute_directory AGENT_VM_BARE "$bare"
[[ "$worktrees" != "$bare" ]] \
    || die 'working-clone and bare-repository parents must differ'

for key in AGENT_VM_USER_UID AGENT_VM_USER_GID AGENT_VM_DOCKER_GID; do
    read_env_value "$key"
    [[ "$REPLY" =~ ^[0-9]+$ ]] || die "$key must be numeric"
done

compose=(docker compose --env-file "$env_file" -f "$base_compose")
if [[ "$mode" == daily ]]; then
    read_env_value AGENT_VM_KUBECONFIG
    kubeconfig=$REPLY
    [[ "$kubeconfig" == /* ]] \
        || die 'AGENT_VM_KUBECONFIG must be an absolute path'
    [[ -f "$kubeconfig" && -r "$kubeconfig" && ! -L "$kubeconfig" ]] \
        || die 'AGENT_VM_KUBECONFIG must be a readable regular file, not a symlink'
    [[ "$(realpath -e -- "$kubeconfig")" == "$kubeconfig" ]] \
        || die 'AGENT_VM_KUBECONFIG must be an exact canonical path'
    compose+=(-f "$kube_compose")
fi

"${compose[@]}" config --quiet \
    || die 'the selected agent Compose configuration is invalid'
mapfile -t compose_services < <("${compose[@]}" config --services)
printf '%s\n' "${compose_services[@]}" | grep -Fxq agent \
    || die 'the selected Compose configuration has no agent service'

if [[ "$operation" != start ]]; then
    agent_id=$("${compose[@]}" ps -q --all agent)
    [[ -n "$agent_id" ]] || die 'the agent service has not been created'
fi

printf 'agent-vm-container: operation=%s mode=%s project=budget-analyzer-agent\n' \
    "$operation" "$mode"

case "$operation" in
    start)
        "${compose[@]}" up -d --no-build agent
        ;;
    stop)
        "${compose[@]}" stop agent
        ;;
    restart)
        "${compose[@]}" restart agent
        ;;
    status)
        "${compose[@]}" ps agent
        ;;
    shell)
        running_id=$("${compose[@]}" ps -q agent)
        [[ -n "$running_id" ]] || die 'the agent service is not running'
        "${compose[@]}" exec agent bash
        ;;
esac
