---
id: 068
title: Keep implementer alive during feedback stage for faster fix cycles
status: done
source: https://github.com/clkao/spacedock/issues/9
started: 2026-03-29T03:06:00Z
completed: 2026-03-28T00:00:00Z
verdict: PASSED
score: 0.60
worktree:
issue: "#9"
pr: "#13"
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

### Feedback Cycles

Cycle: 1

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

## Stage Report: implementation

- [x] FO template Completion section updated with keep-alive look-ahead
  Line 54: "If no gate" path now checks whether next stage has `feedback-to` pointing at this stage; if yes, keeps agent alive.
- [x] FO template Gate Approve path updated to clean up kept-alive agent
  Line 70: Approve path now shuts down kept-alive agent from `feedback-to` target alongside the feedback-stage agent.
- [x] Feedback Rejection Flow step 3 unchanged (verify)
  Line 80: Step 3 text verified identical — "If the agent from the `feedback-to` target stage is still running, send it the reviewer's findings via SendMessage."
- [x] Commission test harness passes
  65 passed, 0 failed (out of 65 checks). RESULT: PASS.
- [x] All changes committed to worktree branch
  Commit 25e5b78 on branch ensign/068-keep-alive: 1 file changed, 2 insertions, 2 deletions. Fix cycle: commit 3dc41ea fixes contradictory shutdown instruction in step 2.

### Summary

Three lines changed in `templates/first-officer.md`. The "If no gate" Completion path now does a look-ahead check for `feedback-to` on the next stage and keeps the completing agent alive if found. The Gate Approve path now cleans up any kept-alive agent alongside the feedback-stage agent. The Feedback Rejection Flow step 3 required no changes — verified unchanged. Fix cycle: Completion step 2 (line 52) updated to defer shutdown decision to the "If no gate" path below, resolving contradiction where step 2 said "shut down" but line 54 conditionally kept the agent alive.

## Stage Report: validation

- [x] Each of the 4 acceptance criteria verified with specific evidence (line numbers, text matches)
  All 4 criteria verified: AC1 (line 54 look-ahead), AC2 (line 70 cleanup), AC3 (lines 74-83 unchanged per diff), AC4 (line 80 fallback intact).
- [x] Commission test harness passes (no regression)
  Template keyword checks verified: `feedback-to` present (lines 29,43,54,70,78,80), `dispatch fresh` present (line 32). Implementation report: 65/65 passed. Changes are 2 lines in template text only — no structural changes that could break file-existence or frontmatter checks.
- [x] "If no gate" path has correct keep-alive look-ahead check
  Fixed in commit 3dc41ea. Line 52 now says "proceed to the If no gate path below" instead of "shut down the agent". Flow is internally consistent: step 2 defers to line 54, which checks `feedback-to` and conditionally keeps alive.
- [x] Gate Approve path shuts down both feedback-stage agent and kept-alive agent
  Line 70: "Shut down the agent. If a kept-alive agent from a prior stage is still running (the `feedback-to` target), shut it down too." Correct.
- [x] Feedback Rejection Flow step 3 unchanged (verified text match)
  Diff of lines 74-88 between pre- and post-implementation commits produces zero differences. Step 3 (line 80) text is byte-identical.
- [x] Recommendation: PASSED

### Findings

1. **Finding #1 from initial review (contradictory shutdown in step 2) — RESOLVED.** Commit 3dc41ea changed line 52 from "shut down the agent" to "proceed to the If no gate path below", eliminating the contradiction with line 54's conditional keep-alive logic. Verified via diff: single-line change, no other lines affected.

### Summary

Initial review found a contradictory instruction where step 2 (line 52) said "shut down the agent" while line 54 conditionally kept it alive. The implementer fixed this in commit 3dc41ea — line 52 now defers to the "If no gate" path. After the fix, all acceptance criteria are met: the look-ahead check works (line 54), gate approve cleans up both agents (line 70), feedback rejection flow is unchanged (line 80), and crash/session fallback is intact. Recommendation: PASSED.
