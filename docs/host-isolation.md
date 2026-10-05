# Development VM And Guest Agent Runtime

**Status:** COMPLETE — the operator confirmed on 2026-10-05 that all eight native
execution phases and human Checkpoints A–D passed, including Mint Docker
retirement. The canonical
[acceptance record](../../orchestration/docs/plans/agent-host-isolation-acceptance.md#native-human-acceptance)
attributes C/D completion to that confirmation; it is not a new agent inspection
of the personal host. Dated evidence below retains its original collection
state, including formerly pending checkpoints.
The completed migration used the
[execution plan](../../orchestration/docs/plans/agent-vm-native-execution-plan.md)
and [human checkpoints](../../orchestration/docs/plans/agent-vm-native-manual-plan.md).
Only preparation Phases 1–2 ran in the former guest container. Checkpoint B.3
deleted that container, its image and all old Docker volumes before the clean
rebuild. Phases 3–8 run natively; the selected final workflow has no agent
container. This repository owns its full tool installers and verifier.

The container procedures and original phase/checkpoint references below describe
the transitional implementation and prior evidence. They are not a second
active migration plan or a live runtime to recreate. Preserve the rebuilt
VM/Kind/Tilt state. Do not repeat completed destructive migration operations.
The new
[remediation plan](../../orchestration/docs/plans/agent-vm-security-review-remediation-plan.md)
owns the review fixes, CA/helper consolidation, transitional source cleanup
and additional host firewall review. That review remains open independently of
completed migration acceptance; follow the orchestration
[host audit runbook](../../orchestration/docs/runbooks/host-isolation-audit.md)
for human-only collection and privately reviewed evidence transfer.

This workspace retains retired container source pending reviewed cleanup:

- `.devcontainer/devcontainer.json` continues to select
  `ai-agent-sandbox/docker-compose.yml` and its pinned Docker-in-Docker feature.
  The operator confirmed Mint Docker retirement at Checkpoint D; do not launch
  this retained source. No native worker needs a personal-host SSH identity.
- Native Phase 3 removed the former guest-agent Compose files, entrypoint,
  environment example and lifecycle commands after proving native independence.
  The historical procedures and evidence below preserve their review context;
  do not recreate that runtime.

Never recreate or launch the retired guest Compose configuration against any
Docker daemon.

## Accepted Reference Configuration

The operator supplied this redacted setup for reproducibility. It is evidence,
not an automatically applied host configuration.

| Item | Accepted value |
| --- | --- |
| VM | `budget-analyzer-agent`; Ubuntu Server 24.04.5 LTS x86-64; 8 vCPU; 24 GiB RAM; QEMU 8.2.2/libvirt 10.0.0 |
| Disk | 200 GiB sparse qcow2 in host pool `agent-vm-images` at `/data/libvirt/agent-vm-images`; guest reported 172 GiB free |
| Guest project root | `/srv/budget-analyzer` |
| Guest Docker data | `/var/lib/docker` |
| Libvirt network | `agent-nat`; bridge `virbr1`; `192.168.231.0/24`; accepted guest address `192.168.231.10` |
| SSH aliases | `budget-agent-vm` and explicit-forward alias `budget-agent-vm-forward` |

The human-owned SSH key, installed SSH configuration, VM launch definition,
firewall policy, authbind authorization, and browser profile remain in trusted
host storage outside guest-writable paths. Repository examples are inert
reference material; changes require human review and explicit installation.
The `Budget Analyzer VM` VS Code profile is editor configuration only. It is
not a Docker profile or a Dev Container configuration.

The host SSH aliases must retain strict host-key checking, the dedicated VM
identity, `IdentitiesOnly yes`, `ForwardAgent no`, `ForwardX11 no`, and no
automatic forwarding. The dedicated VS Code profile must disable automatic and
restored port forwarding. In that profile, also disable **Git: Terminal
Authentication** and **Git: Use Integrated Ask Pass** so VS Code does not inject
its Git credential bridge into guest terminals. Their setting IDs are
`git.terminalAuthentication` and `git.useIntegratedAskPass`; both must be
`false` in the dedicated profile. Close every existing integrated terminal and
create new terminals after changing those settings; only then check that
`GIT_ASKPASS`, `SSH_ASKPASS`, GitHub token variables, and `SSH_AUTH_SOCK` are
absent. Connect with Remote SSH, then open
`/srv/budget-analyzer/worktrees`; the extension host, terminals, tasks, and
language servers run in the guest. Do not choose **Reopen in Container** from
that remote window or install GitHub authentication/publishing extensions.

In a newly created Remote SSH terminal, this command must print nothing:

```bash
env | rg '^(SSH_AUTH_SOCK|GITHUB_TOKEN|GH_TOKEN|GIT_ASKPASS|SSH_ASKPASS)=' || true
```

## Install Guest Prerequisites

The native system installer is preparation Phase 1 output, with reviewed inputs
in [`native/toolchain.json`](../native/toolchain.json), an implementation in
[`scripts/native/provision.py`](../scripts/native/provision.py), and tracked
[focused safety checks](../tests/native/test_provision.py). Review the full
[tool migration inventory](native-tool-inventory.md) before installation.
It assigns every Dockerfile/entrypoint/helper capability to system, user,
optional activation or deliberate retirement. The
[native user-tools guide](native-user-tools.md) supplies the normal-user
installer, read-only verifier and exact Checkpoint B commands. The live B.1
installation and completed B.2/B.3 handoff results are recorded below; final
C/D completion is recorded in the canonical acceptance record above.

The human runs this entry point only at Checkpoint B, after both preparation
phases and all workers have ended, from the normal guest OS user shell.
Do not run it in the authoring container or wrap the entry point in sudo:

```bash
cd /srv/budget-analyzer/worktrees/workspace
sudo -v
./scripts/provision-agent-vm-guest.sh --docker-user "$USER"
```

For the complete repeatable B.1 sequence, use the tracked
[`prepare-agent-vm-native.sh`](../scripts/prepare-agent-vm-native.sh) runner.
It also performs scoped bwrap profile setup and repeated user installation;
path selection, private logs and focused repair commands are owned by the
[native user-tools guide](native-user-tools.md#review-and-system-preparation).
Workers must not invoke this human installer workflow.

Bootstrap prerequisites are Ubuntu 24.04's Python 3.12, systemd VM detection,
sudo, curl, GnuPG, apt/dpkg and core system utilities; the provisioner stops if
they are missing. It requires actual QEMU/KVM detection and no container,
an existing canonical home owned by the selected normal account, matching
architecture, unset Docker endpoint override variables and a default local
Docker context. A marker alone cannot authorize it. Sudo uses the human's
existing authorization with `-n`; no passwordless sudo rule is installed.
Privileged Docker reads explicitly pin the verified Unix socket so root's
separate Docker configuration cannot redirect them to a remote daemon.

It installs missing manifest system packages and verified binaries, signed
Node 24/npm and Azul Zulu JDK 25, Go, compiler/build tools, inspection tools,
VIA assets and Chromium libraries. User agents, handler, browsers, mitmproxy,
helpers and shell/provider configuration belong to Phase 2. Before OS writes,
downloads and repository keys are verified in workspace `tmp/`. It stops on
version/ownership/source collisions rather than replacing an unexpected tool.
Release binaries already matching the manifest are retained.

Existing healthy Docker/Compose is inspected and preserved: no Docker apt
transaction, enable/start/restart, cluster recreation or runtime pruning. Only
a fresh VM without a Docker installation installs Ubuntu Docker/Compose and
enables the guest daemon. Partial/unhealthy installation requires human repair.
Missing apt packages are installed without upgrading existing packages;
simulation rejects dependency upgrades/removals after refreshing apt indexes,
pending dpkg configuration is rejected before writes, and needrestart is
limited to reporting. The installer checks running container
IDs/start times before and after. It requires `/var/lib/docker` and adds only
the selected user to the Docker group if needed. No CA/proxy activation,
repository chown, Git rewrite/clone or config replacement occurs. Installation
reports resolved binary and apt versions for the human handoff.

End the SSH session and reconnect if group membership changed. Do not use
`newgrp`, install a remote Docker context or move Docker data into a shared path.
Real apt/browser installation and repeat-run runtime preservation are human B
evidence; Phase 1 mock passes do not substitute for them.

## Native Phase 1 Preparation Evidence

Execution: 2026-10-04, existing guest preparation container, UID/GID 1000
(`vscode`), workspace checkout at `8222890f1696d7e4f7e204d6b1647e1ffed06fb6`,
initially clean. Orchestration was read-only and clean at
`c7e2580674b8311575457837d368344027e8488f`. The accepted native plan snapshot
SHA-256 is `feadfeb5d8c1d2d915352e6db438053bb95945d446230e880bf32e658668b75b`.
The prior attempt stopped on missing Checkpoint A. The current human-owned
[Native Preparation Handoff](../../orchestration/docs/plans/agent-host-isolation-acceptance.md#native-preparation-handoff)
now records COMPLETE and explicitly clears Phases 1–2. VM confinement,
credential boundary and paired firewall results are attributed to that human
record, not inferred from container names or marker files.

Read-only startup checks: workspace local bare origin, default Docker context,
`unix:///var/run/docker.sock`, `/var/lib/docker`, same-path guest working/bare
bind mounts, nonprivileged host-network guest agent and read-only guest
kubeconfig. Docker inspection used the discovered Compose container name;
the first `$HOSTNAME` lookup was not a Docker object and was corrected. No
cluster mutation or guest OS prerequisite checker ran inside the container.
The in-container `systemd-detect-virt` absence remains compatible with the
human's actual-VM evidence; native installation requires that tool on the OS.

Phase 1 artifacts: system entry point/stdlib engine, reviewed manifest,
tracked disposable fixtures and parity verifier, this procedure and
`native-tool-inventory.md`, README/AGENTS discovery and validation guidance,
and the dependency-doc native-manifest coverage boundary. No transitional
sandbox/Compose/devcontainer or sibling source changes were made.

Validation on 2026-10-04 (exit 0 unless noted):

| Command / review | Result |
| --- | --- |
| `PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest discover -s tests/native -v` | PASS, 36 disposable fixture cases; privileged/download commands mocked; final report `tmp/native-agent-installer/fixtures.log` |
| `PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_manifest.py` | PASS; 25 Dockerfile apt inputs, seven downloads on both architectures, 17 helper sources, current orchestration versions/checksums, ENV/startup dispositions and local links |
| `bash -n scripts/provision-agent-vm-guest.sh` / `shellcheck scripts/provision-agent-vm-guest.sh` | PASS; only changed shell file, no suppressions |
| `PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile scripts/native/provision.py tests/native/test_provision.py tests/native/check_manifest.py` | PASS |
| `./scripts/provision-agent-vm-guest.sh --help` | PASS, interface inspection only; report `tmp/native-agent-installer/help.txt`; no live installation invocation |
| Downloaded NodeSource/Azul keys through isolated GPG fingerprint parser; Go official release metadata and npm registry selection | PASS; reviewed fingerprints and both Go checksums/architecture filenames recorded in manifest; metadata scratch under `tmp/native-agent-installer/` |
| AGENTS checkstyle / portable paths / local links / `git diff --check`, including new-file whitespace checks | PASS; checkstyle read from orchestration's active owner doc; new instruction pointers keep version details in owner files |
| Existing dependency extraction / image evidence / Compose / service build suites | Not applicable: Renovate, workflow, Dockerfile, entrypoints, Compose, transport and service code are untouched; the native manifest remains an explicitly documented manual discovery surface |

Initial fixture failures (Unix-socket filename length and a mock's curl-version
dispatch) were fixed in the tracked fixture, then the suite rerun. There are no
unresolved or pre-existing validation failures in touched files. Final dirty
workspace inputs are the five modified tracked files and five new phase-owned
files shown by `git status --short`; no Git writes or runner-state changes.

Real installation, normal-user helpers/settings/aliases/trust, provider login
and browser/runtime verification remain Phase 2/human B work. Historical
container evidence is not native acceptance.

Boundary limitation: the first read-only signing-key inspection used GPG's
default home and created empty `.gnupg` bookkeeping in the authoring container
user home (directory, public keybox and trust database). No key was imported,
no CA was generated/trusted and no guest system trust store changed. Subsequent
inspection and the installer use a private GPG home under repository `tmp/`.
This outside-repository side effect is disclosed rather than treated as a
compliant work product; its cleanup is left to the human/container retirement.


## Native Phase 2 Preparation Evidence

Execution: 2026-10-04, same guest preparation container, UID/GID 1000
(`vscode`), workspace revision `8222890f1696d7e4f7e204d6b1647e1ffed06fb6`.
Starting dirty inputs were Phase 1's AGENTS/README/dependency/host-isolation
changes, system installer, native manifest/engine/fixtures and inventory; they
were preserved. Read-only sibling inputs: orchestration revision
`c7e2580674b8311575457837d368344027e8488f`, handler revision
`619cdd14f8568fbe40a6e8e821ab16fba95be6ca`. The accepted plan SHA256 remains
`feadfeb5d8c1d2d915352e6db438053bb95945d446230e880bf32e658668b75b`;
run ID `20261004T130118Z-phase-2-09d6b070-160a-4522-8791-94e20f7e1965`.
Runner state/outcomes and all sibling sources remained read-only.

Fresh read-only checks returned default Docker context,
`unix:///var/run/docker.sock` and `/var/lib/docker`; `findmnt` located the
sandbox sources on the guest ext4 same-path worktree mount. Repository
owner-controlled 0775 directories are accepted without permission repair.
VM isolation authority remains the human Checkpoint A handoff referenced above;
these observations alone do not prove the host boundary. No system/user-home
installation, trust change, CA generation, provider call/authentication,
container replacement or cluster mutation occurred.

Artifacts: normal-user installer and read-only verifier with identical path
inputs, separate explicit human ingress trust installer, native Python
installation/trust/proxy adapters, portable helper/skill/prompt resources,
tracked npm transitive integrity lock, conditional human bubblewrap profile,
tracked user/environment/helper fixtures, and
[native user-tools guide](native-user-tools.md) with exact Checkpoint B review,
installation/rerun, trust matrix, authentication, permissions, optional
inspection and native handoff commands. README/AGENTS/TLS/inventory owner
pointers were updated. Manifest adds Ubuntu `apparmor` for the human system
stage and native mappings for all 17 original helper commands. Existing
Dockerfile, entrypoints, Compose/devcontainer and transport remain untouched.
No system tool version changed.

Validation (all final commands exited 0):

| Command / review | Result |
| --- | --- |
| `PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest discover -s tests/native -v` | PASS, 76 cases: 36 existing system fixtures and 40 user/helper cases; report `tmp/native-phase-2/fixtures.log` |
| `PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_manifest.py` | PASS, Dockerfile/orchestration parity and local links; report `tmp/native-phase-2/manifest.log` |
| `PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_user_environment.py` | PASS, full npm integrity lock, all 17 native command mappings, 47 rendered/source shell files with `bash -n` and ShellCheck, source guards, links and new-file whitespace; report `tmp/native-phase-2/environment.log` |
| `PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile` on three new engines, two new fixture/check files, native flow renderer and prompt addon | PASS |
| All three new shell entry points `--help` | PASS, interface only; no live installation |
| AGENTS checkstyle, portable source/config paths, `git diff --check` | PASS; stable repository/Git/worker boundaries preserved; native-install exception is explicitly human-only |

Fixtures use disposable repository `tmp/` homes with synthetic credentials and
mocked installer/trust/provider/proxy commands. They prove repeated installation
without credential/config loss, paths with spaces/apostrophes, origin/owner/
credential rejection, fresh shell and noninteractive wrapper environment,
Bash/zsh source-line and settings/hook idempotence, handler import checks,
missing trust/browser prerequisites, CA import idempotence preserving public
roots, optional listener refusal/lifecycle/cleanup and scoped trust, lean/alias
model-effort/permission arguments, VIA bind/asset validation, flow HTTP/SSE/
WebSocket redaction/export boundary and addon prefix/cache/ancillary behavior.
No fixture uses the actual provider home or changes real trust. Initial fixture
syntax/mock-dispatch failures and an alias ShellCheck shell-identification issue
were corrected; no unresolved validation failure remains.

Decisions/limitations: plain provider commands retain upstream permissions;
existing explicit lean/custom wrappers retain their bypass flags. The handler's
high wrapper calls lean and therefore has full guest access, not a native OS
sandbox. Linux bwrap/seccomp mechanism was verified against current official
OpenAI documentation; loaded Ubuntu AppArmor policy and actual sandbox behavior
require human proof. Native ensure/check diagnose established trust and print
the exact human import command instead of acquiring sudo. Inspection is
installed but inactive; only a human can initialize a separate guest CA.
Occupied listeners are rejected because their identity/addon cannot be proved.

Live system/user/browser installation, provider login, verified HTTPS matrix,
loaded-policy/sandbox proof, old-agent stop and Native Execution Handoff remain
human Checkpoint B work. The companion is unchanged because this invocation
prohibits sibling writes; its B commands remain compatible and this workspace
owner guide supplies their exact missing detail. No later phase ran. End the
handler at the two-phase limit; Phase 3 must require the real human handoff.

The Phase 1 and Phase 2 tables above preserve the validation evidence produced
on 2026-10-04. After the B.1 debugging review, the current tracked suite was
reduced from broad package/helper emulation to nine focused installer-safety
tests plus the two static manifest/environment verifiers. The current harness
does not emulate apt output, package transactions, systemd, AppArmor parsing,
proxy lifecycle or trust-store mutation. The real B.1 run and later human smoke
checks are the integration evidence for those behaviors.

## Human Checkpoint B.1 Evidence

**Status:** COMPLETE on 2026-10-05. This subsection preserves the state at the
end of B.1; the subsequently completed B.2/B.3 evidence follows it.

The operator ran the reviewed scripts from the Ubuntu guest OS as `budgetops`
using `/srv/budget-analyzer/worktrees` and `/srv/budget-analyzer/bare`. System
provisioning completed with the selected Docker containers and start times
unchanged. The scoped `/usr/bin/bwrap` AppArmor profile installed, loaded and
passed its unprivileged namespace check. The first user installation stopped
before user-home mutation because the preflight treated the account's `0750`
home and private-group `0775` `.config` layout as shared writable state. The
source was corrected to accept group write only after verifying the account's
same-name private primary group; shared-group and world-writable paths remain
rejected.

Both the initial and repeated focused user-tool installations then completed.
Each run passed the Claude, Codex, Gemini, Playwright, mitmproxy and AI Session
Handler version checks, resolved the editable handler import from the selected
guest checkout, and verified browser/package/home and fresh-shell command
resolution. The repeat run preserved configuration and produced no duplicate
managed shell or hook failure. Python syntax validation and ShellCheck passed
for the changed native helper and B.1 shell entry points; no fixture tests were
run during this manual debugging cycle.

The preparation runner stopped at the original user preflight failure, so the
operator resumed with its documented focused user-installer command rather than
repeating successful apt and AppArmor work. This debugging worker remained in
the transitional guest container during the manual commands; the installer
recorded no container restart or start-time change. That deviation from the
preferred worker-exit ordering is retained explicitly and is not native runtime
acceptance. The full tools verifier intentionally remains deferred until B.2
establishes trust. Provider authentication, actual Codex sandbox proof, verified
HTTPS, old-agent shutdown and the Native Execution Handoff are not claimed.

Those items were still pending at the B.1 collection point. They subsequently
completed in B.2/B.3 and are recorded below; this historical B.1 limitation is
not being rewritten as earlier evidence.

## Native Execution Handoff Evidence

**Status:** COMPLETE on 2026-10-05; native Phase 3 is the next runner phase.
The orchestration
[acceptance record](../../orchestration/docs/plans/agent-host-isolation-acceptance.md#native-execution-handoff)
owns the complete redacted B.3 and human host-boundary evidence. This section
records the workspace-owned installer and native-runtime handoff.

| Evidence | Result |
| --- | --- |
| Installer sources and tracked preparation evidence | PASS — live installation report captured workspace base `faa63e9`; reviewed B.2/B.3 revisions are `42c0896` and `0195929`, with the latter clean before these evidence edits; Phase 1/2 records retain 36-case and 76-case fixture results and current focused-harness limitations |
| Handler and locked user-tool inputs | PASS — clean handler `619cdd1`, editable import from the guest-local checkout, reviewed npm-lock SHA-256 retained; installation report records the selected exact CLI/browser releases |
| Live system/user install and idempotence | PASS — system provisioning, scoped bwrap profile, corrected private-primary-group handling, initial user install and repeat user install completed without duplicate managed shell/hooks or unintended pre-cutover Docker restart |
| Native identity and command resolution | PASS — `budgetops`, home `/home/budgetops`, container detection `none`, VM detection `kvm`; native verifier passed for 13 repository pairs and fresh login resolved providers, Playwright, helpers and handler from `.local/bin` |
| Provider and permission mode | PASS — native Codex 0.160.0 with configured `gpt-5.6-sol`, high reasoning and explicit bypass/`never`/`danger-full-access` read and updated the guest checkout; this selected mode has full guest access |
| Sandbox mechanism distinction | PASS — scoped AppArmor profile and `codex sandbox -- sh ...` bubblewrap command passed separately; this proves mechanism availability but is not claimed for the selected unrestricted provider/handler mode |
| Native ingress trust | PASS — established host-published root remained unchanged; curl, Python, Node and headless Playwright/Chromium each returned verified HTTP 200 for the exact local HTTPS app; no TLS bypass, guest ingress CA or proxy CA was used |
| Repository/credential/runtime boundary | PASS — local working/bare pairs and editable handler origin verified; no SSH/GPG agent, GitHub token or askpass bridge; default Unix guest Docker, `/var/lib/docker`, loopback `kind-kind`, Ready node and healthy Tilt verified |
| Destructive cutover and rebuild | PASS — human-confirmed empty Docker container/volume state before rebuild; no old agent container, image, provider volume or other old Docker volume retained; only rebuilt Kind state now exists and the complete application smoke test passed |
| Runner and remaining work | PASS/READY — accepted plan hash unchanged and existing state selects Phase 3 in workspace; C must still prove browser/live updates/session lifecycle/reboot and repeated boundary checks, and D must return source and retire Mint Docker |

The live installation report records Claude 2.1.289, Codex 0.160.0, Gemini
0.62.0, Playwright 1.63.0, mitmproxy 12.2.3 and AI Session Handler 0.2.0.
The selected native Codex process explicitly used
`--dangerously-bypass-approvals-and-sandbox`, `approval_policy="never"`,
`sandbox_mode="danger-full-access"` and high reasoning. Docker-group access
also remains guest-root-equivalent. The next handler command intentionally uses
the same unrestricted high wrapper; neither this record nor the successful
bubblewrap fixture describes it as sandboxed.

The B.3 human reset removed every old container and named/anonymous volume and
pruned old images, cache and custom networks only after both empty-state checks
passed. No old Docker volume was retained. The clean guest-local bootstrap then
created the current Kind node and its new anonymous `/var` volume. Imported TLS
validation/Secret installation, required Tilt resources, direct HTTPS and the
full orchestration smoke-test umbrella passed. The edge verifier's GNU awk
portability defect was repaired in orchestration before the successful final
run; its focused result was 84/84 with a 176/176 nested hardening cascade.

The accepted execution-plan SHA-256 remains
`feadfeb5d8c1d2d915352e6db438053bb95945d446230e880bf32e658668b75b`.
`ai-session-handler status` selects `phase-3 Prove Native Workspace Execution`
with this `workspace` checkout as its execution workspace. The operator will
exit the current native provider session before starting that runner. Leave
Tilt running for Phase 3's before/after health checks.

## One-Time Repository Setup

Run this only from a reviewed personal-host checkout, never from the guest or
agent container:

```bash
cd /path/to/common-parent
./workspace/scripts/setup-agent-vm-repositories.sh \
  --host-parent "$PWD" \
  --ssh-host budget-agent-vm \
  --guest-root /srv/budget-analyzer
```

The script discovers every immediate child Git repository under the selected
parent, including `ext-authz` when present. It prints the resolved parent,
guest destination, complete repository set, and selected branches before
requiring the literal confirmation `yes`.

Each host checkout must be clean, attached to a safely named branch, and
contain local `main`. Basenames are restricted to safe characters and must be
unique. The guest root must already exist as the exact canonical writable path.
Symbolic-link repository children, parents, and destinations are rejected.
An existing `vm` remote must already equal the exact selected SSH alias and
guest bare path. The script refuses mismatched or unexpected refs and non-empty
invalid guest destinations, disables SSH agent forwarding, and uses ordinary
non-force Git pushes. It seeds `main` and the current branch, checks out that
branch in the guest clone, and leaves each guest clone with only a guest-local
`origin`.
Existing matching partial setup is repeatable; artifacts newly created by a
failed invocation are cleaned up when the guest remains reachable.

The transfer contains committed Git objects only. It does not copy uncommitted
files, host hooks, host Git configuration, GitHub remotes, tags as a mirror,
credentials, or personal SSH state. The script stops after setup and provides
no daily sync, commit, GitHub push, or publication behavior.

## Historical Guest-Agent Container Setup

This section preserves the former container procedure as migration evidence.
Its Compose, environment-example, entrypoint and lifecycle sources were removed
after native Phase 3 passed, so these commands are intentionally no longer
runnable. Daily agents start as ordinary native guest processes.

From a human-operated guest shell, review and create the ignored runtime file:

```bash
cd /srv/budget-analyzer/worktrees/workspace/ai-agent-sandbox
cp agent-vm.env.example agent-vm.env
id -u
id -g
getent group docker | cut -d: -f3
```

Set `AGENT_VM_USER_UID`, `AGENT_VM_USER_GID`, and
`AGENT_VM_DOCKER_GID` from those results. Keep the reviewed working and bare
parents under `/srv/budget-analyzer`. Before Kind exists, render and explicitly
build only the base configuration:

```bash
docker compose --env-file agent-vm.env \
  -f docker-compose.agent-vm.yml config
docker compose --env-file agent-vm.env \
  -f docker-compose.agent-vm.yml build agent
../scripts/agent-vm-container-start.sh --bootstrap-only
../scripts/agent-vm-container-shell.sh --bootstrap-only
```

The working and bare parents are mounted read/write at their identical guest
paths so Docker bind mounts and local Git origins resolve consistently. The
entrypoint discovers repositories instead of using an ecosystem inventory,
verifies their local origins without rewriting them, installs AI Session
Handler editably from the configured parent, and resolves trust and prompt
helpers from that same parent. Missing repositories are reported; startup
never clones from GitHub.

Authenticate only the selected AI provider inside the container—for example,
`claude auth login` or `codex login`. Do not authenticate `gh`, add a GitHub
remote, forward an SSH agent, or expose a host credential helper. Provider
configuration persists in guest-Docker named volumes and is guest-compromise
scope; it never comes from a personal-host mount.

After `./setup.sh --guest-local` creates Kind, run
`realpath "$HOME/.kube/config"` and set `AGENT_VM_KUBECONFIG` in
`agent-vm.env` to that exact absolute guest path. Do not use a literal `~`.
Then render both files and recreate the same service through the normal helper:

```bash
docker compose --env-file agent-vm.env \
  -f docker-compose.agent-vm.yml \
  -f docker-compose.agent-vm-kubeconfig.yml config
../scripts/agent-vm-container-start.sh
```

The override adds only that read-only kubeconfig. The base configuration starts
without any kubeconfig mount. Guest host networking is intentional: agent
`localhost` reaches guest Kind, ingress, Tilt, and test ports while the mounted
Unix socket remains the single Docker endpoint.

## Historical Agent Container Lifecycle Helpers

These retired guest-run commands shared one implementation and worked from any
current directory when invoked by path:

```bash
/srv/budget-analyzer/worktrees/workspace/scripts/agent-vm-container-start.sh
/srv/budget-analyzer/worktrees/workspace/scripts/agent-vm-container-stop.sh
/srv/budget-analyzer/worktrees/workspace/scripts/agent-vm-container-restart.sh
/srv/budget-analyzer/worktrees/workspace/scripts/agent-vm-container-status.sh
/srv/budget-analyzer/worktrees/workspace/scripts/agent-vm-container-shell.sh
```

Normal operation always loads `agent-vm.env`,
`docker-compose.agent-vm.yml`, and
`docker-compose.agent-vm-kubeconfig.yml`. Start, restart and shell therefore
fail until the exact absolute guest kubeconfig exists. Every command rejects a
remote Docker environment/context, requires the default guest Unix socket and
`/var/lib/docker` data root, validates the repository parents and Compose
service, and reports only the operation and mode rather than environment-file
contents.

`start` uses the existing image without rebuilding it. `stop` stops only the
agent service and preserves the named provider-configuration volumes;
`restart` does not rebuild; none of the helpers starts or restarts Kind, Tilt,
the VM, host forwarding, provider login, or repository transfer.

Only the pre-Kind bootstrap window may add `--bootstrap-only`, for example:

```bash
/srv/budget-analyzer/worktrees/workspace/scripts/agent-vm-container-start.sh \
  --bootstrap-only
/srv/budget-analyzer/worktrees/workspace/scripts/agent-vm-container-shell.sh \
  --bootstrap-only
```

That visibly selects only the base Compose file. Do not use it as the normal
daily path after Kind exists. An intentional image refresh remains a separate,
reviewed `docker compose ... build agent` operation; no lifecycle helper builds
an image.

## Docker And Testcontainers Discovery

Leave `DOCKER_HOST`, `DOCKER_CONTEXT`, and
`TESTCONTAINERS_HOST_OVERRIDE` unset. Native processes use
`/var/run/docker.sock`; Java Testcontainers falls back to its Unix-socket
strategy and published test ports are reachable from the guest OS. The native
verifier rejects a non-default context, inaccessible socket, non-guest Docker
data root, or endpoint override. Diagnose selection with:

```bash
env | rg '^(DOCKER|TESTCONTAINERS)_' || true
docker context show
docker info --format '{{.Name}} {{.DockerRootDir}}'
test -S /var/run/docker.sock
```

Do not add `host.docker.internal`, a TCP/SSH Docker endpoint, a nested daemon,
or a host socket forwarded across the VM boundary as a fallback.

## Daily Branch Transfer

The one-time script is not a sync command. For host-to-guest transfer, the
human pushes a named host branch to the VM, then the guest explicitly fetches:

```bash
# Personal host checkout
git push vm HEAD:refs/heads/feature-name

# Matching guest working clone
git fetch origin
if git show-ref --verify --quiet refs/heads/feature-name; then
  git switch feature-name
else
  git switch --track origin/feature-name
fi
git merge --ff-only origin/feature-name
```

For guest-to-host transfer, first publish the guest commit to its local bare
origin, then fetch and review it on the personal host:

```bash
# Guest working clone
git push origin feature-name

# Personal host checkout
git fetch vm refs/heads/feature-name:refs/remotes/vm/feature-name
git log --oneline --decorate HEAD..vm/feature-name
git diff HEAD...vm/feature-name
git merge --ff-only vm/feature-name
```

Only the personal host may then push to GitHub or create a pull request. Never
force-push, automate publication, or run GitHub authentication in the guest.

## Clean Rebuild

Treat guest runtime state as disposable. For a normal application rebuild,
stop Tilt, run the reviewed guest preflight, rerun `./setup.sh --guest-local`
from the guest orchestration clone, and reinstall frontend dependencies. Native
agents remain ordinary guest processes and need no recreation or kubeconfig
copy. That setup command deletes and recreates Kind; it is not a daily start
command.

For a fully clean environment, create a new Ubuntu 24.04 VM from the reviewed
host configuration, rerun the guest provisioner and one-time repository setup,
transfer only the approved TLS leaf/key/public CA, and bootstrap from reviewed
configuration. Do not export or import Mint/old-guest images, containers,
volumes, databases, Kind state, caches, or snapshots.

## Checkpoint A Handoff

The original container bootstrap ordered these steps: prove the Git round trip
and absence of GitHub authority; transfer
and validate only approved TLS files; launch and authenticate the guest agent
before Kind exists; run `./setup.sh --guest-local` and `npm install` from the
human guest shell; recreate the agent with the kubeconfig override; then start
Tilt and collect live-update/restart evidence. That procedure is historical;
follow the [native human checkpoints](../../orchestration/docs/plans/agent-vm-native-manual-plan.md)
for remaining work and do not repeat it on the healthy guest. The canonical guest
bootstrap command sequence remains in orchestration
[Getting Started](../../orchestration/docs/development/getting-started.md#development-vm-first-bootstrap).

No VM, repository transfer, package installation, Compose launch, certificate
operation, Kind/Tilt bootstrap, GitHub operation, or host configuration change
was performed during Phase 2.

## Historical Container Phase 3 Verification Record

Recorded 2026-10-04:

- The shared lifecycle implementation and five entry commands were exercised
  from outside the workspace with a disposable Compose fixture. Normal start,
  stop, restart, status and shell selected both Compose files; explicit
  bootstrap-only start and shell selected only the base file. The fixture
  confirmed no build, `down`, Kind or Tilt invocation, and preserved provider-
  volume, Kind and Tilt markers across stop/restart.
- Fail-closed fixture cases passed for a missing environment file, missing
  override, invalid kubeconfig, remote Docker environment, non-default context,
  non-Unix endpoint, unexpected Docker data root and missing `agent` service.
  Bash syntax and ShellCheck passed for every lifecycle script and its fixture.
- The redacted orchestration acceptance record was inspected. It records all
  13 selected guest working/bare repository pairs, a two-commit
  `checkstyle-config` host/guest round trip, absent guest GitHub authority,
  guest-local Docker and `kind-kind`, healthy Tilt/application resources, and
  a successful agent restart. It also records positive DNS/download and
  host-initiated SSH/Git controls plus IPv4/IPv6 native and Docker-path denials,
  one `docker0` and one `br-+` reject per `DOCKER-USER` family, and both
  persistence hooks. Host-reboot proof remains current Checkpoint C work.
- This implementation worker could not resolve the reviewed
  `budget-agent-vm` SSH alias and has no host SSH identity, as required by the
  current Mint-container credential boundary. No alternate credential,
  personal-host mount, direct-address bypass or host-Docker fallback was used.
  Consequently, Phase 3 did not directly reproduce in-agent repository/mount/
  credential checks, the disposable identity/add/delete/executable-bit Git
  round trip, disposable published-port and bind-path containers, uncached
  pulls, guest-local representative build/Tilt-file detection, or combined
  guest firewall probes. These are acceptance blockers, not inferred passes.
- The Java and frontend Remote SSH live-update checks were explicitly deferred
  at this historical collection point and remain current Checkpoint C work. No
  shared-folder watcher or fabricated save evidence was substituted.

## Native Phase 3 Execution Evidence

Execution: 2026-10-05, AI Session Handler run
`20261005T111830Z-phase-3-b3aa2059-9596-4a61-8cd5-9f11e6db647d`, native
`budgetops` process in the KVM guest, home `/home/budgetops`, workspace revision
`7ba4654e6961ba68b739e3b47832929968046dcc`, initially clean. The accepted plan
SHA-256 remained
`feadfeb5d8c1d2d915352e6db438053bb95945d446230e880bf32e658668b75b` and
the live handler status identified this Phase 3 attempt and this execution
workspace. PID 1 was systemd, container detection returned `none`, VM detection
returned `kvm`, and the process ancestry resolved through the native
`.local/share/budget-analyzer-native` Codex installation. No old agent worker,
container or image remained.

Native runtime results:

| Proof | Result |
| --- | --- |
| Fresh-environment native tool verifier | PASS before and after source cleanup; 13 local repository pairs, six pinned user tools, browser payload, exact ingress trust, fresh-shell commands and editable handler import from `/srv/budget-analyzer/worktrees/ai-session-handler/src/ai_session_handler` |
| Provider availability and selected mode | PASS; Claude 2.1.289, Codex 0.160.0 and Gemini 0.62.0 resolved from `.local/bin` without printing authentication state. The active handler command line explicitly selected bypass, `never` and `danger-full-access`; it is not sandboxed |
| Explicit sandbox profiles | PASS; current OpenAI permission-profile syntax `-P :workspace` allowed the fixture write, while `-P :read-only` rejected a deliberate write with exit 2/read-only filesystem and left no target. This proof is not attributed to the unrestricted handler |
| Credential and Git boundary | PASS; credential/askpass/agent variables, home credential files and forwarded SSH/GPG sockets were absent. System config had zero keys, global config had only identity keys, and all 13 effective configs had no credential/include/rewrite/extra-header/askpass/SSH-command/GPG keys; every fetch and push URL was its matching guest-local bare origin |
| Disposable Git transport fixture | PASS; two commits through a repository-local bare origin preserved synthetic author identity, one addition, one deletion and executable mode `100755`. No real repository write or external remote was used |
| Disposable Docker fixture | PASS with official `alpine:3.21.3` index digest `sha256:a8560b36e8b8210634f77d9f7f9efd7ffa463e380b75e2e74aff4511df3ef88c`; initial cache inspection was absent and pull output recorded new layer downloads. A named container read a read-only same-path bind and served the marker through `127.0.0.1:18083`; the container was removed. The first attempt established that this Alpine BusyBox omits `httpd`; its cleanup trap passed and the successful rerun used the image's `nc` applet |
| Verified application trust | PASS; native check plus curl, Python, Node and headless Playwright/Chromium each returned verified HTTPS 200 for the exact app origin. Browser routing blocked all other origins; no TLS bypass was used |
| Kind/Tilt preservation | PASS before and after fixtures; context `kind-kind`, loopback HTTPS API, cluster `kind`, node `kind-control-plane` Ready, only that node container running, and all 45 Tilt resources healthy. Docker stayed on the default Unix socket with `/var/lib/docker`; no cluster mutation occurred |

Workspace changes retire the tracked guest-agent Compose files, environment
example, guest entrypoint and six lifecycle scripts. The Mint Compose,
devcontainer, Dockerfile entrypoint and shared helpers remain; the Dockerfile no
longer copies the retired guest entrypoint. README, AGENTS, TLS, dependency and
native-tool owner docs now distinguish native daily execution from historical
container evidence. Static checks enforce that retired source stays absent and
that current `:workspace`/`:read-only` sandbox syntax stays documented.

Validation (final commands exited 0):

| Command / review | Result |
| --- | --- |
| `PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest discover -s tests/native -v` | PASS, 12 focused cases; report `tmp/native-phase-3/validation/fixtures.log` |
| `PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_manifest.py` | PASS, 25 apt inputs, seven downloads, 17 helpers, links and retired-source guard; report `tmp/native-phase-3/validation/manifest.log` |
| `PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_user_environment.py` | PASS, locked dependencies, 17 mappings, 49 shell files/wrappers, source guards and links; report `tmp/native-phase-3/validation/environment.log` |
| Python compilation, Bash syntax and ShellCheck commands from the native owner docs | PASS for all changed Python fixtures and all retained native shell entry points/helpers |
| `docker compose -f ai-agent-sandbox/docker-compose.yml config` | PASS; retained Mint service is `ai-dev`, report `tmp/native-phase-3/validation/mint-compose.yml` |
| `git diff --check`, AGENTS checkstyle and retired-source/dependency review | PASS; no Renovate extraction or evidence-workflow behavior changed |

The first fixture run exposed that disposable private paths inherited the native
account's `0002` umask while the mock identity did not model its verified private
primary group. The fixture now uses explicit private modes and models that group;
production ownership checks were not weakened. No package/user-tool install,
trust import, provider login, proxy activation, VM/cluster restart, application
bootstrap, sibling write, or Git write outside the disposable fixture occurred.
The ignored human-owned `ai-agent-sandbox/agent-vm.env`, if present, was not
deleted; no tracked runtime consumes it. Host firewall/reboot evidence and live
Remote SSH Java/frontend edits remain human Checkpoint C work, and Mint Docker
retirement remains Checkpoint D.
