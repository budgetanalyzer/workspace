# Personal-Host Isolation Audit

This runbook is the canonical reusable procedure for reviewing the boundary
between a personal Linux Mint workstation and the root-capable Budget Analyzer
development VM. It owns the read-only evidence collector, private topology
configuration, current-state verifier and bounded protocol fixture.

This repository does not own a personal machine's concrete network values,
firewall source, service files or evidence. Keep those private and outside all
guest-accessible paths. A successful offline test or evidence collection is not
proof of live isolation.

## Human-Only Boundary

Only the human operator may collect host evidence, discover concrete host
topology, create the private verifier configuration, repair host policy,
install or reload services, stop or start the VM/network, reboot the host, or
run live protocol tests. Normal agents must not acquire host access, execute
these live commands, apply host configuration or ask the guest to administer
the host. Agents may review only explicitly supplied, manually redacted
evidence.

Transfer reviewed source to the personal host through the human-owned Git
workflow. Never give the guest a host SSH identity, mount, credential or remote
administration path.

## Current Go/No-Go Check

After the topology and private policy have been reviewed, the host operator
derives a private configuration from
[`host-isolation-config.example`](../scripts/host-isolation/host-isolation-config.example).
Compare every concrete value with the live and persistent VM definitions; do
not discover values automatically and accept them as policy.

Keep the concrete file at a canonical absolute host-only path, owned by
`root:root`, mode `0600` or `0640`, and outside the checkout. The verifier
requires exactly these keys:

| Key | Reviewed meaning |
| --- | --- |
| `vm_domain`, `vm_network`, `vm_bridge` | One domain, its dedicated libvirt network and host bridge. |
| `vm_mac`, `vm_ipv4`, `vm_gateway`, `dhcp_broadcast` | Stable guest identity and the narrow IPv4/DHCP topology; `vm_ipv4` includes its prefix. |
| `policy_service`, `policy_file`, `policy_loader`, `policy_unit` | Root-owned enforcement service and private source paths. |
| `required_units` | Comma-separated discovered libvirt services/sockets that must require the policy service. |

Unknown, duplicate, missing, malformed or placeholder keys fail. The verifier
also rejects a relative, missing, symlinked, unexpectedly owned or unsafe-mode
configuration. A topology change requires a new human review and matching
private configuration and policy; it is drift, not an input to accept during a
run.

From a reviewed personal-host checkout, the human runs:

```bash
sudo scripts/host-isolation/verify-agent-host-isolation.sh \
  --config /ABSOLUTE/PRIVATE/HOST-ISOLATION.conf
```

The only output is `SUCCESS` or `ERROR`. `SUCCESS` means the configured VM and
dedicated network are live, dynamic AppArmor confinement and passthrough
restrictions match, the reviewed six-rule nftables source and live table match,
the configured boot dependencies are active, and the retired personal-host
Docker path remains absent. `ERROR` means do not run agents until the drift is
understood.

This is a present-state gate. It does not create evidence, exercise every
protocol, prove isolation against hypervisor/kernel defects or replace host
security updates.

## Collect Read-Only Evidence

Use a normal personal-host terminal and inspect the collector before running
it. Supply the domain and network from private human review; there are no live
defaults:

```bash
sudo -v
python3 scripts/host-isolation/collect-host-isolation-evidence.py \
  --confirm-personal-host \
  --domain LIBVIRT_DOMAIN \
  --network LIBVIRT_NETWORK
```

The collector requires Linux Mint on a physical host, a normal user, existing
sudo authorization and installed inspection tools. It refuses guest, VM,
container and root execution. It does not install tools, change or reload
rules, start Docker, connect to the guest, start listeners, generate
certificates or probe another machine. Privileged reads use `sudo -n`; a
failure or 30-second timeout is recorded and required failures make the result
incomplete.

By default it creates a new mode-private `budget-host-audit-*` directory under
the operator's home. `--output-parent` may select only an existing canonical,
user-owned, non-group/world-writable absolute directory outside the checkout.
Repository output paths are refused.

The captures cover live IPv4/IPv6 rules and available backends, UFW effective
and persistent inputs, addresses, routes, listeners, live/persistent libvirt
definitions, AppArmor/process labels, service state and personal-host Docker
retirement. The collector runs no active probe.

## Keep Evidence Private

Keep all raw captures and `index.json` on the personal host outside Git and
guest-accessible storage. The index records hashes for host-side comparison;
it does not prove the collector was trusted or policy stayed unchanged.

The generated `candidate-report.md` uses best-effort redaction. It aliases the
selected domain/network/bridge/tap and removes MACs, UUIDs, public IP literals,
common personal paths and rule comments while preserving rule order, private
and local addresses, CIDRs, protocols, ports, counters, chain/set names and
process names needed for review. It is not a secret scanner. Manually inspect
and consistently redact other interfaces, hostnames, unusual paths and string
matches before sharing. Full XML, systemd unit text and UFW hooks remain
private-only.

Return only the reviewed candidate report or necessary excerpts by explicit
human transfer. If a reviewed report must temporarily exist in the guest, use
the ignored `tmp/host-isolation-audit/` directory. Do not copy raw captures,
the index, private configuration or policy source into the repository.

## Review The Effective Boundary

Before reaching an isolation conclusion, account for all of these paths:

1. Compare live and persistent VM/network definitions. Require one interface
   on the dedicated network, active dynamic AppArmor confinement, no host
   filesystem/device passthrough, clipboard/file transfer, unexpected channel
   or custom QEMU integration, and loopback-only graphics when configured.
2. Trace actual host-input and forwarding traversal through nftables and every
   installed iptables backend. Review raw, mangle, NAT and filter paths for
   IPv4 and IPv6 independently; UFW status alone is insufficient.
3. Account for UFW before-rules and libvirt-created accepts, including DNS,
   DHCP, mDNS, SSDP, multicast, broadcast, ICMP and established traffic. Permit
   only observed required flows, especially IPv6 control traffic.
4. Inspect every host address, route, listener, forwarding/DNAT path and
   alternate interface. Prove the personal-host Docker engine/socket, bridge,
   rules, listeners and obsolete policy hooks remain absent without starting
   Docker.
5. Compare persistent files and activation order with live rules, then repeat
   the evidence after a human-owned reboot. A collection success is not a
   firewall-ordering pass.
6. Retain the separate SSH/editor/browser controls: strict host keys, no
   agent/X11/credential forwarding, no automatic editor port forwarding,
   reviewed extensions, loopback HTTPS forwarding and a dedicated browser
   profile.

Record reachable policy separately from delivered traffic. A rule path can be
defective without proving delivery to a listener; confinement and loopback
listeners are independent controls, not a firewall pass.

## Human-Owned Repair Contract

Stop all affected workers before host repair. The human must create and review
the final nftables source in a root-owned host directory outside Git and all
guest-writable paths. Repository templates and test fixtures are not host
policy and must never be installed as such.

The durable enforcement point is one dedicated nftables `inet` input base
chain at the reviewed priority after conntrack and before observed libvirt/UFW
host-input accepts. Inspect every active hook and backend. Stop if any path can
accept VM-originated host input without traversing that chain. Do not flush a
ruleset or weaken unrelated LAN, VPN or Internet policy.

Discover and privately reconcile the stable domain, dedicated network, bridge,
MAC, guest CIDR, gateway, DHCP destination, IPv6 behavior and applicable
libvirt unit set. Stop on zero/multiple interfaces, another domain sharing the
network, live/persistent differences, unexplained addresses or an unmapped
tap/bridge.

The reviewed policy contains exactly these ordered behaviors:

1. Drop bridge input with a source MAC other than the configured guest.
2. Allow only established/related replies for host-initiated flows.
3. Allow guest TCP/UDP DNS only to the configured gateway.
4. Allow only the observed narrow DHCP flow and destinations.
5. Add only observed required IPv6 control/DNS/DHCP rules, if applicable and
   positively tested.
6. Count/drop mDNS and SSDP, then count/drop every other VM host-input packet.

Keep ephemeral tap names out of persistent policy. If input arrives on a tap
instead of the reviewed bridge, stop and design a separate fail-closed binding.
Do not broaden an interface match to make a test pass.

The private loader must construct one atomic nft batch, optionally delete only
the dedicated table in that batch, append the complete private source, validate
the exact bytes with `nft --check`, then apply those same bytes. It must never
flush another table. Validate root ownership, non-symlink regular files, safe
modes, shell syntax, ShellCheck and systemd unit syntax before first use.

The oneshot policy service must remain active and order before UFW and every
discovered libvirt service/socket capable of creating the network or starting
the domain. Each configured required unit must have persistent `Requires=` and
`After=` dependencies on the policy service. Shut down the VM before first
application; do not restart it until the table read-back and all dependencies
match review.

## Persistence, Rollback And Host Docker Retirement

With workers stopped, prove the reviewed table and dependencies survive a UFW
reload, a controlled selected-network restart while the domain is down, and a
final personal-host reboot. Re-run the complete matrix after reboot. Never
reload by flushing all rules.

Rollback only to reviewed exact backups. Shut down the VM first, preserve
private diagnostics, validate the restored bytes and use normal service
lifecycle commands. Never keep the VM running while deleting or bypassing the
early policy.

Do not invoke the personal-host Docker CLI because socket activation can start
it. Inventory units, packages, consumers, canonical data roots, bridges,
rules, listeners, source/config files and obsolete isolation hooks with
read-only system tools. Human review must simulate package removal, classify
every dependency and quarantine only exact canonical Docker-owned paths in a
fixed root-only location. Never use a wildcard or an unresolved variable for
removal. Final evidence requires absent engine/CLI/socket/data/bridge/rules and
inactive activation paths; retained containerd/runc requires a named non-Docker
consumer. Do not revive Docker to reproduce historical fixtures.

## Prove Protocol Behavior

Only the human operator runs live protocol tests after policy review. Bind
temporary listeners to a selected VM-facing host address, never a wildcard.
Use an unused high port and require a local host positive before interpreting a
guest denial. Pair non-delivery with a dedicated early-policy counter delta or
an exact bridge/tap/source/destination/protocol scoped capture. An unreachable
route, missing positive or broad unrelated counter is `NOT TESTED`.

For UDP, generate distinct non-secret nonces and use the bounded helper:

```bash
control_nonce=$(python3 scripts/host-isolation/host-isolation-protocol-fixture.py nonce)
probe_nonce=$(python3 scripts/host-isolation/host-isolation-protocol-fixture.py nonce)
test "$control_nonce" != "$probe_nonce"
```

The host listener requires an exact family, bind address, high port, expected
host control source and expected guest source. The host sends the control; the
guest sends only the fixed non-protocol nonce payload from its selected source.
For multicast, both listener and sender require the reviewed interface and
group. The listener returns `1` when the guest probe arrives, `3` when the
positive control is missing, and `0` only for receiver non-delivery after the
control. Exit `0` still needs independent ingress/drop attribution.

Never bind to occupied mDNS/SSDP ports, stop their owner or send a valid
discovery message. For those paths, use only the deliberately invalid nonce
payload and an exact scoped capture plus the dedicated drop counter. Stop only
the named temporary listener/capture and retain no unrelated packet payloads.

Run every applicable IPv4 and IPv6 row before and after reboot:

| Path | Required evidence |
| --- | --- |
| Guest-to-host unicast TCP | Selected-address host positive, guest denial and exact early-rule attribution. |
| Guest-to-host unicast UDP | Positive control, guest nonce non-delivery and exact attribution. |
| Disposable multicast UDP | Valid group/interface positive, guest non-delivery and scoped attribution. |
| mDNS and SSDP | No replacement listener; exact nonce ingress and dedicated drop counter. |
| Gateway DNS | TCP/UDP answers only at the reviewed gateway and narrow allow counters; other host addresses denied. |
| DHCP/DHCPv6 | Normal lease succeeds with expected values and only narrow counters; do not force renewal solely for evidence. |
| Required IPv6 control | Each allow has a named purpose and positive counter; an unapproved attempt reaches final drop. |

Also retain guest DNS/verified Internet HTTPS, host-initiated SSH, reviewed Git
transfer and host loopback-only application HTTPS positives. Application,
Kind, Tilt and Kubernetes checks remain orchestration-owned; do not recreate
Kind or mutate the cluster merely to gather isolation evidence.

## Audit Result

Keep a dated private result containing collection time, reviewed revisions,
configuration identity/hash, firewall ordering, protocol/family coverage,
confinement, persistence, positive/negative controls and limitations. Pair pre-
and post-reboot rows. Changed topology, policy bytes, backend or listener
ownership invalidates affected evidence and requires human review before
retesting.
