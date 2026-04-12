---
id: 131
title: Codex first officer: wait bookkeeping for reused worker threads after send_input
status: implementation
source: FO observation during task 117 feedback routing on 2026-04-11
started: 2026-04-11T19:19:27Z
completed:
verdict:
score: 0.68
worktree: .worktrees/spacedock-ensign-codex-first-officer-reused-worker-wait-bookkeeping
issue:
pr:
---

## Problem Statement

Task 130 made reused Codex workers reachable through `send_input` and clarified that they can be explicitly shut down when no longer needed. The remaining gap is bookkeeping: once the FO routes follow-up work to a reused worker, that worker is still being treated as if it were only "available" rather than active again. That makes the entity look idle even when its reused worker is still on the critical path, and it weakens the FO's ability to know when it must block advancement of that entity on the reused result.

The runtime contract needs to be explicit about this lifecycle:

- after `send_input`, the reused worker becomes active again
- FO must track that active reused worker explicitly, not just the original dispatch
- if the reused worker's result is on that entity's critical path, FO must `wait_agent` on that same agent instead of treating `send_input` as fire-and-forget
- status/reporting should describe the worker as active again, not merely reachable
- this waiting is entity-scoped bookkeeping; unrelated ready entities should still be dispatchable
- once the reused cycle is finished and no later advancement is expected, the worker must be shut down explicitly

## Proposed Approach

Keep the change tightly bounded to the Codex first-officer runtime/shared-core contract and the existing runtime-switchable E2E surfaces.

1. Update the Codex FO runtime contract so "reuse through `send_input`" implies an active-again state, not just a routed message.
2. Make the runtime guidance state when the FO must wait: any reused worker whose completion is part of that entity's current critical path must be followed by `wait_agent` on that same worker handle.
3. Keep shutdown semantics explicit: if the reused worker will not receive more input or gating, shut it down after the reused cycle completes.
4. Prove the generic rejection/feedback behavior through the shared rejection-flow test with `--runtime codex`, and keep any Codex-only E2E coverage narrowly focused on the same-handle reuse bookkeeping delta.
5. Do not solve FO behavior gaps by adding more behavioral coaching to the Codex invocation prompt. The test may identify the workflow target and requested entity scope, but the FO behavior under test must come from the skill scaffolding, shared core, runtime adapter, and fixture/workflow structure.

This stays within the existing architecture. It does not require a new workflow mechanism, only clearer runtime contract wording and stronger end-to-end verification of the existing control flow.

## Bounded Implementation Surfaces

- `scripts/test_lib.py`: keep the Codex invocation helper thin and limited to workflow targeting/scope, not behavior shaping.
- `skills/first-officer/references/codex-first-officer-runtime.md`: this is the runtime source of truth for when a reused worker becomes active again, when FO must wait for that entity, and when shutdown is required.
- `skills/first-officer/references/first-officer-shared-core.md`: shared rejection-flow routing requirements must stay aligned with the Codex runtime.
- `tests/test_rejection_flow.py`: this is the shared runtime-switchable rejection/feedback path and should cover the generic Codex rejection-flow behavior.
- `tests/test_codex_packaged_agent_e2e.py`: if retained, this should only prove the narrower Codex same-handle reuse bookkeeping delta rather than re-specifying the whole rejection flow in prompt text.

## Codex FO Prompt Constraints For Tests

When testing Codex FO behavior for this task:

- invoke only `$first-officer` / `spacedock:first-officer`
- keep the invocation prompt minimal: workflow target, runtime scope, and entity scope only
- do not add custom prompt prose that tells FO how to do reuse, waiting, shutdown, or rejection routing
- do not restate runtime rules in `run_goal` text just to make the FO behave
- if the FO needs more guidance, encode it in the scaffolding surfaces under test (`SKILL.md` references, shared core, runtime adapter, or fixture/workflow structure)
- prefer the shared `--runtime codex` test path for generic workflow behavior; reserve Codex-only E2E tests for truly Codex-specific deltas

## Acceptance Criteria

1. The Codex FO runtime explicitly states that `send_input` to a reused worker makes that worker active again, not just addressable.
   Test: a static content check on the assembled Codex FO runtime text verifies the active-again wording is present and unambiguous.
2. The Codex FO runtime explicitly requires `wait_agent` when the reused worker's result is on that entity's critical path.
   Test: a static content check verifies the wait requirement is described alongside reused-worker follow-up, and the live E2E log shows the FO actually waits on the reused path.
3. The Codex FO runtime and shared core explicitly state that reused-worker waiting is entity-scoped, not whole-FO blocking.
   Test: static content checks verify the runtime/shared-core wording says unrelated ready entities may still be dispatched or advanced.
4. The Codex FO runtime and shared-core guidance explicitly require shutdown when the reused worker will not receive more work.
   Test: a static content check verifies the shutdown wording, and live Codex runtime output shows an explicit shutdown call after the reused cycle completes.
5. The shared rejection-flow path exercises Codex rejection follow-up end to end without extra FO prompt coaching.
   Test: `tests/test_rejection_flow.py --runtime codex` reaches the first rejection outcome and shows rejection follow-up behavior driven by scaffolding/runtime, not custom prompt prose.
6. Codex-specific reuse bookkeeping is exercised on the same worker handle.
   Test: the relevant Codex log must show that the reused worker is treated as active again and that the entity-critical-path result is awaited with `wait_agent` on the same handle rather than treated as background work or replacement dispatch.
7. Codex-specific reuse bookkeeping exercises explicit shutdown after the reused cycle.
   Test: the relevant Codex log must show the reused worker is explicitly shut down once it is no longer needed.
8. Codex FO tests for this task do not rely on extra behavioral coaching beyond `$first-officer` invocation plus workflow/entity scope.
   Test: static inspection of the invocation helper and test run goals confirms they identify the workflow target and scope without re-specifying reuse/wait/shutdown/rejection-routing rules.

## Test Plan

- Static checks: low cost, deterministic. Verify the runtime wording in `skills/first-officer/references/codex-first-officer-runtime.md`, the shared rejection-flow wording in `skills/first-officer/references/first-officer-shared-core.md`, and the thin-helper constraints in `scripts/test_lib.py`.
- Shared live Codex E2E: medium cost, required. Use `tests/test_rejection_flow.py --runtime codex` for the generic rejection/feedback path.
- Narrow Codex-specific E2E: only if needed. Keep `tests/test_codex_packaged_agent_e2e.py` limited to the same-handle reuse bookkeeping delta rather than generic rejection-flow coverage.
- No extra unit-only surface is needed for this task. The behavioral guarantee is only meaningful if the live Codex path is exercised.

## Stage Report: ideation

- [x] DONE: Expanded the seed into a full problem statement, proposed approach, acceptance criteria, and test plan.
  The body now defines the reused-worker bookkeeping gap and the desired runtime semantics after `send_input`.
- [x] DONE: Defined the runtime contract so a reused worker becomes active again after `send_input` and FO waits on it when the result is entity-critical-path.
  The new spec text states the active-again, entity-scoped `wait_agent`, and non-global-blocking requirements directly.
- [x] DONE: Identified the bounded implementation surfaces needed for runtime wording and test coverage.
  The body now names the Codex runtime/shared-core surfaces and the relevant live Codex tests.
- [x] DONE: Added concrete acceptance criteria with test methods for each criterion.
  Each criterion now has a matching static or live-E2E test note.
- [x] DONE: Required live Codex E2E coverage for reused-worker follow-up, active-again bookkeeping, wait behavior, and explicit shutdown.
  The test plan now splits shared rejection-flow coverage from the narrower Codex-specific reuse-bookkeeping proof.

### Summary

This ideation pass turns the seed into a bounded runtime spec for Codex reused-worker bookkeeping. The task now focuses on making `send_input` imply an active-again worker state, ensuring entity-critical-path follow-up uses `wait_agent` without blocking unrelated entities, and proving the cycle through the shared Codex rejection-flow path plus any narrower Codex-only reuse-bookkeeping checks that remain necessary.

## Stage Report: implementation

- [x] Read the entity spec and kept the implementation bounded to the listed surfaces.
  The implementation work has stayed on the runtime/shared-core/helper/test surfaces for Codex FO behavior.
- [x] Implemented the runtime-contract and helper wording changes for active-again reused workers and entity-scoped `wait_agent` behavior.
  The Codex runtime and shared-core now state that `send_input` makes the reused worker active again, requires `wait_agent` on the same handle for entity-critical-path results without globally blocking unrelated dispatch, and requires explicit shutdown after the reused cycle. The invocation helper has been cleaned back to a thin targeting/scope surface.
- [x] Updated live Codex test coverage to reduce prompt-layering and align with the scaffolding-first approach.
  The remaining Codex tests are being narrowed so generic rejection behavior lives on the shared `--runtime codex` path while any Codex-only E2E stays focused on the reuse-bookkeeping delta.
- [ ] FAIL: Ran the relevant verification and recorded concrete outcomes.
  Static checks passed, but the live Codex proof is still incomplete. Earlier `tests/test_codex_packaged_agent_e2e.py` runs stalled during worker waits, and the shared `tests/test_rejection_flow.py --runtime codex` path is the next required live proof to stabilize.
- [x] Appended a `## Stage Report: implementation` section to the entity file with every checklist item represented as DONE, SKIPPED, or FAILED.
  This report is appended at the end of the entity file in the assigned worktree copy.
- [x] Committed the work in the worktree before reporting completion.
  The implementation commit includes the runtime wording, helper wording, test updates, and this stage report.

### Summary

The Codex first-officer runtime and shared-core now treat reused `send_input` workers as active again, require same-handle waiting on entity-critical-path reuse without globally blocking unrelated work, and keep explicit shutdown semantics after the reused cycle. The invocation/helper surface has been cleaned toward minimal `$first-officer` targeting only. Static verification has passed, while the remaining live Codex proof still needs to be stabilized on the shared rejection-flow path and, if necessary, a narrower Codex-only reuse-bookkeeping check.
