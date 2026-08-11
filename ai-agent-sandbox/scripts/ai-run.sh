#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  ai-run --help
  ai-run PLAN_NAME [RUN_OPTIONS...]

Run ./docs/plans/PLAN_NAME.md from the current repository with the sandbox's
globally installed high-reasoning Codex wrapper. PLAN_NAME must be a bare
filename stem without .md or path separators. Additional arguments are passed
unchanged to `ai-session-handler run`.

Examples:
  ai-run improve-imports
  ai-run improve-imports --max-phases 1
  ai-run improve-imports --retry-stopped

Set CODEX_MODEL to select a Codex model without changing the plan command.
EOF
}

if (($# == 0)); then
    printf 'ai-run: missing PLAN_NAME\n' >&2
    usage >&2
    exit 2
fi

case "$1" in
    --help|-h)
        if (($# != 1)); then
            printf 'ai-run: --help does not accept additional arguments\n' >&2
            usage >&2
            exit 2
        fi
        usage
        exit 0
        ;;
esac

plan_name="$1"
shift

case "$plan_name" in
    */*|*\\*)
        printf 'ai-run: PLAN_NAME must not contain path separators: %s\n' "$plan_name" >&2
        exit 2
        ;;
    *.md)
        printf 'ai-run: PLAN_NAME must omit the .md suffix; use: %s\n' "${plan_name%.md}" >&2
        exit 2
        ;;
    .|..|-*)
        printf 'ai-run: PLAN_NAME must be a bare filename stem: %s\n' "$plan_name" >&2
        exit 2
        ;;
esac

plan_path="$PWD/docs/plans/$plan_name.md"
if [[ ! -f "$plan_path" ]]; then
    printf 'ai-run: plan file not found: %s\n' "$plan_path" >&2
    exit 2
fi

exec ai-session-handler run \
    --plan "$plan_path" \
    --quiet \
    --agent-cmd "ai-session-handler-codex-high" \
    "$@"
