---
id: 043
title: Stage completion checklist for ensign reporting
status: validation
source: CL
started: 2026-03-26T00:00:00Z
completed:
verdict:
score: 0.80
worktree: .worktrees/ensign-stage-completion-checklist
---

Ensigns currently report completion as free-form text. This lets them rationalize skipping steps without the first officer noticing until it's too late (e.g., skipping the test harness and burying the rationale in a paragraph).

Add a structured checklist that ensigns must fill out when completing a stage. Items come from two sources:

1. **Stage-level requirements** — defined in the README stage definition (e.g., "run tests from Testing Resources section"). These apply to every entity passing through that stage.
2. **Entity-level acceptance criteria** — from the entity body. These are task-specific.

Each item gets a status: done, skipped (with rationale), or failed. The ensign reports the filled checklist to the first officer. The first officer's job is to review the checklist and push back on invalid skip rationales — separating execution from judgment.

Motivated by: a validation ensign skipping the commission test harness and self-approving the skip as reasonable.

## Problem Statement

Ensign completion messages are free-form text. This creates two failures:

1. **Ensigns can skip steps silently** — there's no structure forcing them to account for each requirement, so omissions blend into the summary prose.
2. **First officers can't efficiently review** — they must parse paragraphs to figure out what was done vs. skipped, and buried rationales are easy to miss under time pressure.

The root cause is that execution and judgment are conflated: the ensign both decides what to do and evaluates whether skipping something is acceptable. The first officer has no structured signal to review.

## Proposed Approach

### Checklist item sources

Items come from two places, assembled at dispatch time by the first officer:

1. **Stage-level requirements** — Extracted from the README stage definition. These are the "Outputs" bullets and any special instructions (like the validation stage's Testing Resources reference). They apply to every entity passing through that stage.

2. **Entity-level acceptance criteria** — Extracted from the entity body. These are task-specific criteria written during ideation. The first officer parses them from the entity markdown at dispatch time.

The first officer assembles the combined checklist and includes it in the ensign prompt as a numbered list.

### Checklist format in the ensign prompt

The first officer includes the checklist in the ensign dispatch prompt as a section like:

```
### Completion checklist

Report the status of each item when you send your completion message.
Mark each: DONE, SKIPPED (with rationale), or FAILED (with details).

Stage requirements:
1. {requirement from README stage definition}
2. {requirement from README stage definition}

Acceptance criteria:
3. {criterion from entity body}
4. {criterion from entity body}
```

### Ensign completion report format

The ensign's completion message replaces the current free-form summary with a structured report:

```
Done: {entity title} completed {stage}.

### Checklist

1. {item text} — DONE
2. {item text} — SKIPPED: {rationale}
3. {item text} — DONE
4. {item text} — FAILED: {details}

### Summary
{brief description of what was accomplished}
```

Each item must appear in the report. The ensign cannot omit items — the numbered list from the prompt must be reflected 1:1 in the completion message.

### First officer review procedure

When the first officer receives a checklist completion:

1. **Completeness check** — Verify every item from the dispatched checklist appears in the report. If any are missing, send the ensign back to account for them.
2. **Skip review** — For each SKIPPED item, evaluate the rationale. The first officer's job is judgment: is this skip genuinely acceptable, or is the ensign rationalizing? If the rationale is weak (e.g., "seemed unnecessary", "ran out of time"), push back and ask the ensign to either do the item or provide a stronger justification.
3. **Failure triage** — For FAILED items, determine whether the failure blocks progression. In gate stages (like validation), any failure typically means REJECTED. In non-gate stages, failures may be acceptable depending on context — escalate to the captain if unclear.
4. **Gate decision** — At gate stages, the first officer reports the checklist to the captain with its own assessment of skip rationales, rather than just forwarding the ensign's self-assessment.

### Where this fits in the existing flow

The changes touch two places in the first-officer template:

1. **Dispatch (ensign prompt construction)** — The first officer already reads the README stage definition and entity body before dispatching. The addition is: extract checklist items from both sources and include the `### Completion checklist` section in the ensign prompt. This applies to both the initial dispatch Agent() call and the SendMessage() reuse path.

2. **Event loop (completion handling)** — Step 6 of the dispatch procedure gains a checklist review sub-step between receiving the ensign's message and the gate check. The first officer parses the checklist, evaluates completeness and skip rationales, and may send the ensign back before proceeding to the gate.

No changes to the README schema, entity format, or stage definitions. The checklist is an overlay on the existing dispatch/completion protocol.

## Acceptance Criteria

1. The first-officer template includes instructions for extracting checklist items from (a) the README stage definition and (b) the entity body's acceptance criteria.
2. The ensign prompt template includes a `### Completion checklist` section with numbered items and instructions to report each as DONE/SKIPPED/FAILED.
3. The ensign completion message template uses the structured checklist format instead of free-form summary.
4. The first-officer template includes a checklist review procedure: completeness check, skip rationale review, failure triage.
5. The SendMessage reuse path (step 6b) also includes the checklist in the next-stage message.
6. At gate stages, the first officer's report to the captain includes the checklist with the first officer's assessment of skip rationales.

## Open Questions (Resolved)

**Q: Should the ensign also write the checklist into the entity file body?**
A: No. The checklist is an operational artifact in the completion message. The entity body captures the substantive output (implementation summary, validation report). Mixing operational protocol into entity content would clutter the files.

**Q: Should checklist items be machine-parseable (YAML, JSON)?**
A: No. The consumers are LLM agents (first officer, captain), not scripts. Markdown with a consistent text format (item — STATUS: rationale) is readable by both agents and humans, and avoids format fragility.

**Q: What if the entity body has no explicit acceptance criteria?**
A: The stage-level requirements still apply. The entity-level section of the checklist is simply empty. The first officer should note this when reporting to the captain at gate stages — a task without acceptance criteria is harder to validate.
