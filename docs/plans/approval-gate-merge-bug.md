---
title: Approval Gate Merge Bug
status: ideation
source: testflight-003
started: 2026-03-22T21:17:00Z
completed:
verdict:
score:
worktree: .worktrees/pilot-approval-gate-merge-bug
---

## Problem

The first-officer event loop merges pilot work to main unconditionally when a pilot completes, then checks approval gates when dispatching the next stage. This is wrong — when the next transition is approval-gated, the merge itself should wait for CL's approval.

Observed during testflight-003:
- **score-format-standardization** (validation → done gate): validation pilot completed with PASSED recommendation. First officer merged the branch, cleared the worktree, then asked CL for approval. The work was already on main before CL could review or reject.
- **refit-command** (ideation → implementation gate): ideation pilot completed. First officer merged the branch, advanced status to `implementation`, cleared the worktree, then asked CL for approval. Status was advanced past the gate without approval.

## Root Cause

The first-officer agent template (`agents/first-officer.md`) has the approval check in the Dispatching section (step 3), but the Event Loop's merge step (step 2) doesn't cross-reference it. The event loop says "Merge and finalize" unconditionally after pilot completion.

## Correct Behavior

When a pilot completes a stage and the next transition requires human approval:

1. Do NOT merge. Keep the worktree and branch alive.
2. Report the pilot's findings to CL.
3. Wait for CL's approval.
4. On approval: merge the branch, update frontmatter (advance status, set timestamps/verdict), commit atomically, clean up worktree.
5. On rejection: either discard the branch or re-dispatch the pilot with feedback, depending on CL's instructions.

The worktree is the isolation boundary. The merge IS the transition. Approval must come before the merge, not after.

## Files to Fix

- `agents/first-officer.md` — the generated first-officer template. The Event Loop section needs a gate check before merging.
- `skills/commission/SKILL.md` — the commission skill that generates the first-officer template. The embedded event loop template has the same gap.

## Analysis

### Where the bug lives

**`agents/first-officer.md`** — two locations:

1. **Dispatching step 8** (line 414-422): "Merge and finalize — After pilot completion, merge work back to main atomically." This step runs unconditionally after every pilot completion. It should check whether the completed stage's outbound transition is approval-gated before merging.

2. **Event Loop step 2** (line 434): "Merge and finalize — Follow the merge procedure from Dispatching steps 8-9." This references the unconditional merge. Same problem: no gate check before merging.

The approval gate check exists only in **Dispatching step 3** (line 385-387), which fires when *starting* a new dispatch — too late, because the merge already happened in step 8 of the previous cycle.

**`skills/commission/SKILL.md`** — the embedded first-officer template (lines 357-470) has the identical structure. The template's Dispatching and Event Loop sections are the source of the generated first-officer, so the same fix must be applied to the template.

### Proposed changes

#### Change 1: Add gate check before merge in Dispatching steps 8-9

Replace the current unconditional merge block (steps 8-9) with a gate-aware version:

**Current (step 8):**
> Merge and finalize — After pilot completion, merge work back to main atomically: `git merge --no-commit pilot/{entity-slug}` ...

**Proposed (step 8):**
> **Check approval gate** — Determine the transition the pilot just completed (e.g., if pilot worked on `ideation`, the transition is `ideation → implementation`). If this transition requires human approval:
>   - Do NOT merge yet. Keep the worktree and branch alive.
>   - Report the pilot's findings and recommendation to CL.
>   - Wait for CL's decision.
>   - **On approval:** proceed to step 9 (merge).
>   - **On rejection:** ask CL whether to discard the branch or re-dispatch with feedback. If discarding, clean up worktree/branch (step 10). If re-dispatching, go back to step 6 with CL's feedback appended to the pilot prompt.
>
> If no approval gate applies, proceed directly to step 9.

Then renumber: current step 8 (merge) becomes step 9, current step 9 (cleanup) becomes step 10.

#### Change 2: Update Event Loop step 2

Replace the unconditional merge reference with the gate-aware version:

**Current:**
> Merge and finalize — Follow the merge procedure from Dispatching steps 8-9

**Proposed:**
> **Check gate and merge** — Follow the procedure from Dispatching steps 8-10: check if the completed transition is approval-gated, wait for approval if needed, then merge and clean up.

#### Change 3: Remove the gate check from Dispatching step 3

The current Dispatching step 3 checks the gate *before dispatching the pilot*. This is the wrong place — the gate should be checked after the pilot completes, not before it starts. The pilot does the work; approval decides whether the work gets merged.

Wait — actually, this depends on the semantics. Looking at the observed behavior and the README stage definitions, the gate is on the *transition into* a stage. "Human approval: Yes — before entering this stage." So `ideation → implementation` means approval is needed before entering implementation.

But the pilot for ideation does ideation work. After the pilot completes, the entity should transition to implementation. That transition is gated. So the gate check belongs *after* the ideation pilot completes and *before* the merge that advances the entity to implementation.

The current Dispatching step 3 checks the gate before dispatching, which means it would check the gate on the transition *into the stage being dispatched*. That's semantically correct for preventing dispatch without approval, but it fires at the wrong time — the merge in the prior cycle already advanced the status past the gate.

The fix: **keep** the gate check in Dispatching step 3 for the initial dispatch case (entity already in a stage, needs approval to proceed to next stage). But **also add** the gate check in the post-pilot merge flow (step 8) for the common case where a pilot just completed and the next transition is gated.

Actually, looking more carefully: Dispatching step 3 checks the gate for the transition the first-officer is *about to make*. If the first officer is dispatching a pilot for implementation, it checks "does entering implementation need approval?" This is correct for the initial pass. The problem is only in the event loop: after a pilot completes, the event loop merges unconditionally, then the next dispatch checks the next gate — but the merge already advanced past the current gate.

So the cleanest fix is:
- **Keep** Dispatching step 3 as-is (it handles the initial startup case).
- **Add** a gate check in the merge flow (Dispatching step 8 / Event Loop step 2) that checks whether the outbound transition from the completed stage is gated.

#### Change 4: Apply identical changes to SKILL.md template

The embedded first-officer template in `skills/commission/SKILL.md` (lines 357-470) needs the same structural changes so that newly commissioned pipelines get the fix.

### Edge cases

1. **CL rejects at an approval gate**: The worktree and branch remain alive. CL tells the first officer what to do — either discard (clean up worktree/branch, possibly revert status) or re-dispatch with feedback. The first officer should ask CL explicitly rather than guessing.

2. **Pilot work needs revision after approval-gate review**: CL might say "approved with changes" — the first officer should merge but note the feedback, then the next stage's pilot can address it. Or CL might reject and ask for re-dispatch, in which case the first officer re-dispatches the same stage with CL's feedback.

3. **Multiple entities hitting gates simultaneously**: Each gate decision is independent. The first officer should report all pending gates and handle each approval/rejection individually. Non-gated work can proceed in parallel.

4. **Entity at terminal stage**: The `done` stage has no outbound transition, so no gate check is needed. The merge after the final pilot should proceed unconditionally (modulo the `verdict` field being set).

5. **First startup with entities already past a gate**: Dispatching step 3 handles this — if an entity is already at a stage and the transition into that stage was gated, the entity already passed the gate in a prior session. No re-approval needed.

## Acceptance Criteria

1. **Event Loop gate check**: After a pilot completes, the first officer checks whether the outbound transition is approval-gated *before* merging. If gated, it holds the merge and asks CL.
2. **Worktree preserved during gate wait**: The worktree and branch remain alive while waiting for CL's approval decision. The branch is the evidence CL reviews.
3. **Rejection handling**: On rejection, the first officer asks CL whether to discard or re-dispatch. It does not auto-decide.
4. **Approval triggers merge**: On approval, the first officer proceeds with the normal merge/finalize/cleanup flow.
5. **Non-gated transitions unchanged**: Transitions without approval gates still merge immediately after pilot completion. No behavioral change for the happy path.
6. **Both files updated**: Both `agents/first-officer.md` (reference doc) and `skills/commission/SKILL.md` (template that generates per-pipeline agents) reflect the fix.
7. **Dispatching step 3 preserved**: The initial-dispatch gate check remains for the startup case where the first officer encounters entities that need gated transitions on first run.
