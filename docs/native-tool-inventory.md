# Native Tool Migration Inventory

Phase 1 inventories the checked-in `ai-agent-sandbox/Dockerfile`, both
`entrypoint.sh` and `guest-entrypoint.sh`, `bash_aliases.sh`, settings, every
script, the skill, and the prompt addon. Container contents and ignored staged
proposals are not the tool selection authority. The machine-readable
[toolchain manifest](../native/toolchain.json) owns exact releases, both Linux
architecture URLs/checksums, repository signing fingerprints, package sets,
helper ownership and validation inputs. The
[system provisioner](../scripts/provision-agent-vm-guest.sh) consumes it.

System and normal-user provisioning, helper adaptation and offline verification
are implemented. Follow [native user tools and Checkpoint B](native-user-tools.md)
for installation, trust, authentication and exact handoff commands. Human B and
native Phase 3 runtime verification passed on 2026-10-05; C–D remain pending.
This inventory is the durable parity contract; an assigned disposition alone
does not claim installation or acceptance.

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

The current Dockerfile and orchestration both select Helm **3.20.1**.
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

The manifest maps each of the 17 original commands to its `native_source`.
Portable resources live in `native/helpers/`; native CA and proxy adapters live
in `scripts/native/local_ca.py` and `scripts/native/proxy.py`. Shared Mint
container sources remain available, while the retired guest-agent entrypoint
and lifecycle sources were removed after native Phase 3 proof. Every command
gets an executable user wrapper that loads the same small environment fragment.
The read-only source/environment checker renders those wrappers under `tmp/`
and validates shell syntax and ShellCheck. The manifest's `reviewed_sources`
entrypoint list preserves the original Phase 1 migration provenance; it is not
a native runtime dependency and may name the retired guest entrypoint. Native
`ensure` diagnoses established ingress trust; only the explicit human trust
installer performs privileged imports. Optional proxy
wrappers refuse unidentified occupied listeners, keep TLS verification on and
use a separate human-initialized CA with process-scoped trust.

## Every Helper, Skill And Hook

All native helper installation/configuration is owned by the normal-user
installer in Phase 2, sourced from the reviewed workspace revision. Preserve
the commands; adapt container-specific paths and permissions in native-owned
sources without changing the executing container. Installation/offline checks
must not activate proxy listeners, generate/trust a proxy CA or contact a
provider. `--help` on a proxy wrapper currently starts its proxy, so use mocked
commands for its validation, not live help invocation.

| Checked-in source under `ai-agent-sandbox/` | Disposition, dependencies and validation |
| --- | --- |
| `scripts/ai-run.sh` | Preserve `ai-run` forwarding to handler/high wrapper; Bash + installed handler; shell/static checks and human B smoke |
| `scripts/codex-lean.sh` | Preserve explicit lean wrapper and `CODEX_MODEL`/effort handling; resolve user-installed Codex rather than relying on `/usr/local/bin/codex`; shell/static checks and human B provider smoke; plain Codex defaults remain upstream |
| `scripts/codex-with-proxy.sh`, `scripts/codex-max-with-proxy.sh` | Preserve optional proxy wrappers; native Python/socket + mitmweb + Codex lean; native paths and xhigh effort; shell/Python checks plus optional human inspection smoke |
| `scripts/claude-with-proxy.sh` | Preserve inspection-only launch; native Python/socket + mitmweb + npm Claude; shell/Python checks plus optional human inspection smoke |
| `scripts/claude-with-custom-system-prompt.sh`, `scripts/claude-45-custom-system-prompt.sh`, `scripts/claude-46-custom-system-prompt.sh` | Preserve optional prompt replacement/model selection; native Python/socket + mitmweb and addon; shell/Python checks plus optional human inspection smoke |
| `scripts/start-proxy.sh` | Optional foreground mitmweb UI; explicit activation, loopback bindings and reviewed trust in Phase 2; native Python + mitmweb; shell/static checks and optional human smoke |
| `scripts/mitmflows`, `scripts/mitmflow-detail`, `scripts/mitmflow-body`, `scripts/mitmflow-render.py` | Preserve inspection/render/export commands; Bash + Python stdlib urllib/JSON only, no mitmproxy Python import needed; shell/Python checks and optional human inspection smoke; exports remain repository `tmp/` |
| `scripts/ensure-budget-analyzer-local-ca-trust.sh`, `scripts/check-budget-analyzer-local-ca-trust.sh` | Preserve lazy exact-local-origin trust; native Python + OpenSSL/certutil; ensure/check are read-only, separate human installer uses scoped interactive sudo; static checks plus human B curl/Python/Node/Chromium trust matrix |
| `scripts/via-annotator.sh` | Preserve human foreground launcher, asset validation and strict 127.0.0.1 binding; Bash + sha256sum/Python http.server; shell/static checks and human B smoke; no service/background autostart |
| `scripts/statusline-command.sh` | Source exists but no Dockerfile COPY/active overlay activation; optional helper retained, adapt credential path/cache to normal home and repository `tmp/`; Bash, jq, curl/date/stat/awk and Claude version; shell/static checks, no OAuth read/network during installer |
| `system-prompt-addon.py`, `system-prompt.md` | Optional replacement, preserve required prefix/cache-control and ancillary-request pass-through; mitmproxy venv + Python JSON; Phase 2 native paths/dumps under repository `tmp/`; Python checks and optional human inspection smoke |
| `skills/save-conversation/SKILL.md` | Preserve explicit file-only skill installed for normal user; instructions remain workspace-owned; installation collision checks and static source equality; no startup invocation |
| `settings-overlay.json` | SessionStart emits project AGENTS.md; prompt suggestion/autoCompact controls. Phase 2 merges only explicitly selected workspace-owned settings without overwriting unrelated user configuration; focused repeat-install safety check |
| `bash_aliases.sh` | Preserve explicit model/effort/permission aliases through opt-in native alias fragment. Do not replace `.bash_aliases` or shell contents; append only the environment source line to Bash startup files, and leave aliases opt-in; plain agents retain upstream modes. Use shell/static checks and human B smoke for semantics |

The inventory deliberately preserves optional proxy, annotation and browser
capabilities even when the human chooses not to activate them. Permission-bypass
aliases are explicit choices; system provisioning neither selects them nor
relaxes AppArmor/native sandboxing.

## Dockerfile Environment And Startup Dispositions

| Source surface | Native disposition / validation |
| --- | --- |
| Ubuntu FROM digest, TARGETARCH and version ARGs | Native Ubuntu release/actual QEMU/KVM/architecture checks replace container image selection; manifest replaces binary ARGs. Transitional Dockerfile untouched |
| `CLI_CACHE_BUST`, npm `latest` | No cache-bust-dependent selection; exact user manifest inputs and explicit refresh |
| `DEBIAN_FRONTEND` | Only the human-run apt transaction is noninteractive; not a global user export |
| `SSL_CERT_FILE` | Phase 2 user environment points Python to combined system CA bundle, preserving public roots; B trust matrix |
| `JAVA_HOME`, `MAVEN_HOME`, `PATH` | Use signed OS JDK/Maven; Phase 2 resolves actual JDK path instead of recreating container `/usr/lib/jvm/zulu25` assumption. Include Go/user command prefix explicitly; fresh-shell version resolution proof |
| `PLAYWRIGHT_BROWSERS_PATH` | Ordinary user browser cache; no container `/opt/playwright-browsers` requirement. Phase 2 uses one consistent user location across CLI/library/browser validation |
| `NODE_EXTRA_CA_CERTS` | Plain native Node uses reviewed combined local/public trust configuration in Phase 2. Proxy wrappers activate only explicitly selected proxy trust; no proxy-only root export at install/startup |
| USER creation/rename, UID/GID ARGs, `NOPASSWD:ALL` | Do not reproduce. Validate existing normal account/home, preserve ownership and sudo policy; Docker membership remains explicit guest-root-equivalent authority |
| WORKDIR `/workspace`, ENTRYPOINT and CMD | Native process starts in human-selected guest checkout. No daemon/container lifecycle is needed for agent tools |
| `entrypoint.sh` recursive `chown`, repository `clone`, SSH `origin` rewrite | Retire those side effects; stop on collisions/missing guest-local sources. Human owns Git transfer; native installer never changes repositories/remotes |
| Historical `entrypoint.sh` / `guest-entrypoint.sh` handler `pipx --force --editable`, skills copy and overlay merge | Moved to explicit user installation, not every agent startup. Import-path/command checks remain repeatable; the Mint entrypoint remains and the guest entrypoint was retired after Phase 3 proof |
| Historical `guest-entrypoint.sh` guest origins, credential, Docker and kubeconfig checks | Migrated into the read-only native verifier; the container-specific entrypoint and kubeconfig path were removed after Phase 3 proof |
| Entrypoint banners/version reports/provider auth hints | User installer/verifier reports resolved versions. Human authenticates native provider at B; never import container credentials automatically |
| Dockerfile mitmdump first-run CA generation, `-k`, system proxy-root trust and pipx ensurepath | Retire install-time activation/TLS bypass. Optional proxy trust is separate reviewed workflow; Phase 2 preserves shell/config and does not run automatic ensurepath rewrites |
| `/workspace` creation/ownership, provider `.claude`/`.codex`/`.gemini` directories | Ordinary user's existing home/repositories; no recursive ownership repair, shell replacement or forced provider configuration |
| Mint compose/devcontainer and `setup-env.sh` | Retained until human Checkpoint D; they are not native daily agent launch tools. Retired guest lifecycle/Compose sources are absent and must not be recreated |

## Phase 1 Verification And Handoff

Run the tracked checks from the workspace root:

```bash
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest discover -s tests/native -v
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_manifest.py
bash -n scripts/provision-agent-vm-guest.sh
bash -n scripts/install-agent-vm-bwrap-profile.sh
bash -n scripts/prepare-agent-vm-native.sh
shellcheck scripts/provision-agent-vm-guest.sh scripts/install-agent-vm-bwrap-profile.sh scripts/prepare-agent-vm-native.sh
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile scripts/native/provision.py scripts/native/bwrap_profile.py tests/native/test_provision.py tests/native/test_native_preparation.py tests/native/check_manifest.py
git diff --check
```

The compact harness replaces privileged/download commands only where needed to
prove the safety boundary: wrong OS, container/non-VM execution, a remote
Docker endpoint, root or missing users and missing bootstrap commands reject
before sudo/downloads; checksum failure rejects before mutation; spaced paths
remain single arguments; and a repeat with healthy Docker performs no package
or restart operation. It deliberately does not emulate apt output, package
transactions, systemd, repositories or browser installation. Source parity
checks cover Dockerfile apt/COPY/ENV surfaces, the retained Mint entrypoint and
the retired guest entrypoint disposition,
all helpers, current orchestration tool contracts and documentation links.
Native pins are manual-review inputs; existing Renovate extraction/evidence
configuration is untouched.

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
