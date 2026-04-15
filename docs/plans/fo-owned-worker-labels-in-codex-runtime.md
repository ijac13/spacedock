---
id: 137
title: FO-owned worker labels in Codex runtime
status: ideation
source: FO observation during task 136 dispatch on 2026-04-12
score: 0.58
started: 2026-04-15T03:21:24Z
completed:
verdict:
worktree:
issue:
pr:
---

Codex worker dispatch currently leaks incidental platform nicknames like `Leibniz` into operator-facing updates, even though the first-officer runtime contract already describes a stable FO-owned worker label convention such as `136-ideation/Herschel`. That makes it harder to correlate runtime handles, stage ownership, and later reuse/routing decisions.

This task should tighten the Codex first-officer path so operator-facing status and routing messages use a deterministic FO-generated worker label instead of the nickname returned by `spawn_agent`. The logical worker id (`spacedock:ensign`) and the runtime handle still matter internally, but the captain should not have to reason about incidental nicknames to follow workflow state.
