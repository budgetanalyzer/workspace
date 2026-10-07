# Native Tool Inventory

The machine-readable
[toolchain manifest](../native/toolchain.json) owns exact releases, both Linux
architecture URLs/checksums, repository signing fingerprints, package sets,
helper ownership and validation inputs. The
[system provisioner](../scripts/provision-agent-vm-guest.sh) consumes it.

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
Do not use an unverified architecture-specific download.

The native manifest and orchestration both select Helm **3.20.1**.
Orchestration's `check-tilt-prerequisites.sh` supports >=3.20.0 and <4.0.0;
Helm 4 must not replace this selection. Workspace carries reviewed Linux
kubectl/Kind/Tilt/Helm inputs matching orchestration's
[`pinned-tool-versions.sh`](../../orchestration/scripts/lib/pinned-tool-versions.sh).
That repository also owns `install-verified-tool.sh` for focused installation,
including its guardrail tools. Never run destructive `setup.sh` to obtain a
binary. The manifest verifier detects divergence; resolve owner-contract
changes explicitly rather than installing a conflicting version.

The manifest records an explicit npm registry resolution, including integrity
metadata. Native installation must use those exact versions; a refresh is a
deliberate reviewed input change, never an implicit `latest` lookup. The user
installer owns a normal-user prefix, tracked `native/npm/package-lock.json`
with transitive integrity, resolved-version reports and explicit refresh
behavior. Claude uses the npm distribution because the proxy workflow requires
it. mitmproxy is pinned in pipx; AI Session Handler remains editable from the
reviewed guest checkout, with revision/import-path evidence rather than a PyPI
substitution.

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
| Go / gofmt | System: verified 1.24.1 amd64/arm64 archives in `/opt/budget-analyzer-native/go-1.24.1`; command symlinks in `/usr/local/bin` | Manifest URL/checksum parity; `go version`; `gofmt -h`; human installation on the selected architecture |
| Docker client, daemon and Compose | Existing guest Docker retained; fresh VM alone installs Ubuntu docker.io/docker-compose-v2 and enables Docker | `docker --version`; `docker compose version`; default Unix context; `/var/lib/docker`; before/after running IDs/start times |
| kubectl / Kind / Tilt / Helm | System: verified releases matching orchestration contract; no cluster/service creation | `kubectl version --client --output=json`; `kind version`; `tilt version`; `helm version --template '{{.Version}}'` |
| bubblewrap / native command sandbox support | System: Ubuntu bubblewrap; human scoped profile setup through `scripts/install-agent-vm-bwrap-profile.sh`, preserving existing AppArmor policy | `bwrap --version`; unprivileged namespace and provider sandbox-mode checks; no blanket sudoers change |
| Claude Code, Codex CLI, Gemini CLI | User: pinned npm packages and explicit reviewed refresh; ordinary provider state | `claude --version`; `codex --version`; `gemini --version`; human authenticates only selected provider |
| AI Session Handler | User: editable pipx install from `../ai-session-handler`, never auto-clone | `ai-session-handler --version`; `ai-session-handler-codex-high --help`; pipx Python import path must resolve into guest checkout |
| Playwright/Chromium | System installs reviewed Ubuntu native deps; user installs pinned npm Playwright and its Chromium in user browser data | `playwright --version`; `playwright install --list`; human browser launch/trust smoke |
| VIA 3.0.13 | System: verified official zip + standalone asset SHA-256; read-only HTML/LICENSE/README under `/opt/via-annotator`; normal-user launcher | `via-annotator --version`; `via-annotator --check`; human foreground 127.0.0.1 bind and clean stop |
| mitmproxy/mitmweb/mitmdump | User: isolated pipx 12.2.3; installed capability with optional activation | `mitmproxy --version`; `mitmweb --version`; `mitmdump --version`; Python/static checks and optional human smoke; no proxy startup during installation |

## Native Helper Sources

The manifest maps each retained command name to its one `native_source`.
Portable resources live in `native/helpers/`; native CA and proxy adapters live
in `scripts/native/local_ca.py` and `scripts/native/proxy.py`. Settings, the
conversation skill and prompt resources also live under `native/helpers/`.
Every command
gets an executable user wrapper that loads the same small environment fragment.
The read-only source/environment checker renders those wrappers under `tmp/`
and validates shell syntax and ShellCheck. Every path in the manifest's
`reviewed_sources` map now resolves to an active native or sibling contract.
Native
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
| `ai-run` | `native/helpers/ai-run.sh`; forwards to the installed handler/high wrapper; Bash/static checks and human smoke |
| `codex-lean` | `native/helpers/codex-lean.sh`; preserves explicit `CODEX_MODEL`/effort and high-authority arguments while resolving user-installed Codex; plain Codex remains upstream |
| Codex proxy commands | `scripts/native/proxy.py`; optional mitmweb child plus Codex lean, native paths and xhigh effort; offline argv/lifecycle fixtures |
| Claude proxy/custom-prompt commands | `scripts/native/proxy.py`; inspection-only or prompt replacement/model selection using npm Claude; offline argv/lifecycle fixtures |
| `start-proxy` | `scripts/native/proxy.py`; optional foreground loopback mitmweb UI with reviewed private identity and upstream verification |
| `mitmflows`, `mitmflow-detail`, `mitmflow-body`, `mitmflow-render.py` | `native/helpers/`; Bash + Python stdlib rendering/export with repository-`tmp/` boundaries |
| `ensure-budget-analyzer-local-ca-trust`, `check-budget-analyzer-local-ca-trust` | `scripts/native/local_ca.py`; read-only exact-origin diagnosis. The separate human installer owns scoped OS/NSS mutation and identity-checked legacy convergence |
| `via-annotator` | `native/helpers/via-annotator.sh`; asset validation, strict `127.0.0.1` foreground serving and clean stop |
| `statusline-command` | `native/helpers/statusline-command.sh`; optional normal-home credentials and repository-`tmp/` cache; never activated or invoked by installation |
| Prompt addon and text | `native/helpers/system-prompt-addon.py` and `system-prompt.md`; required prefix/cache-control preservation, ancillary pass-through and private dumps |
| Conversation skill | `native/helpers/skills/save-conversation/SKILL.md`; exact file-only installation with collision checks |
| Settings overlay | `native/helpers/settings-overlay.json`; merges only the AGENTS SessionStart hook and two reviewed controls while preserving unrelated settings |
| Optional aliases | `native/helpers/bash_aliases.sh`; explicit model/effort/permission choices. Shell startup loads only the environment; aliases remain opt-in |

The inventory deliberately preserves optional proxy, annotation and browser
capabilities even when the human chooses not to activate them. Permission-bypass
aliases are explicit choices; system provisioning neither selects them nor
relaxes AppArmor/native sandboxing.

## Native Verification

`scripts/native/verify_release_inputs.py` is the read-only network verifier for
the hosted dependency evidence workflow. It consumes the existing manifest,
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
bash -n scripts/install-agent-vm-bwrap-profile.sh
bash -n scripts/prepare-agent-vm-native.sh
shellcheck scripts/provision-agent-vm-guest.sh scripts/install-agent-vm-bwrap-profile.sh scripts/prepare-agent-vm-native.sh
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile scripts/native/provision.py scripts/native/user_tools.py scripts/native/bwrap_profile.py scripts/native/verify_release_inputs.py tests/native/test_provision.py tests/native/test_native_preparation.py tests/native/test_install_inputs.py tests/native/test_dependency_discovery.py tests/native/test_release_inputs.py tests/native/check_manifest.py tests/native/check_install_inputs.py
actionlint .github/workflows/native-dependency-validation.yml
git diff --check
```

The proposed publication mode validates a source-only copy made from tracked
working-tree files plus reviewed uncommitted required inputs. After the human
commit, use `--publication committed`; only that mode validates a true
`git archive HEAD` and establishes ordinary Git-transfer availability.

The compact harness replaces privileged/download commands only where needed to
prove the safety boundary: wrong OS, container/non-VM execution, a remote
Docker endpoint, root or missing users and missing bootstrap commands reject
before sudo/downloads; checksum failure rejects before mutation; spaced paths
remain single arguments; and a repeat with healthy Docker performs no package
or restart operation. It deliberately does not emulate apt output, package
transactions, systemd, repositories or browser installation. Static checks
validate every native manifest path, rendered helper command, settings/skill
resource, current orchestration tool contract and documentation link. Native
pins remain manual-review inputs; Renovate's shared policy does not infer
arbitrary checksum or signing-key relationships.

The Go archive validator accepts the official top-level `go` directory entry
and its contents, rejects a non-directory root or unrelated paths, and retains
the extraction filter that rejects path traversal. An `unexpected Go archive
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
