# Development VM And Native Agent Runtime

Budget Analyzer agents run directly as the normal development user in a
dedicated Ubuntu VM. Users may connect through SSH with any client or editor
that preserves the boundary documented here. VS Code Remote SSH with the
dedicated profile is the tested editor workflow, but it is not required.
Repositories and provider state live in the guest, and the VM boundary
separates agent processes from personal-host credentials and data. Guest Docker
is reserved for application workloads such as Kind and Testcontainers.

This repository owns native VM identity, the normal user/home, guest-local
repository topology, forwarded-authority rejection, guest Docker selection,
native tool versions, OS/NSS trust readiness and the complete read-only runtime
check. Orchestration owns application bootstrap and daily startup, the exact
local Kind target, Tilt, ingress-file validation and Kubernetes Secret
reconciliation. The
[Getting Started guide](../../orchestration/docs/development/getting-started.md#development-vm-native-workflow)
is the current end-to-end workflow. The
[personal-host isolation audit](host-isolation-audit.md) owns human-only
evidence collection, private topology review, the configurable live verifier,
policy handoff and protocol/persistence proof.

## Security Boundary

The personal host owns the VM definition, dedicated SSH key and configuration,
firewall policy, browser profile, GitHub publication credentials and local TLS
signing key. Keep these outside guest-writable paths.

The guest owns working clones, bare origins, provider authentication, build
caches, Docker state, Kind and Tilt. Agents may have broad authority inside the
guest, especially when they belong to the Docker group or use an explicit
high-authority launcher. Treat the complete VM as agent-compromise scope.

Do not forward an SSH agent, Git askpass helper, GitHub token, personal-host
Docker socket or credential store into the guest. Do not install GitHub
authentication or publishing extensions in any editor environment running in
the guest. GitHub publication remains a personal-host operation.

Host audit collection, live verification, host policy changes, reboot and
protocol testing are human-only. Workspace agents may review explicitly
supplied redacted evidence, but must not acquire host access, run live audit
tools or apply host configuration. Offline fixtures are not live evidence.

## Reference Configuration

The accepted setup uses an Ubuntu Server 24.04 QEMU/KVM VM named
`budget-analyzer-agent`, with guest project root `/srv/budget-analyzer`, Docker
data under `/var/lib/docker`, and a dedicated libvirt NAT network. The host SSH
profiles are `budget-agent-vm` and the separately selected
`budget-agent-vm-forward` for explicit forwarding.

Capacity, addresses and host storage locations are operator choices. They are
not installation inputs owned by this repository. Changes to the VM definition,
network, firewall or host SSH policy require human review.

## SSH Clients And Optional VS Code Profile

The host SSH profiles must retain strict host-key checking, the dedicated VM
identity, `IdentitiesOnly yes`, `ForwardAgent no`, `ForwardX11 no`, and no
automatic forwarding. Any SSH client or editor may use these profiles, provided
it does not weaken those controls or add credential, agent, socket or port
forwarding.

For the tested VS Code Remote SSH workflow, use the dedicated VS Code profile
and disable automatic and restored port forwarding. Also disable **Git:
Terminal Authentication** and **Git: Use Integrated Ask Pass**. Their setting
IDs are `git.terminalAuthentication` and `git.useIntegratedAskPass`; both must
be `false`. Close existing integrated terminals and open fresh ones after
changing these settings.

Connect with your chosen SSH client or editor and work under
`/srv/budget-analyzer/worktrees`. With VS Code Remote SSH, open that directory;
the extension host, terminals, tasks and language servers then run inside the
VM. In every new SSH-connected terminal, regardless of client, this command
must print nothing:

```bash
env | rg '^(SSH_AUTH_SOCK|GITHUB_TOKEN|GH_TOKEN|GIT_ASKPASS|SSH_ASKPASS)=' || true
```

## Native System And User Preparation

The human runs preparation from the normal guest OS account only after affected
workers have stopped:

```bash
cd /srv/budget-analyzer/worktrees/workspace
./scripts/prepare-agent-vm-native.sh
```

The runner performs system provisioning, scoped bubblewrap profile setup and a
repeat user-tools installation. It prompts for the existing bare-repository
parent and writes private logs under `tmp/native-preparation/`. Trust import,
provider authentication and the full tools verifier are separate explicit
human actions documented in
[Native Guest User Tools](native-user-tools.md#review-and-system-preparation).
Workers must not invoke the preparation or installation commands.

The provisioner requires Ubuntu 24.04 under QEMU/KVM, the selected normal
account's canonical home, matching architecture, an unset Docker endpoint
override and the default guest Docker context. It rejects root execution and
non-VM or container execution. It uses the human's existing sudo authorization;
it does not add a passwordless sudo rule.

Downloads, signing keys and checksums are verified in repository `tmp/` before
system writes. The provisioner retains matching releases and stops on
unexpected ownership, version or source collisions. Existing healthy guest
Docker workloads are preserved. A fresh VM may receive Ubuntu Docker and
Compose; a partial or unhealthy installation requires human repair.

Review exact ownership, versions and safety checks in
[Native Tool Inventory](native-tool-inventory.md), `native/toolchain.json`, and
the focused tests before changing preparation behavior.

## Canonical Native Runtime Contract

After human preparation and ingress trust are complete, use one workspace-owned
check for both first application bootstrap and daily startup:

```bash
./scripts/check-agent-vm-tools.sh \
  --worktree-parent "$BUDGET_ANALYZER_WORKTREE_PARENT" \
  --bare-parent "$BUDGET_ANALYZER_BARE_PARENT"
```

Both arguments are mandatory canonical absolute directories selected during
workspace preparation. The check proves the VM/user/home, repository,
forwarded-authority, guest Docker, manifest-owned native tool, managed user
environment and established OS/NSS trust contract. It is read-only and never
uses sudo, installs or repairs anything, authenticates a provider, changes
trust, or changes Docker and Kind. Read
[Native Guest User Tools](native-user-tools.md#canonical-read-only-native-runtime-contract)
before changing or diagnosing this interface. Keep application and exact
Kubernetes-target checks in orchestration.

## One-Time Repository Setup

Run the interactive repository setup from a reviewed personal-host checkout:

```bash
cd /path/to/common-parent
./workspace/scripts/setup-agent-vm-repositories.sh \
  --host-parent "$PWD" \
  --ssh-host budget-agent-vm \
  --guest-root /srv/budget-analyzer
```

The script discovers immediate child Git repositories, displays the exact
repository and branch set, and requires the literal confirmation `yes`. Each
host checkout must be clean, attached to a safely named branch and contain
local `main`. Existing `vm` remotes must already identify the selected SSH
alias and matching guest bare repository.

The command seeds guest bare repositories and working clones, then leaves each
guest clone with only its guest-local `origin`. It transfers committed Git
objects only. It does not copy uncommitted files, hooks, host Git configuration,
GitHub remotes, credentials or personal SSH state. Matching partial setup is
repeatable; the script provides no daily sync or publication behavior.

### Adding One Repository Later

From the personal host's common repository parent, pass the new repository
root to the focused entry point:

```bash
./workspace/scripts/add-agent-vm-repository.sh ./repository-name
```

This command deliberately has one input. It uses the accepted
`budget-agent-vm` SSH profile and `/srv/budget-analyzer` guest root, then applies
the same cleanliness, branch, confirmation, bare-origin and working-clone
rules as the initial setup. The host repository must have a local `main` branch
and a clean checked-out branch. The conventional organization repository name
`.github` is supported; its guest bare repository is `.github.git` and its
working clone is `.github`. Parent-based initial setup discovers it as well.
Other dot-prefixed repository basenames remain unsupported. Use the full setup
command above only when a different reviewed SSH alias or guest root is
intentional.

## Docker And Testcontainers

Leave `DOCKER_HOST`, `DOCKER_CONTEXT` and `TESTCONTAINERS_HOST_OVERRIDE` unset.
Native development processes use `/var/run/docker.sock`; Java Testcontainers
uses its Unix-socket strategy, and published test ports are reachable from the
guest OS. Diagnose selection with:

```bash
env | rg '^(DOCKER|TESTCONTAINERS)_' || true
docker context show
docker info --format '{{.Name}} {{.DockerRootDir}}'
test -S /var/run/docker.sock
```

The native verifier requires the default context, the guest Unix socket and
`/var/lib/docker`. Do not add `host.docker.internal`, a TCP or SSH Docker
endpoint, a nested daemon, or a host socket forwarded across the VM boundary.

## Branch Transfer

The one-time setup script is not a sync command. To transfer a host branch into
the guest, the human pushes to the VM remote and then explicitly updates the
guest working clone:

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

To transfer guest work back, publish the guest commit to its local bare origin,
then fetch and review it on the personal host:

```bash
# Guest working clone
git push origin feature-name

# Personal host checkout
git fetch vm refs/heads/feature-name:refs/remotes/vm/feature-name
git log --oneline --decorate HEAD..vm/feature-name
git diff HEAD...vm/feature-name
git merge --ff-only vm/feature-name
```

Only the personal host may push to GitHub or create a pull request. Never
force-push or automate publication from the guest.

## Application Startup And Rebuild

For daily work, open a fresh normal-user guest shell and run:

```bash
cd /srv/budget-analyzer/worktrees/orchestration
./scripts/bootstrap/check-agent-vm-prerequisites.sh --native-runtime
tilt up
```

Launch `codex`, `claude`, `gemini` or `ai-run` from the relevant guest working
clone. Agent exit and reentry are independent of Tilt, Docker and Kind.

For first bootstrap or an intentional clean application rebuild, follow the
[Getting Started guide](../../orchestration/docs/development/getting-started.md#development-vm-first-bootstrap).
Orchestration `./setup.sh` recreates Kind and is not a daily-start
command. Do not import host Docker state or move Docker data into a shared path.

For a fully clean environment, create a new reviewed Ubuntu VM, rerun native
preparation and repository setup, transfer only the approved TLS leaf, key and
public CA, and bootstrap from tracked configuration. Do not transfer databases,
Kind state, caches or VM snapshots into the replacement environment.

## Personal-Host Access

Workspace owns the explicit loopback-only SSH **host tunnel** from the personal
host to listeners on VM loopback. Orchestration owns **guest publication**:
application and operator endpoints made available from Kubernetes services or
processes on VM loopback. Application and cluster state, endpoint selection,
and publication health remain orchestration concerns.

`budget-agent-vm-forward` is the separately reviewed SSH host profile used as
the tunnel target. It supplies connection identity and boundary controls; it
does not establish a tunnel by itself and must retain no automatic
`LocalForward`. Every tunnel is an explicit foreground `ssh -L` operation from
the personal host. Keep it separate from agent and editor sessions. The host
tunnel carries only the selected TCP streams; it does not forward host SSH/Git
authority or certificate private keys, though browser traffic necessarily
traverses the encrypted tunnel.

### One-Time Narrow Host Authorization

Personal-host port 443 is privileged. The selected host user performs this
one-time setup on the personal host after reviewing the commands and without
broadening any path or mode. It installs `authbind`, rejects the broader
all-addresses port marker, and authorizes only that user to bind
`127.0.0.1:443`:

```bash
host_user="$(id -un)"
host_group="$(id -gn)"

sudo apt update
sudo apt install --yes authbind
sudo test ! -e /etc/authbind/byport/443
sudo install -o "$host_user" -g "$host_group" -m 0500 /dev/null \
  /etc/authbind/byaddr/127.0.0.1,443
sudo stat -c '%A %a %U %G %n' /etc/authbind/byaddr/127.0.0.1,443
sudo test ! -e /etc/authbind/byport/443
```

The `stat` result must identify the selected user and group, permission value
`500` (mode `0500`), and the exact
`/etc/authbind/byaddr/127.0.0.1,443` path. The broader
`/etc/authbind/byport/443` marker must not exist. Stop for human policy repair
if either check fails; do not replace this narrow grant with `authbind --deep`,
root-owned SSH execution, a capability grant to `ssh`, or a lower global
unprivileged-port threshold. Host policy application remains human-only.

### Default Application And Tilt Host Tunnel

After orchestration has started the application and Tilt in the VM, run this
on the personal host as the selected normal user:

```bash
authbind ssh -N -T -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:443:127.0.0.1:443 \
  -L 127.0.0.1:10350:127.0.0.1:10350 \
  budget-agent-vm-forward
```

This single foreground process carries application HTTPS and the Tilt UI.
Press `Ctrl+C` to stop both forwards. `ExitOnForwardFailure=yes` makes a
collision on either personal-host port prevent the combined host tunnel from
starting; resolve the collision rather than changing the loopback bindings or
restoring an automatic forward.

The personal-host resolver must map `app.budgetanalyzer.localhost` to
`127.0.0.1`. Apply that host-OS-specific setting outside the VM. The supported
application origin remains exactly `https://app.budgetanalyzer.localhost`;
never substitute HTTP or a TLS-verification bypass. Certificate creation,
three-file transfer, and guest trust are separate from transport and remain in
[Local Budget Analyzer TLS Trust](local-budget-analyzer-tls.md).

Use these checks on the personal host while the foreground tunnel remains
running:

```bash
ss -ltn '( sport = :443 or sport = :10350 )'
getent ahostsv4 app.budgetanalyzer.localhost
curl --fail --show-error --silent --output /dev/null \
  https://app.budgetanalyzer.localhost
curl --fail --show-error --silent --output /dev/null \
  http://127.0.0.1:10350/
```

The listener output must show `127.0.0.1:443` and `127.0.0.1:10350`; missing
listeners mean the host tunnel is absent or exited. Resolver output must
include `127.0.0.1`; correct the personal-host mapping if it does not. The
application request preserves hostname and certificate verification, so its
error distinguishes name resolution, connection, and certificate failures.
A successful application check alongside a failed Tilt request means the SSH
transport exists but Tilt is unavailable on VM loopback; diagnose Tilt through
orchestration rather than changing the host tunnel.

### Optional Observability Host Tunnel

Observability is not part of the default application/Tilt tunnel. First, in a
separate foreground VM shell, have orchestration establish the guest
publications:

```bash
cd /srv/budget-analyzer/worktrees/orchestration
./scripts/ops/start-observability-port-forwards.sh
```

While that helper remains running, start this separate foreground command on
the personal host:

```bash
ssh -N -T -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:3300:127.0.0.1:3300 \
  -L 127.0.0.1:9090:127.0.0.1:9090 \
  -L 127.0.0.1:16686:127.0.0.1:16686 \
  -L 127.0.0.1:20001:127.0.0.1:20001 \
  budget-agent-vm-forward
```

These ports are unprivileged, so this command deliberately does not use
`authbind`. Press `Ctrl+C` in each foreground process when finished. Keeping
observability separate prevents an optional port collision from taking down
application/Tilt access and avoids publishing observability surfaces when they
are not needed. Orchestration's
[Observability](../../orchestration/docs/architecture/observability.md#access)
owner document and foreground helper remain authoritative for component
identity, guest publication ports, authentication, health checks, and URLs.
