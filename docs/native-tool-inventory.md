# Native Tool Inventory

The machine-readable
[toolchain manifest](../native/toolchain.json) owns system inputs only: OS,
architectures, apt package sets including the reviewed Chromium libraries,
signed repositories and both Linux architecture URLs/checksums for system
downloads. The [system provisioner](../scripts/provision-agent-vm-guest.sh)
loads and validates only that file. The separate
[agent-tool manifest](../native/agent-tools.json) owns provider, normal-user
tool and helper declarations; only the user installer and its verifiers read
it.

System and normal-user provisioning, helper adaptation and offline verification
are implemented. Follow [Native Guest User Tools](native-user-tools.md) for
installation, trust, authentication and verification commands. This inventory
is the durable native capability contract.

## Ownership And Version Policy

Workspace owns the system/user installation entry points and helper sources.
Ubuntu's signed 24.04 repositories own utility patches, Docker/Compose, Maven,
Python and Chromium libraries. NodeSource owns Node major 24 (and npm >=10);
Azul owns Zulu JDK major 25. Their primary signing-key fingerprints are pinned
and all keys in a downloaded key file are checked before privileged writes.
Existing packages are retained; missing packages resolve signed apt candidates.
No installed package is implicitly upgraded. Apt simulation rejects dependency
upgrades/removals before package installation; apt index refresh may already
have occurred. The guard identifies installed-version brackets immediately
after the package name; candidate architecture brackets and trailing dependency
annotations on new installations do not indicate an upgrade. Explicit system
maintenance is a human operation outside a worker session. Ubuntu archive
signing keys remain distribution-managed.

Release tools use exact manifest pins and reviewed SHA-256 values. Go's
lifecycle review remains the shared policy's human responsibility. Refresh
versions, URLs, both architecture checksums and validation patterns together.
Do not use an unverified architecture-specific download. The provisioner
replaces an older managed release with the reviewed manifest release, retains
an equal release, and rejects an installed release that is newer than the
reviewed selection. Release downloads use bounded connection and transfer
timeouts with bounded retries so an unavailable upstream fails visibly.

Workspace does not declare, install or verify kubectl, Helm, Tilt or Kind.
Orchestration owns those platform tools, their pins and their installation;
see its
[getting-started guide](https://github.com/budgetanalyzer/orchestration/blob/main/docs/development/getting-started.md#first-bootstrap).

Provider CLI policy: Claude Code, Codex CLI and Gemini CLI float by
deliberate human decision. They have no repository-pinned version, integrity
value or Renovate tracking. First installation, or an explicit human
`--update-provider NAME` request for one provider, installs that package at
npm `@latest` with `npm install --global` into one managed normal-user provider
prefix. Routine preparation keeps installed provider versions. npm registry
HTTPS and registry integrity verification stay on, and provider installation
never uses `sudo`. Verification checks presence, `--version` exit status,
ownership, containment in the managed package and fresh-shell command
resolution, not a version match. Claude uses the npm distribution because the
proxy workflow requires it.

Playwright stays exact. `native/npm/package-lock.json` is the single source
of its version, integrity and tarball; `native/npm/package.json` must name the
same exact version, and every locked package must resolve over registry HTTPS
with integrity. The reviewed Chromium apt provenance (`chromium_apt_source` in
the toolchain manifest) is a separate input that must name the locked version;
it is never derived from the lockfile, so a lockfile-only upgrade fails until
the apt inputs are reviewed. mitmproxy is pinned in pipx; AI Session Handler
remains editable from the reviewed guest checkout, with revision/import-path
evidence rather than a PyPI substitution.

## Installed Capabilities

Each row names the native owner, method/policy and validation command. Commands
that need activation remain explicit human smoke checks. The manifest lists
every apt package, including all reviewed Chromium shared libraries and fonts.

| Capability | Native owner and installation / update policy | Validation |
| --- | --- | --- |
| Bash, coreutils, find/grep/sed/awk, util-linux, procps, tar/gzip/xz, zip/unzip, sudo, CA certificates, GnuPG, lsb-release | System: Ubuntu apt, retain installed patches | `bash --version`; `dpkg-query -W` manifest packages; `tar --version`; `gpg --version` |
| Git, curl, wget, jq, tree, vim, nano and ripgrep | System: Ubuntu apt | `git --version`; `curl --version`; `wget --version`; `jq --version`; `tree --version`; `vim --version`; `nano --version`; `rg --version` |
| C/C++ compiler, make and build-essential | System: Ubuntu apt | `gcc --version`; `g++ --version`; `make --version` |
| DNS, ping, traceroute, nc; process/socket diagnostics | System: dnsutils, iputils-ping, traceroute, netcat-openbsd; explicit iproute2/lsof/procps | `dig -v`; `ping -V`; `traceroute --version`; `nc -h`; `ss --version`; `lsof -v` |
| OpenSSL, NSS `certutil` | System: openssl/libnss3-tools via apt; installation does not add custom roots | `openssl version`; `certutil -H`; later human trust matrix |
| PDF/image/archive tools | System: poppler-utils, imagemagick, unzip/zip via apt | `pdftotext -v`; `pdfinfo -v`; `identify -version`; `convert -version`; `unzip -v` |
| ShellCheck / actionlint | System: Ubuntu apt / verified pinned release for amd64 and arm64 | `shellcheck --version`; `actionlint --version` |
| Python/pipx/venv/PyYAML | System: python3, python3-pip, python3-venv, python3-yaml, pipx apt packages | `python3 -c 'import yaml, venv; print(yaml.__version__)'`; `pipx --version` |
| Node/npm | System: signed NodeSource major 24; retained patches, npm >=10 | `node --version`; `npm --version` |
| Azul Zulu JDK / Maven | System: signed Azul major 25 / Ubuntu Maven | `java -version`; `javac -version`; `mvn --version` |
| Gradle builds, Maven Local and build caches | User: checked-in service Gradle wrappers; ordinary user home; no global Gradle substitution | Service build and publication checks |
| Go / gofmt | System: verified 1.27.3 amd64/arm64 archives in `/opt/budget-analyzer-native/go-1.27.3`; command symlinks in `/usr/local/bin` | Manifest URL/checksum parity; `go version`; `gofmt -h`; human installation on the selected architecture |
| Docker client, daemon and Compose | Existing guest Docker retained; fresh VM alone installs Ubuntu docker.io/docker-compose-v2 and enables Docker | `docker --version`; `docker compose version`; default Unix context; `/var/lib/docker`; before/after running IDs/start times |
| bubblewrap / native command sandbox support | System: Ubuntu bubblewrap; human scoped profile setup through `scripts/install-agent-vm-bwrap-profile.sh`, preserving existing AppArmor policy | `bwrap --version`; unprivileged namespace and provider sandbox-mode checks; no blanket sudoers change |
| Claude Code, Codex CLI, Gemini CLI | User: floating npm global packages in the managed provider prefix; latest on first install or explicit `--update-provider NAME`; ordinary provider state | `claude --version`; `codex --version`; `gemini --version` exit status, no version match; human authenticates only selected provider |
| AI Session Handler | User: editable pipx install from `../ai-session-handler`, never auto-clone | `ai-session-handler --version`; `ai-session-handler-codex-high --help`; `ai-session-handler-claude-high --help`; `ai-session-handler-claude-medium --help`; pipx Python import path must resolve into guest checkout |
| Playwright/Chromium | System installs reviewed Ubuntu native deps; user installs lockfile-pinned npm Playwright and its Chromium in user browser data | `playwright --version`; `playwright install --list`; human browser launch/trust smoke |
| VIA 3.0.13 | System: verified official zip + standalone asset SHA-256; read-only HTML/LICENSE/README under `/opt/via-annotator`; normal-user launcher | `via-annotator --version`; `via-annotator --check`; human foreground 127.0.0.1 bind and clean stop |
| mitmproxy/mitmweb/mitmdump | User: isolated pipx 12.2.3; installed capability with optional activation | `mitmproxy --version`; `mitmweb --version`; `mitmdump --version`; Python/static checks and optional human smoke; no proxy startup during installation |

## Native Helper Sources

The agent-tool manifest maps each retained command name to its one `native_source`.
Portable resources live in `native/helpers/`; native CA and proxy adapters live
in `scripts/native/local_ca.py` and `scripts/native/proxy.py`. Settings, the
conversation skill and prompt resources also live under `native/helpers/`.
Every command
gets an executable user wrapper that loads the same small environment fragment.
Provider and `codex-lean` wrappers, and the proxy provider launchers, also run
the installed VM boundary first
([launch enforcement](native-user-tools.md#provider-launch-enforcement)).
The read-only source/environment checker renders those wrappers under `tmp/`
and validates shell syntax and ShellCheck. Every workspace-owned path in the
agent-tool manifest's `reviewed_sources` map resolves in a standalone checkout. Native
`ensure` diagnoses established ingress trust; only the explicit human trust
installer performs privileged imports. Optional proxy
wrappers refuse unidentified occupied listeners, keep TLS verification on and
use a separate human-initialized CA with process-scoped trust.

## Every Helper, Skill And Hook

All native helper installation/configuration is owned by the normal-user
installer and sourced from the reviewed workspace revision. Preserve the
commands and normal-user paths in the canonical native sources. Installation/offline checks
must not activate proxy listeners, generate/trust a proxy CA or contact a
provider. `--help` on a proxy wrapper currently starts its proxy, so use mocked
commands for its validation, not live help invocation.

| Retained command or resource | Native implementation, dependencies and validation |
| --- | --- |
| `ai-run` | `native/helpers/ai-run.sh`; selects the installed Codex high wrapper by default or the Claude high wrapper with a leading `--claude`; Bash/static checks and human smoke |
| `claude-lean` | `native/helpers/claude-lean.sh`; owns the fixed lean option set and 11 environment variables, resolves user-installed Claude directly with the installed `system-prompt.md`, or uses `claude-with-proxy` with the default prompt kept for capture; offline argv/environment fixture |
| `codex-lean` | `native/helpers/codex-lean.sh`; preserves explicit `CODEX_MODEL`/effort and high-authority arguments while resolving user-installed Codex; plain Codex remains upstream |
| Codex proxy commands | `scripts/native/proxy.py`; optional mitmweb child plus Codex lean with `CODEX_REAL_BIN` set to the managed provider prefix, native paths and xhigh effort; offline argv/lifecycle fixtures |
| Claude proxy command | `scripts/native/proxy.py`; inspection-only upstream npm Claude from the managed provider prefix with no added Claude environment; offline argv/lifecycle fixtures |
| `start-proxy` | `scripts/native/proxy.py`; optional foreground loopback mitmweb UI with reviewed private identity and upstream verification |
| `mitmflows`, `mitmflow-detail`, `mitmflow-body`, `mitmflow-render.py` | `native/helpers/`; Bash + Python stdlib rendering/export with repository-`tmp/` boundaries |
| `ensure-budget-analyzer-local-ca-trust`, `check-budget-analyzer-local-ca-trust` | `scripts/native/local_ca.py`; read-only exact-origin diagnosis. The separate human installer owns scoped OS/NSS mutation and identity-checked legacy convergence |
| `statusline-command` | `native/helpers/statusline-command.sh`; stdin-only, offline status line; no credentials, network or cache |
| `via-annotator` | `native/helpers/via-annotator.sh`; asset validation, strict `127.0.0.1` foreground serving and clean stop |
| Lean system prompt | `native/helpers/system-prompt.md`; replaces the default main prompt through `claude-lean`; tool guidance matches the lean tool list |
| Conversation skill | `native/helpers/skills/save-conversation/SKILL.md`; exact file-only installation with collision checks |
| Settings overlay | `native/helpers/settings-overlay.json`; merges only two reviewed controls while preserving unrelated settings |
| Optional aliases | `native/helpers/bash_aliases.sh`; three thin lean Claude aliases, `ai-run-claude`, and explicit Codex effort/permission choices. Shell startup loads only the environment; aliases remain opt-in |

The inventory deliberately preserves optional proxy, annotation and browser
capabilities even when the human chooses not to activate them. Permission-bypass
aliases are explicit choices; system provisioning neither selects them nor
relaxes AppArmor/native sandboxing.

## Native Verification

`scripts/native/verify_release_inputs.py` is the read-only network verifier for
the hosted dependency evidence workflow. It consumes the system toolchain manifest,
requires the complete `amd64`/`arm64` table, permits only credential-free HTTPS
and HTTPS redirects, checks exact SHA-256 values and inspects tar/zip members
without installation or execution. Its report is written incrementally so an
unavailable or malformed later asset preserves earlier results. Keep its
download directory under `tmp/`; never substitute its repository-input report
for the canonical installed-VM readiness check.

Run the tracked checks from the workspace root:

```bash
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest discover -s tests/native -v
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_manifest.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_install_inputs.py --publication proposed
PYTHONPYCACHEPREFIX=tmp/pycache python3 scripts/native/verify_release_inputs.py \
  --manifest native/toolchain.json \
  --output tmp/native-release-validation/release-verification.json \
  --download-dir tmp/native-release-validation/downloads
bash -n scripts/provision-agent-vm-guest.sh
bash -n scripts/check-agent-vm-boundary.sh
bash -n scripts/install-agent-vm-bwrap-profile.sh
bash -n scripts/prepare-agent-vm-native.sh
shellcheck scripts/provision-agent-vm-guest.sh scripts/check-agent-vm-boundary.sh scripts/install-agent-vm-bwrap-profile.sh scripts/prepare-agent-vm-native.sh
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile scripts/native/boundary.py scripts/native/provision.py scripts/native/user_tools.py scripts/native/bwrap_profile.py scripts/native/verify_release_inputs.py tests/native/test_boundary.py tests/native/test_provision.py tests/native/test_native_preparation.py tests/native/test_install_inputs.py tests/native/test_dependency_discovery.py tests/native/test_release_inputs.py tests/native/check_manifest.py tests/native/check_install_inputs.py
actionlint .github/workflows/native-dependency-validation.yml
tests/native/check-source-validation-without-orchestration.sh --publication proposed
git diff --check
```

`tests/native/run-source-validation.sh` holds the complete source-validation
command list that publication CI runs; the no-sibling script reruns it from a
copy of this checkout whose parent has no orchestration checkout.

The proposed publication mode validates a source-only copy made from tracked
working-tree files plus reviewed uncommitted required inputs. After the human
commit, use `--publication committed`; only that mode validates a true
`git archive HEAD` and establishes ordinary Git-transfer availability.

The compact harness replaces privileged/download commands only where needed to
prove the safety boundary: wrong OS, container/non-VM execution, a remote
Docker endpoint, root or missing users and missing bootstrap commands reject
before sudo/downloads; a failing boundary Git or Docker probe, including the
privileged `docker info` data-root probe, reports only the command name and
exit status, never its output, while other provisioning command failures keep
their detail; checksum failure rejects before mutation; spaced paths
remain single arguments; and a repeat with healthy Docker performs no package
or restart operation. It deliberately does not emulate apt output, package
transactions, systemd, repositories or browser installation. Static checks
validate every native manifest path, rendered helper command, settings/skill
resource and documentation link. Native
pins remain manual-review inputs; Renovate's shared policy does not infer
arbitrary checksum or signing-key relationships.

The Go archive validator accepts the official top-level `go` directory entry
and its contents, rejects a non-directory root or unrelated paths, and retains
the extraction filter that rejects path traversal. Because that filter ignores
archive directory modes, staging sets every extracted directory to `0755` so
the installed tree stays readable under the preparation runner's private
umask. An `unexpected Go archive
layout` failure occurs during staging before system mutation; review the input
and validator before rerunning the provisioner.

The read-only `certutil -H` check accepts NSS's help exit status of 1 only
when the expected certificate command sections are present (status 0 is also
accepted). Other command failures remain fatal. A run that stops at this check
has already installed system tools; rerun the provisioner after applying the
validation fix to complete verification of the retained installations.

Real apt installation, browser download and launch, the complete native user
environment, provider authentication, TLS trust and repeat-run behavior remain
human verification. Offline safety checks do not establish live VM state.
