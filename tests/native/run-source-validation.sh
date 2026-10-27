#!/usr/bin/env bash
# Single source-validation command list shared by CI and local runs.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: tests/native/run-source-validation.sh [--publication proposed|committed]
                                             [--list | --check NAME]

Runs the workspace source-validation checks from this checkout. Without
--check, every check runs and the command exits 1 if any check failed.
--publication selects check_install_inputs.py mode (default: proposed).
EOF
}

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
publication=proposed
selected=
list=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --publication)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      publication="$2"
      shift 2
      ;;
    --check)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      selected="$2"
      shift 2
      ;;
    --list)
      list=true
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

case "${publication}" in
  proposed | committed) ;;
  *) usage >&2; exit 2 ;;
esac

checks=(
  renovate-config
  native-unit-tests
  native-manifest
  "${publication}-install-inputs"
  static-user-environment
  claude-settings
  lean-launchers
  statusline
  bash-syntax
  shellcheck
  python-syntax
)

if [[ "${list}" == true ]]; then
  printf '%s\n' "${checks[@]}"
  exit 0
fi

cd "${repo}"
python_env=(env PYTHONPYCACHEPREFIX=tmp/pycache python3)

renovate_version() {
  if [[ -n "${RENOVATE_VERSION:-}" ]]; then
    printf '%s\n' "${RENOVATE_VERSION}"
    return
  fi
  sed -n "s/^  RENOVATE_VERSION: '\\([^']*\\)'$/\\1/p" \
    .github/workflows/native-dependency-validation.yml
}

run_check() {
  case "$1" in
    renovate-config)
      local version
      version="$(renovate_version)"
      [[ -n "${version}" ]] || { echo 'Renovate version not found' >&2; return 1; }
      npx --yes --package="renovate@${version}" \
        renovate-config-validator --strict --no-global renovate.json
      ;;
    native-unit-tests)
      "${python_env[@]}" -m unittest discover -s tests/native -v
      ;;
    native-manifest)
      "${python_env[@]}" tests/native/check_manifest.py
      ;;
    "${publication}-install-inputs")
      "${python_env[@]}" tests/native/check_install_inputs.py --publication "${publication}"
      ;;
    static-user-environment)
      "${python_env[@]}" tests/native/check_user_environment.py
      ;;
    claude-settings)
      "${python_env[@]}" tests/native/check_claude_settings.py
      ;;
    lean-launchers)
      "${python_env[@]}" tests/native/check_lean_launchers.py
      ;;
    statusline)
      "${python_env[@]}" tests/native/check_statusline.py
      ;;
    bash-syntax)
      bash -n \
        scripts/provision-agent-vm-guest.sh \
        scripts/install-agent-vm-user-tools.sh \
        scripts/check-agent-vm-boundary.sh \
        scripts/check-agent-vm-tools.sh \
        scripts/install-agent-vm-local-ca-trust.sh \
        scripts/install-agent-vm-bwrap-profile.sh \
        scripts/prepare-agent-vm-native.sh \
        scripts/snapshot-agent-vm.sh \
        tests/native/run-source-validation.sh \
        tests/native/check-source-validation-without-orchestration.sh
      ;;
    shellcheck)
      shellcheck \
        scripts/provision-agent-vm-guest.sh \
        scripts/install-agent-vm-user-tools.sh \
        scripts/check-agent-vm-boundary.sh \
        scripts/check-agent-vm-tools.sh \
        scripts/install-agent-vm-local-ca-trust.sh \
        scripts/install-agent-vm-bwrap-profile.sh \
        scripts/prepare-agent-vm-native.sh \
        scripts/snapshot-agent-vm.sh \
        tests/native/run-source-validation.sh \
        tests/native/check-source-validation-without-orchestration.sh \
        native/helpers/ai-run.sh \
        native/helpers/bash_aliases.sh \
        native/helpers/claude-lean.sh \
        native/helpers/codex-lean.sh \
        native/helpers/statusline-command.sh \
        native/helpers/via-annotator.sh \
        native/helpers/mitmflows \
        native/helpers/mitmflow-detail \
        native/helpers/mitmflow-body
      ;;
    python-syntax)
      "${python_env[@]}" -m py_compile \
        scripts/native/boundary.py \
        scripts/native/provision.py \
        scripts/native/user_tools.py \
        scripts/native/local_ca.py \
        scripts/native/proxy.py \
        scripts/native/bwrap_profile.py \
        scripts/native/verify_release_inputs.py \
        scripts/native/claude_settings.py \
        tests/native/test_boundary.py \
        tests/native/test_provision.py \
        tests/native/test_user_tools.py \
        tests/native/test_local_ca.py \
        tests/native/test_native_preparation.py \
        tests/native/test_install_inputs.py \
        tests/native/test_dependency_discovery.py \
        tests/native/test_release_inputs.py \
        tests/native/test_vm_snapshot.py \
        tests/native/check_manifest.py \
        tests/native/check_install_inputs.py \
        tests/native/check_user_environment.py \
        tests/native/check_claude_settings.py \
        tests/native/check_lean_launchers.py \
        tests/native/check_statusline.py \
        native/helpers/mitmflow-render.py
      ;;
    *)
      echo "Unknown check: $1" >&2
      return 2
      ;;
  esac
}

if [[ -n "${selected}" ]]; then
  run_check "${selected}"
  exit $?
fi

failed=()
for name in "${checks[@]}"; do
  if run_check "${name}"; then
    printf 'PASS %s\n' "${name}"
  else
    printf 'FAIL %s\n' "${name}" >&2
    failed+=("${name}")
  fi
done

if [[ ${#failed[@]} -gt 0 ]]; then
  printf 'Source validation FAILED: %s\n' "${failed[*]}" >&2
  exit 1
fi
printf 'Source validation PASS: %d checks (publication %s) in %s\n' \
  "${#checks[@]}" "${publication}" "${repo}"
