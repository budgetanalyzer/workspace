#!/usr/bin/env bash
# Human-only personal-host cold snapshot of the development VM.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: sudo scripts/snapshot-agent-vm.sh [--domain NAME] SNAPSHOT_ROOT

Run on the personal host only. Cleanly shuts the VM down, copies every disk
into a standalone QCOW2 image together with the domain XML, UEFI NVRAM and
virtual TPM state, writes SHA256SUMS into a new private directory
SNAPSHOT_ROOT/DOMAIN-TIMESTAMP and restarts the VM if it was running.
The default domain is budget-analyzer-agent.
EOF
}

domain=budget-analyzer-agent
snapshot_root=

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      domain="$2"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    -*)
      usage >&2
      exit 2
      ;;
    *)
      [[ -z "${snapshot_root}" ]] || { usage >&2; exit 2; }
      snapshot_root="$1"
      shift
      ;;
  esac
done

die() {
  echo "snapshot-agent-vm: $*" >&2
  exit 1
}

[[ -n "${snapshot_root}" ]] || { usage >&2; exit 2; }
[[ "${snapshot_root}" == /* && "${snapshot_root}" != / ]] \
  || die "SNAPSHOT_ROOT must be an absolute path other than /"
[[ -d "${snapshot_root}" ]] || die "SNAPSHOT_ROOT does not exist: ${snapshot_root}"

virsh_() {
  virsh --connect qemu:///system "$@"
}

state="$(virsh_ domstate "${domain}")"
case "${state}" in
  running) was_running=true ;;
  'shut off') was_running=false ;;
  *) die "domain ${domain} is '${state}'; expected running or shut off" ;;
esac

umask 077
snapshot_dir="${snapshot_root}/${domain}-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -m 0700 "${snapshot_dir}"

finish() {
  local status=$?
  if [[ "${was_running}" == true ]]; then
    virsh_ start "${domain}" >/dev/null || echo "WARNING: failed to restart ${domain}" >&2
  fi
  if [[ ${status} -eq 0 ]]; then
    echo "Snapshot complete: ${snapshot_dir}"
  else
    echo "Snapshot FAILED; ${snapshot_dir} is incomplete and must not be restored" >&2
  fi
}
trap finish EXIT

if [[ "${was_running}" == true ]]; then
  echo "Shutting down ${domain}"
  virsh_ shutdown "${domain}" >/dev/null
  for _ in $(seq 150); do
    [[ "$(virsh_ domstate "${domain}")" == 'shut off' ]] && break
    sleep 2
  done
  # Never force power-off: guest filesystems and Docker/Kind data must be clean.
  [[ "$(virsh_ domstate "${domain}")" == 'shut off' ]] \
    || die "${domain} did not shut down within 300 seconds; nothing was forced"
fi

virsh_ dumpxml --inactive "${domain}" >"${snapshot_dir}/domain.xml"

# Emits tab-separated "disk TARGET SOURCE", "nvram PATH" and "tpm DIR" lines.
plan="$(python3 -I - "${snapshot_dir}/domain.xml" <<'PY'
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
for disk in root.findall('./devices/disk'):
    if disk.get('device', 'disk') != 'disk':
        continue
    target = disk.find('target').get('dev')
    source = disk.find('source')
    path = None if source is None else source.get('file') or source.get('dev')
    if not path:
        sys.exit(f'disk {target} has no local file or block source')
    print('disk', target, path, sep='\t')
nvram = root.find('./os/nvram')
if nvram is not None:
    source = nvram.find('source')
    path = (nvram.text or '').strip() or (source.get('file') if source is not None else '')
    if not path:
        sys.exit('nvram is configured without a local file path')
    print('nvram', path, sep='\t')
for tpm in root.findall('./devices/tpm'):
    backend = tpm.find('backend')
    if backend is None or backend.get('type') != 'emulator':
        sys.exit('only emulated TPM state can be copied')
    source = backend.find('source')
    path = source.get('path') if source is not None else None
    print('tpm', path or f"/var/lib/libvirt/swtpm/{root.findtext('uuid')}", sep='\t')
PY
)"

images=()
while IFS=$'\t' read -r kind first second; do
  case "${kind}" in
    disk)
      echo "Copying disk ${first} from ${second}"
      qemu-img convert -p -O qcow2 "${second}" "${snapshot_dir}/${first}.qcow2"
      images+=("${snapshot_dir}/${first}.qcow2")
      ;;
    nvram)
      echo "Copying NVRAM ${first}"
      cp --archive --reflink=auto "${first}" "${snapshot_dir}/"
      ;;
    tpm)
      echo "Copying TPM state ${first}"
      [[ -d "${first}" ]] || die "TPM state directory not found: ${first}"
      cp --archive "${first}" "${snapshot_dir}/tpm"
      ;;
  esac
done <<<"${plan}"

[[ ${#images[@]} -gt 0 ]] || die "domain ${domain} has no disks"
for image in "${images[@]}"; do
  qemu-img check -q "${image}"
done

sums="$(cd "${snapshot_dir}" && find . -type f -print0 | sort -z | xargs -0 sha256sum)"
printf '%s\n' "${sums}" >"${snapshot_dir}/SHA256SUMS"
