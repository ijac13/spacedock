---
id: 130
title: Codex first officer: support reusable worker threads and explicit shutdown semantics
status: validation
source: FO observation during task 117 rejection flow on 2026-04-10/11
started: 2026-04-11T05:28:44Z
completed:
verdict:
score: 0.72
worktree: .worktrees/spacedock-ensign-codex-first-officer-agent-reuse-semantics
issue:
pr:
---

Codex currently treats worker completion as an end state: the runtime adapter says workers return a concise summary and stop. That is too weak for Spacedock workflows that rely on reusable worker threads and feedback routing. Shared first-officer semantics already allow reuse, feedback-to keep-alives, and explicit shutdown decisions; the Codex adapter needs to describe and support the same lifecycle instead of drifting toward "spawn once, summarize once, stop."

The concrete failure that exposed this gap happened during task 117. The validator rejected the implementation, but the first officer fresh-dispatched a new worker instead of routing the findings back to the original implementation thread. That behavior breaks two expectations:

1. completed workers can still be live and addressable
2. feedback-to routing should prefer the original worker when it is still reusable

## Problem Statement

The repo currently has a semantic mismatch between the shared core and the Codex runtime reference:

- shared core already models reuse as conditional, not impossible
- Codex runtime prose still frames completion as terminal summary-only behavior
- the live Codex path can still reach a completed worker through `send_input`

That mismatch matters because it changes workflow outcomes. A rejected validation should be able to bounce findings to the original implementer when the worker is still available. When reuse is not viable, the first officer should shut down the old worker explicitly and fresh-dispatch a replacement. The runtime needs to tell the truth about both cases.

## Desired Runtime Semantics

The intended lifecycle for Codex workers is:

- A completed worker is reusable only when it is still alive, the first officer still holds a valid handle to it, and the reuse decision says the worker should continue the same entity thread.
- Reuse is allowed only when the shared-core reuse conditions are satisfied, including `reuse_ok`, no `fresh: true` override, and no worktree-mode mismatch.
- `feedback-to` is routed to the original implementation worker when that worker is still reusable. The follow-up message should be delivered through `send_input`, not by spawning a brand-new worker just to carry the feedback.
- A worker must be shut down explicitly when it is no longer needed for any later routing, when reuse is blocked, when the workflow is moving to a different worker that must not inherit the old thread, or when the entity reaches a terminal state.
- "No longer needed" means the worker will not receive further feedback, advancement, or gate-related routing for the current entity. The runtime should not leave that decision implicit.

In practice, this means the Codex path should support two distinct follow-up modes:

1. advancement reuse, where the next stage continues on the same live worker thread
2. rejection/feedback routing, where findings are sent back to the original implementer worker if it is still alive

Both routes should use `send_input` on the existing worker handle when reuse is valid. Fresh dispatch is the fallback, not the default.

## Likely Implementation Surfaces

Keep the implementation bounded to the runtime contract and the tests that prove it:

- `skills/first-officer/references/first-officer-shared-core.md`
  - clarify the reuse decision tree
  - make `feedback-to` routing explicit about reusing the original worker thread when possible
  - state clearly when the old worker must be shut down
- `skills/first-officer/references/codex-first-officer-runtime.md`
  - replace the "completion is summary-only" drift with explicit reuse and shutdown semantics
  - describe `send_input` as the routing path for reused completion, advancement, or feedback messages
  - keep the Codex-specific bounded-run guidance, but stop implying that a completed worker is unreachable
- `tests/test_codex_packaged_agent_e2e.py`
  - add a live Codex exercise that proves a completed worker can receive routed advancement or feedback through `send_input`
  - assert that workers that are not needed anymore are explicitly shut down
- `tests/test_agent_content.py`
  - add static assertions so the shared core and Codex runtime cannot drift apart again

Do not expand this into a broader Codex orchestration rewrite. The task is to align runtime semantics, not redesign the dispatcher.

## Acceptance Criteria

1. The shared-core reuse rules clearly say that a completed worker may be reused only when the live worker is still addressable and the reuse conditions pass.
   - Test: static content assertion against `skills/first-officer/references/first-officer-shared-core.md`.

2. The Codex runtime reference clearly says that a completed worker can receive routed advancement or feedback through `send_input` when reuse is valid, and that explicit shutdown is required when the worker is no longer needed.
   - Test: static content assertion against `skills/first-officer/references/codex-first-officer-runtime.md`.

3. A live Codex runtime exercise proves that a completed implementation worker can receive routed follow-up through `send_input`.
   - Test: extend or add a Codex E2E test so the log shows the reused worker getting the routed message and continuing the entity thread instead of a fresh dispatch.

4. The same live Codex exercise proves that workers that are not needed anymore are explicitly shut down.
   - Test: assert the log includes the shutdown path for the worker that is being retired, or that the runtime emits the shutdown request before replacement dispatch.

5. Existing reuse and packaged-agent regression coverage still passes.
   - Test: rerun the current `tests/test_reuse_dispatch.py`, `tests/test_codex_packaged_agent_e2e.py`, and `tests/test_agent_content.py` coverage around the edited runtime contract.

## Test Plan

- Static checks are cheap and should cover the wording drift risk first.
- The key verification is a live Codex run, because the bug is about whether a completed worker is still routable in practice, not whether the prose sounds correct.
- Use the packaged-agent Codex path as the main exercise, and add a feedback-oriented variant if needed so the test can prove both advancement reuse and rejection routing through `send_input`.
- Keep the live test bounded to one or two entity transitions; the point is to prove routing and shutdown semantics, not to run a full workflow marathon.
- Cost/complexity is moderate: the live Codex run is slower than static checks, but the scope is narrow and the existing Codex harness already supports the path.
- E2E coverage is required. Static wording checks alone do not prove that a completed worker remains addressable or that shutdown happens explicitly.

The desired end state is consistent lifecycle behavior across shared core and Codex: reuse when the worker is still live and reusable, route feedback back to the original thread when possible, and shut down workers explicitly when they are done.

## Stage Report: ideation

1. [DONE] Expanded the task body into a scoped ideation spec with a concrete problem statement. The body now explains the shared-core/Codex mismatch and the task-117 failure that exposed it.
2. [DONE] Defined the desired runtime semantics for completed Codex workers. The spec now says when a worker is reusable, when it must be shut down, and how `feedback-to` should route through `send_input`.
3. [DONE] Identified the likely implementation surfaces and kept them bounded. The spec points to the shared core, the Codex runtime reference, and the Codex/static test surfaces only.
4. [DONE] Added concrete acceptance criteria with per-criterion test mapping. Each criterion now states how it will be tested.
5. [DONE] Made the test plan explicitly require a live Codex runtime exercise. The plan says static checks are insufficient and calls for a live `send_input` verification plus explicit shutdown coverage.
6. [DONE] Appended a complete `## Stage Report` for ideation at the end of the entity body. Every completion-checklist item is represented in the report with DONE status.
7. [DONE] Committed the ideation work after updating the entity body. The commit was created after the spec and stage report were written.

### Summary

This ideation pass turns the original observation into a concrete spec for Codex worker reuse and shutdown semantics. The task now names the mismatch, defines the desired lifecycle, and keeps the implementation bounded to the shared core, Codex runtime reference, and live Codex test coverage.
