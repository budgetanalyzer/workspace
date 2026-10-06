# Native Tool Migration Inventory

The original migration inventoried every capability in the former Mint image,
entrypoints, helpers, settings, skill and prompt addon. Phase 5 retired those
tracked sources after native acceptance. The machine-readable
[toolchain manifest](../native/toolchain.json) owns exact releases, both Linux
architecture URLs/checksums, repository signing fingerprints, package sets,
helper ownership and validation inputs. The
[system provisioner](../scripts/provision-agent-vm-guest.sh) consumes it.

System and normal-user provisioning, helper adaptation and offline verification
are implemented. Follow [native user tools and Checkpoint B](native-user-tools.md)
for installation, trust, authentication and exact handoff commands. Human B and
native Phase 3 runtime verification passed on 2026-10-05. The operator has since
confirmed all phases and C–D complete; see the
[canonical acceptance record](../../orchestration/docs/plans/agent-host-isolation-acceptance.md#native-human-acceptance).
This inventory is the durable native capability contract. Historical
Dockerfile-era behavior below records explicit retention or retirement; it is
not an active build recipe and does not claim live installation.

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

Release tools use exact manifest pins and reviewed SHA-256 values. Keep Go
1.24.1 for migration parity; its lifecycle review remains the shared policy's
human responsibility. Refresh versions, URLs, both architecture checksums and
validation patterns together. Do not use an unverified architecture-specific
Go download. Kind receives the checksum absent from the old Dockerfile.

The native manifest and orchestration both select Helm **3.20.1**.
Orchestration's `check-tilt-prerequisites.sh` supports >=3.20.0 and <4.0.0;
Helm 4 must not replace this selection. Workspace carries reviewed Linux
kubectl/Kind/Tilt/Helm inputs matching orchestration's
[`pinned-tool-versions.sh`](../../orchestration/scripts/lib/pinned-tool-versions.sh).
That repository also owns `install-verified-tool.sh` for focused installation,
including its guardrail tools. Never run destructive `setup.sh` to obtain a
binary. The manifest verifier detects divergence; resolve owner-contract
changes explicitly rather than installing a conflicting version.

The three agents and Playwright previously used unbounded npm selection. The
manifest records one explicit registry resolution on 2026-10-04, including npm
integrity metadata. Native installation must use those exact versions; future
refresh is a deliberate reviewed input change, never an implicit `latest`
lookup. The user installer owns a normal-user prefix, tracked `native/npm/package-lock.json`
with transitive integrity, resolved-version reports and explicit refresh behavior. Claude retains the npm flavor
because the existing proxy workflow requires it. mitmproxy remains pinned
12.2.3 in pipx; AI Session Handler remains editable from the reviewed guest
checkout, with revision/import-path evidence rather than a PyPI substitution.

## Installed Capabilities

Each row names the native owner, method/policy and acceptance command. Commands
that need activation belong to human Checkpoint B or later live smoke checks;
Phase 1 runs only focused safety checks and source/manifest checks. The
manifest lists every apt package, including all reviewed Chromium shared
libraries and fonts.

| Former capability / source | Native owner and installation / update policy | Validation |
| --- | --- | --- |
| Bash, coreutils, find/grep/sed/awk, util-linux, procps, tar/gzip/xz, zip/unzip, sudo, CA certificates, GnuPG, lsb-release (Ubuntu base + RUN) | System: Ubuntu apt, retain installed patches | `bash --version`; `dpkg-query -W` manifest packages; `tar --version`; `gpg --version` |
| Git, curl, wget, jq, tree, vim | System: Ubuntu apt; add explicit nano/ripgrep rather than relying on base/image accidents | `git --version`; `curl --version`; `wget --version`; `jq --version`; `tree --version`; `vim --version`; `nano --version`; `rg --version` |
| C/C++ compiler, make and build-essential | System: Ubuntu apt | `gcc --version`; `g++ --version`; `make --version` |
| DNS, ping, traceroute, nc; process/socket diagnostics | System: dnsutils, iputils-ping, traceroute, netcat-openbsd; explicit iproute2/lsof/procps | `dig -v`; `ping -V`; `traceroute --version`; `nc -h`; `ss --version`; `lsof -v` |
| OpenSSL, NSS `certutil` | System: openssl/libnss3-tools via apt; installation does not add custom roots | `openssl version`; `certutil -H`; later human trust matrix |
| PDF/image/archive tools | System: poppler-utils, imagemagick, unzip/zip via apt | `pdftotext -v`; `pdfinfo -v`; `identify -version`; `convert -version`; `unzip -v` |
| ShellCheck / actionlint | System: Ubuntu apt / verified pinned release for amd64 and arm64 | `shellcheck --version`; `actionlint --version` |
| Python/pipx/venv/PyYAML | System: python3, python3-pip, python3-venv, python3-yaml, pipx apt packages | `python3 -c 'import yaml, venv; print(yaml.__version__)'`; `pipx --version` |
| Node/npm | System: signed NodeSource major 24; retained patches, npm >=10 | `node --version`; `npm --version` |
| Azul Zulu JDK / Maven | System: signed Azul major 25 / Ubuntu Maven | `java -version`; `javac -version`; `mvn --version` |
| Gradle builds, Maven Local and build caches | User: checked-in service Gradle wrappers; ordinary user home; no global Gradle substitution | Later service build/publication phases; no Phase 1 service changes |
| Go / gofmt | System: verified 1.24.1 amd64/arm64 archives in `/opt/budget-analyzer-native/go-1.24.1`; command symlinks in `/usr/local/bin` | Manifest URL/checksum parity; `go version`; `gofmt -h`; human installation on the selected architecture |
| Docker client, daemon and Compose | Existing guest Docker retained; fresh VM alone installs Ubuntu docker.io/docker-compose-v2 and enables Docker | `docker --version`; `docker compose version`; default Unix context; `/var/lib/docker`; before/after running IDs/start times |
| kubectl / Kind / Tilt / Helm | System: verified releases matching orchestration contract; no cluster/service creation | `kubectl version --client --output=json`; `kind version`; `tilt version`; `helm version --template '{{.Version}}'` |
| bubblewrap / native command sandbox support | System: Ubuntu bubblewrap; human scoped profile setup through `scripts/install-agent-vm-bwrap-profile.sh`, preserving existing AppArmor policy | `bwrap --version`; unprivileged namespace smoke check; Phase 3 provider sandbox-mode proof; no blanket sudoers change |
| Claude Code, Codex CLI, Gemini CLI | User: pinned npm packages and explicit reviewed refresh; ordinary provider state | `claude --version`; `codex --version`; `gemini --version`; human authenticates only selected provider |
| AI Session Handler | User: editable pipx install from `../ai-session-handler`, never auto-clone | `ai-session-handler --version`; `ai-session-handler-codex-high --help`; pipx Python import path must resolve into guest checkout |
| Playwright/Chromium | System installs reviewed Ubuntu native deps; user installs pinned npm Playwright and its Chromium in user browser data | `playwright --version`; `playwright install --list`; human B browser launch/trust smoke |
| VIA 3.0.13 | System: verified official zip + standalone asset SHA-256; read-only HTML/LICENSE/README under `/opt/via-annotator`; user launcher at Phase 2 | `via-annotator --version`; `via-annotator --check`; later foreground 127.0.0.1 bind and clean stop |
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

## Retired Container Environment And Startup Dispositions

| Source surface | Native disposition / validation |
| --- | --- |
| Ubuntu base digest, target architecture and version arguments | Native Ubuntu release/actual QEMU/KVM/architecture checks replace image selection; the manifest owns binary versions and both architecture checksums |
| `CLI_CACHE_BUST`, npm `latest` | No cache-bust-dependent selection; exact user manifest inputs and explicit refresh |
| `DEBIAN_FRONTEND` | Only the human-run apt transaction is noninteractive; not a global user export |
| `SSL_CERT_FILE` | Phase 2 user environment points Python to combined system CA bundle, preserving public roots; B trust matrix |
| `JAVA_HOME`, `MAVEN_HOME`, `PATH` | Use signed OS JDK/Maven; Phase 2 resolves actual JDK path instead of recreating container `/usr/lib/jvm/zulu25` assumption. Include Go/user command prefix explicitly; fresh-shell version resolution proof |
| `PLAYWRIGHT_BROWSERS_PATH` | Ordinary user browser cache; no container `/opt/playwright-browsers` requirement. Phase 2 uses one consistent user location across CLI/library/browser validation |
| `NODE_EXTRA_CA_CERTS` | Plain native Node uses reviewed combined local/public trust configuration in Phase 2. Proxy wrappers activate only explicitly selected proxy trust; no proxy-only root export at install/startup |
| USER creation/rename, UID/GID ARGs, `NOPASSWD:ALL` | Do not reproduce. Validate existing normal account/home, preserve ownership and sudo policy; Docker membership remains explicit guest-root-equivalent authority |
| WORKDIR `/workspace`, ENTRYPOINT and CMD | Native process starts in human-selected guest checkout. No daemon/container lifecycle is needed for agent tools |
| `entrypoint.sh` recursive `chown`, repository `clone`, SSH `origin` rewrite | Retire those side effects; stop on collisions/missing guest-local sources. Human owns Git transfer; native installer never changes repositories/remotes |
| Historical entrypoint handler reinstall, skill copy and overlay merge | Moved to explicit user installation, not every agent startup. Import-path/command checks remain repeatable; both entrypoints are retired |
| Historical guest entrypoint origin, credential, Docker and kubeconfig checks | Migrated into the read-only native verifier; the container-specific entrypoint and kubeconfig path are retired |
| Entrypoint banners/version reports/provider auth hints | User installer/verifier reports resolved versions. Human authenticates native provider at B; never import container credentials automatically |
| Dockerfile mitmdump first-run CA generation, `-k`, system proxy-root trust and pipx ensurepath | Retire install-time activation/TLS bypass. Optional proxy trust is separate reviewed workflow; Phase 2 preserves shell/config and does not run automatic ensurepath rewrites |
| `/workspace` creation/ownership, provider `.claude`/`.codex`/`.gemini` directories | Ordinary user's existing home/repositories; no recursive ownership repair, shell replacement or forced provider configuration |
| Mint Compose/editor launch and environment generation | Runtime retired at operator-confirmed Checkpoint D; tracked launch/build sources and exclusive image evidence are removed. Do not recreate them |

## Native Verification And Handoff

Run the tracked checks from the workspace root:

```bash
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest discover -s tests/native -v
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_manifest.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_install_inputs.py --publication proposed
bash -n scripts/provision-agent-vm-guest.sh
bash -n scripts/install-agent-vm-bwrap-profile.sh
bash -n scripts/prepare-agent-vm-native.sh
shellcheck scripts/provision-agent-vm-guest.sh scripts/install-agent-vm-bwrap-profile.sh scripts/prepare-agent-vm-native.sh
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile scripts/native/provision.py scripts/native/bwrap_profile.py tests/native/test_provision.py tests/native/test_native_preparation.py tests/native/test_install_inputs.py tests/native/check_manifest.py tests/native/check_install_inputs.py
git diff --check
```

The proposed publication mode validates a source-only copy made from tracked
working-tree files plus the explicitly reviewed new npm lock and native
settings overlay. After the human commit, use `--publication committed`; only
that mode validates a true `git archive HEAD` and establishes ordinary
Git-transfer availability.

The compact harness replaces privileged/download commands only where needed to
prove the safety boundary: wrong OS, container/non-VM execution, a remote
Docker endpoint, root or missing users and missing bootstrap commands reject
before sudo/downloads; checksum failure rejects before mutation; spaced paths
remain single arguments; and a repeat with healthy Docker performs no package
or restart operation. It deliberately does not emulate apt output, package
transactions, systemd, repositories or browser installation. Static checks
validate every native manifest path, rendered helper command, settings/skill
resource, current orchestration tool contract, documentation link and
retired-source guard. Native pins remain manual-review inputs; Renovate's
shared policy does not infer arbitrary checksum or signing-key relationships.

The Go archive validator accepts the official top-level `go` directory entry
and its contents, rejects a non-directory root or unrelated paths, and retains
the extraction filter that rejects path traversal. If B.1 reports `unexpected
Go archive layout` with the earlier validator, rerun the system provisioner
after applying the fix. That failure occurs during staging, before system
mutation; no installation cleanup is required. The successful real B.1 run is
the integration evidence for the official archive layout.

The read-only `certutil -H` check accepts NSS's help exit status of 1 only
when the expected certificate command sections are present (status 0 is also
accepted). Other command failures remain fatal. A run that stops at this check
has already installed system tools; rerun the provisioner after applying the
validation fix to complete verification of the retained installations.

Real apt installation, browser download/launch, full native user environment,
provider authentication, TLS trust and live repeat-run proof belong to human
Checkpoint B after both preparation phases. Phases 3–8 cannot infer native
acceptance from these safety checks or old container evidence. Phase 1 execution
location, input revisions, command exits and limitations are recorded in
[host-isolation.md](host-isolation.md#native-phase-1-preparation-evidence).
