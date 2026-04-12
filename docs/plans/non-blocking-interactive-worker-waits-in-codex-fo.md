---
id: 138
title: Non-blocking interactive worker waits in Codex first officer
status: ideation
source: FO observation during task 136 dispatch on 2026-04-12
score: 0.66
started: 2026-04-12T18:17:59Z
completed:
verdict:
worktree: .worktrees/spacedock-ensign-non-blocking-interactive-worker-waits-in-codex-fo
issue:
pr:
---

The current Codex first-officer runtime guidance encourages `spawn_agent(...); wait_agent(...)` as the normal dispatch pattern. That works for bounded or single-entity runs, but in an interactive captain conversation it blocks the foreground while a worker is running. During task 136 dispatch, that meant the captain had to interrupt the session just to continue discussing another workflow improvement while the ideation worker was still in flight.

This task should refine the Codex first-officer runtime so interactive sessions keep workers in the background by default. The first officer should only foreground a `wait_agent` when the next orchestration step is truly blocked on that worker result, or when the captain explicitly asks to wait. Bounded/single-entity runs can keep the stricter blocking path where immediate completion is the whole point.
