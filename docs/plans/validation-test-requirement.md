---
title: Validation pilots must run the test harness
status: ideation
source: testflight-005
started: 2026-03-24T00:00:00Z
completed:
verdict:
score: 0.72
worktree:
---

## Problem

Validation ensigns currently do code review only. The README's "Testing Resources" section documents test harnesses and says "Use it for any entity that changes `skills/commission/SKILL.md` or the first-officer template" — but the ensign dispatch prompt never tells validation ensigns to check for or run test resources. The instruction exists in the README but is not actionable because the ensign prompt doesn't reference it.

The first officer is a dispatcher and should not run tests itself. Test execution belongs in the validation ensign's workflow.

## Root Cause

The first-officer template in `skills/commission/SKILL.md` uses a single ensign prompt template for all stages. The prompt says "Do the work described in the stage definition" and copies the stage definition from the README. But the validation stage definition in a generated README describes what to verify and how to assess quality — it does not say "also check the Testing Resources section and run any applicable tests." The Testing Resources section is a separate README section that the ensign has no reason to look at unless told.

## Where Changes Are Needed

**File: `skills/commission/SKILL.md`** — the first-officer template's ensign dispatch prompt.

The generated first-officer has two dispatch paths (main and worktree), each with an ensign prompt template. Both templates need the same addition for validation stages.

### Approach: Conditional validation block in the dispatch prompt

Add a paragraph to the ensign prompt that the first officer includes only when dispatching a validation-stage ensign. The paragraph instructs the ensign to:

1. Check if the pipeline README has a "Testing Resources" section.
2. If it does, read the section to find applicable test harnesses.
3. Determine which tests are relevant based on what files the entity modified (the entity body should contain an implementation summary listing changed files).
4. Run the applicable test scripts and include results in the validation report.
5. A test failure means the entity should be recommended REJECTED, not PASSED.

The first officer already knows what stage it's dispatching for (it reads the stage definition). The change is a conditional text block: "If the stage being dispatched is the validation stage, append the following to the ensign prompt: ..."

### Why Not a Separate Test-Runner Agent?

A separate test-runner dispatched after validation would add pipeline complexity (extra dispatch, extra merge) for no benefit in v0's shuttle mode. The validation ensign is already reviewing the work — running tests is a natural part of validation. YAGNI.

### Why Not Hardcode the Test Script Path?

The ensign prompt should reference the README's Testing Resources section generically, not hardcode `v0/test-commission.sh`. Different pipelines may have different test resources, and the README is the source of truth. The validation ensign reads the README section and decides what to run — same pattern as reading the stage definition.

## Acceptance Criteria

1. When the first officer dispatches a validation ensign, the ensign prompt includes an instruction to check the README's "Testing Resources" section and run applicable tests.
2. The instruction is only added for validation-stage dispatches (not ideation, implementation, etc.).
3. The instruction tells the ensign to include test results in its validation report and to recommend REJECTED if tests fail.
4. The generated first-officer template includes this conditional logic — it is not a manual step.
5. The existing test harness (`v0/test-commission.sh`) passes after the change (no regression).
6. The instruction references the README generically (not a hardcoded script path), so it works for any pipeline that has a Testing Resources section.

## Scope

- Modify the first-officer template in `skills/commission/SKILL.md` (both main and worktree dispatch paths).
- No changes to the README template, test harness, or `agents/first-officer.md` reference doc.
- No new files needed.
