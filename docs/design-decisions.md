# Design Decisions

## AGENTS.md over CLAUDE.md

We use AGENTS.md (the emerging multi-tool standard) instead of CLAUDE.md, injected via a SessionStart hook. This works around two open issues:

- [#18560](https://github.com/anthropics/claude-code/issues/18560) — system-reminder appended to CLAUDE.md contents undermines user instructions with a contradictory "may or may not be relevant" caveat
- [#6235](https://github.com/anthropics/claude-code/issues/6235) — Claude Code doesn't natively read AGENTS.md

The hook in `native/helpers/settings-overlay.json` cats AGENTS.md at session
start. The native user installer merges only that hook and the two reviewed
controls into the normal guest user's existing Claude settings.

## Save Conversation Skill

`/save-conversation` captures the current conversation to a `conversations/`
directory. Files are numbered with kebab-case titles and organized with INDEX
shards. Its canonical source is
`native/helpers/skills/save-conversation/SKILL.md`; the native user installer
copies it byte-for-byte and rejects an unrelated collision.
