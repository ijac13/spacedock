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
pr: #87
---

The current Codex first-officer runtime guidance encourages `spawn_agent(...); wait_agent(...)` as the normal dispatch pattern. That works for bounded or single-entity runs, but in an interactive captain conversation it blocks the foreground while a worker is running. During task 136 dispatch, that meant the captain had to interrupt the session just to continue discussing another workflow improvement while the ideation worker was still in flight.

This task should refine the Codex first-officer runtime so interactive sessions keep workers in the background by default. The first officer should only foreground a `wait_agent` when the next orchestration step is truly blocked on that worker result, or when the captain explicitly asks to wait. Bounded or single-entity runs remain a separate case where immediate waiting is still appropriate because completion is the point of the turn.

## Problem Statement

Codex interactive sessions are conversational, not strictly transactional. The first officer can spawn a worker and still have useful work to do in the same turn, such as discussing scope, clarifying requirements, or advancing a different entity. If the runtime foregrounds `wait_agent` immediately after dispatch, the conversation loses that flexibility and the captain has to interrupt the turn to keep working.

The observed failure from task 136 was not that waiting exists, but that the default waiting behavior was applied in the wrong mode. Interactive FO sessions should treat worker execution as background activity unless the next orchestration step depends on the result or the captain explicitly asks to block. This task is Codex-specific runtime guidance; it should not generalize the behavior into a shared contract for all platforms.

## Proposed Approach

Define two waiting modes in the Codex first-officer runtime guidance:

1. **Interactive mode.** After `spawn_agent`, keep the worker in the background and continue the turn. Foreground a `wait_agent` only when:
   - the next step is blocked on that worker result,
   - the worker result is needed before any other orchestration can proceed,
   - or the captain explicitly asks to wait.
2. **Bounded or single-entity mode.** Keep the current blocking behavior when the session is focused on one entity or one immediate outcome. In that case, waiting right away is still the correct default because the session is already scoped around a single completion.

The implementation should identify interactive vs bounded mode from existing Codex runtime context rather than introducing a new shared abstraction. The goal is a local guidance change: same worker APIs, different waiting policy depending on the session shape.

## Acceptance Criteria

1. Interactive Codex sessions do not foreground `wait_agent` by default after dispatch.
   - Test: run the Codex FO interactive dispatch path and verify the worker is left running in the background until a block condition or explicit wait request occurs.
2. The FO foregrounds `wait_agent` when the next orchestration step is actually blocked on the worker result.
   - Test: use a scenario where the next step requires the worker output and confirm the runtime waits before proceeding.
3. The FO foregrounds `wait_agent` when the captain explicitly asks to wait.
   - Test: drive an interactive session with an explicit wait request and confirm the runtime waits even if no dependency block exists.
4. Bounded or single-entity runs can still wait immediately after dispatch.
   - Test: execute the single-entity/bounded path and confirm the blocking behavior remains unchanged.
5. The behavior stays Codex-specific and does not require a shared-contract change.
   - Test: review the touched runtime guidance and confirm the change is limited to Codex-first-officer behavior, not shared workflow semantics.

## Test Plan

Static checks are the main verification tool because this is a runtime-guidance change, not a new algorithm. Add or update focused tests around the Codex first-officer dispatch path so the policy difference is explicit:

- a unit or integration-level test for interactive mode that asserts `spawn_agent` does not immediately trigger `wait_agent`,
- a test for the blocked-path case that asserts waiting does happen when the next orchestration step depends on the result,
- and a regression test for bounded/single-entity mode that preserves immediate waiting.

Estimated cost is low to moderate because the change should be localized to first-officer runtime guidance and its corresponding harness coverage. Full end-to-end coverage is only needed if the implementation cannot be exercised deterministically through the existing dispatch test harness; otherwise, the targeted runtime tests are enough.

## Stage Report: ideation

- [x] Problem statement expanded
  Explained why interactive Codex FO sessions should not foreground `wait_agent` by default and called out the task 136 failure mode.
- [x] Bounded design proposed
  Distinguished interactive mode from bounded/single-entity mode and kept the change Codex-specific instead of turning it into a shared contract.
- [x] Acceptance criteria defined with test mapping
  Listed five concrete criteria and attached a test approach to each one.
- [x] Test plan made proportional
  Identified static/runtime harness checks as the primary validation path and reserved E2E only if the existing harness cannot cover the behavior deterministically.

### Summary

The task is now scoped as a Codex-only runtime guidance change: interactive sessions should prefer background worker execution, while bounded or single-entity runs may keep immediate waiting. The revised body includes concrete acceptance criteria and a proportional test plan so implementation can be validated without over-scoping the work. This update stays inside the assigned worktree and leaves workflow scaffolding untouched.

## Stage Report: implementation

- [x] DONE: Implement the Codex-specific runtime guidance and minimal supporting tests.
  Updated `skills/first-officer/references/codex-first-officer-runtime.md`, `scripts/test_lib.py`, `tests/test_agent_content.py`, and `tests/test_codex_packaged_agent_ids.py` to make interactive waits background by default while preserving bounded behavior.
- [x] DONE: Preserve the blocked-next-step and explicit-captain-wait paths.
  The Codex runtime now says to wait when the next orchestration step is blocked on the worker result or when the captain explicitly asks to wait; the generated invocation prompt mirrors that rule.
- [x] DONE: Preserve bounded or single-entity immediate waiting.
  Both the runtime doc and the invocation prompt still allow immediate waiting when the run is scoped to a single completion.
- [x] DONE: Keep the change Codex-specific.
  Only the Codex runtime guidance and Codex harness prompt/tests changed; the shared first-officer contract was left untouched.
- [x] DONE: Run targeted verification and record concrete evidence.
  `python3 -m py_compile scripts/test_lib.py` passed; `uv run --with pytest python tests/test_codex_packaged_agent_ids.py` passed (6/6); `uv run --with pytest python tests/test_agent_content.py` passed (28/28).
- [x] DONE: Commit the implementation work in the assigned worktree.
  Code changes were committed as `d5fd50b` (`implement: codex interactive wait policy`).

### Summary

Interactive Codex first-officer guidance now keeps spawned workers in the background by default and only foregrounds `wait_agent` when the next step is blocked or the captain explicitly requests waiting. The bounded and single-entity paths still permit immediate waiting, and the new tests pin both the runtime wording and the generated invocation prompt to that split.
