# Development VM Snapshot Runbook

Creating a point-in-time copy of the native development VM is a human-only
personal-host operation. Agents inside the guest must not administer the host
or create host snapshots. Keep concrete host paths and snapshot inventories
outside this repository.

## Take A Snapshot

End agent sessions, then run this from the workspace checkout on the personal
host. The root must be a private, existing directory that the guest cannot
access, and it must have enough space:

```bash
sudo scripts/snapshot-agent-vm.sh /absolute/private/snapshot-root
```

The script reads every disk path from libvirt, so it works with disks on any
host partition. It:

1. shuts the VM down cleanly and waits for it to stop, without ever forcing a
   power-off;
2. writes `domain.xml`, a standalone `TARGET.qcow2` for each disk (flattening
   backing chains), the UEFI NVRAM file and emulated TPM state into a new
   `0700` directory named `DOMAIN-TIMESTAMP`;
3. runs `qemu-img check` on each image and writes `SHA256SUMS`;
4. restarts the VM if it was running, even when a step fails.

Use `--domain NAME` for a domain other than `budget-analyzer-agent`. The script
exits with an error and keeps the incomplete directory when a disk source is
not local or a step fails. Delete that directory; do not restore it.

The snapshot contains repositories, provider authentication and Docker data.
Treat it as private host material. A snapshot on the same partition as the VM
is only a rollback point; to protect against failure of that partition, copy it
to separate storage.

## Restore

Restoring is a deliberate human operation:

1. Run `sha256sum -c SHA256SUMS` in the snapshot directory.
2. Shut the domain down and keep its current disks before you replace anything.
3. Copy the images, NVRAM and `tpm/` state back to the paths in `domain.xml`,
   or point the domain at the restored files. Fix any access failure with the
   correct ownership, not broader permissions.
4. Start the VM and run the workspace's canonical read-only native runtime
   check.

A snapshot is rollback material for this existing environment. It does not
replace the clean-environment recovery path, which builds a fresh VM.
