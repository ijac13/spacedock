---
id: 086
title: Gate rejection paths don't route to Feedback Rejection Flow
status: validation
source: github issue #22 (observed in task 080)
started: 2026-04-03T05:30:00Z
completed:
verdict:
score: 0.6
worktree: .worktrees/ensign-gate-rejection-feedback
issue: "#22"
pr:
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

## Evidence

From rejection flow E2E logs:
- Every run dispatches bare `ensign` (not `spacedock:ensign`) — the FO doesn't fully read the runtime adapter
- When the FO does complete the bounce (3 dispatches), it works correctly — the gap is in triggering the bounce, not executing it
- Flakiness rate: ~50% with opus/low (1 out of 2 runs failed in 084 validation)
