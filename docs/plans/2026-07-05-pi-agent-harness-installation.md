# Pi Agent Harness Installation Plan

## Goal

Add Pi as an optional preinstalled AI coding harness in the sandbox, with lean
launchers and convenience aliases comparable to the existing `codex-lean`,
`codex-high`, `codex-max`, and proxy flows.

Plain `pi` should remain available with upstream defaults. The sandbox-specific
behavior should live in wrapper scripts and aliases, matching the current Codex
pattern.

## Current Baseline

- `ai-agent-sandbox/Dockerfile` installs Node.js from a pinned NodeSource major
  line: `ARG NODE_MAJOR=20`.
- Current Pi package metadata for `@earendil-works/pi-coding-agent@0.80.3`
  requires `node >=22.19.0`.
- The sandbox currently installs global npm CLIs:
  - `@anthropic-ai/claude-code@latest`
  - `@openai/codex@latest`
  - `@google/gemini-cli@latest`
- Existing lean behavior for Codex is implemented in:
  - `ai-agent-sandbox/scripts/codex-lean.sh`
  - `ai-agent-sandbox/scripts/codex-with-proxy.sh`
  - `ai-agent-sandbox/scripts/codex-max-with-proxy.sh`
  - `ai-agent-sandbox/bash_aliases.sh`
  - `docs/launch-options.md`

## Design Decisions

1. Move the sandbox Node major from 20 to 22.

   Node 22 is an LTS line and satisfies Pi's current `>=22.19.0` requirement.
   This preserves the existing "pinned major line" approach while moving to the
   newer LTS baseline.

2. Install Pi globally through npm.

   Use the documented install form:

   ```bash
   npm install -g --ignore-scripts @earendil-works/pi-coding-agent@latest
   ```

   `--ignore-scripts` follows Pi's own quickstart guidance and reduces install
   side effects.

3. Leave plain `pi` unwrapped.

   Users should be able to run upstream Pi defaults directly. Sandbox-specific
   defaults should live in a new `pi-lean` launcher.

4. Keep `AGENTS.md` loading enabled.

   Pi loads `AGENTS.md` and `CLAUDE.md` from parent directories and the current
   directory by default. This is useful for testing whether repository guidance
   is portable across Codex, Claude Code, Gemini, and Pi.

5. Prefer predictable lean defaults.

   `pi-lean` should avoid loading project-local `.pi` settings and extensions
   unless explicitly requested. That keeps first experiments focused on the
   harness and repo context rather than unreviewed project-local Pi resources.

## Proposed Files

### `ai-agent-sandbox/Dockerfile`

- Change `ARG NODE_MAJOR=20` to `ARG NODE_MAJOR=22`.
- Add `@earendil-works/pi-coding-agent@latest` to the global npm CLI install.
- Consider keeping `--ignore-scripts` scoped to Pi if the other global CLIs rely
  on install scripts. A safe pattern is a separate install step:

  ```dockerfile
  RUN npm install -g --ignore-scripts @earendil-works/pi-coding-agent@latest
  ```

- Create `/home/vscode/.pi` owned by the container user, similar to `.codex`
  and `.gemini`.
- Copy new Pi helper scripts into `/usr/local/bin` and mark them executable.

### `ai-agent-sandbox/scripts/pi-lean.sh`

Create a launcher that maps sandbox env vars to Pi CLI flags.

Recommended defaults:

```bash
#!/usr/bin/env bash
set -euo pipefail

REAL_PI="${PI_REAL_BIN:-/usr/local/bin/pi}"
if [ ! -x "$REAL_PI" ]; then
    REAL_PI="$(command -v pi)"
fi

thinking_level="${PI_THINKING_LEVEL:-high}"

args=(
    --thinking "$thinking_level"
    --no-approve
    --no-extensions
    --no-prompt-templates
)

if [ -n "${PI_MODEL:-}" ]; then
    args+=(--model "$PI_MODEL")
fi

if [ -n "${PI_MODELS:-}" ]; then
    args+=(--models "$PI_MODELS")
fi

if [ "${PI_NO_SESSION:-}" = "1" ]; then
    args+=(--no-session)
fi

exec "$REAL_PI" "${args[@]}" "$@"
```

Notes:

- Do not include `--no-context-files`; `AGENTS.md` loading is part of the
  experiment.
- Use `--no-approve` to avoid trusting project-local `.pi` settings, packages,
  and extensions by default.
- Leave skills enabled initially. Pi can discover Agent Skills, and comparing
  skill behavior may be useful. If this proves noisy, add `PI_NO_SKILLS=1` or a
  separate `pi-minimal` launcher later.
- Keep session persistence enabled initially because Pi's session tree and
  export behavior are part of the harness evaluation. Use `PI_NO_SESSION=1` for
  ephemeral runs.

### `ai-agent-sandbox/scripts/pi-with-proxy.sh`

Create a proxy launcher matching the Codex proxy script:

- Reuse `PROXY_PORT`, `WEB_PORT`, `MITM_PASS`, `HTTP_PROXY`, `HTTPS_PROXY`, and
  `NODE_EXTRA_CA_CERTS` behavior from `codex-with-proxy.sh`.
- Start or reuse `mitmweb`.
- Invoke `pi-lean "$@"`.

### `ai-agent-sandbox/scripts/pi-max-with-proxy.sh`

Create a tiny wrapper:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_SCRIPT="$SCRIPT_DIR/pi-with-proxy"
if [ ! -x "$BASE_SCRIPT" ]; then
    BASE_SCRIPT="$SCRIPT_DIR/pi-with-proxy.sh"
fi

export PI_THINKING_LEVEL="xhigh"
exec "$BASE_SCRIPT" "$@"
```

### `ai-agent-sandbox/bash_aliases.sh`

Add aliases:

```bash
alias pi-dangerous="pi-lean"
alias pi-high="env PI_THINKING_LEVEL=high pi-lean"
alias pi-max="env PI_THINKING_LEVEL=xhigh pi-lean"
alias pi-proxy="pi-with-proxy"
alias pi-high-proxy="env PI_THINKING_LEVEL=high pi-with-proxy"
alias pi-max-proxy="pi-max-with-proxy"
alias pi-ephemeral="env PI_NO_SESSION=1 pi-lean"
```

### `ai-agent-sandbox/entrypoint.sh`

- Add Pi to the AI CLI verification section.
- Add Pi auth guidance to the startup banner:

  ```text
  Pi     - export provider API key or run 'pi' then '/login'
  ```

### `docs/launch-options.md`

Document:

- Plain `pi` keeps upstream defaults.
- `pi-lean` provides sandbox defaults.
- `pi-high` and `pi-max` map to `--thinking high` and `--thinking xhigh`.
- `PI_MODEL` can pin a model, for example `openai-codex/gpt-5.5`.
- `PI_MODELS` can constrain model cycling.
- `PI_NO_SESSION=1` disables session persistence for a run.
- Proxy variants mirror Codex proxy behavior.

### `README.md`

Update "What's Inside" to include Pi once implementation lands.

## Provider And Model Notes

Useful Pi provider IDs:

| Provider ID | Auth path |
|-------------|-----------|
| `openai-codex` | ChatGPT Plus/Pro subscription via `/login` |
| `openai` | `OPENAI_API_KEY` or stored API key |
| `anthropic` | `ANTHROPIC_API_KEY` or Claude Pro/Max via `/login` |
| `google` | `GEMINI_API_KEY` |
| `github-copilot` | GitHub Copilot subscription via `/login` |

Useful model invocation examples:

```bash
PI_MODEL=openai-codex/gpt-5.5 pi-max
PI_MODEL=anthropic/claude-opus-4-8 pi-high
PI_MODELS="openai-codex/*:xhigh,anthropic/*opus*:high" pi-lean
```

## Validation Plan

After implementation, rebuild the devcontainer image and verify:

```bash
node --version
npm --version
claude --version
codex --version
gemini --version
pi --version
pi --help
npx playwright install --list
```

Run shell validation:

```bash
shellcheck \
  ai-agent-sandbox/scripts/pi-lean.sh \
  ai-agent-sandbox/scripts/pi-with-proxy.sh \
  ai-agent-sandbox/scripts/pi-max-with-proxy.sh
```

Run compose validation because the sandbox image and helper scripts changed:

```bash
docker compose -f ai-agent-sandbox/docker-compose.yml config
```

Manual smoke tests inside the rebuilt container:

```bash
pi --list-models codex
pi-lean --help
PI_NO_SESSION=1 pi-lean -p "Say ok"
PI_THINKING_LEVEL=xhigh pi-lean --help
```

Proxy smoke test:

```bash
pi-proxy --help
```

Then confirm the mitmweb UI starts and that Pi traffic honors
`HTTP_PROXY`/`HTTPS_PROXY` for provider calls.

## Rollback Plan

If Node 22 breaks existing CLIs or Playwright:

1. Revert `NODE_MAJOR` to 20.
2. Remove Pi from the global npm install.
3. Leave the plan document as historical context or update it with the blocker.

If Pi installs but runtime behavior is unstable:

1. Keep Node 22 only if existing CLIs validate cleanly.
2. Remove Pi aliases from `bash_aliases.sh`.
3. Keep plain `pi` available only if it does not affect existing workflows.

## Open Questions

- Should `pi-lean` disable skills by default, or keep skills enabled for
  cross-harness Agent Skills experimentation?
- Should `pi-lean` default to session persistence, or should it mimic Codex's
  no-history default more strictly?
- Should we pin Pi to a specific version after initial testing instead of using
  `@latest` with `CLI_CACHE_BUST`?
- Should the proxy launcher set `PI_SKIP_VERSION_CHECK=1` and `PI_TELEMETRY=0`
  by default to reduce non-provider startup traffic during inspections?
