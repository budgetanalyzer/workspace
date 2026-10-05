# Native Guest User Tools And Checkpoint B

**Status:** Human B.1 system/user installation and repeat-run verification
completed on 2026-10-05. B.2 trust, authentication and full verification remain
pending.

Phase 2 supplies reviewed installers and focused offline safety checks. The
human runs the following sequence from the Ubuntu development VM OS as its
normal development user after both authoring phases and all old workers end.
These instructions complete workspace's part of the companion
[Checkpoint B](../../orchestration/docs/plans/agent-vm-native-manual-plan.md#checkpoint-b-install-and-launch-native-agents).
The companion remains read-only under this worker's repository boundary.
Live installation, authentication, sandbox execution and verified browser
traffic remain human evidence; offline checks do not establish acceptance.

## Review And System Preparation

Privately preserve existing guest configuration. Review `git diff`, new files,
[native tool inventory](native-tool-inventory.md), `native/toolchain.json`,
`native/npm/package-lock.json`, and the native installation entry points. The
system stage must complete first, including Chromium shared libraries/fonts,
JDK 25, Node 24, Python, pipx and bubblewrap. Preserve Docker, Kind, Tilt, all
container volumes and provider state. Do not run orchestration `setup.sh`.

The repeatable B.1 workflow lives in the tracked
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
environment fragment, and repeats user installation. It stops on the first
failure. Each invocation keeps a private log under
`tmp/native-preparation/prepare-*.log`; no operational source lives in `tmp/`.
Reruns retain the existing installations and unrelated configuration. Trust
import, provider login and the full tools verifier remain B.2 steps below.

The individual tracked entry points remain available for focused repair.
From the guest OS workspace checkout:

```bash
native_worktree_parent=$(cd .. && pwd -P)
read -r -p 'Existing guest bare-repository parent: ' native_bare_parent
test -d "$native_bare_parent"
sudo -v
./scripts/provision-agent-vm-guest.sh --docker-user "$(id -un)"
```

Reconnect if the system stage changed Docker-group membership. Run as the same
normal account; never put `sudo` before either user installer or verifier.
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
The former `developers.openai.com/codex/security` page now refers to a separate
security product; its link to Agent approvals & security is the relevant source.
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
sudo -v
./scripts/install-agent-vm-bwrap-profile.sh --docker-user "$(id -un)"
```

The installer reuses the system provisioner's Ubuntu/QEMU/KVM, normal-user,
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
review. User preflight checks for the profile when the kernel restriction is
active; loaded-policy and real command sandbox proof remain human gates.

After user installation, test plain Codex's actual Linux sandbox without a
provider call from workspace `tmp/`:

```bash
mkdir -p tmp/native-sandbox-proof
cd tmp/native-sandbox-proof
codex sandbox linux -- sh -c 'printf "native sandbox command passed\n"'
cd ../..
```

Inspect installed CLI help/config if the syntax changes; do not substitute a
permission bypass to claim sandbox acceptance. Run the native provider probe in
the mode actually selected and record that mode in the human handoff.

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

The second run retains installed packages, configuration, credentials and the
single managed hook/shell line. Chromium installation is rechecked by the
pinned Playwright installer; it may recover a missing payload, never upgrades
the npm selection. Trust is not required to finish user tool installation; the
full read-only verifier requires established system/NSS trust after the next
section. Installation does not authenticate, launch proxies or generate CAs.

One normal development home owns `.m2/repository`, `.gradle`, `.claude`, `.codex`,
`.gemini`, `.pki/nssdb` and `.cache/ms-playwright`. No container cache/provider
volume is copied. Managed tools live under `.local/share/budget-analyzer-native`:
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

Claude configuration merges only `promptSuggestionEnabled`, `autoCompactEnabled`
and the AGENTS SessionStart command from the reviewed overlay. Other settings,
permission/model choices and user hooks survive. The file-only conversation
skill is retained byte-for-byte. An unrelated existing skill/command, changed
managed resource, symlink or altered npm lock stops for private human review.
The statusline helper is installed but remains optional and is never activated
or invoked during installation; an explicit invocation can use this user's
Claude OAuth state. Its private cache stays under workspace `tmp/`.

`installation.json` records source revisions/dirty paths, home/user, repository
parents, reviewed versions, npm-lock SHA256 and resolved mitmproxy dependencies.
The handler is editable from the local checkout; the verifier checks its import
origin, global command resolution and high wrapper help. Ordinary source edits
remain visible; handler dependency/entry-point changes require an explicit
human pipx reinstall after review. mitmproxy's exact top-level release is pinned;
pipx resolves transitive PyPI dependencies on first install and records them.
Reruns retain that environment. npm uses the tracked full integrity lock with
`npm ci`, isolated config/cache and verified HTTPS. Reviewed npm lifecycle scripts
may compile their locked optional dependencies. Never resolve `latest` during
installation. An explicit npm refresh requires reviewing both manifest and lock,
then privately removing only this managed npm environment and rerunning; the
installer refuses to perform that removal or upgrade automatically.

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
personal host. A stale publication requires the existing host-only renewal and
three-file transfer workflow, not a new guest CA or host `setup.sh` rerun.

From the guest workspace OS shell, with the environment fragment loaded:

```bash
./scripts/install-agent-vm-local-ca-trust.sh \
  --worktree-parent "$native_worktree_parent" --bare-parent "$native_bare_parent"
ensure-budget-analyzer-local-ca-trust
check-budget-analyzer-local-ca-trust
./scripts/check-agent-vm-tools.sh \
  --worktree-parent "$native_worktree_parent" --bare-parent "$native_bare_parent"
```

The human-only trust installer verifies CA validity, exact hostname/leaf chain,
normal-user/VM identity and guest-local repositories before using explicit
interactive `sudo install` and `sudo update-ca-certificates` for the one public
root. NSS imports use this user's database and only the managed nickname;
public roots and other NSS entries remain. Password-protected NSS databases
stop for private human review. No command receives blanket passwordless sudo.
Installed `ensure` and `check` are read-only in native execution. Missing/stale
system or NSS trust fails with the exact human installer command; agents never
silently run privileged trust repair. Missing OpenSSL/certutil maps to status
12; publication/system/environment/NSS failures retain statuses 10/11/13/14/15.

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

The browser probe proves the launching user's NSS trust and blocks navigation
to other origins; a verified local authentication redirect is acceptable.
Playwright's default browser launch permissions are upstream defaults; this
probe does not claim Chromium OS sandbox acceptance. No client uses an insecure
TLS option. Record real command exits, not merely browser-cache presence.

## Authentication, Permissions And Native Handoff

Authenticate only selected providers natively: `codex login`, `claude auth login`
or interactive `gemini`. Keep those inputs out of logs. Do not import container
state or authenticate GitHub. Run a benign read of a workspace file and record
which provider, model selection and permission mode actually ran.

| Command | Actual permission behavior |
| --- | --- |
| Plain `codex`, `claude`, `gemini` | Native upstream defaults/configuration; wrappers only load environment and forward arguments |
| `codex-lean`, its proxy variants | Existing explicit `--dangerously-bypass-approvals-and-sandbox`, `approval_policy="never"`, `sandbox_mode="danger-full-access"`; not an OS sandbox |
| `ai-session-handler-codex-high`, `ai-run` | Handler selects high reasoning and calls `codex-lean exec`; therefore full guest access in this selected mode |
| `claude-with-proxy` | Plain Claude permission arguments, inspection only |
| Claude custom-prompt/model wrappers | Existing explicit `--dangerously-skip-permissions`; optional selection retains the old permission behavior |
| Optional aliases | Original explicit bypass/effort/model choices in managed `aliases.sh`; never sourced by default |

Human opt-in aliases use `. "$HOME/.local/share/budget-analyzer-native/aliases.sh"`.
Explicit CLI model choices survive forwarding; `CODEX_MODEL` remains supported.
The `xhigh` proxy effort spelling is corrected. Docker-group membership gives
all these processes broad guest-root-equivalent authority regardless of native
command sandboxing. The VM and host policy remain the personal-host boundary.

Open a fresh login shell and a VS Code Remote SSH terminal in the guest, then
check in each (using this shell's derived parents):

```bash
id -un
printf '%s\n' "$HOME"
command -v codex claude gemini ai-session-handler ai-session-handler-codex-high ai-run playwright
ai-session-handler --version
ai-session-handler-codex-high --help
check-budget-analyzer-local-ca-trust
./scripts/check-agent-vm-tools.sh \
  --worktree-parent "$BUDGET_ANALYZER_WORKTREE_PARENT" --bare-parent "$BUDGET_ANALYZER_BARE_PARENT"
```

Record the installation report, live rerun/config preservation, trust matrix,
actual sandbox mode, native provider proof and host boundary evidence in the
human-owned Native Execution Handoff. Follow B.3 to stop only the old guest
agent and preserve its volumes/image; do not stop Docker/Kind/Tilt. Resume the
same guest-local orchestration runner state from a native shell with the
companion's command only after handoff completion. End this authoring handler
at its two-phase limit. Phase 3 remains gated by human handoff.

## Optional Human Inspection Setup

Normal sessions remain unproxied. mitmproxy/mitmweb/mitmdump and all flow/prompt
helpers are installed for parity, but no signing key or inspection CA is
created, copied or trusted during installation or safety checks. If inspection is
wanted, the human creates a separate **guest-owned** CA after source review:

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

Never copy a proxy signing key from the host/container. `start-proxy` and optional
provider wrappers require this private CA/token, bind proxy/UI to 127.0.0.1 and
keep upstream TLS verification on. They refuse occupied ports rather than
reusing an unidentified proxy or assuming the correct addon is loaded. Provider
wrappers own/stop their child, assemble a private public+inspection CA bundle
under workspace `tmp/mitmproxy-private`, and scope proxy/trust variables to that
provider process. Their bundle is removed on exit. No system/NSS inspection-root
import, global proxy export or upstream bypass runs. Raw `start-proxy` starts
only the UI/proxy; it does not proxy ordinary sessions. Flow renderer exports
stay under workspace `tmp/mitmproxy-flows`; addon dumps and statusline caches
are private files under workspace `tmp/`. Full captured requests can contain
secrets; inspect/clean those directories privately after stopping listeners.

Remove only the human-created inspection directory and private capture/dump
files after review to retire interception. Existing container CA/state remains
untouched. Optional real interception is a separate human test, not required
for ordinary native acceptance; Phase 2 validates its offline argv/lifecycle.

## Offline Validation

Run from workspace, without actual provider calls, homes or trust changes:

```bash
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m unittest discover -s tests/native -v
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_manifest.py
PYTHONPYCACHEPREFIX=tmp/pycache python3 tests/native/check_user_environment.py
bash -n scripts/install-agent-vm-user-tools.sh
bash -n scripts/check-agent-vm-tools.sh
bash -n scripts/install-agent-vm-local-ca-trust.sh
bash -n scripts/install-agent-vm-bwrap-profile.sh
bash -n scripts/prepare-agent-vm-native.sh
shellcheck scripts/install-agent-vm-user-tools.sh scripts/check-agent-vm-tools.sh scripts/install-agent-vm-local-ca-trust.sh scripts/install-agent-vm-bwrap-profile.sh scripts/prepare-agent-vm-native.sh native/helpers/*.sh native/helpers/mitmflows native/helpers/mitmflow-detail native/helpers/mitmflow-body
PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile scripts/native/user_tools.py scripts/native/local_ca.py scripts/native/proxy.py scripts/native/bwrap_profile.py tests/native/test_user_tools.py tests/native/test_native_preparation.py tests/native/check_user_environment.py native/helpers/system-prompt-addon.py native/helpers/mitmflow-render.py
git diff --check
```

The compact harness uses disposable homes and command shims under workspace
`tmp/`. It checks repeat installation without credential/settings loss,
pre-mutation origin and credential-bridge rejection, read-only verification,
missing browser/trust reporting, quoted path forwarding, runner sequencing and
short-circuit behavior. It invokes no real trust, provider, package, Docker or
AppArmor command and generates no CA. The static source checker renders
generated wrappers into `tmp/`, validates native mappings/locks/links and runs
shell syntax/ShellCheck. Human B owns real package/browser behavior, loaded
AppArmor proof, authentication, HTTPS and installed-helper smoke checks.
