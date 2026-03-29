---
id: 073
title: Auto-bounce rejection at feedback stages without captain approval
status: validation
source: 033 validation incident — FO waited for captain on a clear rejection
started: 2026-03-29T16:45:00Z
completed:
verdict:
score: 0.75
worktree: .worktrees/ensign-073-auto-reject
---

When a feedback stage (one with `feedback-to`) has `gate: true` and the validator recommends REJECTED, the FO currently presents the rejection at the gate and waits for the captain to explicitly approve or reject. This is unnecessary — the validator already decided REJECTED with specific findings. The captain had to say "do that, and check the workflow to see why we think this needed to be raised."

## Problem

The FO template's gate flow treats approve and reject symmetrically:

1. Validator completes → FO presents stage report at gate
2. Captain says approve or reject
3. FO acts accordingly

But approve and reject are asymmetric in consequence:
- **Approve** is consequential — it advances state, triggers merge, creates PRs, archives entities. The captain should explicitly authorize this.
- **Reject with feedback-to** is just "try again" — it bounces findings back to the implementer. No state advances, no irreversible action. The captain doesn't need to authorize a retry.

## Observed incident

Task 033 validation: the validator returned REJECTED with 3 specific findings. The FO presented the gate review and waited. The captain had to explicitly say "it should go back to implementer without me deciding." The round-trip added no information — the captain would only intervene if they disagreed with the rejection, which is the rare case.

## Proposed behavior

When a feedback stage's validator recommends REJECTED:
- The FO automatically enters the Feedback Rejection Flow (send findings back to implementer)
- The FO informs the captain: "Validation rejected 033 — sending back to implementer with findings: [brief summary]"
- The captain can intervene if they disagree (e.g., "no, close it" or "no, approve it anyway")

When a feedback stage's validator recommends PASSED:
- The FO presents at the gate as today — captain explicitly approves or rejects
- This is the consequential path (merge, PR, archive)

The gate guardrail ("NEVER self-approve") still applies to PASSED recommendations. The change is: REJECTED recommendations at feedback stages skip the gate wait.

## Template Sections to Change

Two sections in `templates/first-officer.md` need modification:

### 1. "Completion and Gates" — gate flow (lines 85-106)

The current `**If gate:**` path presents all stage reports to the captain and waits. This needs a branch: if the completed stage has `feedback-to` AND the validator recommends REJECTED, auto-bounce instead of waiting.

**Current text (line 85):**
```
**If gate:** Present the stage report to the captain:
```

**Proposed replacement — insert a feedback-rejection check before the standard gate presentation:**

```
**If gate:** First, check whether the completed stage has a `feedback-to` property AND the stage report recommends REJECTED (any failed checklist items or explicit REJECTED recommendation).

**If gate + feedback-to + REJECTED:** Auto-bounce — enter the Feedback Rejection Flow immediately without waiting for captain approval. Notify the captain:

\```
Auto-bounced: {entity title} — {stage} REJECTED

{one-line summary of key findings}

Sending findings back to {feedback-to target stage} for revision. Say "override" to intervene.
\```

If the captain intervenes before the feedback cycle completes (e.g., "override — approve it", "override — discard it"), halt the feedback cycle and follow the captain's direction using the standard gate resolution paths (Approve or Reject + discard).

**If gate + no feedback-to, OR gate + feedback-to + PASSED:** Present the stage report to the captain:
```

The standard gate presentation block (lines 87-93), the GATE APPROVAL GUARDRAIL, and all approve/reject resolution paths remain unchanged.

### 2. "Feedback Rejection Flow" — entry trigger (line 110)

The current trigger is "a REJECTED verdict from the captain." This needs to also fire on auto-bounce.

**Current text (line 110):**
```
When a feedback stage's gate results in a REJECTED verdict from the captain:
```

**Proposed replacement:**
```
When a feedback stage is rejected — either auto-bounced (validator recommended REJECTED) or explicitly rejected by the captain at the gate:
```

### 3. "Feedback Rejection Flow" — cycle count check (line 113, step 2)

The cycle count check needs to account for auto-bounce: if the count would hit the limit, do NOT auto-bounce — present at the gate instead and let the captain decide.

**Current text (line 113):**
```
2. **Check cycle count** — Look for a `### Feedback Cycles` section in the entity file body. If it exists, read the current count. If the count is >= 3, escalate to the captain with a summary of all findings across cycles and ask for direction. Do not dispatch another cycle.
```

**Proposed replacement:**
```
2. **Check cycle count** — Look for a `### Feedback Cycles` section in the entity file body. If it exists, read the current count. If the count is >= 3, escalate to the captain with a summary of all findings across cycles and ask for direction — do not dispatch another cycle, regardless of whether this was an auto-bounce or captain-initiated rejection.
```

No material change — the existing escalation behavior already covers this. The clarification just makes explicit that auto-bounce does not bypass the cycle limit.

### 4. "Feedback Rejection Flow" — step 6 gate re-presentation (line 117)

After a feedback cycle completes (target agent fixes, reviewer re-checks), the updated result goes through the gate again. The same auto-bounce logic applies: if the reviewer still recommends REJECTED, auto-bounce again (subject to cycle limits). If PASSED, present at the gate for captain approval.

**Current text (line 117):**
```
6. **FO presents updated result at gate** — Increment the cycle count. Append or update a `### Feedback Cycles` section in the entity file body with the new count (e.g., `Cycle: 1`, `Cycle: 2`). Then present the reviewer's updated stage report at the gate for captain review. Same gate flow as before: captain approves or rejects.
```

**Proposed replacement:**
```
6. **FO processes updated result** — Increment the cycle count. Append or update a `### Feedback Cycles` section in the entity file body with the new count (e.g., `Cycle: 1`, `Cycle: 2`). Then re-enter the gate flow from "Completion and Gates" — the same auto-bounce vs. present logic applies (REJECTED auto-bounces again subject to cycle limits; PASSED goes to captain for approval).
```

## Edge Cases

### Stages with `gate: true` but no `feedback-to`
These are non-feedback gated stages. There is no implementer to bounce findings back to. Both approve AND reject require captain decision — the auto-bounce logic only applies when `feedback-to` is present. The proposed wording handles this: the condition is `gate + feedback-to + REJECTED`.

### Cycle limit reached during auto-bounce
If the cycle count is >= 3, the Feedback Rejection Flow's step 2 escalates to the captain regardless of how the rejection was triggered. The auto-bounce does not bypass the cycle limit. This means on the 4th rejection, the FO falls back to presenting at the gate and waiting.

### Captain override after auto-bounce
The captain sees the "Auto-bounced" notification and can intervene at any point by saying "override." This covers:
- "Override — approve it anyway" → follow standard Approve path
- "Override — discard it" → follow Reject + discard path
- "Override — I want to review it" → halt feedback cycle, present full gate review

The override mechanism is simple: the captain just speaks up. The FO checks for captain messages before each step of the feedback cycle.

### Validator recommends PASSED at a feedback stage
No change from today. PASSED goes through the full gate with captain approval. The auto-bounce only applies to REJECTED.

### Auto-bounce + worktree concerns
No special handling needed. The Feedback Rejection Flow already handles worktree management (keeping agents alive, dispatching into the same worktree). Auto-bounce just changes the trigger, not the mechanics.

## Acceptance Criteria

1. When a feedback stage (has `feedback-to`) with `gate: true` completes with a REJECTED recommendation, the FO enters the Feedback Rejection Flow immediately without waiting for captain approval.
2. The FO notifies the captain of the auto-bounce with a brief summary of findings and a way to intervene ("override").
3. When a feedback stage completes with a PASSED recommendation, the FO presents at the gate and waits for captain approval (unchanged behavior).
4. When a gated stage does NOT have `feedback-to`, both approve and reject require captain decision (unchanged behavior).
5. The cycle limit (>= 3) still triggers escalation to the captain, even on auto-bounce — the FO does not auto-bounce past the cycle limit.
6. The captain can override an auto-bounce at any point during the feedback cycle by saying "override."
7. After a feedback cycle triggered by auto-bounce, the updated result re-enters the same gate logic: REJECTED auto-bounces again (subject to cycle limits), PASSED goes to captain.

## Stage Report: ideation

- [x] Exact template sections identified with line numbers
  Four sections in `templates/first-officer.md`: gate flow (L85), feedback trigger (L110), cycle count check (L113), gate re-presentation (L117)
- [x] Proposed wording changes drafted
  Full before/after text provided for all four sections
- [x] Edge cases addressed
  Five edge cases: no feedback-to stages, cycle limits, captain override, PASSED recommendations, worktree concerns
- [x] Acceptance criteria defined
  Seven acceptance criteria covering the auto-bounce trigger, notifications, override mechanism, cycle limits, and unchanged behavior paths

### Summary

Identified four template sections that need modification in `templates/first-officer.md` to implement auto-bounce rejection. The key design decision is that auto-bounce applies only when both conditions are met: the stage has `feedback-to` AND the validator recommends REJECTED. This preserves captain authority for consequential actions (approvals, non-feedback rejections) while eliminating unnecessary round-trips on the common "try again" path. The captain retains an "override" escape hatch and the existing cycle-limit escalation prevents infinite auto-bounce loops.
