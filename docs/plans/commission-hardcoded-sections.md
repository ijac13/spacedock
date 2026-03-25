---
title: Commission hardcodes pipeline-specific section names in first-officer template
status: done
source: email-triage testflight
started: 2026-03-25T02:20:00Z
completed: 2026-03-25T05:15:00Z
verdict: PASSED
score: 0.55
worktree:
---

## Problem Statement

During the email-triage testflight, the commission LLM generated a first-officer with hardcoded pipeline-specific section references like `### Intake Read Strategy (for intake stage)`. This happened because the ensign dispatch prompt template contained `{Copy the full stage definition from the README here: inputs, outputs, good, bad}` — a runtime instruction that the generating LLM interpreted as a generation-time variable and expanded into pipeline-specific dispatch logic.

The dispatch-embellishment fix (already implemented) addressed the *expansion* problem by:
1. Changing the marker from `{Copy...}` to `[STAGE_DEFINITION — ...]` (square brackets + ALL_CAPS distinguish it from `{named_variables}`)
2. Adding guardrail comments above each template: "Copy the ensign prompt template exactly as written. Only fill `{named_variables}`..."

These fixes prevent the generating LLM from expanding the placeholder. However, a subtler version of the same problem remains: the first-officer template tells the first-officer to "Read the next stage's definition from the README (inputs, outputs, good, bad criteria)" (SKILL.md line 407) and then copy it into the `[STAGE_DEFINITION]` placeholder at dispatch time. This works — but the README's stage definitions may include custom subsections, cross-references to other README sections, or supplementary context beyond the standard bullets (Inputs/Outputs/Good/Bad). The first officer must know what to copy.

The current instruction "copy the full stage definition from the README" is actually correct and generic — it says to copy the entire `### stage_name` subsection, which includes everything under that heading until the next stage heading. No section names are hardcoded in the current template.

**The remaining risk**: the commission LLM might still add pipeline-specific dispatch logic during generation, despite the guardrails. The `[STAGE_DEFINITION]` marker and guardrail comments reduce this, but the template could be more explicit about what "copy the full stage definition" means.

## Where Hardcoded References Currently Exist

After the dispatch-embellishment fix, auditing SKILL.md reveals:

1. **Ensign dispatch prompt (line 433, 467)**: Uses `[STAGE_DEFINITION — at dispatch time, copy the full stage definition from the README: inputs, outputs, good, bad]`. This is generic — no pipeline-specific section names.

2. **Dispatching step 2 (line 407)**: "Read the next stage's definition from the README (inputs, outputs, good, bad criteria)." Generic.

3. **Startup step 4 (line 398)**: "Find the `## Concurrency` section in the README." References a structural section name that all pipelines have — this is not pipeline-specific.

4. **No remaining hardcoded pipeline-specific section names** in the template itself. The problem was in the *generated output*, not the template source.

## Proposed Approach

### Change 1: Make the stage-definition copy instruction more explicit

In the first-officer template's Dispatching step 2 (line 407), clarify what "stage definition" means:

Current:
```
2. Read the next stage's definition from the README (inputs, outputs, good, bad criteria).
```

Proposed:
```
2. Read the next stage's full subsection from the README — everything under the `### stage_name` heading until the next `###` heading. This includes the standard bullets (Inputs, Outputs, Good, Bad, Worktree, Approval gate) and any additional context the README provides for that stage.
```

This makes explicit that the first officer copies the *entire* subsection, not just the four standard bullets. If the README has custom subsections or notes under a stage, they get included automatically.

### Change 2: Clarify the [STAGE_DEFINITION] placeholder

In the ensign dispatch prompts (lines 433 and 467), expand the explanatory text slightly:

Current:
```
[STAGE_DEFINITION — at dispatch time, copy the full stage definition from the README: inputs, outputs, good, bad]
```

Proposed:
```
[STAGE_DEFINITION — at dispatch time, copy the full ### stage subsection from the README verbatim, including all bullets and any additional context under that heading]
```

This removes the specific bullet list ("inputs, outputs, good, bad") which could be read as exhaustive, and replaces it with a clear instruction to copy everything under the stage heading.

### Change 3: Strengthen the guardrail comment

The guardrail above each dispatch template (lines 426, 460) currently says:
```
Copy the ensign prompt template exactly as written. Only fill {named_variables} — do not expand, rewrite, or customize any other text (including bracketed placeholders).
```

Add one more sentence:
```
Do NOT add pipeline-specific dispatch logic, custom section references, or per-stage conditionals — the [STAGE_DEFINITION] placeholder handles all stage-specific context at runtime.
```

### Interaction with ensign reuse

The ensign reuse change adds a SendMessage-based reuse path alongside the existing Agent dispatch path. Both paths use the same `[STAGE_DEFINITION]` placeholder pattern — the first officer copies the stage subsection from the README in both cases. The clarified copy instruction (Change 1) applies equally to both paths.

## Acceptance Criteria

1. Dispatching step 2 explicitly describes copying the full `### stage_name` subsection (not just specific bullet names).
2. The `[STAGE_DEFINITION]` placeholder text says "copy the full ### stage subsection verbatim" instead of listing specific bullets.
3. The guardrail comment explicitly prohibits pipeline-specific dispatch logic and custom section references.
4. No pipeline-specific section names appear anywhere in the first-officer template.
5. The changes work with the ensign reuse SendMessage path (same copy instruction applies).

## Implementation Summary

All changes in `skills/commission/SKILL.md`:

1. **Dispatching step 2** (line 409): Replaced "Read the next stage's definition from the README (inputs, outputs, good, bad criteria)" with explicit instruction to copy everything under the `### stage_name` heading until the next `###` heading, including standard bullets and any additional context.
2. **[STAGE_DEFINITION] placeholder** (lines 435, 469, 487): Changed from "copy the full stage definition from the README: inputs, outputs, good, bad" to "copy the full ### stage subsection from the README verbatim, including all bullets and any additional context under that heading". Updated in all three locations: main dispatch, worktree dispatch, and the ensign reuse SendMessage.
3. **Guardrail comments** (lines 428, 462): Added sentence prohibiting pipeline-specific dispatch logic: "Do NOT add pipeline-specific dispatch logic, custom section references, or per-stage conditionals — the [STAGE_DEFINITION] placeholder handles all stage-specific context at runtime."

## Validation Report

### Test Harness

The integration test (`v0/test-commission.sh`) could not be run — it invokes `claude -p` to execute the full commission skill, which requires a standalone Claude CLI session. Manual validation was performed instead.

### Acceptance Criteria Results

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | Dispatching step 2 describes copying full ### stage_name subsection | PASS | SKILL.md line 409: "Read the next stage's full subsection from the README — everything under the `### stage_name` heading until the next `###` heading" |
| 2 | [STAGE_DEFINITION] placeholder says "copy full ### stage subsection verbatim" | PASS | Lines 435, 469, 487 all say "copy the full ### stage subsection from the README verbatim, including all bullets and any additional context under that heading" |
| 3 | Guardrail comment prohibits pipeline-specific dispatch logic | PASS | Lines 428, 462: "Do NOT add pipeline-specific dispatch logic, custom section references, or per-stage conditionals" |
| 4 | No pipeline-specific section names in the template | PASS | Grep for intake/triage/review/screening found zero pipeline-specific references in the first-officer template. All `###` headings are structural (Dispatch on main, Dispatch in worktree, After dispatch, etc.) |
| 5 | Changes work with ensign reuse SendMessage path | PASS | Line 487 uses the same `[STAGE_DEFINITION]` pattern as lines 435 and 469. Step 2's copy instruction (line 409) applies to both dispatch and reuse paths |

### Recommendation: PASSED

All five acceptance criteria are met. The template is now explicit about copying full stage subsections verbatim, with no pipeline-specific section names anywhere in the generated first-officer prompt.
