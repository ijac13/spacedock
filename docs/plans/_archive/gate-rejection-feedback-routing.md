---
id: 086
title: Gate rejection paths don't route to Feedback Rejection Flow
status: done
source: github issue #22 (observed in task 080)
started: 2026-04-03T05:30:00Z
completed: 2026-04-06T17:05:46Z
verdict: PASSED
score: 0.6
worktree:
issue: "#22"
pr: "#34"
---

When the captain rejects at a validation gate with `feedback-to`, the FO follows the generic "Reject + redo" path instead of entering the Feedback Rejection Flow. It shuts down both agents and dispatches fresh ones sequentially, instead of keeping the implementer alive and routing findings to it.

See issue #22 for full analysis.

## Root cause analysis

The shared core (`references/first-officer-shared-core.md`) has these gate paths:

```
If the stage is gated:
- never self-approve
- present the stage report to the human operator
- keep the worker alive while waiting at the gate
- if the stage is a feedback gate that recommends REJECTED,
  auto-bounce directly into the feedback rejection flow
```

**Gap 1: Only auto-bounce is covered.** Line 96 handles the case where the reviewer recommends REJECTED and the FO auto-bounces without waiting for the captain. But there's no explicit path for when the captain manually confirms a rejection at a gated `feedback-to` stage. The FO falls through to generic gate handling (which doesn't know about `feedback-to`).

**Gap 2: Ambiguous test prompt.** The rejection flow E2E tells the FO "approve the REJECTED verdict so the rejection flow proceeds." This is ambiguous — "approve" could mean "approve the gate" (advance to next stage) or "confirm the rejection" (enter feedback flow). The FO interprets this differently each run, explaining the observed flakiness:
- 084 opus/low run 1: 1 dispatch (stopped at rejection)
- 084 opus/low run 2: 3 dispatches (full rejection bounce)
- Main opus/low: 3 dispatches (full rejection bounce)

**Gap 3: No captain-rejection gate path.** The gate paths need an explicit entry:
```
If the captain rejects at a gated stage that has `feedback-to`:
- enter the Feedback Rejection Flow
- route findings to the feedback-to target stage
- this takes priority over generic rejection handling
```

## Proposed fix

Two changes:

1. **Shared core** — Add an explicit gate path for captain-initiated rejection with `feedback-to`, before the generic rejection handling.

2. **Test prompt** — Change "approve the REJECTED verdict" to something unambiguous like "When the reviewer recommends REJECTED, confirm the rejection so the feedback flow routes fixes back to implementation."

## Stage Report: implementation

1. Shared core updated — explicit captain-rejection gate path added for `feedback-to` stages: **DONE**
   - Added bullet to `## Completion and Gates` gated-stage handling in `references/first-officer-shared-core.md` line 97
   - Captain rejection at a gated `feedback-to` stage now explicitly enters the Feedback Rejection Flow, taking priority over generic rejection handling
2. Test prompt clarified — no longer ambiguous about "approve the REJECTED verdict": **DONE**
   - Changed from "approve the REJECTED verdict so the rejection flow proceeds" to "confirm the rejection so the feedback flow routes fixes back to implementation"
3. Static tests pass: **DONE**
   - 51 passed, 0 failed
4. Rejection flow E2E passes with opus/low: **DONE**
   - 5 passed, 0 failed (out of 5 checks)
   - 3 ensign dispatches observed (implementation, validation, fix after rejection)
   - Full rejection bounce completed successfully
5. Changes committed on ensign/gate-rejection-feedback branch: **DONE**
   - Commit `3fcd207`

## Evidence

From rejection flow E2E logs:
- Every run dispatches bare `ensign` (not `spacedock:ensign`) — the FO doesn't fully read the runtime adapter
- When the FO does complete the bounce (3 dispatches), it works correctly — the gap is in triggering the bounce, not executing it
- Flakiness rate: ~50% with opus/low (1 out of 2 runs failed in 084 validation)

## Stage Report: validation

1. Merge main into validation branch: **DONE** — Already up to date, no conflicts.
2. Verify shared-core change: **DONE** — One bullet added at line 97 of `references/first-officer-shared-core.md`, inside the "If the stage is gated:" block, immediately after the existing auto-bounce bullet. Wording is clear: "if the captain rejects at a gated stage that has `feedback-to`, enter the Feedback Rejection Flow and route findings to the `feedback-to` target stage. This takes priority over generic rejection handling." Correctly addresses Gap 3 from the root cause analysis.
3. Verify test prompt change: **DONE** — Changed from "approve the REJECTED verdict so the rejection flow proceeds" to "confirm the rejection so the feedback flow routes fixes back to implementation." The new wording eliminates the ambiguity identified in Gap 2 — "confirm" cannot be misread as "approve the gate," and the expected outcome (feedback flow routing) is explicit.
4. Static tests: **DONE** — 51 passed, 0 failed.
5. Rejection flow E2E (3+ runs, opus/low): **DONE** — 4 runs total:
   - Run 1: PASS — 3 ensign dispatches, 5/5 checks, 287s
   - Run 2: PASS — 3 ensign dispatches, 5/5 checks, 247s
   - Run 3: FAIL — 2 ensign dispatches, timed out at 600s due to API rate limit ("You've hit your limit"). Log analysis confirms the FO correctly entered the Feedback Rejection Flow and dispatched the fix worker (dispatch 2); it failed only because the API rate limit prevented the 3rd dispatch. This is an infrastructure issue, not a logic failure.
   - Run 4: PASS — 3 ensign dispatches, 5/5 checks, 276s (replacement run)
   - **Result: 3/3 non-rate-limited runs passed. FO correctly entered feedback flow in all 4 runs.**
6. Regression check: **DONE** — Gate guardrail E2E (opus/low) passed 7/7 checks. The added shared-core bullet did not break gate-hold behavior or self-approval prevention.
7. Recommendation: **PASSED**

### Evidence

**Flakiness improvement:** Before the fix, the rejection flow had ~50% flakiness with opus/low (1 of 2 runs failed in 084 validation). After the fix, 3 of 3 valid runs passed (100%). The single FAIL was caused by API rate limiting, not routing logic — the FO's log shows it correctly identified the rejection, entered the Feedback Rejection Flow, and dispatched the fix worker before hitting the limit.

**Root cause addressed:** In all 4 runs, the FO explicitly mentioned entering the "Feedback Rejection Flow" and routing fixes back to implementation. The run 3 log shows: "Confirming the rejection and entering the Feedback Rejection Flow to route fixes back to implementation." This confirms both the shared-core instruction and the disambiguated test prompt are working as intended.

**No regressions:** Gate guardrail test passed cleanly, confirming the new shared-core bullet does not interfere with normal gate behavior.
