# Development VM And Guest Agent Runtime

**Status:** Phase 2 static preparation and the lifecycle-helper implementation
are complete. The operator completed the Checkpoint A repository, credential,
TLS, bootstrap, stack-health and agent-restart checks; Java/frontend live-update
checks remain deferred to Checkpoint B. The original Phase 3 stopped at the
Mint-to-guest access gap recorded below. Remaining work now uses the separate
[VM continuation plan](../../orchestration/docs/plans/agent-host-isolation-vm-continuation-plan.md)
inside the guest agent, after its
[manual continuation handoff](../../orchestration/docs/plans/agent-host-isolation-manual-plan.md#continuation-handoff-start-the-vm-execution-plan).

This workspace keeps two deliberately separate environments:

- `.devcontainer/devcontainer.json` continues to select
  `ai-agent-sandbox/docker-compose.yml` and its pinned Docker-in-Docker feature.
  Keep Mint Docker available through Checkpoint B. Continuation workers run in
  the guest agent container; they do not need an SSH identity on Mint.
- `ai-agent-sandbox/docker-compose.agent-vm.yml` is selected explicitly on the
  development VM. It builds the shared tool image on the guest daemon, uses
  guest host networking, and mounts the guest Docker socket. Socket access lets
  the agent fully administer or destroy guest repositories and runtime state;
  the VM is the security boundary.

Never launch the guest Compose configuration against the personal-host Docker
daemon. It has no privileged mode, nested daemon, personal-host workspace,
home-directory, SSH-agent, host kubeconfig, credential-helper, or libvirt mount.

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

Run the one-time repository setup in the next section first. Then review the
provisioner and run it from a human-operated guest shell:

```bash
cd /srv/budget-analyzer/worktrees/workspace
./scripts/provision-agent-vm-guest.sh --docker-user "$USER"
```

It installs Ubuntu's Docker and Compose packages, Git, OpenSSL, ShellCheck, NSS
trust tools, Node.js 24/npm, and Azul Zulu JDK 25. It enables the guest daemon,
requires `/var/lib/docker`, and adds only the named guest user to the Docker
group. End the SSH session and reconnect after it succeeds. Do not use
`newgrp`, install a remote Docker context, or move Docker data into a shared
path.

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

## Configure And Start The Guest Agent

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

## Agent Container Lifecycle Helpers

These stable guest-run commands share one implementation and work from any
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
`TESTCONTAINERS_HOST_OVERRIDE` unset. The container uses
`/var/run/docker.sock`; Java Testcontainers falls back to its Unix-socket
strategy and published test ports are reachable through guest host networking.
The entrypoint rejects a non-default context, inaccessible socket, non-guest
Docker data root, or endpoint override. Diagnose selection with:

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
from the guest orchestration clone, reinstall frontend dependencies, and
recreate the agent with the exact regenerated kubeconfig. That setup command
deletes and recreates Kind; it is not a daily start command.

For a fully clean environment, create a new Ubuntu 24.04 VM from the reviewed
host configuration, rerun the guest provisioner and one-time repository setup,
transfer only the approved TLS leaf/key/public CA, and bootstrap from reviewed
configuration. Do not export or import Mint/old-guest images, containers,
volumes, databases, Kind state, caches, or snapshots.

## Checkpoint A Handoff

After repository setup and guest provisioning, follow
[orchestration Checkpoint A](../../orchestration/docs/plans/agent-host-isolation-manual-plan.md#checkpoint-a-set-up-repositories-and-bootstrap-the-guest)
in order: prove the Git round trip and absence of GitHub authority; transfer
and validate only approved TLS files; launch and authenticate the guest agent
before Kind exists; run `./setup.sh --guest-local` and `npm install` from the
human guest shell; recreate the agent with the kubeconfig override; then start
Tilt and collect live-update/restart evidence. Keep Mint Docker available
through Checkpoint B. Complete the manual continuation handoff before running
the remaining implementation inside the guest agent. The canonical guest
bootstrap command sequence remains in orchestration
[Getting Started](../../orchestration/docs/development/getting-started.md#development-vm-first-bootstrap).

No VM, repository transfer, package installation, Compose launch, certificate
operation, Kind/Tilt bootstrap, GitHub operation, or host configuration change
was performed during Phase 2.

## Phase 3 Verification Record

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
  persistence hooks. Host-reboot proof remains Checkpoint B work.
- This implementation worker could not resolve the reviewed
  `budget-agent-vm` SSH alias and has no host SSH identity, as required by the
  current Mint-container credential boundary. No alternate credential,
  personal-host mount, direct-address bypass or host-Docker fallback was used.
  Consequently, Phase 3 did not directly reproduce in-agent repository/mount/
  credential checks, the disposable identity/add/delete/executable-bit Git
  round trip, disposable published-port and bind-path containers, uncached
  pulls, guest-local representative build/Tilt-file detection, or combined
  guest firewall probes. These are acceptance blockers, not inferred passes.
- The Java and frontend Remote SSH live-update checks remain explicitly
  deferred to Checkpoint B. No shared-folder watcher or fabricated save
  evidence was substituted.
