---
title: Use initialPrompt frontmatter for first-officer auto-start
id: 033
status: ideation
source: Claude Code changelog
started: 2026-03-25T19:00:00Z
completed:
verdict:
score: 0.45
worktree:
---

Claude Code now supports `initialPrompt` in agent frontmatter to auto-submit a first turn. The first-officer template currently uses an `AUTO-START` section in the agent body that instructs the LLM to "begin immediately." This is a prompt convention that the LLM could ignore.

Replace the `AUTO-START` body section with `initialPrompt` in the generated first-officer frontmatter. This makes auto-start a platform feature rather than a prompt instruction.

Scope: update the agent file generation in `skills/commission/SKILL.md` to add `initialPrompt` to the first-officer frontmatter and remove the `AUTO-START` section from the body. Update `agents/first-officer.md` reference doc. Test harness may need the guardrail check updated (currently checks for `AUTO-START`).
