---
id: 131
title: Codex first officer: wait bookkeeping for reused worker threads after send_input
status: backlog
source: FO observation during task 117 feedback routing on 2026-04-11
started:
completed:
verdict:
score: 0.68
worktree:
issue:
pr:
---

Task 130 aligned the shared/core and Codex runtime semantics so completed workers can be reused through `send_input` and explicitly shut down when no longer needed. During task 117, a narrower operational gap remained: after routing feedback back to the reused implementation worker, the FO did not immediately treat that worker as active again or wait on it, so the session looked idle even though the worker was still progressing.

This follow-up should tighten the Codex first-officer runtime around reused-worker lifecycle bookkeeping:

- when FO sends follow-up work to a reused worker via `send_input`, that worker becomes active again
- FO should track that active reused worker explicitly, not just the original spawn event
- when the reused worker’s result is on the critical path, FO must `wait_agent` on that same agent instead of treating `send_input` as fire-and-forget
- status/reporting should make it clear that a reused worker is active again, not merely “reachable”

The goal is that reused Codex workers are not only semantically reusable, but operationally observed through completion in the same way fresh-dispatched workers are.
