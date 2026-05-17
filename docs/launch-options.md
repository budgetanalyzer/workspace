# AI CLI Launch Options

## Standard Usage

Run `claude` for the normal path. Convenience aliases are also installed:

| Alias | Effect |
|-------|--------|
| `dangerous` | `--dangerously-skip-permissions` |
| `high` | Higher effort defaults |
| `max` | Maximum effort defaults |

All aliases also set `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true` and `ENABLE_CLAUDEAI_MCP_SERVERS=false`.

## Codex Lean Usage

The sandbox installs `codex-lean` and aliases `codex` to it. The wrapper always launches Codex with the lean sandbox defaults from `ai-agent-sandbox/codex-config.toml`:

- no project instruction loading (`project_doc_max_bytes = 0`)
- no web search
- no MCP app/connectors
- no subagents
- no browser/computer/image tools
- no hooks or plugin hooks
- no TUI notifications, animations, status line, or terminal title updates
- `danger-full-access` with approval prompts disabled, relying on the external container sandbox

Convenience aliases:

| Alias | Effect |
|-------|--------|
| `codex` | `codex-lean` |
| `codex-dangerous` | `codex-lean` |
| `codex-high` | `codex-lean` with high reasoning effort |
| `codex-max` | `codex-lean` with extra-high reasoning effort |
| `codex-proxy` | `codex-with-proxy` |
| `codex-high-proxy` | `codex-with-proxy` with high reasoning effort |
| `codex-max-proxy` | `codex-max-with-proxy` |

## Proxy Launchers

- `claude-with-proxy` — traffic inspection only
- `claude-with-custom-system-prompt` — traffic inspection + prompt replacement (not required for normal development)
- `codex-with-proxy`, `codex-*-with-proxy` — Codex lean equivalents

Browse [`ai-agent-sandbox/scripts/`](/workspace/workspace/ai-agent-sandbox/scripts/) for the full set of launchers.

Request dumps are written to `/tmp/claude-proxy-dumps/` with CWD and timestamp in filenames.

### Why the custom system prompt launcher exists

Anthropic's default system prompt includes verbose per-tool elaboration that duplicates what belongs in AGENTS.md, consuming context window on every request. Claude Code's `--system-prompt` and `--system-prompt-file` flags *append* to the default prompt rather than replacing it, so a mitmproxy addon swaps the prompt in-flight as a workaround. See [AGENTS.md](/workspace/workspace/AGENTS.md) for operating rules and source-of-truth pointers.

## Disabling Tools

```bash
claude --disallowedTools "Agent" --dangerously-skip-permissions
```

Disabling the Agent (subagent) tool is useful in small microservice repos where direct Grep/Glob/Read is faster than autonomous subagent exploration. The Agent tool is designed for large monorepos.

## Auth

- **Claude** — `claude auth login`
- **Codex** — `export OPENAI_API_KEY` or `codex login`; normal launches use `codex-lean`
- **Gemini** — `export GEMINI_API_KEY` or run `gemini` to sign in
