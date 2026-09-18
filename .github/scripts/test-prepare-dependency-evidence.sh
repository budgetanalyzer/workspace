#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
helper="${script_dir}/prepare-dependency-evidence.sh"
payload_cap_bytes=25165824
test_root="$(mktemp -d)"
trap 'rm -rf "${test_root}"' EXIT

output_value() {
  local output_file="$1"
  local key="$2"

  awk -F= -v key="${key}" '$1 == key { value = $2 } END { if (value == "") exit 1; print value }' \
    "${output_file}"
}

compressible_case="${test_root}/compressible"
mkdir -p "${compressible_case}/workspace-image-scan"
truncate -s "$((payload_cap_bytes + 1048576))" \
  "${compressible_case}/workspace-image-scan/complete-evidence.bin"
compressible_digest="$(sha256sum "${compressible_case}/workspace-image-scan/complete-evidence.bin" | cut -d' ' -f1)"
(
  cd "${compressible_case}"
  GITHUB_OUTPUT=outputs.txt \
    GITHUB_STEP_SUMMARY=summary.md \
    bash "${helper}" evidence/archive.tar.gz 'Compressible evidence' workspace-image-scan
)

compressible_tar_bytes="$(output_value "${compressible_case}/outputs.txt" uncompressed_bytes)"
compressible_gzip_bytes="$(output_value "${compressible_case}/outputs.txt" compressed_bytes)"
[[ "${compressible_tar_bytes}" -gt "${payload_cap_bytes}" ]]
[[ "${compressible_gzip_bytes}" -le "${payload_cap_bytes}" ]]
[[ "$(output_value "${compressible_case}/outputs.txt" upload_allowed)" == true ]]
mkdir "${compressible_case}/extracted"
tar --extract --gzip --file "${compressible_case}/evidence/archive.tar.gz" \
  --directory "${compressible_case}/extracted"
extracted_digest="$(sha256sum "${compressible_case}/extracted/workspace-image-scan/complete-evidence.bin" | cut -d' ' -f1)"
[[ "${extracted_digest}" == "${compressible_digest}" ]]

overflow_case="${test_root}/overflow"
mkdir -p "${overflow_case}/workspace-image-scan"
head -c "$((payload_cap_bytes + 1048576))" /dev/urandom \
  > "${overflow_case}/workspace-image-scan/complete-evidence.bin"
if (
  cd "${overflow_case}"
  GITHUB_OUTPUT=outputs.txt \
    GITHUB_STEP_SUMMARY=summary.md \
    bash "${helper}" evidence/archive.tar.gz 'Overflow evidence' workspace-image-scan
); then
  echo 'Expected an oversized compressed payload to fail.' >&2
  exit 1
fi

overflow_gzip_bytes="$(output_value "${overflow_case}/outputs.txt" compressed_bytes)"
[[ "${overflow_gzip_bytes}" -gt "${payload_cap_bytes}" ]]
[[ "$(output_value "${overflow_case}/outputs.txt" upload_allowed)" == false ]]

missing_case="${test_root}/missing"
mkdir -p "${missing_case}"
if (
  cd "${missing_case}"
  bash "${helper}" evidence/archive.tar.gz 'Missing evidence' workspace-image-scan
); then
  echo 'Expected a missing allowlisted input to fail.' >&2
  exit 1
fi

traversal_case="${test_root}/traversal"
mkdir -p "${traversal_case}"
if (
  cd "${traversal_case}"
  bash "${helper}" evidence/archive.tar.gz 'Traversal evidence' ../workspace-image-scan
); then
  echo 'Expected an input traversal path to fail.' >&2
  exit 1
fi

echo 'prepare-dependency-evidence tests passed'
