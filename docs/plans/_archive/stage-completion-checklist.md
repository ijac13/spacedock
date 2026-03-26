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

### Runtime compliance test design (e2e)

The original failure mode had two layers: (1) the ensign silently skipped work, and (2) the first officer didn't catch it. Rather than testing these layers in isolation with synthetic prompts, this design runs the real first-officer agent end-to-end: commission a test pipeline, put a test entity through a stage, and verify the actual agent communication follows the checklist protocol.

#### How agent communication is logged

When the first officer runs, it creates a team via `TeamCreate` and dispatches ensigns via `Agent()`. All inter-agent messages (including ensign completion reports) are stored as JSON arrays in `~/.claude/teams/{team_name}/inboxes/{agent_name}.json`. Each message has `from`, `text`, `summary`, and `timestamp` fields. The `team-lead.json` inbox contains all messages sent to the first officer, including ensign completion messages.

The team name is deterministic: `{project_name}-{dir_basename}`, where `project_name` is derived from the git repo name and `dir_basename` is the pipeline directory name. For a test pipeline at `./checklist-test/`, the team name would be something like `{test_project}-checklist-test`.

#### Test phases

The test has three phases, extending the pattern from `test-commission.sh`:

**Phase 1: Commission a test pipeline** (reuse existing commission test approach)

```bash
TEST_DIR="$(mktemp -d)"
cd "$TEST_DIR"
git init test-project && cd test-project

PROMPT="/spacedock:commission

All inputs for this workflow:
- Mission: Track tasks through stages
- Entity: A task
- Stages: backlog → work → done
- Approval gates: none
- Seed entities:
  1. test-checklist — Verify checklist protocol works (score: 25/25)
- Location: ./checklist-test/

Skip interactive questions and confirmation.
Do NOT run the pilot phase — just generate the files."

claude -p "$PROMPT" \
  --plugin-dir "$REPO_ROOT" \
  --permission-mode bypassPermissions \
  --verbose --output-format stream-json \
  2>&1 > "$TEST_DIR/commission-log.jsonl"
```

Key design choices:
- **No gates.** Stages are `backlog → work → done` with no approval gates. This means the first officer can process the entity all the way through without blocking for captain input, so `claude -p` completes naturally.
- **One entity.** Minimal scope — one entity goes through one stage (backlog → work).
- **Fresh git repo.** Isolation from the real spacedock repo. `git init` provides the bare minimum git context the first officer needs.

After commission, add acceptance criteria to the test entity so the checklist has entity-level items to check:

```bash
cat >> "$TEST_DIR/test-project/checklist-test/test-checklist.md" << 'AC'

## Acceptance Criteria

1. The output file contains the word "hello"
2. The output file is valid UTF-8
AC
```

Then commit so the first officer has a clean working tree:

```bash
cd "$TEST_DIR/test-project"
git add -A && git commit -m "commission: initial pipeline"
```

**Phase 2: Run the first officer**

```bash
cd "$TEST_DIR/test-project"

claude -p "Process all entities through the pipeline." \
  --agent first-officer \
  --permission-mode bypassPermissions \
  --bare \
  --verbose --output-format stream-json \
  --max-budget-usd 2.00 \
  2>&1 > "$TEST_DIR/fo-log.jsonl"
```

Key flags:
- `--agent first-officer` — loads the generated `.claude/agents/first-officer.md`
- `--bare` — prevents CLAUDE.md, hooks, and user-level config from interfering with the test
- `--max-budget-usd 2.00` — safety cap; the test should cost well under $1 but this prevents runaway spending if something goes wrong
- `--permission-mode bypassPermissions` — the first officer needs to create files, run bash, and use Agent/TeamCreate without interactive prompts

The first officer will:
1. Create team, read README, run status
2. Find `test-checklist` in backlog, dispatch an ensign into `work`
3. The ensign does the work, sends a completion message with checklist
4. First officer does checklist review (step 7)
5. No gate on `work`, so it proceeds to the next stage or terminal
6. Session completes

**Phase 3: Validate the team inbox**

After the first officer finishes, inspect the team inbox files for checklist compliance.

```bash
# Find the team directory.
# The team name is {project_name}-{dir_basename}.
# project_name comes from the git repo dir name ("test-project"),
# dir_basename from the pipeline dir ("checklist-test").
TEAM_DIR=$(ls -d ~/.claude/teams/*checklist-test* 2>/dev/null | head -1)

if [ -z "$TEAM_DIR" ]; then
  fail "team directory not found"
else
  INBOX="$TEAM_DIR/inboxes/team-lead.json"
```

**Check 1: Ensign sent a completion message with a checklist section.**

```bash
  # Extract ensign messages (from != "team-lead")
  # The inbox is a JSON array; ensign messages have "from": "ensign-..."
  ENSIGN_MSGS=$(python3 -c "
import json, sys
msgs = json.load(open('$INBOX'))
for m in msgs:
    if m.get('from','').startswith('ensign-'):
        t = m.get('text','')
        if '\"type\"' not in t:  # skip protocol messages
            print(t)
")

  if echo "$ENSIGN_MSGS" | grep -qi "### Checklist"; then
    pass "ensign completion message contains ### Checklist section"
  else
    fail "ensign completion message contains ### Checklist section"
  fi
```

**Check 2: Every checklist item has a DONE/SKIPPED/FAILED status.**

```bash
  # Count items with status markers in the ensign's message
  ITEM_COUNT=$(echo "$ENSIGN_MSGS" | grep -ciE "(DONE|SKIPPED|FAILED)")
  # We expect at least 2 items: stage requirements + acceptance criteria
  if [ "$ITEM_COUNT" -ge 2 ]; then
    pass "ensign reported status for at least 2 checklist items"
  else
    fail "ensign reported status for at least 2 checklist items (found $ITEM_COUNT)"
  fi
```

**Check 3: Completion message has a ### Summary section.**

```bash
  if echo "$ENSIGN_MSGS" | grep -qi "### Summary"; then
    pass "ensign completion message contains ### Summary section"
  else
    fail "ensign completion message contains ### Summary section"
  fi
```

**Check 4: Acceptance criteria items appear in the checklist.**

```bash
  # The entity had 2 acceptance criteria items.
  # Check at least one appears in the ensign's checklist.
  if echo "$ENSIGN_MSGS" | grep -qiE "hello|UTF-8|output file"; then
    pass "ensign checklist includes entity acceptance criteria items"
  else
    fail "ensign checklist includes entity acceptance criteria items"
  fi
```

**Check 5 (stream-json log): First officer performed checklist review.**

The stream-json log captures the first officer's reasoning. If the first officer did checklist review, its text output should mention reviewing the checklist or evaluating completeness.

```bash
  if grep -qiE "checklist review|completeness check|skip review|all items accounted" \
     "$TEST_DIR/fo-log.jsonl"; then
    pass "first officer performed checklist review"
  else
    fail "first officer performed checklist review"
  fi
fi
```

**Cleanup:**

```bash
# Remove the test team directory
rm -rf "$TEAM_DIR"
rm -rf "$TEST_DIR"
```

#### How this catches the original failure mode

In the original incident, the ensign would have been dispatched with a checklist including "Run tests from the Testing Resources section." Under the old protocol (free-form completion), the ensign just said "PASSED" in prose and omitted mentioning the test harness. Under the checklist protocol:

1. The ensign's completion message must contain `### Checklist` with every item accounted for — Check 1 and Check 2 verify this structure exists.
2. If the ensign marks the test harness as SKIPPED, the first officer's checklist review (step 7) evaluates the rationale — Check 5 verifies the first officer actually performed the review.
3. The entity-level acceptance criteria show up in the checklist — Check 4 verifies the first officer assembled items from both sources.

The test doesn't directly verify that the first officer pushes back on a weak skip rationale (that would require a more complex setup where the ensign is primed to skip with a bad excuse, and we verify the first officer sends it back). But it does verify the structural prerequisites: the ensign reports in the right format, and the first officer reviews the report before proceeding.

#### Implementation notes

- **Implemented at `scripts/test-checklist-e2e.sh`** — separate from `test-commission.sh` since they test different concerns (template generation vs. runtime behavior).
- **Validates from stream-json log, not team inbox.** The first officer calls `TeamDelete` at session end, removing the team inbox files before the test can read them. The stream-json log is persistent and captures both the Agent dispatch prompt and the first officer's review output.
- **Run time:** Phase 1 (commission) takes ~30-60s. Phase 2 (first officer + ensign) takes ~60-120s. Total: ~2-3 minutes.
- **Cost:** ~$0.80 per run based on observed usage. The `--max-budget-usd 2.00` cap prevents surprises.
- **Determinism:** LLM output varies between runs. The checks are deliberately lenient (grep for keywords, not exact strings).

#### E2e test results

Ran `bash scripts/test-checklist-e2e.sh` — 9/9 checks passed:

- Commission produced test-checklist.md and first-officer.md
- Dispatch prompt contains Completion checklist section
- Dispatch prompt has DONE/SKIPPED/FAILED instructions
- Dispatch prompt includes entity acceptance criteria ("hello", "UTF-8")
- Dispatch prompt includes stage requirement items ("deliverables", "summary")
- First officer performed checklist review (text mentions "All 4 items reported as DONE")
- First officer review references item statuses
- Dispatch prompt has structured completion message template (### Checklist, ### Summary)

The first officer assembled a 4-item checklist (2 stage requirements + 2 acceptance criteria), dispatched the ensign with the checklist in the prompt, the ensign completed all items and reported them as DONE, and the first officer explicitly reviewed the checklist before proceeding.

### Verdict

PASSED — All acceptance criteria met. Commission test harness passes (59/59). E2e checklist compliance test passes (9/9). Implementation is clean, internally consistent, and correctly scoped to `templates/first-officer.md`.
