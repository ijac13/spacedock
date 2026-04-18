---
id: 193
title: "Separate acceptance criteria (entity-level) from checklist (stage-level)"
status: validation
source: "captain observation during #186 gate-review triage — current practice conflates 'acceptance criteria' (when the task is done) with 'checklist' (what this dispatch does). Ensigns treat AC items as stage-level todos, making 'defer to validation' feel legitimate even when the AC belongs to the overall entity. Cleaner separation: AC lives at entity level (properties of the final outcome), checklist lives at stage level (mechanical steps for this dispatch)."
started: 2026-04-18T05:50:46Z
completed:
verdict:
score: 0.7
worktree: .worktrees/spacedock-ensign-separate-ac-from-checklist-entity-vs-stage
issue:
pr:
mod-block: merge:pr-merge
---

## Why this matters

Today both `docs/plans/README.md` and `skills/first-officer/references/first-officer-shared-core.md` use "acceptance criteria" as a term, and the FO builds dispatch checklists from "stage outputs and entity acceptance criteria" (shared-core line 60). In practice this conflates two different concepts:

- **AC (entity-level):** "when is THIS TASK done?" — properties of the final deliverable or outcome. Verifiable from the entity's end state regardless of which stage ran. Example: "Branch on main shows `OPUS_MODEL ?= opus`" or "`test_standing_teammate_spawn` passes on opus-4-7."
- **Checklist (stage-level):** "what does THIS DISPATCH do?" — mechanical steps for this specific invocation. Example: "run make test-live-claude-opus, capture fo-log citations, revert if red." Doesn't persist past the dispatch.

When the two are conflated, problems follow:

1. **Ensigns treat ACs as stage-level to-dos** and feel free to "defer" one to a later stage — but an entity-level AC is a property of done-ness, not a task, so deferral makes no sense.
2. **Gate reviews check stage-reports against stage-AC lists** instead of against entity-AC coverage, missing ACs that span stages.
3. **Entity body growth is uneven** — some ACs are properly entity-level ("file exists at path X"), others are really ideation/implementation to-do items ("run diagnosis 3×") that shouldn't be ACs at all.
4. **Validation lacks a clean contract** — is it checking "every AC has evidence from some stage" or "every AC was verified in validation specifically"? Unclear today.

**Concrete example from this session:** #186 cycle-2 ideation wrote AC-5 as "3× `test_standing_teammate_spawn` runs on opus-4-7." The ensign read that as "work to do during implementation" and deferred it. If AC-5 had been framed as the entity-level property "`test_standing_teammate_spawn` passes reliably on opus-4-7," the deferral wouldn't have made sense — the ENTITY isn't done until that holds, regardless of which stage verifies it.

## Audit of recent entity bodies (ideation evidence)

Sampled 20 entities from `docs/plans/` (9 active, 11 archived) and classified each AC:

- **E (entity-level):** a property of the final deliverable / end state. Grep-able or re-runnable by a future reader at any time.
- **S (stage-level disguised as AC):** a stage action ("run X", "produce analysis Y", "capture Z"). Reads as a to-do.
- **M (mixed):** captain-decision-at-gate, meta-scope, or hybrid.

| Entity | Total | E | S | M | Notes |
|--------|------:|--:|--:|--:|-------|
| #184 opus-4-7-standing-teammate-flakiness | 3 | 3 | 0 | 0 | clean |
| #192 limit-fo-checklist-to-three-items | 5 | 4 | 0 | 1 | AC-3 "captain decides" |
| #186 green-opus-4-7-full-suite | 7 | 2 | 5 | 0 | worst offender — ACs read as diagnose/fix/check steps |
| #191 revisit-commission-skill-behavior | 6 | 6 | 0 | 0 | clean |
| #189 test-feedback-keepalive-two-path | 6 | 5 | 1 | 0 | AC-6 "budget" is meta |
| #188 streaming-watcher-over-filesystem-polling | 6 | 6 | 0 | 0 | clean |
| #177 opus-4-7-ensign-hallucination-scope | 7 | 2 | 5 | 0 | worst offender — experiment-run ACs |
| #190 claude-team-build-path-doubling | 3 | 3 | 0 | 0 | clean |
| #140 codex-completion-notifications | 6 | 3 | 3 | 0 | AC-4/5/6 are meta-scope |
| cherry-pick-claude-team-narrowing (archived) | 5 | 5 | 0 | 0 | clean |
| lazy-standing-teammate-spawn (archived) | 0 | — | — | — | empty section |
| ensign-bash-poll-not-sleep (archived) | 5 | 4 | 1 | 0 | AC-5 "stage report must include decision" |
| diagnose-opus-4-7-fo-regression (archived) | 5 | 0 | 5 | 0 | **worst offender — 0% entity-level** |
| pin-opus-4-6-ci-default (archived) | 4 | 4 | 0 | 0 | clean |
| ensign-prompt-tool-call-discipline (archived) | 3 | 3 | 0 | 0 | clean |
| migrate-live-tests-to-streaming-watcher (archived) | 6 | 4 | 2 | 0 | AC-5/6 are commit-discipline |
| streaming-fo-watcher-per-step-timeouts (archived) | 13 | 13 | 0 | 0 | clean |
| standing-teammate-enumeration-usage-payload (archived) | 12 | 12 | 0 | 0 | clean |
| standing-teammate-mod-hook (archived) | 12 | 12 | 0 | 0 | clean |
| build-dispatch-structured-helper (archived) | 14 | 14 | 0 | 0 | clean |

**Totals:** 125 ACs → ~102 entity-level (82%), ~22 stage-level (17%), ~1 mixed (1%). 10/19 entities are fully clean; 3 are worst offenders.

**Pattern observation.** Diagnostic / experiment / analysis tasks dominate the stage-level population. When the deliverable *is* the analysis itself, authors naturally write "run the experiment" as the AC — but the entity-level property is "the analysis concludes X with evidence Y," not "an experiment was run." Code-landing and prose-landing tasks are almost always clean (grep-able end states). The problem is real but concentrated: ~17% of ACs are miswritten, heavily skewed toward the diagnostic class.

**Implication for migration:** a blanket retrofit isn't warranted. The three worst offenders are either archived (#diagnose-opus-4-7 already closed) or under active work with their own gate review (#186, #177); fixing those mid-flight destabilizes them. The right migration scope is **prospective**: ship the distinction for new entities; leave historical bodies as-is.

## Proposed approach

### Core distinction (unchanged from seed)

- **AC** = properties of the deliverable/outcome. "Task is done when …"
- **Checklist** = per-dispatch mechanical steps. "For this stage, do …"
- **Stage outputs** (workflow README) describe what each stage must produce — they feed both AC-coverage reasoning and checklist items but are themselves neither.

### Where the distinction lives

- **`skills/first-officer/references/first-officer-shared-core.md`** — the dispatch contract (current line 60) is rewritten so ACs and checklists are named distinctly and AC-coverage is a gate-review obligation, not a checklist-completion obligation.
- **`docs/plans/README.md`** — the workflow README gains an "Acceptance criteria vs. checklist" note in its stage prose, and the task-body template grows an explicit `## Acceptance criteria (entity-level)` section. No YAML schema changes.
- **`skills/commission/SKILL.md`** — the generated-workflow template mirrors the `docs/plans/` shape so newly commissioned workflows inherit the distinction by default.
- **Entity template (both in `docs/plans/README.md` and in the commission generator)** — body template includes a prose one-liner reminding authors that AC items are entity-level properties, not stage to-dos.

### Validation semantics

Validation's job becomes: "pull every entity-level AC from the entity body; confirm evidence exists for each across the stage reports, and re-verify the evidence where cheap." Not "did this stage verify its own AC list."

### Gate review semantics

FO at every gate: "has this stage moved the entity closer to satisfying every relevant AC? Is there a named AC left unaddressed that this stage was the right place to address?" Not "did the stage complete all items in its dispatch checklist." This is additive to the existing DONE/SKIPPED/FAILED count on the checklist, not a replacement.

## Resolved design questions

### Q1 — Entity template shape (should `docs/plans/README.md` stipulate a specific AC section format?)

**Recommendation: yes, but loose.** Stipulate a required section heading (`## Acceptance criteria`) and a format convention (one top-level `**AC-N — ...**` item per line, each followed by a "verified by" clause), but do not mandate length, count, or a rigid grammar. Rationale from the audit: clean entities already use this shape voluntarily. Codifying it costs nothing and gives the FO + validator a predictable anchor. The "verified by" clause is the same discipline #189 and #188 already demonstrate ("Test method: grep X for Y").

**Concrete template (goes into `docs/plans/README.md` §Task Template and into `skills/commission/SKILL.md`'s generated template):**

```markdown
## Acceptance criteria

Each AC names a property of the finished entity (not a stage action) and how it is verified.

**AC-1 — {Property of end state, phrased as "X is true" / "Y exists" / "Z passes".}**
Verified by: {grep / test name / file path / command output that a future reader can reproduce.}

**AC-2 — ...**
Verified by: ...
```

### Q2 — Migration (retrofit existing entities or let them age out?)

**Recommendation: no retrofit. Prospective only.** Audit shows 10/19 entities are already clean and the three worst offenders are either archived or under active gate review. Rewriting a live entity's ACs mid-cycle destabilizes the gate contract. Rewriting archived entities is a waste of pilot time.

Concretely: the distinction applies to any entity that enters ideation AFTER #193 merges. Entities already past ideation when #193 merges keep their existing ACs. This is captured explicitly in the Out of Scope section below.

### Q3 — Per-stage AC subsets (some ACs genuinely belong to one stage — e.g., "ideation produces a test plan")

**Recommendation: stage-output territory, not AC territory.** "Ideation produces a test plan" is already the `Outputs:` of the ideation stage in the README. It does not need to be echoed as an entity-level AC; if ideation doesn't produce a test plan the gate review rejects on stage-output grounds. The entity-level AC would be the property downstream: e.g., "a test plan exists in the entity body specifying which tests cover each AC." That is entity-level (grep-able at any time). Framing it as "ideation must produce X" collapses back into stage-outputs.

Practical rule for authors: if you catch yourself writing an AC that names a stage ("ideation must …", "implementation must …"), stop and ask whether the end-state property is "a test plan exists" / "the static suite is green" / "the prose section contains X." Those are entity-level; the stage that produces them is incidental.

### Q4 — Validation's job post-change

**Recommendation: validation cross-checks the entity's AC list against evidence accumulated across all prior stages; it does not maintain its own separate AC list.** Validation's stage outputs already say "Verify each acceptance criterion with evidence" — that prose stands and gains teeth once ACs are properly entity-level.

Concretely, `docs/plans/README.md` validation stage's Outputs section gets one sentence appended: *"Pull every `**AC-N**` item from the entity body; confirm the evidence cited in each 'Verified by' clause still reproduces, and confirm any AC lacking evidence is flagged."* This is additive, not a rewrite.

### Q5 — Interaction with #192

**Recommendation: keep them distinct and compatible, document the relationship once.** #192 caps the CHECKLIST at ≤ 3 linchpin items. #193 clarifies WHY the checklist can be that small — because the AC lives elsewhere at entity level, and checklist items are dispatch-specific signals, not work-breakdowns. They compose cleanly:

- #192 tells the FO "name at most 3 checklist items per dispatch."
- #193 tells the FO and the author "the AC list is a separate, entity-level artifact; checklists are derived per-dispatch."

The only concrete interaction point is the shared-core prose near line 60. #192's amendment adds the linchpin framing there; #193 adds the AC-vs-checklist distinction in the same neighborhood. Sequence the edits so #193 lands after #192 to avoid rebase churn, or resolve in one merge if they land back-to-back. (Captain decides at gate; both edits are small.)

### Q6 — Workflow-specific override shape (should workflows be able to customize the AC convention via frontmatter?)

**Recommendation: no frontmatter override in this entity.** Following the #192 precedent (captain amended out frontmatter overrides on the grounds that "don't add configurability until multiple workflows actually need different caps"), the AC convention ships as prose + template. A workflow that wants a different shape edits its own README. Mechanism-level enforcement is out of scope for #193.

If at a later date the divergence across workflows proves real, a follow-up task can add `entity.ac-format: loose|strict` or similar. Not this entity.

## Concrete edits specified

### Edit 1 — `skills/first-officer/references/first-officer-shared-core.md`

This edit operates on the two-part structure #192 landed in the `## Dispatch` numbered list: the single sentence at line 60 and the linchpin-discipline paragraph at line 62. #193 MUST preserve every piece of #192's linchpin framing (`at most 3 items`, `0, 1, 2, or 3 items are all valid; do not pad to reach 3`, `Name what separates a good outcome from a ceremonial one`) and add the AC-vs-checklist distinction in the same neighborhood.

**Current (verbatim from shared-core):**

Line 60:

> 2. Build a numbered checklist from stage outputs and entity acceptance criteria.

Line 62 (the linchpin-discipline paragraph #192 landed):

>    The dispatch checklist is a **per-dispatch, stage-level** list of linchpin signals — at most 3 items — that demonstrate this specific dispatch's job is done well. It is distinct from entity-level acceptance criteria. The cap is an upper bound, not a target: 0, 1, 2, or 3 items are all valid; do not pad to reach 3. This is not a work-breakdown. The ensign already knows how to read the entity body, commit before signaling complete, and write a stage report; those are covered by structural conventions and MUST NOT appear in the checklist. Name what separates a good outcome from a ceremonial one.

**New (merged rewrite of lines 60 and 62 — retains every piece of #192's linchpin framing, adds the AC distinction):**

Line 60 (item 2 of the numbered list):

> 2. Build a numbered checklist of dispatch-specific linchpins from the target stage's `Outputs:` bullets and any entity-level acceptance criteria this stage is the natural place to advance. Checklist items are the per-dispatch signals that this stage's contribution is sound; they are not the AC list and are not a work-breakdown.

Line 62 (the paragraph directly below, preserving #192's linchpin discipline verbatim and appending the AC distinction):

>    The dispatch checklist is a **per-dispatch, stage-level** list of linchpin signals — at most 3 items — that demonstrate this specific dispatch's job is done well. It is distinct from entity-level acceptance criteria. The cap is an upper bound, not a target: 0, 1, 2, or 3 items are all valid; do not pad to reach 3. This is not a work-breakdown. The ensign already knows how to read the entity body, commit before signaling complete, and write a stage report; those are covered by structural conventions and MUST NOT appear in the checklist. Name what separates a good outcome from a ceremonial one. **Entity-level acceptance criteria (AC) are properties of the finished entity, not stage actions** — they live in the entity body's `## Acceptance criteria` section and are cross-checked at every gate (see `## Completion and Gates`), independent of this checklist's DONE/SKIPPED/FAILED accounting.

The #192 paragraph is preserved verbatim; the AC-vs-checklist sentence is appended as the final sentence. The single-line item 2 is rewritten to drop `from stage outputs and entity acceptance criteria` (which conflated the two concepts #193 separates) and to frame the checklist as dispatch-specific linchpins whose source is stage `Outputs:` plus stage-appropriate AC advancement, not AC enumeration.

**And in `## Completion and Gates`, after the existing "`{N} done, {N} skipped, {N} failed`" line, add:**

> **AC coverage cross-check.** Additionally, at every gate, scan the entity body's `## Acceptance criteria` section and confirm each `**AC-N**` item has at least one evidence citation from this stage's report or a prior stage report. Name any AC without evidence; REJECT if this stage was the natural place to address it. This cross-check is independent of checklist DONE/SKIPPED/FAILED accounting — checklist items are dispatch signals, AC items are entity properties.

### Edit 2 — `docs/plans/README.md`

**In the `### ideation` stage Outputs section, after the existing bullet "Acceptance criteria must include how each criterion will be tested," append:**

> Acceptance criteria are **entity-level** — they describe properties of the finished task (end-state facts a future reader can verify), not stage actions. Items that describe stage work ("run X 3 times", "produce analysis Y") belong in the stage report's checklist, not in the AC list. If an AC item reads as an imperative verb phrase ("Run …", "Produce …", "Capture …"), rewrite it as the end-state property it produces ("Test X passes reliably", "Analysis Y concludes with cited evidence", "File Z contains string W").

**In the `### validation` stage Outputs section, append one sentence after "Verify each acceptance criterion with evidence":**

> Pull every `**AC-N**` item from the entity body's `## Acceptance criteria` section; reproduce the evidence cited in each "Verified by" clause; flag any AC without evidence. Validation's job is cross-check, not re-derive.

**Replace the Task Template at the bottom with:**

```yaml
---
id:
title: Task name here
status: backlog
source:
started:
completed:
verdict:
score:
worktree:
---

Brief description of this task and what it aims to achieve.

## Acceptance criteria

Each AC names a property of the finished entity (not a stage action) and how it is verified.

**AC-1 — {End-state property.}**
Verified by: {grep / test name / file path / command a future reader can reproduce.}
```

### Edit 3 — `skills/commission/SKILL.md`

**In the generated-README Entity Template section (currently at `SKILL.md` around line 307-325 per the audit), mirror Edit 2's template shape** — the commission skill's generated README gets the same `## Acceptance criteria` template block so newly commissioned workflows inherit the convention.

**Also add one sentence to the per-stage Outputs guidance (currently line 269)** clarifying that Outputs bullets become checklist items at dispatch, and any entity-level properties the stage produces belong under the entity-body `## Acceptance criteria` heading, not in the stage Outputs.

## Acceptance criteria

Each AC names a property of the finished entity (not a stage action) and how it is verified.

**AC-1 — Shared-core dispatch contract distinguishes AC from checklist.**
Verified by: `grep -n "Entity-level acceptance criteria (AC) are properties of the finished entity" skills/first-officer/references/first-officer-shared-core.md` returns exactly one match near line 60, in the `## Dispatch` section. The existing "Build a numbered checklist …" line is replaced (not duplicated).

**AC-2 — Shared-core gate review adds AC-coverage cross-check.**
Verified by: `grep -n "AC coverage cross-check" skills/first-officer/references/first-officer-shared-core.md` returns one match in the `## Completion and Gates` section. The prose names the `**AC-N**` anchor format and the REJECT condition.

**AC-3 — `docs/plans/README.md` ideation stage names the AC-vs-stage-action rule.**
Verified by: `grep -n "Acceptance criteria are \*\*entity-level\*\*" docs/plans/README.md` returns one match inside the `### ideation` subsection. The prose names the imperative-verb rewrite rule.

**AC-4 — `docs/plans/README.md` validation stage names the cross-check.**
Verified by: `grep -n "Pull every \`\*\*AC-N\*\*\` item" docs/plans/README.md` returns one match inside the `### validation` subsection.

**AC-5 — `docs/plans/README.md` task template includes the `## Acceptance criteria` section.**
Verified by: reading the Task Template block in `docs/plans/README.md` shows a `## Acceptance criteria` heading with the "Each AC names a property" guidance and one exemplar `**AC-1 — ...**` item with a `Verified by:` line.

**AC-6 — `skills/commission/SKILL.md` generated template mirrors the convention.**
Verified by: `grep -n "## Acceptance criteria" skills/commission/SKILL.md` returns at least one match inside the template block; `grep -n "Each AC names a property" skills/commission/SKILL.md` also returns one match. Commission test harness (`scripts/test-harness.md` or the existing static test covering generated-workflow shape) passes unchanged.

**AC-7 — #193's own AC list is self-consistent with the distinction.**
Verified by: captain judgment at ideation gate. AC-7 is a meta-AC on the entity's own AC list shape; it is not mechanically grep-testable and cannot be reproduced from a future repo state. The captain confirms at gate that every other AC above reads as an end-state property (grep output / file contents / suite status), with no item phrased as "implementer runs X" or "ideation produces Y." The `## Self-consistency check (pre-gate)` section below records the author's walk-through as evidence supporting captain review.

**AC-8 — Static suite green post-merge.**
Verified by: `make test-static` passes on main after the PR merges. No new test added unless AC-6's commission-harness test needs extension; if added, it appears in the static suite.

## Test plan

- **Static, primary:** five grep-based assertions (AC-1 through AC-5) against the two edited files. Add one static test case to the existing commission-harness or scaffolding-guardrail test suite that asserts the commission-generated README contains the `## Acceptance criteria` template block (AC-6). Roughly one new test file or ~20 lines added to an existing one. `make test-static` covers AC-8.
- **Behavioral, required (before merge):** one live FO dispatch on any trivial task in `docs/plans/` (or a throwaway fixture) that follows the new template. Confirm (a) the FO-built checklist is distinct from the AC list in the entity body, (b) the FO's gate-review output names AC-coverage separately from checklist DONE/SKIPPED/FAILED. One run sufficient — but the run is required, not optional. Rationale: the payload of this change is FO behavioral discipline (checklist-building and gate-review prose). Static grep tests confirm the prose landed; they cannot confirm the prose changes FO behavior in practice. A single ~$1 dispatch closes that gap cheaply relative to the risk of prose that reads right but doesn't bite at runtime.
- **E2E not required.** No code or test plumbing changes beyond the required behavioral spot-check above.
- **Cost estimate:** ~$1-3 (one required spot-check dispatch; static tests are free). No multi-run budget.

## Self-consistency check (pre-gate)

Walking each of this entity's own ACs against the stage-action rewrite rule:

- AC-1 names an end-state grep result. ✓ entity-level.
- AC-2 names an end-state grep result. ✓ entity-level.
- AC-3, AC-4 name end-state grep results. ✓ entity-level.
- AC-5 names an end-state file content property. ✓ entity-level.
- AC-6 names end-state grep results + test suite status. ✓ entity-level.
- AC-7 is a meta-AC on the entity's own AC list shape. Its `Verified by:` clause is `captain judgment at ideation gate` — the property is entity-level (the AC list's self-consistency as a property of the final entity body), but verification is not grep-reproducible, so captain review stands in for mechanical test. ✓ entity-level; meta-verified.
- AC-8 names an end-state test-suite status. ✓ entity-level.

No AC reads as an imperative verb directed at an implementer. The distinction #193 proposes holds for #193 itself.

## Out of scope

- **Retrofitting existing entity bodies.** Entities already past ideation at #193 merge time keep their existing ACs. The three audit worst-offenders (#186, #177, archived #diagnose-opus-4-7) are not rewritten.
- **Per-AC enforcement mechanisms** ("every AC must have a test name"). The "Verified by:" line is a convention, not a mechanism-level check.
- **Auto-generating ACs from stage outputs.** Different problem.
- **Rewiring `claude-team build` to accept `acceptance_criteria` vs `checklist` as separate input JSON keys.** Out of scope — current single-checklist input still works; the AC list lives in the entity body and is read by the FO during dispatch assembly, not passed as structured input.
- **Workflow-specific frontmatter override for AC convention.** Following #192's precedent, no configurability knob until a second workflow needs a different shape.

## Cross-references

- **#192** — 3-item checklist cap. Tightly related; #193 clarifies why the checklist can be small. Sequence: #193 lands after #192 to avoid rebase churn on the shared-core line-60 neighborhood. Captain may choose to stack them.
- **#186** — concrete case that surfaced the confusion. AC-5's "3× `test_standing_teammate_spawn`" is the archetypal stage-level-disguised-as-AC item. Not retrofitted under this entity.
- **#191** — commission skill UX revisit. If #191 reshapes the commission flow substantially, the AC-6 edit point may move; rebase and re-target the same template-block anchor.
- `docs/plans/README.md` — workflow README updated per Edit 2
- `skills/first-officer/references/first-officer-shared-core.md` — dispatch + gate prose updated per Edit 1
- `skills/commission/SKILL.md` — generated template updated per Edit 3

## Stage Report

### Summary

Audited 20 recent entity bodies (125 ACs total): ~82% entity-level, ~17% stage-level disguised as AC, concentrated in diagnostic/experiment tasks (#186, #177, archived diagnose-opus-4-7). Data validates the problem without justifying blanket retrofit — migration is prospective only. Resolved all 6 seed questions: (Q1) prescribe a loose template shape with a "Verified by:" convention; (Q2) no retrofit; (Q3) stage-outputs cover stage-specific properties, not AC subsets; (Q4) validation cross-checks entity-level ACs; (Q5) distinct from #192, lands after; (Q6) no frontmatter override, following #192's precedent. Specified three concrete edits (shared-core dispatch + gate, `docs/plans/README.md` stages + template, commission SKILL.md generated template) with exact before/after prose. Produced 8 self-consistent entity-level ACs for #193 itself, each with a grep-based or suite-status "Verified by" clause. Test plan is static-primary (~5 grep assertions + 1 commission-harness check + `make test-static`), with one optional behavioral spot-check dispatch (~$1-3).

### Checklist

1. **Resolve the 6 open design questions with concrete before/after wording — DONE.** Each question addressed in `## Resolved design questions` with explicit recommendation: loose-template-with-convention (Q1), prospective-only migration (Q2), stage-outputs-not-AC-subsets (Q3), validation-cross-checks (Q4), #192-sequencing (Q5), no-frontmatter-override (Q6). Concrete template block given for Q1; Edit-1/Edit-2/Edit-3 blocks give exact before/after prose for shared-core, `docs/plans/README.md`, and commission SKILL.md.

2. **Audit ~20 recent entity bodies with AC classification — DONE.** 20 entities sampled (9 active, 11 archived); 125 ACs classified into E (entity-level, 102), S (stage-level-as-AC, 22), M (mixed, 1). Distribution table and worst-offender names (#186, #177, archived diagnose-opus-4-7-fo-regression) recorded in `## Audit of recent entity bodies`. Pattern identified: diagnostic/experiment tasks dominate the stage-level population; code- and prose-landing tasks are already clean. Audit informs the no-retrofit migration decision.

3. **Produce refined entity-level ACs, template-update spec, shared-core prose change, test plan — DONE.** 8 ACs written (AC-1 through AC-8) each with a "Verified by" grep/suite-status clause. Template-update spec in Edit 2 (`docs/plans/README.md` stage prose + task template). Shared-core prose change in Edit 1 (dispatch line 60 + gate cross-check paragraph). Commission-skill edit in Edit 3. Test plan specifies 5 grep assertions + 1 commission-harness extension + `make test-static`, with one optional behavioral spot-check. Self-consistency check walks #193's own ACs against the stage-action rewrite rule and confirms zero violations.

### Cycle 2 — staff-review amendments landed

Three blocking amendments from staff review applied in-place on main (non-worktree stage); no implementation stage work dispatched.

1. **Edit 1 respec against post-#192 shared-core — DONE.** Opened `skills/first-officer/references/first-officer-shared-core.md`; captured both line 60 (`Build a numbered checklist from stage outputs and entity acceptance criteria.`) and line 62 (the linchpin-discipline paragraph landed by #192 — `at most 3 items`, `0, 1, 2, or 3 items are all valid; do not pad to reach 3`, `Name what separates a good outcome from a ceremonial one`). Edit 1 now presents a merged rewrite: line 62's #192 paragraph preserved verbatim with the AC-vs-checklist sentence appended as its final sentence; line 60 rewritten to frame the checklist as dispatch-specific linchpins sourced from stage `Outputs:` plus stage-appropriate AC advancement (dropping the conflated `from stage outputs and entity acceptance criteria`). The silent #192 regression flagged by staff review is now impossible — every piece of #192's linchpin framing appears verbatim in the new Edit 1 block.

2. **AC-7 Verified-by clause corrected — DONE.** Changed from `reading this AC list` to `captain judgment at ideation gate`. Prose now explicitly names AC-7 as a non-grep-testable meta-AC and points to `## Self-consistency check (pre-gate)` as the author's walk-through evidence supporting captain review. The Self-consistency bullet for AC-7 is updated to match.

3. **Test plan behavioral spot-check promoted to required — DONE.** The bullet formerly labeled `Behavioral, spot-check:` with `One run sufficient` is now `Behavioral, required (before merge):` with explicit rationale: payload is FO behavioral discipline, static grep tests confirm prose landed but cannot confirm behavior changed, one ~$1 dispatch closes that gap cheaply. Cost estimate updated to label the spot-check required (not optional). No new AC added; the test plan's own prose carries the requirement.

### Summary

Staff-review blockers landed. Edit 1 now merges lines 60 and 62 verbatim + append, preserving #192's linchpin framing while adding the AC-vs-checklist distinction. AC-7's `Verified by:` clause is now internally consistent (captain judgment for a meta-AC). Behavioral spot-check is required, not optional. Non-blocking nice-to-haves from the staff review (diagnostic-class exemplar, legacy-entities note, evidence-reproduction cost cap) were captain-deferred and remain out of scope.
