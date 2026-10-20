# Design Decisions

## AGENTS.md over CLAUDE.md

We use AGENTS.md (the emerging multi-tool standard) as the instruction source
instead of CLAUDE.md. Current Claude Code loads `AGENTS.md` natively through
normal project-instruction discovery, so no `CLAUDE.md` shim or injection hook
is needed. The
[settings replacement](native-user-tools.md#claude-settings-replacement)
removes the legacy `SessionStart` hook that also injected `AGENTS.md`, so the
instructions appear exactly once; the settings overlay merges only the two
reviewed controls. Related upstream issues:

- [#18560](https://github.com/anthropics/claude-code/issues/18560) — system-reminder appended to CLAUDE.md contents undermines user instructions with a contradictory "may or may not be relevant" caveat; one reason a CLAUDE.md-based workaround was rejected
- [#6235](https://github.com/anthropics/claude-code/issues/6235) — historical context: the earlier support request for native AGENTS.md reading, from before Claude Code closed that gap

## Save Conversation Skill

`/save-conversation` captures the current conversation to a `conversations/`
directory. Files are numbered with kebab-case titles and organized with INDEX
shards. Its canonical source is
`native/helpers/skills/save-conversation/SKILL.md`; the native user installer
copies it byte-for-byte and rejects an unrelated collision.
