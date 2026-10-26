# Native Guest User Tools

This guide owns human installation, trust, authentication and verification for
the normal development user in the Ubuntu VM. Run live installation commands
only after source review and after affected workers have stopped. Offline checks
alone do not establish the live VM state.

## Review And System Preparation

Privately preserve existing guest configuration. Review `git diff`, new files,
[native tool inventory](native-tool-inventory.md), `native/toolchain.json`,
`native/agent-tools.json`, `native/npm/package-lock.json`, and the native
installation entry points. The
system stage must complete first, including Chromium shared libraries/fonts,
JDK 25, Node 24, Python, pipx and bubblewrap. Preserve Docker, Kind, Tilt, all
application volumes and provider state. Do not run orchestration `setup.sh`.

The repeatable workflow lives in the tracked
[preparation runner](../scripts/prepare-agent-vm-native.sh). After source review
and all workers exit, run from the guest OS workspace checkout:

```bash
./scripts/prepare-agent-vm-native.sh
```

It derives this workspace's worktree parent and prompts for the existing bare
parent. For unattended path selection, pass `--bare-parent` and optionally
`--worktree-parent`; both must be canonical absolute directories. The runner
uses the normal guest user, validates sudo authorization, runs the system
provisioner and scoped bwrap profile installer, installs user tools, loads the
environment fragment, and repeats user installation. A repeatable
`--component NAME` limits both user-installation runs to those
[components](#components); system provisioning and the bwrap profile still run.
It stops on the first failure. Each invocation keeps a private log under
`tmp/native-preparation/prepare-*.log`; no operational source lives in `tmp/`.
Reruns retain the existing installations and unrelated configuration. Trust
import, provider login and the full tools verifier remain separate actions
below.

The individual tracked entry points remain available for focused repair.
From the guest OS workspace checkout:

```bash
native_worktree_parent=$(cd .. && pwd -P)
read -r -p 'Existing guest bare-repository parent: ' native_bare_parent
test -d "$native_bare_parent"
sudo -v
./scripts/provision-agent-vm-guest.sh --docker-user "$(id -un)" \
  --worktree-parent "$native_worktree_parent" --bare-parent "$native_bare_parent"
```

Reconnect if the system stage changed Docker-group membership. Run as the same
normal account; never put `sudo` before either user installer or verifier.
Provisioning, the bwrap profile installer, user installation, trust
installation and both verifiers run the shared
[VM boundary check](#pre-agent-vm-boundary-check) before anything else. First
provisioning treats missing Docker and Git as installable; partial Docker,
unsafe ownership or forwarded authority still stop it before any write.
The scripts derive home from the account database and reject containers,
non-QEMU/KVM machines, wrong owners, missing local clones/bare origins,
additional remotes/push URLs, Git credential helpers/includes/rewrites,
forwarded sockets, credential stores and endpoint/proxy overrides. Repositories
may retain their existing owner-controlled group-write mode. Managed home
resources reject world writes, symlinks and group writes unless the group is
verified as the account's same-name private primary group. No Git configuration
repair or recursive ownership change runs. Diagnostic errors never print Git
config values or credentials. Missing prerequisites stop the installer.

## Codex Sandbox Prerequisites

Current [official OpenAI guidance](https://learn.chatgpt.com/docs/agent-approvals-security#os-level-sandbox),
fetched on 2026-10-04, states that Linux uses bubblewrap and seccomp by default.
The official page establishes the Linux mechanism; it does not prescribe the
Ubuntu profile below. This is workspace's narrowly scoped Ubuntu setup for the
kernel's restricted unprivileged-user-namespace setting.

When the restriction is `1`, keep Ubuntu's packaged `/etc/apparmor.d/bwrap`
profile if present. If it is absent, review the workspace
[profile](../native/apparmor/bwrap). The tracked
[bwrap installer](../scripts/install-agent-vm-bwrap-profile.sh) installs only
that missing profile, loads it and runs an unprivileged namespace smoke check.
The preparation runner invokes it automatically after system provisioning. For
a focused human rerun from the guest OS:

```bash
native_worktree_parent=$(cd .. && pwd -P)
read -r -p 'Existing guest bare-repository parent: ' native_bare_parent
sudo -v
./scripts/install-agent-vm-bwrap-profile.sh --docker-user "$(id -un)" \
  --worktree-parent "$native_worktree_parent" --bare-parent "$native_bare_parent"
```

The installer reuses the system provisioner's shared VM boundary check,
ownership and guest Docker checks, rejects profile symlinks, and requires
AppArmor to be enabled when the restriction is active. Existing profile bytes
are preserved. If an identical workspace profile exists but the namespace
check fails, it retries loading that reviewed profile; a distribution/custom
profile needing reload remains a private human review. A failed smoke check
stops rather than changing the global restriction. Repeated successful runs
do not rewrite or reload an already working profile, reboot the VM, or change
Docker workloads. No restriction means only the namespace check runs.

The profile grants user namespaces to `/usr/bin/bwrap`; it does not disable
AppArmor, change the global user-namespace sysctl, add sudoers permissions or
attach to other programs. Reload an existing distro profile only after private
review. The `base` component checks for the profile when the kernel restriction
is active; loaded-policy and real command sandbox proof remain human gates.

After user installation, test plain Codex's actual Linux sandbox without a
provider call from workspace `tmp/`:

```bash
mkdir -p tmp/native-sandbox-proof
cd tmp/native-sandbox-proof
codex sandbox -P :workspace -- sh -c 'printf "native sandbox command passed\n"'
cd ../..

test ! -e tmp/native-sandbox-proof/read-only-denied
if codex sandbox -P :read-only -C tmp/native-sandbox-proof -- \
  sh -c 'printf "must not exist\n" > read-only-denied'; then
  printf 'ERROR: read-only sandbox allowed a write\n' >&2
  exit 1
fi
test ! -e tmp/native-sandbox-proof/read-only-denied
```

The explicit built-in profiles follow current
[OpenAI permission-profile guidance](https://learn.chatgpt.com/docs/permissions).
Inspect installed CLI help/config if the syntax changes; do not substitute a
permission bypass to claim sandbox acceptance. Run the native provider probe in
the mode actually selected and record that mode with the installation evidence.

## Install User Tools And Environment

After reconnecting, derive paths again in the guest workspace checkout:

```bash
native_worktree_parent=$(cd .. && pwd -P)
read -r -p 'Existing guest bare-repository parent: ' native_bare_parent
./scripts/install-agent-vm-user-tools.sh \
  --worktree-parent "$native_worktree_parent" --bare-parent "$native_bare_parent"
. "$HOME/.config/budget-analyzer-native/env.sh"
./scripts/install-agent-vm-user-tools.sh \
  --worktree-parent "$native_worktree_parent" --bare-parent "$native_bare_parent"
```

Add a repeatable `--component NAME` to either run to install only those
[components](#components). The second run retains installed packages,
configuration, credentials and the single managed hook/shell line. A rerun
after a reviewed Playwright lock or mitmproxy version change converges those
installations, as described below. Chromium installation
is rechecked by the pinned Playwright installer, which installs the browser the
locked version selects. Repeat runs keep installed provider CLI versions. Trust is not required to finish user tool installation; the
full read-only verifier requires established system/NSS trust after the next
section. Installation does not authenticate, launch proxies or generate CAs.

### Components

Installation and verification are scoped to five components declared in
`native/agent-tools.json`. Every managed file, installed command, setting, home
path, environment key and check belongs to exactly one of them:

| Component | Owns |
| --- | --- |
| `base` | System packages, Node/npm, JDK and download releases, the bwrap AppArmor gate, the environment fragment and shell startup line, npm configuration, opt-in aliases and the shared boundary/installer modules |
| `claude` | Claude Code, the settings overlay merge, the conversation skill, `claude-lean` and its system prompt, and the `CLAUDE_CONFIG_DIR` check |
| `codex` | Codex CLI, `codex-lean` and the `CODEX_HOME` check |
| `gemini` | Gemini CLI and the `GEMINI_CLI_HOME` check |
| `extras` | AI Session Handler and its checkout requirement, `ai-run`, proxy and mitm helpers, mitmproxy, Playwright with its lock, Chromium apt packages and `PLAYWRIGHT_BROWSERS_PATH`, the statusline, `via-annotator` and the local CA trust helpers |

With no `--component`, `install` and `check` cover every component in that
order. The VM boundary always runs first; if it fails, no component runs and
the command fails for every selection. Each component then checks the shared
trust-environment conflict rule and only its own other prerequisites, writes
only its own files and records, and reports `PASS` or `FAIL`; the command exits nonzero if any selected component failed, after
reporting all of them. A component that is not selected is left untouched, not
uninstalled. Fresh-shell command resolution covers only the selected
components' commands.

The trust-environment rule is declared once, as `trust_environment` in
`native/agent-tools.json`: `SSL_CERT_FILE`, `NODE_EXTRA_CA_CERTS` and
`REQUESTS_CA_BUNDLE`, which the base fragment exports. Every component's
`install` and `check` fail when one of them is set in the caller's
environment to anything other than the managed system bundle, and report only
the key name. Unset or managed values pass. The proxy launchers set their
inspection bundle only in the provider child's environment after the boundary
passes, so they do not trip this rule. Run checks from a normal shell; inside
a proxied provider session the boundary already rejects the inherited proxy
variables.

The non-base components require only that `base` has been installed (its
state record and environment fragment exist), because every `.local/bin`
wrapper sources that fragment; a stale `base` does not block them. Provider
launches and provider checks do run the installed base `boundary.py`
([launch enforcement](#provider-launch-enforcement)), so refresh `base` before
the providers when the boundary changes. A provider's
check never requires an extra: `claude-lean --proxy` uses the optional
`claude-with-proxy` from `extras`, but the `claude` check does not. Installing
the trust helpers does not require trust; the `extras` check does.

The reviewed `native/npm/package-lock.json` is the Playwright-only project; its
reviewed SHA-256 is pinned once, in `tests/native/test_install_inputs.py`.
It is the single source of Playwright's version, integrity and tarball. The
focused input checker validates every locked package's registry HTTPS URL and
SHA-512 integrity, that `package.json` names the same exact Playwright version,
that the separately reviewed `chromium_apt_source` in `native/toolchain.json`
names the locked version, that no provider CLI enters the project, and
required-input Git ignore/publication state. Before publication,
its `proposed` mode builds a disposable source-only tree from tracked
working-tree source plus explicitly reviewed uncommitted required inputs. That
proves proposed closure, not committed-source availability. After the human
commits the reviewed change, run the `committed` mode and require its true
`git archive HEAD` proof before reporting that an ordinary Git transfer is
reproducible.

One normal development home owns `.m2/repository`, `.gradle`, `.claude`, `.codex`,
`.gemini`, `.pki/nssdb` and `.cache/ms-playwright`. Do not import provider state
from another environment. Managed tools live under `.local/share/budget-analyzer-native`:
locked local npm packages, dedicated pipx environments, portable helper resources,
private inspection resources only if human-created, and an installation report.
Commands in `.local/bin` source the small environment fragment themselves, so
noninteractive handler workers do not depend on interactive aliases or shell
startup. Existing Bash startup files receive one source line; login and Remote
SSH Bash terminals use the same fragment. For a zsh login account the installer
also appends that line to `.zprofile`/`.zshrc`, preserving existing contents.
The fragment uses POSIX shell syntax; startup files are never replaced with an
entire managed shell configuration. It resolves `JAVA_HOME` from installed `javac`, sets Maven's
system home, consistent browser/package paths and the combined system CA bundle
for Python, requests and Node. It exports no proxy or credentials.

Claude configuration merges only `promptSuggestionEnabled` and
`autoCompactEnabled` from the reviewed overlay. Other settings,
permission/model choices and user hooks survive. The file-only conversation
skill is retained byte-for-byte. An unrelated existing skill/command, changed
managed resource, symlink or altered npm lock stops for private human review.

Each component keeps its own records under
`.local/share/budget-analyzer-native/state/<component>/`: `managed-files.json`
(digests of the files it manages) and `installation.json` (workspace revision
and dirty paths, home/user and repository parents). The `extras` report adds
the handler revision, npm-lock SHA256, Playwright and mitmproxy versions and
resolved mitmproxy dependencies; each provider report adds its resolved
version. There is no migration from earlier combined records; the human
installs agent tooling from a clean state.
The handler is editable from the local checkout; the verifier checks its import
origin, global command resolution and both high wrapper help commands. Ordinary
source edits remain visible; handler dependency/entry-point changes require an
explicit human pipx reinstall after review. After adding a reviewed console
script, stop affected workers and run this from a fresh shell before rerunning
the user installer:

```bash
pipx reinstall ai-session-handler
```

mitmproxy's exact top-level release is pinned;
pipx resolves transitive PyPI dependencies on install and records them.
Reruns retain that environment until the declared version differs from the
`mitmproxy_version` in the last successful `extras` installation record; the
installer then uninstalls only the managed mitmproxy pipx environment and
installs the declared release. The Playwright project uses the tracked full
integrity lock with `npm ci`, isolated config/cache and verified HTTPS, and
never touches the provider prefix. Reviewed npm lifecycle scripts may compile
their locked optional dependencies. When the reviewed lock differs from the
`npm_lock_sha256` in that record, a rerun copies the new `package.json` and
lock and runs `npm ci`, which replaces the managed `node_modules` wholesale;
`playwright install chromium` then installs the newly selected browser. The
record is written only after a successful run, so an interrupted refresh
converges on the next rerun. The lock, `package.json` and the Chromium apt
inputs in `native/toolchain.json` are still reviewed together before merge.

### Provider CLIs

Claude Code, Codex CLI and Gemini CLI float. Each is an npm global package in
the managed provider prefix `.local/share/budget-analyzer-native/providers`,
separate from the Playwright project in `.local/share/budget-analyzer-native/npm`;
npm global installs keep each package's dependency tree separate. The user
installer installs a missing provider at `@latest` with registry HTTPS, npm
integrity verification on and no `sudo`; it never resolves a newer version for
an installed provider during routine preparation. The `.local/bin` wrappers and
proxy adapters launch providers from the prefix's `bin` directory, including
the `CODEX_REAL_BIN` path that Codex proxy commands pass to `codex-lean`. Every
provider launch first passes the
[VM boundary](#provider-launch-enforcement).

To update one provider, stop its workers and run, from a fresh shell:

```bash
./scripts/install-agent-vm-user-tools.sh \
  --worktree-parent "$native_worktree_parent" --bare-parent "$native_bare_parent" \
  --update-provider codex
```

`NAME` is `claude`, `codex` or `gemini`. Other providers and the Playwright
project stay unchanged. With `--component`, the updated provider's component
must be selected. That provider's `state/NAME/installation.json` records its
resolved version. Verification checks presence, `--version` exit status, ownership,
containment in the managed package and fresh-shell resolution, not a version
match.

### Claude Settings Replacement

A separate, human-run script makes `~/.claude/settings.json` match the reviewed
file `native/helpers/claude-settings.json`. It is not an installed command and
not a manifest entry, and it is independent of the user installer:

```bash
python3 scripts/native/claude_settings.py check    # read-only: 0 equal, 1 differs, 2 unreadable/invalid
python3 scripts/native/claude_settings.py apply
```

`apply` is idempotent. If the parsed JSON already equals the canonical file it
prints "already up to date" and changes nothing. Otherwise it copies the existing
file to `settings.json.bak-YYYYmmddTHHMMSS` beside it, then atomically replaces
it with the canonical content (mode `0600`). A missing file is created without a
backup; a symlink or non-regular target is refused. Use `--settings-path PATH`
to target another file.

This is a full replacement: keys not in the canonical file are dropped, so edit
`native/helpers/claude-settings.json` to keep a new setting. It removes the
legacy `SessionStart` hook, so Claude Code's native `AGENTS.md` loading is the
only source and the text appears once. It also sets the default model to Claude
Code's `opus` alias. The installer's overlay merge
(`promptSuggestionEnabled`, `autoCompactEnabled`) leaves the replaced file
unchanged, so the two do not conflict.

The canonical file points `statusLine` at the installed `statusline-command`
helper (`native/helpers/statusline-command.sh`), so run the user installer
before `apply` so the command exists. The helper reads only the status line JSON
on stdin and prints one line: the directory (`$HOME` shown as `~`), model,
`ctx N%`, `5h N% (reset)` and `7d N% (reset)`, with resets as relative durations
(`XdYh`, `XhYm`, `Ym` or `now`). A segment whose value is missing or null is
omitted (for example `5h`/`7d` without plan rate limits, or `ctx` before the
first response); an unparsable reset time keeps the percentage without the
parenthesized duration. It makes no network calls and reads no credentials. See
[Lean Claude Launchers](launch-options.md#lean-claude-launchers) for the
launch side.

## Pre-Agent VM Boundary Check

Before agent work, after a VM reboot and when diagnosing isolation, run the
boundary check from the workspace checkout as the normal development user:

```bash
./scripts/check-agent-vm-boundary.sh \
  --worktree-parent "$BUDGET_ANALYZER_WORKTREE_PARENT" \
  --bare-parent "$BUDGET_ANALYZER_BARE_PARENT"
```

Before user installation has exported those variables, pass the same canonical
parents used for preparation. Both arguments are required. The check is
read-only: it never uses sudo, installs, repairs, authenticates or changes Git,
trust or Docker state. A nonzero result means agent work must not start; repair
the reported state privately and rerun the check.

Success proves only the VM boundary:

- Ubuntu 24.04 running directly under QEMU/KVM, not in a container, as the
  canonical normal account with a matching `HOME`. The home must not be
  world-writable or have unsafe group write.
- No forwarded credential socket, token, askpass, Git configuration
  injection, proxy, TLS bypass or Docker/Testcontainers endpoint override, and
  no `~/.git-credentials` or `~/.netrc`.
- Canonical repository parents that contain this workspace checkout. Every
  guest working clone has only a matching guest-local bare origin and no
  credential/include/rewrite/forwarding Git configuration.
- The default Docker context, `unix:///var/run/docker.sock`, a real guest Unix
  socket and the `/var/lib/docker` data root. Missing guest Docker fails.

It does not require provider CLIs, agent helpers, AI Session Handler,
platform binaries, an orchestration checkout or any other sibling checkout.
Orchestration does not invoke it, and orchestration's own setup and startup
checks do not depend on it. Those belong to the full
verifier below. The boundary check is not an alias for `check --component
base`; every component selection runs it first. `scripts/native/boundary.py` owns these rules, and
the system provisioner, bwrap profile installer, user installer, trust
installer and full verifier run them first. During first provisioning, missing
Docker or Git is treated as installable. Partial Docker installations,
unhealthy existing Docker, unsafe ownership, symlinks and forwarded authority
still fail before any write.

### Provider Launch Enforcement

Every workspace-managed provider launch runs the same `VmBoundary` rules before
the provider starts, and fails closed. A forwarded agent, credential store,
injected Git configuration, proxy variable or non-guest Docker endpoint then
blocks the launch without relying on the manual check:

| Launch path | Guard |
| --- | --- |
| `claude`, `codex`, `gemini` in `.local/bin` | The wrapper sources the environment fragment, then runs the installed base `boundary.py` with `BUDGET_ANALYZER_WORKTREE_PARENT` and `BUDGET_ANALYZER_BARE_PARENT`, and `exec`s the provider only on success |
| `claude-lean` | Starts Claude only through the guarded `claude` wrapper or `claude-with-proxy` |
| `codex-lean` | Its wrapper runs the same guard, then pins `CODEX_REAL_BIN` to the managed `codex`, so an inherited value cannot select an unchecked binary |
| `claude-with-proxy`, `codex-with-proxy`, `codex-max-with-proxy` | `proxy.py` runs the boundary in-process before it starts mitmweb, sets proxy or trust variables (`SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`, `NODE_EXTRA_CA_CERTS`) or starts a provider |
| AI Session Handler wrappers and `ai-run` | Resolve `codex-lean` or `claude-lean` through `PATH`, so they reach the guards above |

The installed copy lives in the native root, not a workspace clone. It
therefore requires the selected workspace checkout to exist instead of
requiring that it runs from that clone; every other rule is unchanged. On
success it writes nothing to stdout or stderr, so handler and `codex exec`
output parsing is unaffected. On failure it writes the boundary reason to
stderr, exits nonzero and never prints Git configuration, environment values
or credentials. There is no bypass switch, cache or "already checked" marker;
each launch reruns the check, whose cost grows with the number of local
repositories.
`check_provider` runs `.local/bin/NAME --version`, so provider verification
exercises the guard. `start-proxy`, Playwright, mitmproxy tools, trust helpers,
`via-annotator` and the statusline are not provider launches and are not
guarded.

The guard protects against human misconfiguration, not a compromised agent,
which can already edit its own home. Keep running the manual check above to
diagnose a blocked launch and before work started outside these launchers.
New wrappers take effect only after the human reinstalls the user tools.

## Canonical Read-Only Native Runtime Contract

`scripts/check-agent-vm-tools.sh` is the workspace's full native runtime
verifier. Orchestration does not invoke it. From the reviewed workspace
checkout, after native preparation and exact ingress trust are complete, run:

```bash
./scripts/check-agent-vm-tools.sh \
  --worktree-parent "$BUDGET_ANALYZER_WORKTREE_PARENT" \
  --bare-parent "$BUDGET_ANALYZER_BARE_PARENT"
```

The two explicit arguments are required canonical absolute directories. They
identify the reviewed guest working-clone parent and its existing guest-local
bare-repository parent; the verifier does not guess or repair either path.
Add a repeatable `--component NAME` to check only those
[components](#components), for example after updating one provider.

Without `--component`, success proves the complete workspace-owned runtime
contract, starting with the [VM boundary check](#pre-agent-vm-boundary-check):

- Ubuntu 24.04 running directly under QEMU/KVM, with the canonical normal
  account home and safe ownership.
- No forwarded credential socket, token, askpass, Git configuration injection,
  proxy, TLS bypass or Docker/Testcontainers endpoint override.
- Standalone guest-local working clones with only matching guest-local bare
  origins and no credential/include/rewrite/forwarding Git configuration.
- The default Docker context, `unix:///var/run/docker.sock`, a real guest Unix
  socket and `/var/lib/docker` data root.
- Every component: no conflicting `SSL_CERT_FILE`, `NODE_EXTRA_CA_CERTS` or
  `REQUESTS_CA_BUNDLE`, also under `--component`.
- `base`: all manifest packages, Node major 24, npm 10 or newer, JDK/Javac
  major 25, exact manifest download releases and current shared environment
  files.
- `claude`, `codex`, `gemini`: each present, owned provider CLI at its floating
  version with its own current settings, skill and launchers.
- `extras`: Chromium apt packages, the reviewed AI Session Handler checkout,
  exact Playwright and mitmproxy releases, Playwright Chromium, current helper
  resources and read-only exact ingress OS/NSS trust verification.
- Fresh-shell command resolution for every component's commands.

The verifier performs no writes. It never invokes sudo, installs packages,
mutates trust, authenticates providers, edits Git configuration, repairs
repositories, or changes Docker, Kind or application state. A nonzero result is
a failed prerequisite for agent work in the reported component; use the
reported human preparation or trust procedure after workers stop. Do not weaken
the contract to permit an application-only Node baseline or partial credential
check, and do not report a component selection as the full check.
`native/toolchain.json` remains the sole system version inventory and
`native/agent-tools.json` the sole agent-tool capability and component
inventory; the lock
owns the Playwright version.

## Refresh Installed User Resources

`native/helpers/` is the canonical location for helper, settings, prompt and
skill resources. The agent-tool manifest maps installed command names directly to those
sources or to the native adapters under `scripts/native/`.

After the reviewed source is transferred and every affected worker has ended,
the human must rerun the focused normal-user installation sequence in
[Install User Tools And Environment](#install-user-tools-and-environment),
including its repeat run. That refresh converges the installed manifest,
settings overlay and helper resources, then proves idempotence. To refresh only
the affected components, pass `--component NAME` to both runs. Files recorded
by a component's previous installation but no longer managed by any component
are removed only when their recorded digest still matches; a modified, symlinked or out-of-home retired
path stops the refresh for private review before anything is removed. Do not rerun
system provisioning solely for this source refresh, and do not remove provider
state or the human-created optional inspection directory.

Afterward, run the read-only tool verifier from a fresh shell. If the separate
trust installation is incomplete, complete the human trust procedure in the
next section before the full verifier. Repository fixtures do not update the
live home and are not evidence that the refresh occurred.

## Establish Exact Ingress Trust

First validate the three existing human-transferred TLS inputs, without
changing Kubernetes or creating certificates:

```bash
"$native_worktree_parent/orchestration/scripts/bootstrap/install-imported-ingress-tls.sh" --validate-only
openssl x509 -in "$native_worktree_parent/orchestration/nginx/certs/k8s/_mkcert-rootCA.pem" \
  -noout -sha256 -fingerprint
```

Compare the public root fingerprint privately with the approved host transfer.
Only the public ingress root is imported. The mkcert signing key remains on the
personal host. A stale publication requires the host-only certificate
preparation or renewal command and three-file transfer workflow, not a new
guest CA or a VM `setup.sh` run.

Trust responsibilities are intentionally singular: the personal host signs
browser certificates, orchestration validates the transferred files and
reconciles the Kubernetes TLS Secret, and workspace installs/verifies guest OS
and NSS trust. Run the command below only from a reviewed workspace revision,
with reviewed supplied files, after every affected worker has exited. Rerun it
after every certificate renewal.

The installer takes the public root and current leaf as explicit inputs; the
hostname is fixed at `app.budgetanalyzer.localhost`. Workspace code never
derives these paths. The command below passes orchestration's published TLS
file locations (see orchestration's
[host-published local ingress CA](../../orchestration/docs/development/local-environment.md#host-published-local-ingress-ca)
guide). From the guest workspace OS shell, with the environment fragment
loaded:

```bash
tls_dir="$native_worktree_parent/orchestration/nginx/certs/k8s"
./scripts/install-agent-vm-local-ca-trust.sh \
  --worktree-parent "$native_worktree_parent" --bare-parent "$native_bare_parent" \
  --ca-file "$tls_dir/_mkcert-rootCA.pem" \
  --leaf-file "$tls_dir/_wildcard.budgetanalyzer.localhost.pem"
ensure-budget-analyzer-local-ca-trust
check-budget-analyzer-local-ca-trust
./scripts/check-agent-vm-tools.sh \
  --worktree-parent "$native_worktree_parent" --bare-parent "$native_bare_parent"
```

The human-only trust installer verifies that neither supplied file contains a
private key, the root is an unexpired `CA:TRUE` certificate and the unexpired
leaf verifies for the exact hostname anchored only at the supplied root, plus
normal-user/VM identity and guest-local repositories, before using explicit
interactive `sudo install` and `sudo update-ca-certificates` for the one public
root. Its sole managed system destination is
`/usr/local/share/ca-certificates/budget-analyzer-local-mkcert.crt`. If the
exact legacy `budget-analyzer-local-ingress-ca.crt` path exists, it is removed
only after regular-file, no-symlink, root ownership, safe-mode and certificate
identity checks prove it is the approved root; identity is rechecked just
before removal. A different or unparseable legacy root reports both relevant
SHA-256 identities when available and stops before any `sudo` or NSS mutation.
The human must review that unexplained root explicitly; do not rename, retain
as stale managed trust or delete it through an unattended invocation.

NSS imports use this user's database and only the managed nickname;
public roots and other NSS entries remain. NSS path checks use the native
preflight's same verified private-primary-group exception: a group-writable
path is accepted only when that group belongs exclusively to this account;
shared-group and world-writable paths still stop. Password-protected NSS
databases stop for private human review. No command receives blanket
passwordless sudo.
After the system and NSS imports, the installer rechecks both stores and
verifies the supplied leaf against the combined system bundle. Only then does
it record the approved public root at
`$HOME/.local/share/budget-analyzer-native/trust/approved-local-root.pem`
(mode `0600`, directory `0700`); a failed installation writes no new record.

Installed `ensure` and `check` are read-only in native execution and take no
certificate paths. They compare the OS source, combined bundle and NSS entry
with the recorded root and require that root to be an unexpired CA. A missing
record or missing/stale system or NSS trust fails with the human installer
command; agents never silently run privileged trust repair. Missing
OpenSSL/certutil maps to status 12; record/publication/system/environment/NSS
failures use statuses 10/11/13/14/15, and an unsafe record path uses 16. These
checks report store state only, not browser acceptance.

After the installer succeeds, the final state can be checked without changing
trust:

```bash
canonical_ca=/usr/local/share/ca-certificates/budget-analyzer-local-mkcert.crt
legacy_ca=/usr/local/share/ca-certificates/budget-analyzer-local-ingress-ca.crt
test -f "$canonical_ca" && test ! -L "$canonical_ca"
test ! -e "$legacy_ca" && test ! -L "$legacy_ca"
stat -c '%U:%G %a %F' "$canonical_ca" # expected: root:root 644 regular file
check-budget-analyzer-local-ca-trust
openssl verify -CAfile /etc/ssl/certs/ca-certificates.crt "$tls_dir/_wildcard.budgetanalyzer.localhost.pem"
openssl x509 -in "$HOME/.local/share/budget-analyzer-native/trust/approved-local-root.pem" \
  -noout -sha256 -fingerprint
certutil -L -d "sql:$HOME/.pki/nssdb" -n 'Budget Analyzer local mkcert CA' -a \
  | openssl x509 -noout -sha256 -fingerprint
```

The read-only helper verifies the canonical certificate and combined bundle,
requires the legacy source to be absent, and checks the managed NSS nickname
and CA flags against the recorded root. The direct commands make the expected
one-source state visible; compare the displayed record and NSS fingerprints
privately with the approved publication. The supplied-leaf `openssl verify`
mirrors orchestration's `check-tilt-prerequisites.sh` system-trust check; it
proves neither NSS trust nor the certificate actually served by ingress.

### Browser Acceptance Check

After initial installation and after every renewal, with the application
running, the human verified HTTPS matrix below is required. Its Chromium probe
is the browser acceptance check: it opens exactly
`https://app.budgetanalyzer.localhost/` in the normal Workspace
Chromium/Playwright browser, which uses this user's `$HOME/.pki/nssdb`. Store
checks, the supplied-leaf system-trust check, curl, Python and Node passing do
not establish browser acceptance: if the system bundle trusts roots A and B
while NSS trusts only A, an application serving a root B leaf passes those
checks yet fails in Chromium.

Human verified HTTPS matrix, from a fresh guest shell:

```bash
. "$HOME/.config/budget-analyzer-native/env.sh"
curl --fail --show-error https://app.budgetanalyzer.localhost/ >/dev/null
python3 - <<'PY'
import urllib.request
with urllib.request.urlopen('https://app.budgetanalyzer.localhost/', timeout=20) as response:
    print('Python verified HTTPS:', response.status)
PY
node - <<'JS'
fetch('https://app.budgetanalyzer.localhost/', {redirect: 'manual'})
  .then(r => {if (r.status >= 500) throw Error('ingress unavailable'); console.log('Node verified HTTPS:', r.status)})
  .catch(e => {console.error(e.message); process.exitCode = 1});
JS
node - <<'JS'
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage();
    let ingressResponse;
    page.on('response', r => {
      if (r.url() === 'https://app.budgetanalyzer.localhost/') ingressResponse = r;
    });
    await page.route('**/*', route => {
      const url = new URL(route.request().url());
      return url.origin === 'https://app.budgetanalyzer.localhost' ? route.continue() : route.abort();
    });
    try {await page.goto('https://app.budgetanalyzer.localhost/', {waitUntil: 'domcontentloaded', timeout: 20000})}
    catch (e) {if (!ingressResponse) throw e}
    if (!ingressResponse || ingressResponse.status() >= 500) throw Error('ingress response missing/unavailable');
    console.log('Chromium verified HTTPS:', ingressResponse.status());
  } finally {await browser.close()}
})().catch(e => {console.error(e.message); process.exitCode = 1});
JS
```

The browser probe proves the launching user's NSS trust for the certificate
actually served by ingress and blocks navigation to other origins; a verified
local authentication redirect is acceptable. It must succeed without
`ignoreHTTPSErrors`, certificate exceptions or any other verification bypass; a
certificate error leaves no ingress response and fails the probe.
Playwright's default browser launch permissions are upstream defaults; this
probe does not claim Chromium OS sandbox acceptance. No client uses an insecure
TLS option. Record real command exits, not merely browser-cache presence.

## Authentication, Permissions And Verification

Authenticate only selected providers natively: `codex login`, `claude auth login`
or interactive `gemini`. Keep those inputs out of logs and do not authenticate
GitHub. Run a benign read of a workspace file and record which provider, model
selection and permission mode actually ran.

| Command | Actual permission behavior |
| --- | --- |
| Plain `codex`, `claude`, `gemini` | Native upstream defaults/configuration; wrappers load the environment, run the [launch boundary](#provider-launch-enforcement) and forward arguments |
| `codex-lean`, its proxy variants | Existing explicit `--dangerously-bypass-approvals-and-sandbox`, `approval_policy="never"`, `sandbox_mode="danger-full-access"`; not an OS sandbox |
| `ai-session-handler-codex-high`, `ai-session-handler-claude-high`, `ai-session-handler-claude-medium`, `ai-run` | Handler selects high-reasoning `codex-lean exec` or high- or medium-effort `claude-lean`; all selected modes have full guest access |
| `claude-with-proxy` | Upstream Claude permission behavior through the inspection proxy, with no added Claude environment |
| `claude-lean` | Explicit `--dangerously-skip-permissions` with the workspace system prompt; lean option set and 11 environment variables scoped to the launch |
| `claude-lean --proxy`, `claude-lean-proxy`, `claude-lean-proxy-high` | Explicit `--dangerously-skip-permissions` through `claude-with-proxy`; same lean option set and environment, with the default prompt kept for capture unless a trailing prompt flag is supplied |
| Optional aliases | Four thin lean aliases select medium or high effort and/or proxy mode; `ai-run-claude` selects the Claude handler; Codex aliases retain explicit effort/permission choices; never sourced by default |

Human opt-in aliases use `. "$HOME/.local/share/budget-analyzer-native/aliases.sh"`.
Explicit CLI model choices survive forwarding; `CODEX_MODEL` and
`ANTHROPIC_MODEL` remain supported for their corresponding providers. The
`xhigh` proxy effort spelling is corrected. Docker-group membership gives all
these processes broad guest-root-equivalent authority regardless of native
command sandboxing. The VM and host policy remain the personal-host boundary.

Open a fresh login shell and a fresh terminal through the SSH client or editor
you intend to use, then check in each (using this shell's derived parents). If
you use the tested VS Code Remote SSH workflow, include a fresh Remote SSH
terminal:

```bash
id -un
printf '%s\n' "$HOME"
command -v codex claude gemini ai-session-handler ai-session-handler-codex-high ai-session-handler-claude-high ai-session-handler-claude-medium ai-run playwright
ai-session-handler --version
ai-session-handler-codex-high --help
ai-session-handler-claude-high --help
ai-session-handler-claude-medium --help
check-budget-analyzer-local-ca-trust
./scripts/check-agent-vm-tools.sh \
  --worktree-parent "$BUDGET_ANALYZER_WORKTREE_PARENT" --bare-parent "$BUDGET_ANALYZER_BARE_PARENT"
```

Record the installation report, repeat-run configuration preservation, trust
matrix, actual sandbox mode, provider proof and host-boundary evidence. Follow
[Development VM And Native Agent Runtime](host-isolation.md) for the current
runtime and repository-transfer boundaries.

## Optional Human Inspection Setup

Normal sessions remain unproxied. mitmproxy/mitmweb/mitmdump and all flow/prompt
helpers are installed as optional capabilities, but no signing key or inspection
CA is created, copied or trusted during installation or safety checks. If
inspection is wanted, the human creates a separate **guest-owned** CA after
source review:

```bash
. "$HOME/.config/budget-analyzer-native/env.sh"
umask 077
inspection_dir="$HOME/.local/share/budget-analyzer-native/inspection"
mkdir -m 700 "$inspection_dir"
mitmdump --listen-host 127.0.0.1 --listen-port 19080 \
  --set "confdir=$inspection_dir" --set ssl_insecure=false
# Stop with Ctrl+C after initial CA creation; do not send provider traffic yet.
python3 - <<'PY'
import os
from pathlib import Path
import secrets
root = Path.home() / '.local/share/budget-analyzer-native/inspection'
(root / 'web-token').write_text(secrets.token_urlsafe(32) + '\n')
for path in root.iterdir():
    if path.is_file(): path.chmod(0o600)
PY
```

Never copy a proxy signing key from another machine. `start-proxy` and optional
provider wrappers require this private CA/token, bind proxy/UI to 127.0.0.1 and
keep upstream TLS verification on. They refuse occupied ports rather than
reusing an unidentified proxy. Provider
wrappers own/stop their child, assemble a private public+inspection CA bundle
under workspace `tmp/mitmproxy-private`, and scope proxy/trust variables to that
provider process. Their bundle is removed on exit. No system/NSS inspection-root
import, global proxy export or upstream bypass runs. Raw `start-proxy` starts
only the UI/proxy; it does not proxy ordinary sessions. Flow renderer exports
stay under workspace `tmp/mitmproxy-flows`. Full captured requests can contain
secrets; inspect/clean those directories privately after stopping listeners.

Remove only the human-created inspection directory and private capture
files after review to disable interception. Optional real interception is a
separate human test; automated checks validate its offline argv and lifecycle.

## Human Clean-Install Handoff

Workspace no longer serves as orchestration's startup verifier, the VM
boundary check has its own entry point, installation and verification are
component-scoped, provider CLIs float and the trust installer takes explicit
inputs. These steps are human-only and have not been run by an agent. There is
no in-place upgrade or migration from the previous layout. That layout used one
combined npm prefix and kept its only records directly in the native root, as
`$HOME/.local/share/budget-analyzer-native/managed-files.json` and
`installation.json`; it had no trust record. The new layout keeps per-component
records under `state/COMPONENT/`, so a fresh install has no record of the old
files. Any old managed file left at a path the new install plans, notably the
old `~/.local/bin` wrappers, is then an unmanaged collision.

1. Clean install. After every worker has stopped, from a fresh shell:
   1. List the previously managed paths, read-only and without printing file
      contents. The old record lists the native-root files, the environment
      fragment and the `~/.local/bin` wrappers; keep only the paths outside the
      native root and config directory:

      ```bash
      old_root="$HOME/.local/share/budget-analyzer-native"
      old_config="$HOME/.config/budget-analyzer-native"
      jq -r 'keys[]' "$old_root/managed-files.json" |
        grep -vF -e "$old_root/" -e "$old_config/"
      ```

   2. Review that list privately, then move each listed file that still exists
      into a private directory outside `.local` and `.config`, for example
      `mkdir -m 0700 "$HOME/budget-analyzer-native-previous"` and
      `mv -n -- PATH "$HOME/budget-analyzer-native-previous/"`. Do not
      delete or overwrite them, and do not move unlisted files.
   3. Move aside the old native root `$old_root` (it also holds the old npm
      prefix, pipx state, records and any optional inspection directory) and
      `$old_config` the same way. Keep provider homes, credentials,
      `~/.claude/settings.json` (the install merges its overlay) and the
      conversation skill (unchanged content). The `# budget-analyzer-native`
      shell-startup line stays; until reinstallation, new shells report the
      missing fragment, and the base install accepts the identical line.
   4. From a fresh shell in the reviewed workspace checkout, run
      `./scripts/prepare-agent-vm-native.sh` as described in
      [Review And System Preparation](#review-and-system-preparation). Review
      any reported collision privately instead of forcing it.

   The guarded provider wrappers from
   [Provider Launch Enforcement](#provider-launch-enforcement) take effect only
   after this reinstallation. Until then, the old wrappers, if still present,
   run providers without the boundary.
2. Trust. Run `install-agent-vm-local-ca-trust.sh` with the explicit
   `--ca-file` and `--leaf-file` inputs from
   [Establish Exact Ingress Trust](#establish-exact-ingress-trust).
3. Verification. From a fresh shell, run the
   [VM boundary check](#pre-agent-vm-boundary-check), then
   `./scripts/check-agent-vm-tools.sh` for all components (or one
   `--component NAME` at a time to isolate a failure). In the orchestration
   checkout, run its `./scripts/bootstrap/check-tilt-prerequisites.sh`, a
   separate orchestration check that does not invoke workspace. With the
   application running, perform the exact-URL Chromium/Playwright
   [Browser Acceptance Check](#browser-acceptance-check). After every
   certificate renewal, repeat step 2 and the browser acceptance check.
4. Publication. After the human commits, run
   `tests/native/run-source-validation.sh --publication committed` (which
   includes `check_install_inputs.py --publication committed`) and confirm
   publication CI passes.

## Offline Validation

Run from workspace, without actual provider calls, homes or trust changes:

```bash
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest discover -s tests/native -v
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_manifest.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_install_inputs.py --publication proposed
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_user_environment.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_claude_settings.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_lean_launchers.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_statusline.py
bash -n scripts/install-agent-vm-user-tools.sh
bash -n scripts/check-agent-vm-boundary.sh
bash -n scripts/check-agent-vm-tools.sh
bash -n scripts/install-agent-vm-local-ca-trust.sh
bash -n scripts/install-agent-vm-bwrap-profile.sh
bash -n scripts/prepare-agent-vm-native.sh
shellcheck scripts/install-agent-vm-user-tools.sh scripts/check-agent-vm-boundary.sh scripts/check-agent-vm-tools.sh scripts/install-agent-vm-local-ca-trust.sh scripts/install-agent-vm-bwrap-profile.sh scripts/prepare-agent-vm-native.sh native/helpers/*.sh native/helpers/mitmflows native/helpers/mitmflow-detail native/helpers/mitmflow-body
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile scripts/native/boundary.py scripts/native/user_tools.py scripts/native/local_ca.py scripts/native/proxy.py scripts/native/bwrap_profile.py tests/native/test_local_ca.py tests/native/test_boundary.py tests/native/test_user_tools.py tests/native/test_native_preparation.py tests/native/test_install_inputs.py tests/native/check_user_environment.py tests/native/check_install_inputs.py scripts/native/claude_settings.py tests/native/check_claude_settings.py tests/native/check_lean_launchers.py tests/native/check_statusline.py native/helpers/mitmflow-render.py
tests/native/check-source-validation-without-orchestration.sh --publication proposed
git diff --check
```

`tests/native/run-source-validation.sh` is the complete source-validation
command list used by publication CI. The no-sibling script reruns it from a
copy of this checkout with no orchestration sibling; workspace validation and
the documentation link check never require an orchestration checkout, and
links into `../orchestration/` are checked only when that sibling exists.

Once the lock and checker are committed, replace `--publication proposed` with
`--publication committed`. The latter fails unless every required input is in
`HEAD` and validates only the extracted `git archive HEAD` source.

The compact harness uses disposable homes, trust stores and command shims under
workspace `tmp/`. It checks exact duplicate convergence, unknown-root refusal
before mutation, symlink/ownership rejection, idempotence, preservation of
unrelated NSS entries, read-only trust verification, repeat installation
without credential/settings loss, pre-mutation origin and credential-bridge
rejection, missing browser/trust reporting, quoted path forwarding, runner
sequencing and short-circuit behavior. Boundary fixtures pass with only the
workspace checkout and no provider, helper, handler or platform command. They
reject every identity, authority, repository and guest Docker negative case
without writes, in both checkout and installed-copy modes. Launch-guard
fixtures run every rendered provider launch path and every proxy launcher,
proving that a boundary failure starts no provider or proxy and that success
adds no output. It invokes no real trust, provider,
package, Docker or AppArmor command and generates no CA. The static source checker renders
generated wrappers into `tmp/`, validates native mappings/locks/links and runs
shell syntax/ShellCheck. The human owns real package/browser behavior, loaded
AppArmor proof, authentication, HTTPS and installed-helper smoke checks.
