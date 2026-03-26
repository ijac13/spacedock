---
id: 043
title: Stage completion checklist for ensign reporting
status: implementation
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

## Implementation Summary

All changes are in `templates/first-officer.md`. No changes to the README schema, entity format, or commission skill.

### Changes made

**Dispatching step 3 — Assemble completion checklist:** Added between step 2 (read stage definition) and the concurrency check. The first officer builds a numbered checklist from two sources: stage requirements (from README **Outputs** bullets) and entity-level acceptance criteria (from the entity body). Items are numbered sequentially across both sources.

**Ensign prompt templates (both main and worktree paths):** Added a `### Completion checklist` section with the `[CHECKLIST]` placeholder and instructions to report each item as DONE, SKIPPED (with rationale), or FAILED (with details). Updated the completion message format to use `### Checklist` and `### Summary` sections instead of free-form text.

**Step 7 — Checklist review:** Added between ensign completion and the approval gate check. Three sub-steps: (a) completeness check — verify all items present, (b) skip review — evaluate rationale quality, (c) failure triage — assess whether failures block progression.

**Step 8b — SendMessage reuse path:** Updated to assemble a new checklist for the next stage and include the `### Completion checklist` section in the reuse message.

**Step 8c — Gate reporting:** Updated to include the ensign's checklist with the first officer's assessment of skip rationales, failure impact, and overall recommendation when reporting to the captain.

**Event loop:** Added checklist review as step 2 between receiving the worker message and the gate check.

**Step renumbering:** Steps 6-8 became 7-10 to accommodate the new checklist review step.

## Validation Report

### Commission test harness

Ran `bash scripts/test-commission.sh` — 59/59 checks passed. The test harness validates that the generated first-officer template is structurally correct, has all guardrails, has no leaked template variables or absolute paths, and produces a working status script with valid entity frontmatter.

### Acceptance criteria verification

All six acceptance criteria were verified by reading the implementation diff and the final `templates/first-officer.md`:

1. **Checklist extraction instructions** — PASSED. Dispatching step 3 "Assemble completion checklist" instructs the first officer to extract items from both the README stage definition's Outputs bullets and the entity body's acceptance criteria section. Handles the no-acceptance-criteria case explicitly.

2. **Ensign prompt `### Completion checklist` section** — PASSED. Both the main dispatch prompt (line 64) and worktree dispatch prompt (line 102) include the `### Completion checklist` section with `[CHECKLIST]` placeholder, DONE/SKIPPED/FAILED instructions, and the "Every checklist item must appear" constraint.

3. **Structured completion message format** — PASSED. Both prompts specify `### Checklist` and `### Summary` sections in the ensign's SendMessage template, replacing the old free-form `"Summary: {brief description}"` format.

4. **Checklist review procedure** — PASSED. Step 7 includes three sub-steps: (a) completeness check with pushback template, (b) skip rationale review with weak-rationale examples and pushback template, (c) failure triage with gate-stage blocking logic.

5. **SendMessage reuse path includes checklist** — PASSED. Step 8b's reuse path explicitly says "assemble a new checklist for the next stage (following step 3)" and the SendMessage template includes the `### Completion checklist` section with `[CHECKLIST]` placeholder.

6. **Gate reporting includes checklist with assessment** — PASSED. Step 8c's gate reporting now includes five specific items: the ensign's full checklist, first officer's judgment on skip rationales, impact assessment for failures, explicit note if no acceptance criteria, and overall recommendation.

### Internal consistency

All cross-references between steps were verified:
- Step 7 → step 8, step 8b → step 9 (merge), step 8b reuse → step 3 and step 7, step 8c approve → step 8b/step 9, step 8c redo → step 7, step 8c discard → step 10
- Event loop steps 2-3 reference dispatching steps 7-8 correctly

### Test harness coverage gap

The current test harness (`scripts/test-commission.sh`) validates template structure but has no checks specific to the checklist feature. The following checklist-related assertions could be added to the test harness for future protection:

1. **Generated first-officer contains checklist assembly instructions** — `grep -q "Assemble completion checklist\|completion checklist" "$FO"` (verifies the checklist protocol survived commission generation)
2. **Generated first-officer contains checklist review procedure** — `grep -q "Checklist review\|checklist review" "$FO"` (verifies the review step is present)
3. **Generated first-officer ensign prompt has checklist section** — `grep -q "Completion checklist" "$FO"` (verifies ensign prompt includes the checklist section)

These are straightforward grep checks that fit the existing test pattern. They would catch a regression where the checklist feature is dropped from the template.

### Analysis: Can we test the "ensign skips checklist" failure mode?

The captain asked whether we can write a test that catches an ensign skipping checklist items or rationalizing skips. The original failure pattern was:

1. Ensign dispatched for validation
2. Ensign skips running the test harness
3. Ensign reports PASSED without the test evidence
4. First officer doesn't catch it
5. Captain catches it

**What the checklist protocol changes:** The checklist forces the ensign to explicitly account for every item (DONE/SKIPPED/FAILED). The first officer now has a structured signal to review, with instructions to push back on weak skip rationales. This converts silent omission into visible SKIPPED entries that trigger review.

**What's testable vs. not:**

- **Testable (template level):** We can verify the generated template contains the checklist protocol, review instructions, and pushback templates. The three grep checks above cover this. This is what the test harness is designed for.

- **Not testable in the current test harness (runtime behavior):** Whether an LLM ensign actually follows the checklist instructions, or whether the first officer actually pushes back on weak rationales, is a runtime behavior question. The test harness runs commission (template generation), not the first-officer workflow. Testing runtime compliance would require a different kind of test — one that runs the first-officer agent with a mock entity through dispatch/completion/review. That's a substantial new test infrastructure beyond the scope of this task.

- **Partially addressable (structural):** The checklist protocol itself is the mitigation. The key design insight is separation of concerns: the ensign must account for every item (execution), and the first officer evaluates skip rationales (judgment). Even if an ensign marks something SKIPPED with a weak rationale, the first officer's review procedure is now explicit, with examples of weak rationales to reject. The structured format makes it much harder for a skip to go unnoticed compared to free-form prose.

**Recommendation:** Add the three template-level grep checks to `test-commission.sh` to prevent regressions. The runtime compliance test design below covers the deeper question.

### Runtime compliance test design

The original failure mode had two layers: (1) the ensign silently skipped work, and (2) the first officer didn't catch it. The checklist protocol addresses both: it forces the ensign to explicitly account for every item, and it gives the first officer a structured review procedure. A runtime compliance test should verify both layers.

#### Test concept

Use `claude -p` to simulate ensign and first-officer behavior in isolation, the same way `test-commission.sh` uses `claude -p` to simulate commission. No team infrastructure needed — we're testing whether the prompt instructions produce the right output format, not whether SendMessage works.

#### Test 1: Ensign produces structured checklist

Simulate an ensign receiving a checklist prompt. Verify the response accounts for every item.

**Setup:** Create a minimal task file in a temp directory with known acceptance criteria.

```bash
# Create a fake task file
cat > "$TEST_DIR/test-task.md" << 'TASK'
---
id: 001
title: Add widget support
status: implementation
---

Implement widget rendering in the display module.

## Acceptance Criteria

1. Widget renders correctly in all supported formats
2. Error handling for malformed widget data
3. Unit tests cover widget rendering
TASK
```

**Prompt:** Construct an ensign-style prompt with a concrete checklist, but strip the SendMessage instruction and replace it with "write your completion report to stdout":

```bash
PROMPT="You are working on: Add widget support

Stage: implementation

### Stage definition:

A task moves to implementation once its design is approved. Write the code or make the changes described in the task.

- **Inputs:** The task description and acceptance criteria
- **Outputs:** Working code committed to the repo, with a summary of what was built
- **Good:** Minimal changes that satisfy acceptance criteria, clean code, tests
- **Bad:** Over-engineering, skipping tests, ignoring edge cases

### Completion checklist

Report the status of each item when you write your completion report.
Mark each: DONE, SKIPPED (with rationale), or FAILED (with details).

Stage requirements:
1. Working code committed to the repo
2. Summary of what was built and where

Acceptance criteria:
3. Widget renders correctly in all supported formats
4. Error handling for malformed widget data
5. Unit tests cover widget rendering

DO NOT actually write any code. This is a test of the reporting format only.
Write your completion report below. Every checklist item must appear.
Pretend you completed items 1-4 successfully and item 5 was skipped because the test framework is not set up yet.

### Checklist

{numbered checklist with each item followed by — DONE, SKIPPED: rationale, or FAILED: details}

### Summary
{brief description}"

claude -p "$PROMPT" --output-format text 2>/dev/null > "$TEST_DIR/ensign-output.txt"
```

**Validation checks:**

```bash
# Every checklist item number appears in the response
for N in 1 2 3 4 5; do
  grep -qE "^${N}\." "$TEST_DIR/ensign-output.txt"
done

# At least one item is marked DONE
grep -qiE "DONE" "$TEST_DIR/ensign-output.txt"

# Item 5 is marked SKIPPED (as instructed)
grep -qiE "5\..*SKIPPED" "$TEST_DIR/ensign-output.txt"

# Response contains ### Checklist and ### Summary sections
grep -q "### Checklist" "$TEST_DIR/ensign-output.txt"
grep -q "### Summary" "$TEST_DIR/ensign-output.txt"

# No items are silently omitted — count items with a status marker
REPORTED=$(grep -cE "^[0-9]+\..*—.*(DONE|SKIPPED|FAILED)" "$TEST_DIR/ensign-output.txt")
[ "$REPORTED" -ge 5 ]
```

This test verifies the prompt format is strong enough that the model produces structured output with every item accounted for. It would catch a regression where the checklist instructions are weakened or dropped.

#### Test 2: First-officer catches missing items

Simulate a first-officer receiving an incomplete ensign report. Verify it pushes back.

**Prompt:**

```bash
PROMPT="You are a first officer reviewing an ensign's completion report.

The ensign was dispatched with this checklist:

1. Working code committed to the repo
2. Summary of what was built and where
3. Widget renders correctly in all supported formats
4. Error handling for malformed widget data
5. Unit tests cover widget rendering

The ensign sent this completion message:

---
Done: Add widget support completed implementation.

### Checklist

1. Working code committed to the repo — DONE
2. Summary of what was built and where — DONE
3. Widget renders correctly in all supported formats — DONE

### Summary
Implemented widget rendering.
---

Items 4 and 5 are missing from the report. Follow this review procedure:

a. Completeness check — Verify every item from the dispatched checklist appears in the report. If any items are missing, identify them.
b. Skip review — For each SKIPPED item, evaluate the rationale.
c. Failure triage — For FAILED items, determine whether the failure blocks progression.

Write your review. If items are missing, state which ones and that the ensign must account for them."

claude -p "$PROMPT" --output-format text 2>/dev/null > "$TEST_DIR/fo-review.txt"
```

**Validation checks:**

```bash
# First officer identifies the missing items
grep -qE "4|error handling|malformed" "$TEST_DIR/fo-review.txt"
grep -qE "5|unit test|test" "$TEST_DIR/fo-review.txt"

# First officer indicates pushback (not approval)
grep -qiE "missing|incomplete|account for|not included" "$TEST_DIR/fo-review.txt"
```

This test verifies the review instructions are strong enough that the model catches omissions rather than rubber-stamping.

#### Test 3: First-officer catches weak skip rationale

Same structure as Test 2, but the ensign reports all items with a weak SKIPPED rationale for the test harness item.

**Prompt:**

```bash
PROMPT="You are a first officer reviewing an ensign's completion report.

The ensign was dispatched with this checklist:

1. Validation report with what was tested and pass/fail evidence
2. Run tests from the Testing Resources section (commission test harness)
3. PASSED/REJECTED recommendation

The ensign sent this completion message:

---
Done: Feature X completed validation.

### Checklist

1. Validation report with what was tested and pass/fail evidence — DONE
2. Run tests from the Testing Resources section — SKIPPED: seemed unnecessary for this change
3. PASSED/REJECTED recommendation — DONE: PASSED

### Summary
Reviewed the implementation and it looks correct.
---

Follow this review procedure:

b. Skip review — For each SKIPPED item, evaluate the rationale. Is the skip genuinely acceptable, or is the ensign rationalizing? Weak rationales include 'seemed unnecessary', 'ran out of time', 'not applicable' without explanation. If the rationale is weak, push back.

Write your review."

claude -p "$PROMPT" --output-format text 2>/dev/null > "$TEST_DIR/fo-skip-review.txt"
```

**Validation checks:**

```bash
# First officer identifies item 2 skip as problematic
grep -qiE "weak|insufficient|not acceptable|rationaliz|push back|seemed unnecessary" "$TEST_DIR/fo-skip-review.txt"

# First officer does NOT simply approve
! grep -qiE "^all items.*acceptable\|checklist looks good\|approved" "$TEST_DIR/fo-skip-review.txt"
```

This test directly reproduces the original incident: an ensign skipping the test harness with "seemed unnecessary." It verifies the first-officer review instructions are strong enough to catch exactly this failure mode.

#### Implementation approach

These three tests can be packaged as a single script (e.g., `scripts/test-checklist-compliance.sh`) following the same pattern as `test-commission.sh`: setup, run `claude -p`, validate output, report PASS/FAIL per check.

**Key differences from the commission test harness:**
- Faster execution: each `claude -p` call is a simple prompt/response with no file generation, so each should take ~10-15 seconds vs. 30-60 for commission.
- No plugin needed: these tests run plain `claude -p` prompts, not skill invocations.
- Inherently probabilistic: LLM outputs vary between runs. The checks should be lenient enough to handle formatting variation (e.g., grep for item numbers and status keywords, not exact strings). A check that fails 1 in 20 runs is still useful — it's a smoke test, not a unit test.

**What this proves and what it doesn't:**
- **Proves:** The checklist prompt format is strong enough to produce structured output. The review instructions are strong enough to catch omissions and weak rationales. These are the two properties the protocol depends on.
- **Doesn't prove:** That a real ensign in a real dispatch will always follow the format under all conditions. But no test can prove that for an LLM — the best we can do is verify the instructions produce the right behavior in controlled conditions, which is what these tests do.
- **Doesn't test:** The first officer's completeness check in a live team context (matching dispatched checklist items against reported items). That requires the full Agent/SendMessage infrastructure and is out of scope.

#### Minimal viable version

If cost or time is a concern, Test 3 alone is the highest-value test. It directly reproduces the original incident (ensign skips test harness with weak rationale) and verifies the first-officer review catches it. Tests 1 and 2 add defense in depth but Test 3 is the one that would have caught the actual bug.

### Verdict

PASSED — All acceptance criteria met. Implementation is clean, internally consistent, and the commission test harness passes (59/59). The template changes are correctly scoped to `templates/first-officer.md`. Runtime compliance test design is provided above with concrete prompts, validation checks, and a minimal viable starting point.
