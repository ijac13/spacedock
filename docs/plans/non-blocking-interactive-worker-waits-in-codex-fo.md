---
id: 138
title: Non-blocking interactive worker waits in Codex first officer
status: implementation
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

### Feedback Cycles

- Cycle 1 (2026-04-12): Validation REJECTED. The validator accepted the Codex-specific wording change and the static contract checks, but rejected the task because the acceptance criteria still implied behavioral proof that the current harness did not provide. The entity was routed back to implementation in the worktree to tighten the claims to what the tests actually prove and prepare it for a fresh validation pass.
- Cycle 2 (2026-04-12): Validation REJECTED again. The validator found one bounded live Codex result for the single-entity wait path, but AC1 and AC3 still lacked compliant interactive evidence, the shared Codex rejection-flow test path was broken by a `run_codex_first_officer(... stop_checker=...)` mismatch, and the branch was still asserting FO behavior through a custom prompt-coached Codex invocation that conflicts with `tests/README.md`. Route back to implementation in the same worktree to replace the prompt-coached test shape with shared `--runtime codex` coverage where feasible and to repair the broken shared Codex path.
