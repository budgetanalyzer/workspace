# Development VM Snapshot Runbook

Use this runbook to create a recoverable point-in-time copy of the native
development VM. This is a human-only personal-host operation. Agents running
inside the guest must not administer the host or create host snapshots.

The VM disk may live anywhere selected by the operator. Always discover its
source from libvirt; do not assume `/var/lib/libvirt/images`. Keep concrete
host paths, storage topology and snapshot inventories outside this repository.

## Snapshot Choice

Prefer a cold snapshot: stop the VM cleanly, then create either a native
snapshot of its host storage or a standalone QCOW2 copy. A cold snapshot avoids
guest-filesystem and Docker/Kind consistency problems and does not create an
active libvirt overlay chain.

- A Btrfs, ZFS or thin-LVM snapshot is the fastest option when the VM storage
  already uses that technology. Follow the host storage's reviewed procedure
  while the VM is shut off.
- `qemu-img convert` is the portable fallback. It can read a raw or QCOW2
  source and flatten a QCOW2 backing chain into one standalone QCOW2 image.
- A snapshot on the same data partition is only a rollback point. Keep a copy
  on separate storage when recovery from failure of that partition matters.
- Avoid libvirt internal snapshots as the primary backup. They depend on image
  format and firmware support, are not independent of the source disk, and can
  make later merging or recovery more complicated.

Every snapshot contains the guest repositories, provider authentication,
Docker data and other sensitive state. Store it as private host material with
access no broader than the VM itself.

## Preconditions

1. End agent sessions and stop or settle application work that must be
   consistent in the snapshot.
2. Choose a private snapshot root with enough capacity. Do not place it in a
   guest-accessible directory or in this repository.
3. Run every command in this document on the personal host. The accepted
   system-libvirt domain is `budget-analyzer-agent`.

Set an explicit destination and create a new directory. Replace the example
snapshot root with the reviewed absolute host path:

```bash
vm_domain=budget-analyzer-agent
snapshot_root=/absolute/private/host/snapshot-root
snapshot_id=$(date -u +%Y%m%dT%H%M%SZ)
snapshot_dir="${snapshot_root}/${vm_domain}-${snapshot_id}"

test "$snapshot_root" != /
sudo install -d -m 0700 "$snapshot_dir"
```

## Discover And Stop The VM

Record all configured disks before shutdown. The `Source` column is
authoritative even when an image is on a nonstandard data partition:

```bash
sudo virsh --connect qemu:///system domblklist \
  "$vm_domain" --inactive --details \
  | sudo tee "$snapshot_dir/block-devices.txt"

sudo virsh --connect qemu:///system domstate "$vm_domain"
sudo virsh --connect qemu:///system shutdown "$vm_domain"
```

Repeat the `domstate` command until it reports `shut off`:

```bash
sudo virsh --connect qemu:///system domstate "$vm_domain"
```

Do not use `virsh destroy` for an ordinary snapshot. It is equivalent to
removing power and can leave guest filesystems and application data
inconsistent.

After shutdown, capture the persistent domain definition:

```bash
sudo virsh --connect qemu:///system dumpxml \
  "$vm_domain" --inactive \
  | sudo tee "$snapshot_dir/domain.xml" >/dev/null
```

## Copy Every Disk

For each disk listed by `domblklist`, inspect its source and backing chain. Stop
if the source is missing or `qemu-img` cannot read it:

```bash
sudo qemu-img info --backing-chain /exact/source/path
```

Create one standalone image per disk. Use the libvirt target name, such as
`vda`, in the destination filename:

```bash
sudo qemu-img convert -p -O qcow2 \
  /exact/source/path \
  "$snapshot_dir/vda.qcow2"
```

Repeat this operation for `vdb` and any other writable storage disks. Read-only
installation media need not be copied when the exact source is independently
available and recorded.

When using a host-storage snapshot instead, include every writable source in
one consistency point. Do not take independent live snapshots at different
times and describe the result as an atomic VM snapshot.

## Preserve Firmware And Device State

Check the persistent XML for UEFI NVRAM or a virtual TPM:

```bash
sudo virsh --connect qemu:///system dumpxml "$vm_domain" --inactive \
  | rg '<(loader|nvram|tpm)([ >])'
```

If an `<nvram>` path is present, copy that exact file into the private snapshot
directory while the VM remains off. The loader firmware itself is supplied by
the host package and does not normally need to be copied.

```bash
sudo cp --archive --reflink=auto \
  /exact/nvram/path \
  "$snapshot_dir/"
```

If a virtual TPM is present, include its libvirt-managed state using the
personal host's reviewed libvirt procedure. A disk image without its matching
TPM state is not a complete restorable snapshot. Do not guess a state path or
copy changing TPM state from a running VM.

## Validate And Restart

Check every resulting QCOW2 image before restarting the domain:

```bash
sudo qemu-img check "$snapshot_dir/vda.qcow2"
sudo qemu-img info --backing-chain "$snapshot_dir/vda.qcow2"
sudo sha256sum "$snapshot_dir/vda.qcow2" \
  | sudo tee "$snapshot_dir/SHA256SUMS" >/dev/null
```

Repeat the checks for every copied disk and append each additional checksum
with `sudo tee -a "$snapshot_dir/SHA256SUMS"`. A standalone image should report
no backing file. Retain `domain.xml`, `block-devices.txt`, the checksum file,
every disk image and any required NVRAM or TPM state together.

Start the VM and confirm its state:

```bash
sudo virsh --connect qemu:///system start "$vm_domain"
sudo virsh --connect qemu:///system domstate "$vm_domain"
```

## Recovery Boundary

Restoration changes personal-host VM state and remains a deliberate human
operation. Before restoring:

1. Verify the snapshot checksums and confirm that every configured writable
   disk and required firmware/device-state file is present.
2. Shut the domain off and preserve its current disks before replacing or
   repointing anything.
3. Restore into explicit paths, then review the saved XML against the current
   domain definition. A custom destination must have correct host mount,
   ownership and libvirt access; never solve access failures with broad file
   permissions.
4. Start the restored VM without simultaneously exposing the superseded copy
   under the same network identity.
5. Run the workspace's canonical read-only native runtime check after boot.

A VM snapshot is rollback material for this existing environment. It is not a
substitute for the clean-environment recovery path, which creates a fresh VM
and rebuilds application state from tracked configuration.
