#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage:
  setup-agent-vm-repositories.sh \
    --host-parent PATH --ssh-host HOST_ALIAS --guest-root ABSOLUTE_PATH
  setup-agent-vm-repositories.sh \
    --repository PATH --ssh-host HOST_ALIAS --guest-root ABSOLUTE_PATH

Discover every immediate child Git repository under a host parent, or select
one repository explicitly. Create matching bare repositories and working clones
under ABSOLUTE_PATH in the guest, add a `vm` remote to each host repository,
and seed `main` plus the checked-out branch.

The command is a one-time, interactive host operation. It preserves normal SSH
host-key verification, disables agent forwarding, and never contacts GitHub
from the guest. There is deliberately no non-interactive confirmation option.
EOF
}

die() {
    printf 'setup-agent-vm-repositories: %s\n' "$*" >&2
    exit 1
}

host_parent=''
repository=''
ssh_host=''
guest_root=''

while (($#)); do
    case "$1" in
        --host-parent|--repository|--ssh-host|--guest-root)
            (($# >= 2)) || die "$1 requires a value"
            case "$1" in
                --host-parent) host_parent=$2 ;;
                --repository) repository=$2 ;;
                --ssh-host) ssh_host=$2 ;;
                --guest-root) guest_root=$2 ;;
            esac
            shift 2
            ;;
        --help|-h)
            (($# == 1)) || die '--help does not accept other arguments'
            usage
            exit 0
            ;;
        *)
            die "unknown argument: $1"
            ;;
    esac
done

[[ -n "$host_parent" || -n "$repository" ]] \
    || die 'exactly one of --host-parent or --repository is required'
[[ -z "$host_parent" || -z "$repository" ]] \
    || die '--host-parent and --repository are mutually exclusive'
[[ -n "$ssh_host" ]] || die '--ssh-host is required'
[[ -n "$guest_root" ]] || die '--guest-root is required'
[[ "$ssh_host" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] \
    || die '--ssh-host must be a safe SSH alias'
[[ "$guest_root" =~ ^/[A-Za-z0-9._/-]+$ ]] \
    || die '--guest-root must be an absolute path with safe characters'
[[ "$guest_root" != / ]] || die '--guest-root must not be the filesystem root'
[[ "$guest_root" != *'//' && "$guest_root" != */../* && "$guest_root" != */.. \
    && "$guest_root" != *'/./'* && "$guest_root" != */. ]] \
    || die '--guest-root must already be normalized'

command -v git >/dev/null || die 'git is required'
command -v realpath >/dev/null || die 'realpath is required'
command -v ssh >/dev/null || die 'ssh is required'

declare -a candidates=()
if [[ -n "$host_parent" ]]; then
    host_parent=$(realpath -e -- "$host_parent") \
        || die 'could not resolve --host-parent'
    [[ -d "$host_parent" ]] || die "host parent is not a directory: $host_parent"
    for candidate in "$host_parent"/*; do
        [[ -d "$candidate" ]] || continue
        candidates+=("$candidate")
    done
    github_candidate="$host_parent/.github"
    if [[ -d "$github_candidate" ]]; then
        candidates+=("$github_candidate")
    fi
else
    [[ ! -L "$repository" ]] \
        || die "repository path must not be a symbolic link: $repository"
    repository=$(realpath -e -- "$repository") \
        || die 'could not resolve --repository'
    [[ -d "$repository" ]] || die "host repository is not a directory: $repository"
    candidates+=("$repository")
fi

declare -a repo_paths=()
declare -a repo_names=()
declare -a repo_branches=()
declare -a repo_main_oids=()
declare -a repo_branch_oids=()
declare -A seen_names=()

for candidate in "${candidates[@]}"; do
    top=$(git -C "$candidate" rev-parse --show-toplevel 2>/dev/null) || continue
    [[ ! -L "$candidate" ]] \
        || die "repository path must not be a symbolic link: $candidate"
    top=$(realpath -e -- "$top") || die "could not resolve repository path: $candidate"
    candidate=$(realpath -e -- "$candidate") || die "could not resolve selected path: $candidate"
    if [[ -n "$host_parent" ]]; then
        [[ "$top" == "$candidate" ]] || continue
        [[ "$(dirname -- "$candidate")" == "$host_parent" ]] \
            || die "repository resolves outside the selected parent: $candidate"
    else
        [[ "$top" == "$candidate" ]] \
            || die "selected path is not a Git repository root: $candidate"
    fi

    name=$(basename -- "$candidate")
    [[ "$name" == .github || "$name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] \
        || die "unsupported repository basename: $name"
    [[ -z "${seen_names[$name]:-}" ]] || die "duplicate repository basename: $name"
    seen_names[$name]=1

    [[ -z "$(git -C "$candidate" status --porcelain=v1 --untracked-files=all)" ]] \
        || die "host repository is not clean: $name"
    branch=$(git -C "$candidate" symbolic-ref --quiet --short HEAD) \
        || die "host repository has detached HEAD: $name"
    [[ "$branch" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ ]] \
        || die "unsupported selected branch name in $name: $branch"
    git -C "$candidate" show-ref --verify --quiet refs/heads/main \
        || die "host repository has no local main branch: $name"

    for marker in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD; do
        [[ ! -e "$(git -C "$candidate" rev-parse --git-path "$marker")" ]] \
            || die "host repository has an operation in progress: $name"
    done
    for marker in rebase-merge rebase-apply; do
        [[ ! -d "$(git -C "$candidate" rev-parse --git-path "$marker")" ]] \
            || die "host repository has a rebase in progress: $name"
    done

    expected_url="$ssh_host:$guest_root/bare/$name.git"
    if git -C "$candidate" remote get-url vm >/dev/null 2>&1; then
        mapfile -t fetch_urls < <(git -C "$candidate" remote get-url --all vm)
        mapfile -t push_urls < <(git -C "$candidate" remote get-url --push --all vm)
        ((${#fetch_urls[@]} == 1 && ${#push_urls[@]} == 1)) \
            || die "existing vm remote has multiple URLs: $name"
        [[ "${fetch_urls[0]}" == "$expected_url" && "${push_urls[0]}" == "$expected_url" ]] \
            || die "existing vm remote points somewhere else: $name"
    fi

    repo_paths+=("$candidate")
    repo_names+=("$name")
    repo_branches+=("$branch")
    repo_main_oids+=("$(git -C "$candidate" rev-parse refs/heads/main)")
    repo_branch_oids+=("$(git -C "$candidate" rev-parse "refs/heads/$branch")")
done

((${#repo_paths[@]} > 0)) || {
    if [[ -n "$host_parent" ]]; then
        die "no immediate child Git repositories found under $host_parent"
    fi
    die "selected path is not a Git repository: $repository"
}

if [[ -n "$host_parent" ]]; then
    printf 'Resolved host parent: %s\n' "$host_parent"
else
    printf 'Resolved repository:  %s\n' "$repository"
fi
printf 'SSH host alias:      %s\n' "$ssh_host"
printf 'Guest root:          %s\n' "$guest_root"
printf 'Guest bare parent:   %s/bare\n' "$guest_root"
printf 'Guest clone parent:  %s/worktrees\n' "$guest_root"
printf 'Repositories (%d):\n' "${#repo_names[@]}"
for i in "${!repo_names[@]}"; do
    printf '  %s (main; selected branch: %s)\n' "${repo_names[$i]}" "${repo_branches[$i]}"
done
printf 'Type yes to create this exact setup: '
IFS= read -r confirmation
[[ "$confirmation" == yes ]] || die 'confirmation declined; nothing changed'

ssh_options=(-o ForwardAgent=no)

ssh "${ssh_options[@]}" "$ssh_host" sh -s -- "$guest_root" <<'REMOTE'
set -eu
root=$1
[ -d "$root" ] || {
    printf 'guest root is missing: %s\n' "$root" >&2
    exit 1
}
[ "$(realpath -e "$root")" = "$root" ] || {
    printf 'guest root is unresolved or not canonical: %s\n' "$root" >&2
    exit 1
}
[ -w "$root" ] || {
    printf 'guest root is not writable: %s\n' "$root" >&2
    exit 1
}
for parent in "$root/bare" "$root/worktrees"; do
    [ ! -L "$parent" ] || {
        printf 'guest repository parent must not be a symbolic link: %s\n' "$parent" >&2
        exit 1
    }
    if [ -e "$parent" ]; then
        [ -d "$parent" ] && [ "$(realpath -e "$parent")" = "$parent" ] || {
            printf 'guest repository parent is unresolved or non-canonical: %s\n' "$parent" >&2
            exit 1
        }
    fi
done
REMOTE

# Validate every guest destination before changing either the guest or host.
for i in "${!repo_names[@]}"; do
    name=${repo_names[$i]}
    branch=${repo_branches[$i]}
    main_oid=${repo_main_oids[$i]}
    branch_oid=${repo_branch_oids[$i]}
    ssh "${ssh_options[@]}" "$ssh_host" sh -s -- \
        "$guest_root" "$name" "$branch" "$main_oid" "$branch_oid" <<'REMOTE'
set -eu
root=$1
name=$2
branch=$3
main_oid=$4
branch_oid=$5
bare="$root/bare/$name.git"
worktree="$root/worktrees/$name"

check_ref() {
    ref=$1
    expected=$2
    if git --git-dir="$bare" show-ref --verify --quiet "$ref"; then
        actual=$(git --git-dir="$bare" rev-parse "$ref")
        [ "$actual" = "$expected" ] || {
            printf 'guest bare repository has mismatched %s: %s\n' "$ref" "$name" >&2
            exit 1
        }
    fi
}

[ ! -L "$bare" ] || {
    printf 'guest bare destination must not be a symbolic link: %s\n' "$bare" >&2
    exit 1
}
if [ -e "$bare" ]; then
    [ "$(realpath -e "$bare")" = "$bare" ] || {
        printf 'guest bare destination is unresolved or non-canonical: %s\n' "$bare" >&2
        exit 1
    }
    if [ -d "$bare" ] && [ -z "$(find "$bare" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
        :
    elif ! git --git-dir="$bare" rev-parse --is-bare-repository 2>/dev/null | grep -qx true; then
        printf 'guest bare destination is non-empty or invalid: %s\n' "$bare" >&2
        exit 1
    else
        for ref in $(git --git-dir="$bare" for-each-ref --format='%(refname)'); do
            case "$ref" in
                refs/heads/main|"refs/heads/$branch") ;;
                *)
                    printf 'guest bare repository has an unexpected ref %s: %s\n' "$ref" "$name" >&2
                    exit 1
                    ;;
            esac
        done
        check_ref refs/heads/main "$main_oid"
        check_ref "refs/heads/$branch" "$branch_oid"
    fi
fi

[ ! -L "$worktree" ] || {
    printf 'guest working destination must not be a symbolic link: %s\n' "$worktree" >&2
    exit 1
}
if [ -e "$worktree" ]; then
    [ "$(realpath -e "$worktree")" = "$worktree" ] || {
        printf 'guest working destination is unresolved or non-canonical: %s\n' "$worktree" >&2
        exit 1
    }
    if [ -d "$worktree" ] && [ -z "$(find "$worktree" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
        :
    elif ! top=$(git -C "$worktree" rev-parse --show-toplevel 2>/dev/null) \
        || [ "$(realpath -e "$top")" != "$(realpath -e "$worktree")" ]; then
        printf 'guest working destination is non-empty or invalid: %s\n' "$worktree" >&2
        exit 1
    else
        [ -z "$(git -C "$worktree" status --porcelain=v1 --untracked-files=all)" ] || {
            printf 'guest working clone is not clean: %s\n' "$name" >&2
            exit 1
        }
        git -C "$worktree" symbolic-ref --quiet HEAD >/dev/null || {
            printf 'guest working clone has detached HEAD: %s\n' "$name" >&2
            exit 1
        }
        remotes=$(git -C "$worktree" remote)
        [ "$remotes" = origin ] || {
            printf 'guest working clone must have only origin: %s\n' "$name" >&2
            exit 1
        }
        [ "$(git -C "$worktree" remote get-url origin)" = "$bare" ] || {
            printf 'guest working clone origin mismatch: %s\n' "$name" >&2
            exit 1
        }
        if git -C "$worktree" show-ref --verify --quiet refs/heads/main; then
            [ "$(git -C "$worktree" rev-parse refs/heads/main)" = "$main_oid" ] || {
                printf 'guest working clone has mismatched main: %s\n' "$name" >&2
                exit 1
            }
        fi
        if git -C "$worktree" show-ref --verify --quiet "refs/heads/$branch"; then
            [ "$(git -C "$worktree" rev-parse "refs/heads/$branch")" = "$branch_oid" ] || {
                printf 'guest working clone has mismatched selected branch: %s\n' "$name" >&2
                exit 1
            }
        fi
    fi
fi
REMOTE
done

declare -a added_remotes=()
declare -a created_names=()
completed=false

cleanup() {
    status=$?
    if [[ "$completed" == true || $status -eq 0 ]]; then
        return
    fi
    printf 'Setup failed; cleaning artifacts created by this invocation.\n' >&2
    for path in "${added_remotes[@]}"; do
        git -C "$path" remote remove vm >/dev/null 2>&1 || true
    done
    if ((${#created_names[@]})); then
        ssh "${ssh_options[@]}" "$ssh_host" sh -s -- "$guest_root" "${created_names[@]}" <<'REMOTE' || true
set -eu
root=$1
shift
for name in "$@"; do
    bare="$root/bare/$name.git"
    worktree="$root/worktrees/$name"
    if [ -f "$worktree/.git/agent-vm-setup-created" ]; then
        rm -rf -- "$worktree"
    fi
    if [ -f "$bare/agent-vm-setup-created" ]; then
        rm -rf -- "$bare"
    fi
done
REMOTE
    fi
    return "$status"
}
trap cleanup EXIT

for i in "${!repo_names[@]}"; do
    name=${repo_names[$i]}
    ssh "${ssh_options[@]}" "$ssh_host" sh -s -- "$guest_root" "$name" <<'REMOTE'
set -eu
root=$1
name=$2
bare="$root/bare/$name.git"
mkdir -p -- "$root/bare" "$root/worktrees"
if [ ! -e "$bare" ]; then
    git init --bare --initial-branch=main "$bare" >/dev/null
    : >"$bare/agent-vm-setup-created"
elif [ -d "$bare" ] && [ -z "$(find "$bare" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
    git init --bare --initial-branch=main "$bare" >/dev/null
fi
REMOTE
    created_names+=("$name")

    if ! git -C "${repo_paths[$i]}" remote get-url vm >/dev/null 2>&1; then
        git -C "${repo_paths[$i]}" remote add vm \
            "$ssh_host:$guest_root/bare/$name.git"
        added_remotes+=("${repo_paths[$i]}")
    fi

    GIT_SSH_COMMAND='ssh -o ForwardAgent=no' \
        git -C "${repo_paths[$i]}" push vm refs/heads/main:refs/heads/main
    if [[ "${repo_branches[$i]}" != main ]]; then
        GIT_SSH_COMMAND='ssh -o ForwardAgent=no' \
            git -C "${repo_paths[$i]}" push vm \
                "refs/heads/${repo_branches[$i]}:refs/heads/${repo_branches[$i]}"
    fi

    ssh "${ssh_options[@]}" "$ssh_host" sh -s -- \
        "$guest_root" "$name" "${repo_branches[$i]}" <<'REMOTE'
set -eu
root=$1
name=$2
branch=$3
bare="$root/bare/$name.git"
worktree="$root/worktrees/$name"

git --git-dir="$bare" symbolic-ref HEAD refs/heads/main
if [ ! -e "$worktree" ]; then
    git clone "$bare" "$worktree" >/dev/null
    : >"$worktree/.git/agent-vm-setup-created"
elif [ -d "$worktree" ] && [ -z "$(find "$worktree" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
    git clone "$bare" "$worktree" >/dev/null
fi

git -C "$worktree" fetch --prune origin
if git -C "$worktree" show-ref --verify --quiet "refs/heads/$branch"; then
    git -C "$worktree" switch "$branch" >/dev/null
    git -C "$worktree" merge --ff-only "origin/$branch" >/dev/null
else
    git -C "$worktree" switch --track -c "$branch" "origin/$branch" >/dev/null
fi
[ -z "$(git -C "$worktree" status --porcelain=v1 --untracked-files=all)" ]
REMOTE
done

for name in "${repo_names[@]}"; do
    ssh "${ssh_options[@]}" "$ssh_host" sh -s -- "$guest_root" "$name" <<'REMOTE'
set -eu
root=$1
name=$2
rm -f -- \
    "$root/bare/$name.git/agent-vm-setup-created" \
    "$root/worktrees/$name/.git/agent-vm-setup-created"
REMOTE
done

completed=true
printf 'Repository setup complete for %d repositories.\n' "${#repo_names[@]}"
printf 'The guest working clones use only guest-local origins under %s/worktrees.\n' "$guest_root"
