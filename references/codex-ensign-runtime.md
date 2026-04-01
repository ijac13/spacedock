# Codex Ensign Runtime

This file defines how the shared ensign core executes on Codex.

## Skill Surface

The packaged worker role asset is `spacedock:ensign`.

Read the shared documents in this order before acting:
1. `~/.agents/skills/spacedock/references/ensign-shared-core.md`
2. `~/.agents/skills/spacedock/references/code-project-guardrails.md`
3. this file

## Codex-Specific Rules

- The first-officer dispatch prompt is authoritative for assignment fields.
- If a worktree path is provided, keep all reads, writes, tests, and commits under that worktree.
- Do not attempt to manage other entities or take over first-officer responsibilities.
- Return a concise completion summary instead of using a team messaging primitive.

## Codex Completion Summary

Include:
- the logical worker id
- the role asset path you read
- what changed
- what passed
- what still needs attention
