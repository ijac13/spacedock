---
id: 125
title: "Entity body accumulation anti-pattern — stage reports shouldn't append forever"
status: ideation
source: "FO diagnosis after both 116 cycle-2 and cycle-3 impl ensigns died from context overflow driven by entity-body reads"
score: 0.85
worktree:
started: 2026-04-10T21:25:50Z
completed:
verdict:
issue:
pr:
---

Stage reports currently accumulate in the entity body of the task file itself. Each implementation cycle, validation cycle, feedback rejection, and re-implementation appends more content — ideation reports, stage reports, feedback cycles sections, addenda, reviewer findings. After two or three cycles on a task of moderate complexity, the entity body can grow past 800 lines. Every subsequent ensign dispatched on that task has to read the entire accumulated history to understand its instructions, which blows up its context budget before it can reach the actual deliverable.

## Empirical evidence — task 116 killed two impl ensigns

During the 2026-04-10 session, task 116 `readme-and-architecture-refresh` killed two consecutive implementation ensigns by this exact mechanism:

**Cycle-2 impl ensign (kept alive across feedback):** started at ~80% context after cycle 1, died silently at 200k after writing stage report content into an ever-growing entity body. Left +43/-53 uncommitted lines of actual README changes in the worktree.

**Cycle-3 impl ensign (fresh dispatch with explicit 60% escalation warning):** peaked at **170,668 resident tokens (85.3% of 200k)** across 111 turns. Died mid-turn. Diagnostic tool-use counts from its jsonl:

| Tool target | Read count | Edit count |
|---|---|---|
| `docs/plans/readme-and-architecture-refresh.md` (entity body, 792 lines) | **25** | **9** |
| `README.md` (121 lines — the actual deliverable) | 1 | **0** |

The cycle-3 ensign read its own task body **25 times** and the README **once**. It edited the task body **9 times** and the README **zero times**. It spent all of its context on reading and editing its own instructions + accumulated history, never touching the deliverable before dying.

Notably, the cycle-3 ensign was actively trying to **prune** the entity body when it died — the uncommitted diff showed `+150/-262` lines, a net reduction. This is evidence that the right organic instinct (shrink the entity body) is already present in worker behavior; what's missing is architectural support for keeping it small from the start.

## Root cause

The entity body conflates two very different kinds of content:

1. **The spec** — stable, small: problem statement, acceptance criteria, design decisions, stage definitions, active directives from the current cycle.
2. **The execution log** — accumulating, large: ideation stage report, implementation stage reports (possibly multiple cycles), validation stage reports (possibly multiple cycles), feedback cycles section, addenda, independent reviewer findings.

Current design: both live in one markdown file. The entity body is the single source of truth for both "what to do" and "what has been done". This works for small single-cycle tasks. It catastrophically fails for tasks that go through multiple feedback cycles or substantial iteration, because every cycle adds 100–200 lines of execution log that the next cycle's ensign has to read just to find the active directives.

Secondary cause: the dispatch prompt template currently says "Read the entity file at {path} for full context". This pulls the entire 800-line blob into the ensign's context on turn 1 and again on every subsequent turn that needs to reference it.

## Design directions (ideation to choose)

Four possible fixes, in rough order of schema disruption:

### Option A — Separate stage-history file
Move completed stage reports to a companion file `{slug}-stage-history.md` alongside the entity file. The entity body retains only the spec + active current-cycle stage report. The history file is append-only and workers don't need to read it unless doing historical analysis. **Minimal schema change; rebase-safe.**

### Option B — Archive completed stage reports per cycle
When a cycle completes, move the current stage report out of the entity body into `_archive/stage-reports/{slug}-{stage}-cycle{N}.md`. The entity body gets pruned to just the spec + upcoming work. **More aggressive; requires a workflow step to perform the move at cycle boundary.**

### Option C — Stage reports never touch the entity body
Ensigns write their stage reports to standalone files from the start (`{workflow_dir}/stage-reports/{slug}-{stage}-cycle{N}.md`). The FO reads them at gate time. The entity body is permanently a short spec. **Largest schema change; cleanest separation.**

### Option D — Inline directives in dispatch prompt; entity body stays accumulating
Change FO behavior only: dispatch prompts contain the full directive list inline. Ensigns are told NOT to read the entity body; they get everything from the prompt. Stage reports still accumulate but ensigns only read+write at the very end once. **Fewest schema changes; most dispatch-template changes. Catches the symptom without fixing the underlying storage.**

Ideation should evaluate how each option interacts with refit, commission, the status tool, and the PR body template (task 118's extraction rules source the motivation lead from "entity body paragraph(s) between closing `---` and the first `##` heading" — that source will change depending on which option lands).

## Scope

- Architectural ideation choosing an option (or hybrid)
- Implementation of the chosen option
- Migration path for in-flight tasks with accumulated entity bodies (task 116 is the obvious test case)
- Update the dispatch template in `skills/first-officer/references/claude-first-officer-runtime.md` to reflect the new pattern
- Update the ensign shared core in `skills/ensign/references/ensign-shared-core.md` to reflect the new stage-report-write path
- Update `skills/commission/SKILL.md` if the workflow schema changes
- Update `skills/refit/SKILL.md` similarly
- Update workflow README templates
- Update the pr-merge mod's extraction rules (task 118) if the entity body source structure changes

## Out of scope

- Retroactively pruning all 106 archived entities' stage reports (one-time cleanup; separate task if wanted)
- Changes to frontmatter fields (tasks 122, 123 own that surface)
- The underlying context-aware-reuse rule (task 121 is orthogonal — 125 is about what the ensign reads, 121 is about when to fresh-dispatch)

## Acceptance Criteria (ideation to refine)

1. Stage reports from different cycles do not accumulate into a single ever-growing blob that every subsequent ensign must re-read. A separation mechanism is in place.
2. A fresh ensign dispatched on a mid-flight task's next cycle consumes **<10% of its context budget** from reading spec + current directives (measured: tokens consumed by Read tool calls on entity-associated files, divided by the model context window).
3. Task 116's own backlog is unblocked: either by prune-and-rescue on 116's existing 792-line entity body, or by accepting 116 shipped-as-is with partial cycle-3 recovery + a successor task for remaining work.
4. `tests/test_agent_content.py` has a static assertion that the FO dispatch template does NOT unconditionally instruct the ensign to "read the entity file body for full context".
5. Existing suites stay green: `test_agent_content.py`, `test_rejection_flow.py`, `test_merge_hook_guardrail.py`, `test_dispatch_completion_signal.py`.

## Test Plan

- Static assertion in `test_agent_content.py` for AC-4 (low cost, required).
- Unit tests for any new files/paths introduced by Option A/B/C (if chosen).
- E2E regression: modify `tests/test_rejection_flow.py` or add a new test that drives a task through 3+ feedback cycles and verifies the entity body does not grow unboundedly.
- **Ground-truth measurement**: dispatch a cycle-4 ensign on task 116 under the new pattern, record its peak resident tokens, verify <100k (ideally <60k). This is a session-live measurement, not a CI test.

## Related

- **Task 116** `readme-and-architecture-refresh` — the observed test case. Died twice from this anti-pattern. Cycle-4 dispatched via inline-directives workaround (Option D applied ad-hoc) concurrent with this task seed.
- **Task 121** `fo-context-aware-reuse` — complementary and orthogonal. 121 is about when to fresh-dispatch; 125 is about what the ensign reads when dispatched. Both matter for FO reliability.
- **Task 118** `pr-merge-mod-rich-body-template` — just landed. Its PR-body extraction rules depend on the current entity-body structure; 125's Option A/B/C may require 118's extraction rules to update in lockstep.
- **Issue #63** (local) — fuzzy prose template anti-pattern umbrella. 125 is a specific instance: the entity body is the prose spec for ensigns, and it has the same fragility as the dispatch template issue #63 calls out.
- **External FO feedback (2026-04-10)** — the experiment pipeline FO's "prose where there should be structure" meta-thesis. 125 is one of the structural fixes that thesis implies.

## Stage Report: ideation

- [x] Evaluate options A-D against criteria
  See option evaluation matrix below.
- [x] Pick recommended option with justification
  Option A (separate stage-history file) recommended; see rationale.
- [x] Define concrete acceptance criteria with test methods
  Six ACs defined with specific test approaches.
- [x] Define test plan proportional to chosen option
  Three-tier plan: static assertions, unit tests, measurement test.

### Option Evaluation

**Criteria key:** schema disruption (lower is better), refit/commission compatibility, PR body extraction compatibility (task 118), status tool compatibility, implementation effort.

**Option A — Separate stage-history file (`{slug}-stage-history.md`)**

- Schema disruption: LOW. The entity body format is unchanged — it just stops accumulating old stage reports. A companion file appears alongside the entity file. No frontmatter changes. No new directory structure.
- Refit/commission: COMPATIBLE. Commission seeds entity files the same way. Refit needs no changes — it doesn't touch stage reports. The archive step moves both files together.
- PR body extraction: COMPATIBLE. The motivation lead comes from "entity body paragraph(s) between closing `---` and the first `##` heading" — this region is the spec paragraph, which stays in the entity body unchanged. Stage reports live below `##` headings and were never part of the extraction source.
- Status tool: COMPATIBLE. The status script reads frontmatter only. No changes needed.
- Implementation effort: LOW. Three touch points: (1) ensign shared core writes completed stage reports to the history file instead of the entity body, (2) FO dispatch template stops telling ensigns to "read the entity file for full context" and instead provides targeted reading instructions, (3) FO completion gate reads the stage report from the history file.

**Option B — Archive completed stage reports per cycle**

- Schema disruption: MEDIUM. Introduces `_archive/stage-reports/` directory. Requires a workflow step at cycle boundaries to move content. The entity body is still the initial write target — the move happens later.
- Refit/commission: MINOR FRICTION. Commission must know about the archive directory. Refit must handle the new path convention.
- PR body extraction: COMPATIBLE (same reasoning as A — extraction sources the spec paragraph, not stage reports).
- Status tool: COMPATIBLE.
- Implementation effort: MEDIUM. Requires a new FO workflow step at cycle boundaries. The timing of the move (who triggers it, when) adds complexity. The ensign still writes to the entity body initially, so the accumulation problem is only partially solved within a cycle — it's solved across cycles but not within a long single cycle.

**Option C — Stage reports never touch the entity body**

- Schema disruption: HIGH. Changes the fundamental ensign output contract. Stage reports go to `{workflow_dir}/stage-reports/{slug}-{stage}-cycle{N}.md`. The entity body becomes a pure spec. Every reference to "write a stage report section in the entity file" must change.
- Refit/commission: MODERATE FRICTION. Commission must scaffold the `stage-reports/` directory. Refit must handle migration. Archive must collect scattered files.
- PR body extraction: COMPATIBLE (same as A/B — spec paragraph untouched).
- Status tool: NEEDS UPDATE. If the status tool ever needs to display stage report summaries (not current, but plausible), it would need to know about the new location.
- Implementation effort: HIGH. Touches ensign shared core, FO shared core, FO runtime, commission, refit, archive workflow, and potentially the status tool. The number of files that reference the stage report protocol is large.

**Option D — Inline directives in dispatch prompt; entity body stays accumulating**

- Schema disruption: NONE. No file format changes.
- Refit/commission: COMPATIBLE. Nothing changes in the schema.
- PR body extraction: COMPATIBLE. Entity body unchanged.
- Status tool: COMPATIBLE.
- Implementation effort: LOW for the dispatch template change. But: does not fix the root cause. The entity body still grows. The ensign still writes stage reports into it. The FO still reads it at completion gates. The problem is deferred, not solved. Task 116's cycle-3 ensign was actively trying to prune the entity body when it died — even with inline directives, the ensign will eventually need to read the entity body to write its own stage report, and the accumulated history is still there.

### Recommendation: Option A (separate stage-history file)

**Justification grounded in empirical data:**

Task 116's cycle-3 ensign read its entity body 25 times and edited it 9 times. The entity body was 792 lines. Of those 792 lines, roughly 100-150 were spec content (problem statement, ACs, scope, design directions) and the remaining 600+ were accumulated stage reports from cycles 1-3. If completed stage reports had been in a separate file, the entity body would have been ~150 lines. At ~4 tokens/line, that's ~600 tokens per read instead of ~3,200 — an 80% reduction per read. Over 25 reads, that's ~65,000 tokens saved, which is 32% of the 200k context window.

Option A is the right choice because:

1. **Smallest schema disruption that fixes the root cause.** Unlike Option D (which treats the symptom), A removes accumulated history from the entity body entirely. Unlike Option C (which redesigns the write path), A keeps the ensign writing to the entity body for the *current* stage report — only completed reports move to the history file.

2. **The write-then-move pattern matches existing FO behavior.** The FO already moves entity files to `_archive/` at terminal stage. Moving completed stage reports to a companion file at stage boundaries is the same pattern at a smaller scale.

3. **PR body extraction is unaffected.** The motivation lead extraction rule sources from the spec paragraph (between `---` and first `##`), which is preserved unchanged.

4. **Option D's ad-hoc success on task 116 cycle-4 validates the direction, not the mechanism.** The inline-directives workaround worked because it reduced the ensign's initial context load. Option A achieves the same reduction structurally, without requiring the FO to inline all directives (which creates its own scaling problem as directive complexity grows).

**Concrete mechanism:**

- The ensign writes its stage report as `## Stage Report: {stage_name}` in the entity body (unchanged from current protocol).
- When the FO processes a stage completion and advances to the next stage, it moves the completed `## Stage Report` section from the entity body into `{slug}-stage-history.md` (companion file, same directory as the entity file).
- The history file is append-only. Format: each entry is the full stage report section, preceded by a `<!-- cycle {N}, stage {name}, {ISO timestamp} -->` separator comment.
- The FO dispatch template changes from "Read the entity file at {path} for full context" to targeted instructions that tell the ensign what to read and where.
- The ensign shared core's Stage Report Protocol is unchanged — it still says "write or replace a `## Stage Report` section in the entity file body."

**FO Write Scope impact:** The FO already owns state-transition commits at dispatch/advance boundaries. Moving completed stage reports out of the entity body at advance time is a natural extension of the FO's state management responsibility. This requires adding "stage-history file maintenance" to the FO Write Scope list. This is a minor, well-scoped addition — the FO is moving content it already reads (the stage report it just reviewed at the gate), not generating new content.

### Refined Acceptance Criteria

1. **AC-1: Stage report separation.** After a stage completion + advance, the completed stage report section is absent from the entity body and present in `{slug}-stage-history.md`. The entity body retains only the spec + any current-cycle active content.

2. **AC-2: Context budget.** A fresh ensign dispatched on a mid-flight task's next cycle consumes <10% of its context budget from reading the entity file. Measured: tokens consumed by the first Read of the entity file, divided by 200k. For an entity body of ~150 lines (spec + current directives), this is ~600 tokens / 200k = 0.3%.

3. **AC-3: Dispatch template update.** The FO dispatch template in `claude-first-officer-runtime.md` does NOT contain the unconditional instruction "Read the entity file at {path} for full context."

4. **AC-4: Static assertion.** `tests/test_agent_content.py` has a test that asserts the dispatch template does not unconditionally instruct reading the entity file "for full context."

5. **AC-5: PR body extraction unaffected.** The pr-merge mod's extraction rules continue to source the motivation lead from entity body paragraph(s) between closing `---` and the first `##` heading. No changes to `mods/pr-merge.md` are required.

6. **AC-6: Existing suites green.** `test_agent_content.py`, `test_rejection_flow.py`, `test_merge_hook_guardrail.py`, `test_dispatch_completion_signal.py` all pass.

### Test Plan

**Tier 1 — Static assertions (CI, low cost):**

- New test in `test_agent_content.py`: assert the dispatch template in `claude-first-officer-runtime.md` does not contain the phrase "Read the entity file at" followed by "for full context" as an unconditional instruction. This catches regressions where someone re-adds the blanket read instruction.
- New test in `test_agent_content.py`: assert the FO shared core's FO Write Scope section mentions stage-history file maintenance (ensuring the scope doc stays in sync with the implementation).

**Tier 2 — Unit tests (CI, medium cost):**

- Test that the ensign shared core's Stage Report Protocol still instructs writing to the entity body (ensuring the write path is unchanged).
- Test that the FO shared core's Completion and Gates section references reading stage reports and moving them to the history file (ensuring the move step is documented).

**Tier 3 — Measurement test (session-live, high value):**

- Dispatch a cycle-4+ ensign on a multi-cycle task (task 116 is the natural candidate). Record peak resident tokens. Verify <100k (target <60k). This is not a CI test — it's a session-live measurement performed during implementation validation. The measurement validates AC-2 against real-world context pressure.

**Regression:**

- Run the full existing test suite (`test_agent_content.py`, `test_rejection_flow.py`, `test_merge_hook_guardrail.py`, `test_dispatch_completion_signal.py`, and all other `test_*.py` files) before and after implementation. No regressions.

### Summary

Option A (separate stage-history file) is recommended. It fixes the root cause — stage reports accumulating in the entity body — with minimal schema disruption. The ensign write path is unchanged (stage reports still go into the entity body). The FO gains a new responsibility at stage boundaries: move the completed stage report to a companion `{slug}-stage-history.md` file. The dispatch template loses its blanket "read the entity file for full context" instruction in favor of targeted reading instructions. PR body extraction, the status tool, refit, and commission are all unaffected. The empirical data from task 116 predicts an 80% reduction in per-read token cost for the entity file, saving ~65k tokens over the lifecycle of a multi-cycle task.
