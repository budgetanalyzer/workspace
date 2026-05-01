# Design Decisions

## AGENTS.md over CLAUDE.md

We use AGENTS.md (the emerging multi-tool standard) instead of CLAUDE.md, injected via a SessionStart hook. This works around two open issues:

- [#18560](https://github.com/anthropics/claude-code/issues/18560) — system-reminder appended to CLAUDE.md contents undermines user instructions with a contradictory "may or may not be relevant" caveat
- [#6235](https://github.com/anthropics/claude-code/issues/6235) — Claude Code doesn't natively read AGENTS.md

The hook in `settings-overlay.json` cats AGENTS.md at session start, which arrives as a system-reminder without the subversive suffix.

## CLAUDE_CODE_DISABLE_AUTO_MEMORY

Set in `devcontainer.json` remoteEnv. Disables Claude Code's automatic memory feature, which lets the agent decide on its own what to remember across sessions. This is a personal preference for 100% control over what goes into AI context — if you prefer the memory feature (many users do), remove this env var.

## Save Conversation Skill

`/save-conversation` captures the current conversation to a `conversations/` directory. Files are numbered with kebab-case titles, organized with INDEX shards.
