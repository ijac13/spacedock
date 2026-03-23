---
title: Approval Gate Merge Bug
status: implementation
source: testflight-003
started: 2026-03-22T21:17:00Z
completed:
verdict:
score:
worktree: .worktrees/pilot-approval-gate-merge-bug
---

## Problem

The first-officer merges pilot work to main after each stage completes. This is wrong on two levels:

1. **Approval gates bypassed.** When the next transition is approval-gated, the merge happens before CL can review or reject.
2. **Intermediate stages pollute main.** Even for non-gated transitions (e.g., implementation → validation), merging implementation to main before validation is done means bad code lands on main if validation fails. There's no clean rollback.

The correct model: **one branch per entity, one merge to main at the end.** The worktree stays alive from first dispatch through final approval. All stages (ideation, implementation, validation) happen on the same branch. Main only gets touched when the entity is fully validated and CL approves.

Observed during testflight-003:
- **score-format-standardization** (validation → done gate): validation pilot completed with PASSED recommendation. First officer merged the branch, cleared the worktree, then asked CL for approval. The work was already on main before CL could review or reject.
- **refit-command** (ideation → implementation gate): ideation pilot completed. First officer merged the branch, advanced status to `implementation`, cleared the worktree, then asked CL for approval. Status was advanced past the gate without approval.
- **refit-command** (implementation → validation): implementation was merged to main before validation. If validation had failed, bad code would already be on main.

## Root Cause

The first-officer agent template (`agents/first-officer.md`) has the approval check in the Dispatching section (step 3), but the Event Loop's merge step (step 2) doesn't cross-reference it. The event loop says "Merge and finalize" unconditionally after pilot completion.

## Correct Behavior

One branch per entity. One merge to main. The full lifecycle on a single worktree:

```
backlog → create worktree, dispatch ideation pilot
  → ideation complete → [approval gate: ideation → implementation] → hold, ask CL
  → CL approves → dispatch implementation pilot in SAME worktree
  → implementation complete → dispatch validation pilot in SAME worktree (no gate, no merge)
  → validation complete → [approval gate: validation → done] → hold, ask CL
  → CL approves → merge to main, set done/verdict/completed, clean up worktree
```

Rules:
1. **Never merge intermediate stages to main.** Main only gets the final atomic merge.
2. **At approval gates:** hold the worktree, report to CL, wait.
3. **At non-gated transitions:** dispatch the next pilot in the same worktree. No merge, no new branch.
4. **On approval:** if more stages remain, continue on the same branch. If terminal (done), merge to main.
5. **On rejection:** ask CL whether to discard the branch or re-dispatch with feedback.

The worktree is the isolation boundary for the entity's entire lifecycle, not per-stage.

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
5. **Non-gated transitions stay on branch**: Transitions without approval gates dispatch the next pilot in the same worktree. No merge to main.
6. **Both files updated**: Both `agents/first-officer.md` (reference doc) and `skills/commission/SKILL.md` (template that generates per-pipeline agents) reflect the fix.
7. **Dispatching step 3 preserved**: The initial-dispatch gate check remains for the startup case where the first officer encounters entities that need gated transitions on first run.

## Implementation Summary

Two files changed:

**`agents/first-officer.md`** — The Dispatch Lifecycle section (lines 28-44) now describes the one-branch model: create worktree once, check approval gate after each pilot, dispatch next pilot in the same worktree for non-terminal transitions, merge to main only at the terminal stage.

**`skills/commission/SKILL.md`** — The embedded first-officer template (section 2d) received the substantive rewrite:

- **Dispatching steps 4-5** made worktree-aware: step 4 sets the `worktree` field only if not already set; step 5 creates the worktree only on first dispatch, skips if the entity already has an active worktree from a prior stage.
- **Dispatching step 8** replaced the unconditional merge with a gate-aware decision point. After pilot completion, it checks the outbound transition. If gated: hold, report, wait for CL. If not gated and more stages remain: dispatch next pilot in same worktree (back to step 6). Only proceeds to merge (step 9) when the entity reaches its terminal stage.
- **Dispatching step 9** is now "Merge to main" — only reachable at the terminal stage. Merges atomically, updates frontmatter (terminal status, clear worktree, set completed/verdict).
- **Dispatching step 10** is cleanup (worktree remove, branch delete) — unchanged logic, renumbered.
- **Event Loop step 2** changed from "Merge and finalize" to "Check gate and advance" — references the gate-aware procedure from steps 8-10.
- **State Management** updated: `worktree` field is set when entity first leaves backlog, cleared only after final merge to main.
- **Dispatching step 3** preserved: the initial-dispatch gate check remains for the startup case.

## Validation Report

Recommendation: **PASSED**

All seven acceptance criteria verified against the implementation diffs in `agents/first-officer.md` and `skills/commission/SKILL.md`.

### Criteria Results

1. **Event Loop gate check** — PASS. Dispatching step 8 replaced unconditional merge with gate check. Event Loop step 2 references the gate-aware procedure (steps 8-10). Evidence: SKILL.md step 8 "Check approval gate — Determine the outbound transition..."; Event Loop step 2 "Check gate and advance."

2. **Worktree preserved during gate wait** — PASS. Step 8: "Do NOT merge. Keep the worktree and branch alive — the branch is the evidence CL reviews." State Management: "worktree: — set when entity first leaves backlog. Cleared only after final merge to main (terminal stage)."

3. **Rejection handling** — PASS. Step 8: "On rejection: ask CL whether to discard the branch or re-dispatch with feedback." Does not auto-decide.

4. **Approval triggers merge** — PASS. Step 8 on approval at terminal stage: "proceed to step 9 (merge)." Step 9 explicitly gated: "Only when the entity has reached its terminal stage."

5. **Non-gated transitions stay on branch** — PASS. Step 8: "If no approval gate applies and more stages remain, dispatch the next pilot in the same worktree (go back to step 6 — no merge, no new branch)." Step 5 made worktree-conditional: "first dispatch only...If the entity already has an active worktree, skip this step."

6. **Both files updated** — PASS. `agents/first-officer.md` Dispatch Lifecycle rewritten with gate-aware steps 4-6. `skills/commission/SKILL.md` template steps 4-5, 8-10, Event Loop step 2, and State Management all updated consistently.

7. **Dispatching step 3 preserved** — PASS. Step 3 unchanged in diff; still checks approval gates before initial dispatch.

### One-Branch-Per-Entity Model

The core lifecycle is correctly implemented across both files:
- Worktree created once at first dispatch, persists through all stages.
- No intermediate merges — non-terminal transitions loop back to dispatch (step 6).
- Approval gates hold the merge and ask CL.
- Merge to main only at terminal stage after approval.
- Reference doc (`first-officer.md`) and operational template (`SKILL.md`) are consistent.
