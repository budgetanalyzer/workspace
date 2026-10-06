# Host-Isolation Audit Tools

These are human-operated personal-host audit tools. Read
[`docs/host-isolation-audit.md`](../../docs/host-isolation-audit.md) before live
use. Normal agents must run only the offline tests.

- `collect-host-isolation-evidence.py` performs fail-closed, read-only Mint
  host collection into a private directory outside the checkout. It never runs
  active probes.
- `host-isolation-protocol-fixture.py` provides bounded selected-address UDP
  controls and probes; non-delivery requires a positive control and separate
  ingress/drop attribution.
- `host-isolation-config.example` is a placeholder-only template for a private
  root-owned host configuration.
- `host_isolation_config.py` strictly parses configuration and validates
  topology-derived XML and nftables expectations.
- `verify-agent-host-isolation.sh` is the live root-only binary `SUCCESS` or
  `ERROR` gate and requires `--config /absolute/private/path`.

Run all focused offline tests from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tests/host-isolation-audit -v
```
