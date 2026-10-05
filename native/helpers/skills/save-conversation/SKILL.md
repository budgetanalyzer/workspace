---
name: save-conversation
description: "This skill should be used when the user says 'write conversation', 'write this conversation', 'save this', 'save conversation', or any similar instruction to capture the current conversation to disk."
version: 0.1.0
---

# Save Conversation Protocol

Write the current conversation to the `conversations/` directory in the current working directory.

## Steps

### 1. Discover Next Number
Glob `conversations/[0-9]*-*.md` to find the highest-numbered conversation file. The next conversation number is that number + 1. If the `conversations/` directory doesn't exist, create it and start at 001.

### 2. Learn the Format
Read TWO recent conversation files to learn the current format. Match the structure exactly.

### 3. Learn the INDEX Format
Find INDEX shard files (`conversations/INDEX-*.md`). Read the shard covering the next conversation number (e.g., `INDEX-151-200.md` for conversations 151-200). Match the existing entry format. If no INDEX shards exist, create the first one (e.g., `INDEX-001-050.md`).

### 4. Write the Conversation File
Write as `conversations/NNN-kebab-case-title.md`.

### 5. Update the INDEX Shard
Append the new entry to the appropriate INDEX shard. If the shard doesn't exist (e.g., conversation 201 needs `INDEX-201-250.md`), create it following existing shard patterns.

### 6. Check for Post-Write Hook
Check if `FINALIZE-CONVERSATION.md` exists in the current working directory. If found, read and execute its instructions. If not, skip.

## Rules

- File operations only. Create/update files on disk. Nothing more.
- Write whatever the user wants captured — do not judge content worthiness.
