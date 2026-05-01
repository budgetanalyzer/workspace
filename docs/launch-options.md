# Claude Code Launch Options

## Standard Usage

Run `claude` for the normal path. Convenience aliases are also installed:

| Alias | Effect |
|-------|--------|
| `dangerous` | `--dangerously-skip-permissions` |
| `high` | Higher effort defaults |
| `max` | Maximum effort defaults |

All aliases also set `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=true` and `ENABLE_CLAUDEAI_MCP_SERVERS=false`.

## Proxy Launchers

- `claude-with-proxy` — traffic inspection only
- `claude-with-custom-system-prompt` — traffic inspection + prompt replacement (not required for normal development)
- `codex-with-proxy`, `codex-*-with-proxy` — Codex equivalents

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
- **Codex** — `export OPENAI_API_KEY` or `codex login`
- **Gemini** — `export GEMINI_API_KEY` or run `gemini` to sign in
