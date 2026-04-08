---
id: 101
title: "Codex FO incorrectly enters single-entity mode during normal dispatch"
status: backlog
source: CL observation
started:
completed:
verdict:
score:
worktree:
issue:
pr:
---

When the Codex runtime dispatches an entity, it enters single-entity mode even during normal (non-pipe) operation. Single-entity mode is designed for `claude -p` / non-interactive invocations where a specific entity is named for processing. During normal interactive dispatch, the FO should use the standard event loop with team support.

Observed behavior: the Codex FO resolved entity 087 (which was already in implementation) and announced it was in single-entity mode, treating it as if the user had asked to process that specific entity through the workflow in pipe mode.

This likely stems from how the Codex runtime adapter interprets the initial prompt or entity resolution — it may be unconditionally entering single-entity mode when it should only do so for explicit `-p` style invocations.
