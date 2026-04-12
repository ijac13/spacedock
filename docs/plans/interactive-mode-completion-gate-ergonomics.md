---
id: 140
title: Codex interactive-mode completion and gate ergonomics
status: implementation
source: FO observation during task 136 completion handling on 2026-04-12
score: 0.64
started: 2026-04-12T18:25:22Z
completed:
verdict:
worktree: .worktrees/spacedock-ensign-interactive-mode-completion-gate-ergonomics
issue:
pr:
---

The current Codex interactive runtime is functionally correct but too easy to drift away from the real next action. A worker can complete in the background, write a valid stage report, and notify the first officer, but the interactive session can keep talking about unrelated topics while the completed entity sits unprocessed. That is what happened in task 136: ideation finished, but the gate was not foregrounded until the captain explicitly asked for it.

There is a second, related problem in the same flow. During follow-on dispatch, ideation-stage work was treated as if it should default to an isolated worktree even though the workflow metadata does not mark `ideation` as `worktree: true`. That is the wrong default. Stage metadata must control dispatch behavior, and non-worktree stages must stay on the main branch unless the metadata says otherwise.

Single-entity mode already behaves more like the desired end state because it is outcome-driven and naturally stops on the entity result. Interactive Codex mode needs an equivalent event rule: a worker completion for a gated or critical-path stage should immediately become the first officer's next required action. The completion notification should foreground the stage report, force gate handling if a gate is pending, and only then allow unrelated orchestration to continue.

The same rule should apply to validation-stage rejections that already have a deterministic next step. When a validator recommends `REJECTED` and the stage defines `feedback-to`, the first officer should not leave that result sitting at a pseudo-gate waiting for another reminder. In interactive Codex mode, the completion should be foregrounded and the rejection should auto-route into the `feedback-to` stage immediately, while still surfacing the reroute and findings clearly to the captain.

This task stays Codex-specific. The goal is not to redesign the shared first-officer contract for every environment, but to make Codex interactive sessions treat completion events and stage metadata as first-class runtime signals.

## Proposed Approach

### 1. Foreground completion events in interactive sessions

Treat worker completion notifications as an interrupt-worthy event when the entity is in a stage that requires immediate operator attention. In practice, the FO should not let the conversation drift past a completed gated stage. When a completion arrives, the next required action should be to inspect the stage report, advance or reject the gate, and only then resume unrelated task handling.

This is a bounded ergonomics rule, not a new scheduling system. It only changes the order in which the FO responds inside an interactive Codex session.

### 2. Make dispatch honor stage metadata explicitly

Dispatch should derive its mode from the stage definition instead of assuming worktree isolation as a default. The key rule is simple: if a stage is not marked `worktree: true`, dispatch on main. Worktree creation should happen only when the metadata asks for it.

That keeps `ideation` and other shared-context stages aligned with the workflow schema. It also prevents the runtime from creating unnecessary worktrees just because a stage is being dispatched interactively.

### 3. Keep the scope inside Codex runtime guidance

The implementation should stay in the Codex-specific runtime guidance and dispatch logic. If a future change proves the same foregrounding rule belongs in the shared first-officer contract, that can be considered later. For this task, the safer path is to tighten the Codex behavior first and avoid broadening the surface area prematurely.

## Test Plan

The current shared live `--runtime` harness covers general first-officer behavior, dispatch shape, and stage transitions. What it does not cover well today is the interactive Codex path where completion notifications arrive while the conversation is still live. That missing coverage is the core risk here.

The test plan should therefore split into two buckets:

1. Shared `--runtime` coverage that already exists and should continue to pass.
2. Missing Codex interactive coverage that must be added for this task because the bug only appears when completion events arrive asynchronously during an interactive session.

This task needs interactive tests. Static checks alone are not enough because the failure mode is about ordering: the completion arrives, but the FO does not foreground it soon enough.

### Proposed new tests

1. `test_codex_completion_foregrounds_gate` - verify that a completion notification for a gated stage becomes the next operator action instead of being buried behind unrelated conversation. Purpose: prove the FO interrupt ordering. Coverage intention: interactive Codex path only.
2. `test_codex_dispatch_respects_stage_worktree_metadata` - verify that a stage without `worktree: true` dispatches on main and does not default into worktree creation. Purpose: prevent the regression that treated ideation as a worktree-backed stage. Coverage intention: metadata-driven dispatch behavior.
3. `test_codex_interactive_gate_after_completion` - verify that when a worker finishes a gated stage, the gate is presented before any unrelated follow-up orchestration continues. Purpose: prove the gate is foregrounded, not deferred. Coverage intention: interactive event handling.
4. `test_codex_validation_rejection_autoroutes_feedback` - verify that an interactive validation `REJECTED` result with `feedback-to` immediately reroutes to the implementation worker instead of waiting for a second prompt. Purpose: prove deterministic rejection handling is foregrounded as the next action. Coverage intention: interactive Codex rejection flow only.
5. `test_shared_runtime_regression` - keep the existing live `--runtime` harness scenarios passing unchanged. Purpose: guard against breaking the shared workflow runtime while tightening Codex behavior. Coverage intention: existing shared harness only.

## Acceptance Criteria

1. Interactive Codex sessions foreground a worker completion for a gated stage before continuing unrelated conversation.
   Test method: run the new interactive Codex completion test and assert that the stage report or gate prompt appears as the immediate next action after completion.
2. Dispatch honors stage metadata and does not default non-worktree stages into worktrees.
   Test method: run the dispatch metadata test and assert that a stage without `worktree: true` is launched on main.
3. Gated stages are handled immediately after completion, not deferred behind other orchestration.
   Test method: run the gate foregrounding test and verify the gate prompt is emitted before any unrelated follow-up instruction.
4. Validation-stage `REJECTED` results with `feedback-to` auto-route immediately in interactive Codex sessions.
   Test method: run the rejection autoroute test and verify the implementation stage receives the findings without waiting for a second captain prompt.
5. Existing shared live `--runtime` coverage continues to pass.
   Test method: run the current shared harness tests and confirm no regressions in the existing runtime behavior.
6. The task remains Codex-specific and does not require a shared-contract rewrite to validate the fix.
   Test method: review the changed scope and confirm the implementation and tests only touch Codex interactive runtime guidance plus the relevant dispatch path.

## Stage Report: ideation

- DONE - Expanded the seed into a full problem statement with the interactive completion foregrounding issue, the task 136 observation, and the specific non-worktree dispatch default bug.
- DONE - Proposed a bounded Codex-specific design for foregrounding completion events and honoring stage metadata during dispatch.
- DONE - Updated the test plan to distinguish existing shared live `--runtime` harness coverage from missing Codex interactive coverage.
- DONE - Documented proposed new tests with a specific purpose and coverage intention for each one.
- DONE - Defined concrete acceptance criteria and gave a test method for each.
- DONE - Kept the work on the main-branch entity file and did not rely on a worktree.
- DONE - Appended this `## Stage Report: ideation` section with checklist items and a summary.

### Summary

This ideation pass tightens the task around two Codex runtime gaps: completion events that fail to stay foregrounded in interactive sessions, and dispatch behavior that should follow stage metadata instead of defaulting non-worktree stages into worktrees. The proposed change is intentionally narrow, stays Codex-specific, and is testable with new interactive coverage plus regression checks for the existing shared `--runtime` harness.
