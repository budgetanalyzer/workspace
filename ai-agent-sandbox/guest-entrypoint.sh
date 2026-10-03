#!/usr/bin/env bash
set -Eeuo pipefail

die() {
    printf 'guest-entrypoint: %s\n' "$*" >&2
    exit 1
}

worktree_parent=${BUDGET_ANALYZER_WORKTREE_PARENT:-}
bare_parent=${BUDGET_ANALYZER_BARE_PARENT:-}
[[ "$worktree_parent" == /* && "$bare_parent" == /* ]] \
    || die 'configured working and bare repository parents must be absolute paths'
[[ -d "$worktree_parent" ]] || die "working-clone parent is missing: $worktree_parent"
[[ -d "$bare_parent" ]] || die "bare-repository parent is missing: $bare_parent"
[[ -S /var/run/docker.sock ]] || die 'guest Docker socket is missing at /var/run/docker.sock'
command -v docker >/dev/null || die 'Docker CLI is missing from the shared tool image'
command -v jq >/dev/null || die 'jq is missing from the shared tool image'
[[ -z "${DOCKER_HOST:-}" ]] || die 'DOCKER_HOST must remain unset for local socket discovery'
[[ -z "${DOCKER_CONTEXT:-}" ]] || die 'DOCKER_CONTEXT must remain unset for local socket discovery'
[[ -z "${TESTCONTAINERS_HOST_OVERRIDE:-}" ]] \
    || die 'TESTCONTAINERS_HOST_OVERRIDE must remain unset for endpoint discovery'
[[ -z "${SSH_AUTH_SOCK:-}" ]] || die 'SSH agent forwarding is disabled in the guest runtime'
[[ -z "${GITHUB_TOKEN:-}${GH_TOKEN:-}${GIT_ASKPASS:-}${SSH_ASKPASS:-}" ]] \
    || die 'GitHub token and askpass variables are disabled in the guest runtime'
[[ -z "$(git config --global --get-all credential.helper 2>/dev/null || true)" ]] \
    || die 'global Git credential helpers are disabled in the guest runtime'
# Do not expose even empty forwarding variables to the agent process.
unset SSH_AUTH_SOCK GITHUB_TOKEN GH_TOKEN GIT_ASKPASS SSH_ASKPASS
[[ "$(docker context show)" == default ]] || die 'Docker context must be default'
[[ "$(docker info --format '{{.DockerRootDir}}')" == /var/lib/docker ]] \
    || die 'mounted Docker socket is not the guest daemon with /var/lib/docker data root'

if [[ -n "${KUBECONFIG:-}" ]]; then
    [[ -f "$KUBECONFIG" && -r "$KUBECONFIG" ]] \
        || die "configured kubeconfig is not a readable file: $KUBECONFIG"
    [[ "$(kubectl config current-context)" == kind-kind ]] \
        || die 'mounted kubeconfig current context is not kind-kind'
    kube_cluster=$(kubectl config view --minify -o jsonpath='{.clusters[0].name}')
    kube_server=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')
    [[ "$kube_cluster" == kind-kind ]] \
        || die 'mounted kubeconfig does not reference cluster kind-kind'
    [[ "$kube_server" =~ ^https://(127\.0\.0\.1|localhost|\[::1\]):[0-9]+$ ]] \
        || die 'mounted kubeconfig API server is not guest loopback HTTPS'
fi

printf '%s\n' '--- Guest-local Budget Analyzer repositories ---'
repo_count=0
shopt -s nullglob
for repo_path in "$worktree_parent"/*; do
    [[ -d "$repo_path" ]] || continue
    top=$(git -C "$repo_path" rev-parse --show-toplevel 2>/dev/null) || continue
    [[ "$(realpath -e "$top")" == "$(realpath -e "$repo_path")" ]] || continue
    name=$(basename -- "$repo_path")
    expected_origin="$bare_parent/$name.git"
    origin=$(git -C "$repo_path" remote get-url origin 2>/dev/null) \
        || die "$name has no origin; rerun the reviewed host setup after inspecting it"
    [[ "$origin" == "$expected_origin" ]] \
        || die "$name origin is not the matching guest-local bare repository"
    [[ "$(git -C "$repo_path" remote)" == origin ]] \
        || die "$name has remotes other than its guest-local origin"
    printf '  %s (%s)\n' "$name" "$(git -C "$repo_path" branch --show-current)"
    repo_count=$((repo_count + 1))
done

if ((repo_count == 0)); then
    printf 'No guest working clones were found under %s.\n' "$worktree_parent" >&2
    printf 'Run the reviewed host-side repository setup; startup will not clone from GitHub.\n' >&2
fi

workspace_sandbox="$worktree_parent/workspace/ai-agent-sandbox"
ai_session_handler_dir="$worktree_parent/ai-session-handler"
if [[ -f "$ai_session_handler_dir/pyproject.toml" ]]; then
    command -v pipx >/dev/null || die 'pipx is required to install AI Session Handler'
    pipx install --force --editable "$ai_session_handler_dir"
    command -v ai-session-handler >/dev/null \
        || die 'ai-session-handler is unavailable after installation'
    command -v ai-session-handler-codex-high >/dev/null \
        || die 'ai-session-handler-codex-high is unavailable after installation'
    printf 'AI Session Handler installed editably from %s.\n' "$ai_session_handler_dir"
else
    printf 'AI Session Handler repository is missing at %s.\n' "$ai_session_handler_dir" >&2
fi

if [[ -d "$workspace_sandbox/skills" ]]; then
    mkdir -p /home/vscode/.claude/skills
    cp -R "$workspace_sandbox/skills/." /home/vscode/.claude/skills/
fi

settings_overlay="$workspace_sandbox/settings-overlay.json"
settings_file=/home/vscode/.claude/settings.json
if [[ -f "$settings_overlay" ]]; then
    mkdir -p "$(dirname "$settings_file")"
    if [[ -f "$settings_file" ]]; then
        settings_tmp=$(mktemp)
        jq -s '.[0] * .[1]' "$settings_file" "$settings_overlay" >"$settings_tmp"
        mv "$settings_tmp" "$settings_file"
    else
        cp "$settings_overlay" "$settings_file"
    fi
fi

printf '\nGuest AI Coding Sandbox\n'
printf 'Working clones: %s\n' "$worktree_parent"
printf 'Bare origins:   %s\n' "$bare_parent"
printf 'Docker:         guest /var/run/docker.sock (full guest administration)\n'
if [[ -r "${KUBECONFIG:-}" ]]; then
    printf 'Kubernetes:     %s\n' "$KUBECONFIG"
else
    printf 'Kubernetes:     not mounted; recreate with the kubeconfig override after bootstrap\n'
fi
printf 'Authentication: use only the selected AI provider; do not log in to GitHub\n\n'

exec "$@"
