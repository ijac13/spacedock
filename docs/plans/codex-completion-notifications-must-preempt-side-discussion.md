---
id: 153
title: "Codex FO: completion notifications must preempt side discussion"
status: backlog
source: "CL direction during 2026-04-14 session after task 148 validation completion handling"
started:
completed:
verdict:
score: 0.69
worktree:
issue:
pr:
---

Follow-up to task 140.

Task 140 put the right interactive Codex rule into the runtime contract, but the actual async completion-notification path still is not hardened enough. When a worker finishes in the background and Codex surfaces a completion notification, the first officer can still answer unrelated user text before consuming that completion into the entity's real next action. That is what reappeared during task 148: the validator completed, but the FO did not immediately inspect the result and foreground the validation gate.

This task should close the gap between the contract wording and the real notification-driven behavior. The target is not "be generally more attentive"; it is a specific runtime rule for active entities in interactive Codex sessions.

## Required behavior change

In interactive Codex mode, any completion notification for an active entity becomes an interrupt-worthy dispatch event. The FO must process it before engaging in side discussion.

Specifically:

1. When a completion notification indicates that a worker for an active entity finished, the FO immediately treats that notification as the entity's next required action.
2. The FO reads the latest stage report or completion evidence and reconciles it with entity state before answering unrelated conversation.
3. If the completed stage is gated, gate presentation becomes the next required action before any unrelated orchestration or discussion continues.
4. If the completed stage is `validation` and the report recommends `REJECTED` and the stage defines `feedback-to`, the FO routes the rejection immediately instead of leaving it sitting at a pseudo-gate behind unrelated conversation.
5. If the completed stage is non-gated but is on the entity's critical path, the FO advances, redispatches, or reports the blocked state before answering unrelated workflow chatter.
6. Side discussion may resume only after the completion event has been consumed into one of: gate presentation, routed feedback, stage advancement, terminal merge/PR-pending handling, or an explicit blocked state report.
7. This rule must be enforced for the actual async notification surface (`<subagent_notification>` or the equivalent Codex completion event), not only for synchronous `wait_agent(...)` paths.

## Non-goals

- Do not revisit the pre-completion background-wait policy from task 138.
- Do not redesign shared-core scheduling across every runtime.
- Do not "prove" the behavior only by adding prompt text or doc-text tautologies.

## Acceptance Criteria

1. In interactive Codex mode, when a background worker for a gated stage completes and emits a completion notification, the FO's next action is gate handling before unrelated conversation continues.
   - Test: add Codex-targeted coverage that exercises a real completion-notification path and verifies the final FO output foregrounds the gate rather than replying to side discussion first.
2. In interactive Codex mode, when validation completes with `REJECTED` and `feedback-to`, the completion notification triggers immediate reroute to the target stage.
   - Test: Codex rejection-flow coverage proves the reroute is initiated from the completion event rather than only from a bounded `wait_agent(...)` path.
3. The runtime contract and guardrail tests mention the active-entity completion-notification rule explicitly enough that this event surface cannot regress silently.
   - Test: static checks cover the shipped runtime wording and the harness path that handles completion notifications.
4. The task remains a focused hardening follow-up to 140 rather than a reopening of 138 or a broad shared-core rewrite.
   - Test: branch review confirms the change stays inside Codex interactive completion handling and related tests.

## Test Plan

- Live Codex E2E around a gated stage where the worker completes in the background and the captain sends unrelated conversation immediately afterward; verify the FO interrupts itself to foreground the gate.
- Live Codex rejection-flow E2E that proves a validation completion notification with `REJECTED` and `feedback-to` auto-routes before side discussion.
- Static guardrails that mention the notification path explicitly and keep the runtime guidance aligned with the tested behavior.
