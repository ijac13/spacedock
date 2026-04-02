# Codex Ensign Runtime

This file defines how the shared ensign core executes on Codex.

## Agent Surface

The packaged worker role asset is `spacedock:ensign`.
When the worker resolves that logical id itself, it should use the convention:
`~/.agents/skills/{namespace}/agents/{name}.md`.

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

After sending that one completion summary, stop immediately.
Do not keep exploring files, do not wait for another assignment, and do not send multiple summaries.
