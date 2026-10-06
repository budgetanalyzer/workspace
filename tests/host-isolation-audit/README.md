# Host-Isolation Audit Tests

This suite tests collector redaction/fail-closed behavior, bounded UDP controls,
strict private-configuration parsing, topology substitution, drift rejection
and the verifier's binary missing-config contract. Fixtures use documentation
addresses and synthetic names only; they are not evidence of live isolation.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tests/host-isolation-audit -v
```
