---
id: 153
title: "Codex FO: completion notifications must preempt side discussion"
status: ideation
source: "CL direction during 2026-04-14 session after task 148 validation completion handling"
started: 2026-04-15T04:11:21Z
completed:
verdict:
score: 0.69
worktree:
issue:
pr:
---

Follow-up to task 140.

Task 140 established the right contract: in interactive Codex mode, a completed gated or critical-path stage becomes the next required action before unrelated orchestration continues. The remaining gap is narrower and more concrete: the actual async completion-notification surface still lets the first officer drift into side discussion before consuming the completion event.

That is what reappeared during task 148's validation completion handling. The validator finished in the background, Codex surfaced the completion, and the FO still answered unrelated conversation before reconciling the validation result into the entity's true next action. This follow-up should close that runtime-ordering gap, not restate the contract again.

## Problem Statement

Task 138 covered pre-completion wait policy: in interactive Codex mode, workers may run in the background until the next orchestration step is blocked on their result. Task 140 covered post-completion ergonomics and contract wording: once the result exists, gated and critical-path completions should become the next required action.

This task is the remaining implementation gap between those two:

- the worker is already complete
- the completion arrives asynchronously in an interactive Codex session
- the FO receives a real completion event for an active entity
- the FO must consume that event before replying to unrelated side discussion

The relevant surface is the actual Codex async completion signal for a spawned worker, whether it appears as `<subagent_notification>` or the equivalent completion event/tool transcript item. A bounded `wait_agent(...)` path is not enough proof here because the regression is specifically about what happens when completion arrives while the captain is still talking about something else.

## Scope Boundary

- In scope: interactive Codex completion ordering after a background worker finishes.
- In scope: how the FO consumes async completion into gate presentation, advancement, reroute, or explicit blocked/terminal reporting.
- In scope: a narrow Codex interactive test surface that can prove ordering against real side discussion.
- Out of scope: changing task 138's background-wait policy before completion.
- Out of scope: rewriting shared first-officer scheduling semantics across Claude and Codex.
- Out of scope: proving the fix only by prompt text, runtime prose, or invocation-prompt coaching.

## Approach Options

### Recommended: add a narrow Codex interactive completion-ordering test surface

Keep the implementation local to the Codex runtime contract and add one focused interactive Codex harness path that can observe:

1. a worker dispatched into the background,
2. an async completion notification,
3. an immediate unrelated captain message,
4. the FO choosing completion handling before side discussion.

This is the smallest approach that proves the real bug. It likely means extending the existing PTY test utilities for Codex or adding a sibling Codex interactive helper, then writing one or two focused live E2Es.

### Alternative: rely on `codex exec --json` non-interactive logs

This is cheaper but insufficient. The existing `run_codex_first_officer()` and `CodexLogParser` path can prove bounded completion, `wait_agent(...)`, reuse, and rejection ordering in non-interactive runs. It cannot prove that an async completion preempts a later unrelated captain message because there is no side-discussion turn to interrupt.

### Alternative: push the whole rule into shared core

This broadens the task without evidence that the bug is shared. The observed gap is on the Codex interactive notification surface, so the safer design is to harden that runtime first and leave shared-core generalization to a later task only if another runtime exhibits the same failure.

## Required Behavior

In interactive Codex mode, any completion notification for an active entity becomes an interrupt-worthy dispatch event. The FO must consume that event before continuing unrelated side discussion.

Concrete outcomes:

1. If the completed stage is gated, the FO immediately reads the stage report or completion evidence and presents the gate review as the next required action.
2. If the completed stage is non-gated but on the entity's critical path, the FO advances the entity, redispatches the next stage, or reports the concrete blocked state before returning to unrelated discussion.
3. If the completed stage is `validation`, the report recommends `REJECTED`, and the stage defines `feedback-to`, the FO immediately routes the rejection to the `feedback-to` target instead of letting the result sit behind side discussion.
4. Side discussion may resume only after the completion event has been consumed into one of:
   - gate presentation / waiting-for-approval
   - routed `feedback-to` follow-up
   - next-stage advancement or redispatch
   - terminal merge / PR-pending handling
   - explicit blocked-state reporting
5. This ordering rule applies to the real async completion-notification surface, not just to synchronous `wait_agent(...)` paths that already foreground completion by construction.

## Likely Implementation Surfaces

Keep the branch local to Codex interactive completion handling:

- `skills/first-officer/references/codex-first-officer-runtime.md`
  - tighten the wording around async completion notifications so it explicitly governs the interactive completion-event path, not just bounded waits
- Codex interactive harness support
  - extend [scripts/test_lib_interactive.py](/Users/clkao/git/spacedock/scripts/test_lib_interactive.py) for Codex or add a narrow Codex sibling helper
  - current harness coverage is Claude-only for PTY interaction and non-interactive for Codex
- New focused Codex interactive E2E(s)
  - one gated completion preemption test
  - one rejection-flow preemption test, or a single carefully-scoped test that proves both notification consumption and immediate reroute
- Supporting guardrails
  - [tests/README.md](/Users/clkao/git/spacedock/tests/README.md) if the new Codex interactive harness needs usage guidance
  - [tests/test_agent_content.py](/Users/clkao/git/spacedock/tests/test_agent_content.py) for lightweight contract guardrails only

Avoid widening into `skills/first-officer/references/first-officer-shared-core.md` unless a tiny metadata exposure is unavoidable. The task is not a shared-core scheduler rewrite.

## Acceptance Criteria

1. In interactive Codex mode, when a background worker for a gated stage completes and emits an async completion notification, the FO's next user-visible action is gate handling before any reply to unrelated side discussion.
   - Test method: live Codex PTY E2E with a gated fixture. Let the worker finish in the background, then immediately send unrelated captain text. Assert the transcript shows gate review / waiting-for-approval before any answer to the unrelated text.
2. In interactive Codex mode, when a background worker completes a non-gated stage that is on the entity's critical path, the FO consumes the completion into advancement, redispatch, or an explicit blocked-state report before answering unrelated side discussion.
   - Test method: live Codex PTY E2E with a non-gated multi-stage fixture. After completion and immediate unrelated captain text, assert the transcript shows concrete advancement or blocked-state handling before side-discussion response.
3. In interactive Codex mode, when `validation` completes with `REJECTED` and `feedback-to`, the async completion notification triggers immediate rejection routing to the target stage before unrelated side discussion resumes.
   - Test method: live Codex PTY E2E using the rejection-flow fixture. After the validation completion notification and immediate unrelated captain text, assert the transcript shows rejection handling and routed follow-up before any unrelated reply.
4. The implementation targets the real async completion-notification surface rather than re-proving bounded `wait_agent(...)` behavior or injecting behavioral coaching into the invocation prompt.
   - Test method: branch review plus focused static checks confirm the new coverage uses a live interactive Codex path, the Codex invocation prompt stays minimal, and any static assertions are limited to runtime/harness guardrails.
5. The task remains a focused follow-up to 140 and does not reopen 138 or broaden into a shared-core rewrite.
   - Test method: diff review confirms the touched files stay inside Codex interactive runtime guidance, a Codex-specific interactive harness, and focused Codex tests.

## Test Plan

- Required live E2E: gated completion preempts side discussion in an interactive Codex session.
  - Cost: medium/high
  - Reason: this is the direct reproduction of the observed bug and cannot be proven by `codex exec --json`
- Required live E2E: validation `REJECTED` + `feedback-to` completion preempts side discussion and routes the follow-up immediately.
  - Cost: high
  - Reason: this is the highest-risk follow-on path because it combines async completion ordering with existing rejection-routing semantics
- Recommended live E2E: non-gated critical-path completion preempts side discussion with advancement or blocked-state reporting.
  - Cost: medium/high
  - Reason: this keeps the fix from overfitting gated-only behavior
- Supporting static checks: keep the Codex runtime wording and prompt-discipline guardrails aligned with the live behavior under test.
  - Cost: low
  - Reason: useful regression net, but explicitly not the proof surface
- Existing non-interactive Codex E2Es such as [tests/test_gate_guardrail.py](/Users/clkao/git/spacedock/tests/test_gate_guardrail.py) and [tests/test_rejection_flow.py](/Users/clkao/git/spacedock/tests/test_rejection_flow.py) remain valuable regression coverage for bounded paths, but they do not satisfy this task's primary proof requirement because they do not model side discussion after background completion.

E2E need: yes. A real interactive Codex run is required for acceptance because the bug is about async completion ordering against unrelated captain messages.

## Stage Report: ideation

- DONE - Clarified the scope boundary relative to task 138 and task 140.
  - 138 owns pre-completion background wait policy.
  - 140 owns the contract that completed gated/critical-path work becomes the next required action.
  - This task owns the remaining async completion-notification ordering gap in interactive Codex mode.
- DONE - Specified the concrete behavior for gated completions, non-gated critical-path completions, and `validation` + `feedback-to` rejection handling.
- DONE - Identified the narrow implementation surfaces: Codex first-officer runtime guidance, a Codex interactive PTY harness surface, focused interactive Codex E2Es, and lightweight static guardrails.
- DONE - Reframed acceptance criteria around real completion-notification paths instead of doc-text tautologies or bounded `wait_agent(...)` flows.
- DONE - Produced a proportional test plan with required live Codex interactive E2Es and explicitly called out why non-interactive Codex coverage is not sufficient.
- DONE - Kept the task scoped away from a broad shared-core rewrite.
- DONE - Updated only the entity body on main and appended this ideation report.

### Summary

The task is now scoped as a Codex-interactive follow-up to task 140: harden the actual async completion-notification path so background worker completions preempt side discussion until they are consumed into the entity's real next action. Because this almost certainly requires a new Codex interactive E2E surface, the ideation gate should get an independent reviewer.
