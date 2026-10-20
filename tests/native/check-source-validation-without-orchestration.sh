#!/usr/bin/env bash
# Runs the full source-validation suite from a copy of this checkout whose
# parent has no orchestration sibling, proving workspace validation never
# reads or requires an orchestration checkout.
set -euo pipefail

usage() {
  echo 'Usage: tests/native/check-source-validation-without-orchestration.sh [--publication proposed|committed]'
}

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
publication=proposed

while [[ $# -gt 0 ]]; do
  case "$1" in
    --publication)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      publication="$2"
      shift 2
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

mkdir -p "${repo}/tmp"
scratch="$(mktemp -d "${repo}/tmp/isolated-source-validation.XXXXXX")"
trap 'rm -rf -- "${scratch}"' EXIT
copy="${scratch}/workspace"
mkdir "${copy}"

# Copy the working tree with its Git metadata, excluding scratch output.
tar -C "${repo}" --exclude=./tmp -cf - . | tar -C "${copy}" -xf -

if [[ -e "${scratch}/orchestration" ]]; then
  echo 'Unexpected orchestration sibling next to the validation copy' >&2
  exit 1
fi

"${copy}/tests/native/run-source-validation.sh" --publication "${publication}"
printf 'Source validation without an orchestration sibling PASS (%s)\n' "${publication}"
