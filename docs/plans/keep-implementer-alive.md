---
id: 068
title: Keep implementer alive during feedback stage for faster fix cycles
status: ideation
source: https://github.com/clkao/spacedock/issues/9
started: 2026-03-29T03:06:00Z
completed:
verdict:
score: 0.60
worktree:
issue: "#9"
pr:
---

When a feedback stage runs, the FO shuts down the implementer and redispatches on rejection. Keeping the implementer alive during review would enable faster fix cycles — the implementer retains full context and can fix immediately on rejection.

See GitHub issue #9 for details.

## Problem

The FO template's Completion section (line 52-54) shuts down the agent immediately when a non-gated stage completes: "If no gate, shut down the agent." When implementation completes and the next stage is validation (a feedback stage with `feedback-to: implementation`), the implementer is already gone before validation starts.

The Feedback Rejection Flow (step 3) handles this: "If it was shut down, dispatch an agent into the same worktree." This works but the fresh agent must re-read the entity, understand the codebase, and parse the findings — losing the original agent's full context.

## Proposed Approach

Three touch points in `templates/first-officer.md`:

### Change 1: Completion, "If no gate" path (line 54)

Current:
> **If no gate:** If terminal, proceed to merge. Otherwise, run `status --next` and dispatch the next stage fresh.

Proposed:
> **If no gate:** If terminal, proceed to merge. Otherwise, check whether the next stage has `feedback-to` pointing at this stage. If yes, keep the agent alive — do not shut it down. Run `status --next` and dispatch the next stage.

### Change 2: Gate Approve path (line 70)

Current:
> **Approve:** Shut down the agent. Dispatch a fresh agent for the next stage.

Proposed:
> **Approve:** Shut down the agent. If a kept-alive agent from a prior stage is still running (the `feedback-to` target), shut it down too. Dispatch a fresh agent for the next stage.

### Change 3: Feedback Rejection Flow step 3 (line 80)

No change needed. Already says: "If the agent from the `feedback-to` target stage is still running, send it the reviewer's findings via SendMessage." With the keep-alive behavior, this path becomes the common case instead of the fallback.

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Implementer crashes while idle | Feedback Rejection Flow step 3 handles this: "If it was shut down, dispatch an agent into the same worktree." Crash = shut down. No change needed. |
| Session boundary (FO restarts) | FO has no memory of which agents are alive. Step 3's fallback dispatches a fresh agent if the implementer is gone. Same as today. |
| Multiple entities in flight | Each entity's agents are independent. Agent names include the entity slug, so no collision. |
| Approval (happy path) | Gate approve shuts down both reviewer and kept-alive implementer. |
| Non-adjacent `feedback-to` | Only the immediate next stage is checked. Non-adjacent `feedback-to` uses the existing redispatch fallback. |

## Acceptance Criteria

1. FO template Completion section keeps the agent alive when the next stage has `feedback-to` pointing at the completing stage
2. FO template Gate Approve path shuts down the kept-alive target-stage agent alongside the feedback-stage agent
3. Feedback Rejection Flow step 3 works unchanged (the kept-alive agent is now the common case)
4. Crash/session-boundary fallback (redispatch) still works when the kept-alive agent is gone

## Stage Report: ideation

- [x] Problem statement with concrete examples from this session
  Documented: FO shuts down implementer at Completion (line 52-54) before validation starts; Feedback Rejection Flow step 3 redispatches but loses context. Issue #9 describes the manual workaround used in task 065.
- [x] Proposed FO template changes with exact wording
  Three touch points identified: (1) Completion "If no gate" path adds look-ahead check for `feedback-to`, (2) Gate Approve path adds cleanup of kept-alive agent, (3) Feedback Rejection Flow step 3 unchanged — already handles the keep-alive case.
- [x] Edge cases addressed (what if implementer crashes, session boundary, etc.)
  Five scenarios covered: crash (fallback redispatch), session boundary (no FO memory, fallback), multiple entities (independent agents), approval (clean shutdown of both), non-adjacent feedback-to (only checks immediate next stage).
- [x] Acceptance criteria defined
  Four testable criteria covering keep-alive behavior, approval cleanup, rejection flow compatibility, and crash fallback.

### Summary

The change is narrowly scoped to the FO template's Completion section. When a non-gated stage completes, the FO checks whether the immediate next stage has `feedback-to` pointing back. If yes, the agent stays alive instead of being shut down. The Feedback Rejection Flow already handles the keep-alive case — this change just ensures the agent is actually alive when rejection happens. On approval, both agents are shut down. Crash and session-boundary fallbacks work unchanged.
