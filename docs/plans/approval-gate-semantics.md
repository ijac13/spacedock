---
title: Fix approval gate placement and ensign lifecycle at gates
status: implementation
source: testflight sd6-test observation
started: 2026-03-24T03:30:00Z
completed:
verdict:
score: 0.88
worktree: .worktrees/ensign-approval-gate-semantics
---

Two related issues with approval gate behavior observed in sd6-test commission.

## Issue 1: Approval gates placed on wrong stage

### Problem

User specifies `approval gates: interview-prep -> interview, synthesis -> done`. The intent: review the OUTPUT of interview-prep before interview starts.

The generated README puts `Human approval: Yes` on `interview-prep` (the source), not `interview` (the target). The first-officer checks the NEXT stage's approval field before dispatching. So the gate fires BEFORE interview-prep work starts (user approves a blank entity) instead of AFTER (user reviews the persona/script). The user never sees the work before the interview runs.

The SKILL.md template instruction (Section 2a, line 262) says: `"If the transition INTO this stage is in approval_gates: Yes"`. This is semantically correct, but the LLM interprets `interview-prep -> interview` as "interview-prep has the gate" — it reads the arrow source as the annotated stage.

### Options evaluated

**Option A: Better wording in the template instruction.** Change "If the transition INTO this stage is in approval_gates" to something less ambiguous. Problem: any natural-language instruction can be misread. The current wording IS correct and the LLM still got it wrong. More words won't reliably fix an LLM misinterpretation — this is a structural problem, not a phrasing problem.

**Option B: Add examples showing correct placement.** Add an explicit example like "For gates `A -> B`, put `Human approval: Yes` on B, not A." This helps but still relies on the LLM following instructions correctly. A determined misinterpretation can skip examples. Better than Option A but not robust.

**Option C: Restructure gate representation.** Instead of a per-stage `Human approval` field, add a separate `## Approval Gates` section in the README that lists the transitions explicitly (e.g., "Before entering `interview`: captain reviews interview-prep output"). This removes the ambiguity entirely — there's no per-stage field to put on the wrong stage. The first-officer reads the section directly. Downside: changes the README format and the first-officer's gate-checking logic.

**Option D: Flip the semantic model.** Change the per-stage field from "approval required to ENTER this stage" to "approval required AFTER this stage completes." Put the field on the SOURCE stage. This matches the LLM's natural interpretation: `interview-prep -> interview` means interview-prep has the gate. The first-officer checks the CURRENT stage's approval field after the ensign completes, rather than the NEXT stage's field before dispatch. Downside: the semantic meaning of the field changes — "this stage requires review before the pipeline advances" rather than "entering this stage requires review."

### Recommendation: Option D (flip the semantic model)

Option D is the strongest choice for three reasons:

1. **Aligns with LLM intuition.** The arrow `A -> B` naturally reads as "A has a gate." Fighting this interpretation with better wording is fragile. Working WITH the LLM's natural reading eliminates the misinterpretation class entirely.

2. **Simpler mental model.** "This stage's output needs review" is more intuitive than "entering this stage requires review." The gate belongs to the stage that PRODUCES the work being reviewed, not the stage that consumes it.

3. **Minimal structural change.** The per-stage `Human approval` field stays. Only its semantics flip: it now means "review output before advancing" instead of "review before entering." The README template instruction changes from one sentence to one sentence. The first-officer's gate check moves from "check next stage before dispatch" to "check completed stage after ensign reports back."

The field is renamed from `Human approval` to `Approval gate` to signal the semantic change and avoid confusion with the old meaning.

### Concrete changes

**File: `skills/commission/SKILL.md` — Section 2a (README template)**

Change the per-stage `Human approval` line from:

```
- **Human approval:** {If the transition INTO this stage is in approval_gates: "Yes — {reason} before entering this stage." Otherwise: "No"}
```

To:

```
- **Approval gate:** {If this stage is the SOURCE in an approval_gates transition (i.e., this_stage -> next_stage): "Yes — captain reviews output before advancing to next_stage." Otherwise: "No"}
```

**File: `skills/commission/SKILL.md` — Section 2d (first-officer template)**

In the Dispatching section, step 4 currently checks the NEXT stage's approval field before dispatch. Remove this pre-dispatch gate check. Gates are now checked AFTER completion in step 7.

Step 4 changes from:
> **Check human approval** — Read the next stage's `Human approval` field from the README. If it says `Yes`, ask captain before dispatching.

To:
> (removed — approval gates are checked after stage completion, not before dispatch)

Renumber remaining steps (5 becomes 4, 6 becomes 5, 7 becomes 6).

Step 7 (now step 6, "After dispatch") changes from checking the NEXT stage's field to checking the COMPLETED stage's field:

> **Check approval gate** — Read the `Approval gate` field of the stage the ensign just completed. If it says `Yes`:

The rest of the gate logic (hold for review, approval/rejection handling) stays the same.

In the Event Loop section, step 2 changes analogously: check the completed stage's `Approval gate` field, not the next stage's `Human approval` field.

In the Startup section, step 3 changes the field name from `Human approval` to `Approval gate`.

## Issue 2: Ensign lifecycle at approval gates

### Problem

Ensigns currently go idle after completing stage work — no explicit shutdown. The first-officer has no `SendMessage` shutdown or keep-alive logic. This wastes resources when no gate applies (ensign lingers) and loses context when a gate applies (ensign goes away, rejection requires a fresh spawn that lacks the work context).

### Design

Add ensign lifecycle management to the first-officer template's "After dispatch" section. The policy:

1. **Ensign completes stage work** and sends completion message to team-lead.
2. **First-officer checks the completed stage's `Approval gate` field.**
3. **If no gate:** Send `shutdown_request` to the ensign immediately. Ensign approves and exits. Proceed to dispatch next stage (if any) with a fresh ensign.
4. **If gate applies:** Do NOT shut down the ensign. Report findings to captain and wait for decision.
   - **On approval:** Send `shutdown_request` to the ensign. Ensign exits. Dispatch fresh ensign for the next stage.
   - **On rejection + redo:** Send feedback to the SAME ensign via `SendMessage(to="ensign-{slug}", message="Rejection feedback: {captain's feedback}. Please redo the {stage} work addressing this feedback.")`. The ensign retains full context from its original work and can iterate. When the ensign completes the redo, re-enter the gate check.
   - **On rejection + discard:** Send `shutdown_request` to the ensign. Clean up worktree/branch if applicable.

### Concrete changes to first-officer template

**"After dispatch (both paths)" section** — Replace the current step 7 with:

```markdown
6. **Ensign lifecycle and approval gate** — When the ensign sends its completion message:

   a. Read the `Approval gate` field of the stage the ensign just completed.

   b. **If no approval gate:**
      - Send shutdown to the ensign: `SendMessage(to="ensign-{slug}", message={ type: "shutdown_request", reason: "Stage complete, no gate" })`
      - If more stages remain, dispatch a new ensign for the next stage (re-enter step 1).
      - If terminal stage, proceed to merge/finalize (step 7).

   c. **If approval gate applies:**
      - Do NOT shut down the ensign. Keep it alive for potential redo.
      - If the {entity_label} is in a worktree: do NOT merge. The branch is the evidence captain reviews.
      - Report the ensign's findings and recommendation to captain.
      - Wait for captain's decision:
        - **Approve:** Send shutdown to the ensign. If more stages remain, dispatch a new ensign for the next stage. If terminal, proceed to merge/finalize.
        - **Reject + redo:** Send feedback to the same ensign: `SendMessage(to="ensign-{slug}", message="Redo requested. Feedback: {captain's feedback}. Revise your work for the {stage} stage addressing this feedback. Commit and send a new completion message when done.")` When the ensign completes the redo, re-enter this step (6a).
        - **Reject + discard:** Send shutdown to the ensign. Clean up worktree/branch if applicable. Re-dispatch a fresh ensign or ask captain for direction.
```

**Event Loop section** — Update step 2 to match the same lifecycle logic:

```markdown
2. **Ensign lifecycle and gate check** — Follow the procedure from Dispatching step 6: check the completed stage's `Approval gate` field, manage ensign shutdown or keep-alive, handle approval/rejection.
```

## Files changed

| File | Change |
|------|--------|
| `skills/commission/SKILL.md` Section 2a | Rename `Human approval` to `Approval gate`, flip semantics to source-stage annotation |
| `skills/commission/SKILL.md` Section 2d | Remove pre-dispatch gate check (old step 4), add ensign lifecycle logic to "After dispatch", update Event Loop, rename field in Startup step 3 |

No changes to the status script, seed entity generation, or Phase 1/3 of the commission skill.

## Acceptance criteria

1. **Gate placement correctness:** Commission a test pipeline with `approval gates: A -> B`. The generated README has `Approval gate: Yes` on stage A (the source), not stage B.
2. **First-officer reads gates correctly:** The first-officer checks the completed stage's `Approval gate` field after ensign reports back, not the next stage's field before dispatch.
3. **Ensign shutdown on non-gated completion:** When an ensign completes a stage with no approval gate, the first-officer sends `shutdown_request` to the ensign.
4. **Ensign kept alive at gates:** When an ensign completes a stage with an approval gate, the first-officer does NOT shut it down. Captain is prompted for review.
5. **Redo sends feedback to same ensign:** On rejection + redo, the first-officer sends feedback via `SendMessage` to the existing ensign (not a fresh spawn).
6. **Redo re-enters gate check:** After an ensign completes a redo, the gate check runs again (captain reviews the revised work).
7. **Existing tests pass:** No regressions in commission or first-officer behavior for pipelines without approval gates.
