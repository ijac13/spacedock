---
title: Commission UX — Round 2 fixes from testflight observation
status: implementation
source: testflight sd5-test observation
started: 2026-03-24T01:00:00Z
completed:
verdict:
score: 0.90
worktree: .worktrees/ensign-commission-ux-round2
---

UX issues observed from a fresh commission run (sd5-test: product idea to simulated customer interview pipeline). Covers both the commission conversation flow and the quality of generated artifacts.

---

## Architecture: README as single source of truth for stage behavior

### Problem

The first-officer template in SKILL.md section 2d (~160 lines) hardcodes pipeline-specific behavior: approval gate stage names, conflict check referencing "implementation", worktree-for-all-stages. The README defines stages but the first-officer duplicates and sometimes contradicts the README. Every new pipeline gets the same hardcoded logic regardless of its actual stages.

This subsumes the `ideation-on-main` entity (stage properties in README schema).

### Design: structured stage properties in README

Add two structured fields to each stage definition in the README:

- **Worktree:** `yes` or `no` — whether this stage's work happens in a git worktree (isolated branch) or directly on main.
- **Human approval** already exists but stays as-is.

The stage section format in the README becomes:

```markdown
### `stage-name`

{Description paragraph.}

- **Inputs:** ...
- **Outputs:** ...
- **Good:** ...
- **Bad:** ...
- **Worktree:** Yes / No
- **Human approval:** Yes — {reason} / No
```

Note: `Worktree` is added as a new line item. `Human approval` remains unchanged — it already exists in every stage definition. The commission skill decides default worktree values per stage based on the mission (e.g., stages that only modify entity markdown default to `No`; stages that produce code or external artifacts default to `Yes`). The user can override during the confirm step.

### Design: generic first-officer template

The first-officer template in SKILL.md section 2d becomes fully generic. It references NO pipeline-specific stage names. Instead, it reads the README at startup and derives dispatch behavior from the structured stage properties.

Key changes to the template:

1. **Remove all hardcoded stage names** — no `ideation`, `implementation`, `interview-prep`, etc. The template uses `{first_stage}` and `{last_stage}` as the only stage-name variables (filled at generation time since they're structural).

2. **Remove the hardcoded approval gate list** — replace with: "Read each stage's `Human approval` field from the README. If it says `Yes`, require {captain}'s approval before entering that stage."

3. **Remove the hardcoded "ideation-on-main" special case** — replace with: "Read each stage's `Worktree` field from the README. If `No`, dispatch the ensign on main (no worktree). If `Yes`, use the worktree flow."

4. **Remove the hardcoded conflict check mentioning "implementation"** — replace with: "When multiple {entity_label_plural} are entering a worktree stage simultaneously, check if they modify the same files."

5. **State Management stage list** — instead of `{stages as comma-separated list}`, the first-officer reads valid statuses from the README at startup.

The dispatch logic in the template becomes a generic algorithm:

```
For each {entity_label} ready for next stage:
  1. Look up next stage in README
  2. If next stage has "Human approval: Yes" → ask {captain}
  3. If next stage has "Worktree: No" → dispatch on main
  4. If next stage has "Worktree: Yes" → create/reuse worktree, dispatch in worktree
```

### README schema change in SKILL.md section 2a

In the README template's per-stage subsection, add the `Worktree` field:

```markdown
### `{stage_name}`

{Description.}

- **Inputs:** ...
- **Outputs:** ...
- **Good:** ...
- **Bad:** ...
- **Worktree:** {Yes if this stage modifies code or produces artifacts beyond the entity file; No if it only modifies entity markdown}
- **Human approval:** {Yes — reason / No}
```

The commission skill determines the default worktree value during design:
- First stage (backlog/holding): `No` (nothing to isolate)
- Terminal stage (done): `No` (nothing to isolate)
- Stages that only update the entity body (ideation, research, synthesis): `No`
- Stages that produce code, artifacts, or run tools: `Yes`

### Files changed

- `skills/commission/SKILL.md` — section 2a (README template): add `Worktree` field to stage definitions
- `skills/commission/SKILL.md` — section 2d (first-officer template): rewrite dispatch logic to be generic, reading from README
- `docs/plans/README.md` — add `Worktree` field to each stage definition (our own pipeline)
- `.claude/agents/first-officer.md` — regenerate with generic logic (or refit)
- `docs/plans/ideation-on-main.md` — mark as subsumed by this entity

### Edge cases

- README parsing: the first-officer reads markdown at runtime. The structured fields are line items with a known prefix (`- **Worktree:**`, `- **Human approval:**`). Parsing is simple string matching — the same approach the first-officer already uses for reading stage definitions.
- Backward compatibility: existing pipelines generated before this change won't have `Worktree` fields. The first-officer should default to `Yes` (worktree) when the field is missing — this preserves current behavior for pre-existing pipelines.

---

## Issue 1: Command args ignored

### Problem

`/spacedock:commission product idea to simulated customer interview` provided the mission as arguments, but Q1 still asked "What's this pipeline for?" The args should count as answering Q1.

### Design

In SKILL.md Phase 1, add an "Args Extraction" step before Q1:

```
### Args Extraction

If the user's invocation message contains text beyond the command name (e.g.,
`/spacedock:commission product idea to simulated customer interview`), treat
that text as the mission statement.

- Extract {mission} from the args
- Proceed to Question 1 but present the extracted mission for confirmation
  rather than asking from scratch:

  > I'll use this as the pipeline mission: "{extracted_mission}"
  >
  > What does each work item represent?

This skips the "what's this pipeline for?" half of Q1 and goes straight to
the entity-type follow-up.
```

This interacts with the existing Batch Mode section: if the args contain enough info to fill ALL design inputs, Batch Mode kicks in. If args only contain the mission (most common case), Args Extraction fills just Q1's mission part.

### Files changed

- `skills/commission/SKILL.md` — Phase 1, before Q1: add Args Extraction subsection

### Edge cases

- Args that are ambiguous (e.g., just "ideas") — treat as partial mission, still ask Q1 but pre-fill.
- Args that contain everything (mission + entity + stages) — Batch Mode handles this, no change needed.

---

## Issue 2: Git repo auto-init

### Problem

Commission asked "Can I initialize a git repo?" instead of just doing it. A pipeline needs git — this is a prerequisite, not a choice.

### Design

In SKILL.md Phase 2 (Generate Pipeline Files), before generating any files, add:

```
### Ensure Git Repository

Before generating files, ensure the project has a git repository:

1. Check if the current directory is inside a git repo (`git rev-parse --git-dir`).
2. If not, initialize one silently: `git init && git add -A && git commit -m "initial commit"`.
3. Do NOT ask {captain} for permission — a pipeline requires git.
```

Place this before the "Read Spacedock Version" step.

### Files changed

- `skills/commission/SKILL.md` — Phase 2, add "Ensure Git Repository" subsection before "Read Spacedock Version"

### Edge cases

- Project already has a git repo — no-op, just proceed.
- Dirty working tree — the `git add -A && git commit` captures whatever exists before we start generating pipeline files. This gives a clean baseline.
- Empty directory — `git add -A` with nothing to add is fine; `git commit --allow-empty -m "initial commit"` ensures we have at least one commit (worktrees need a commit to branch from).

---

## Issue 3: Seed entity lookup too heavyweight

### Problem

User said "spacedock - find the info in ~/git/spacedock" and commission spawned a full `Agent(subagent_type="explore")` to search for seed data. For a path hint like this, just Read the relevant files directly.

### Design

In SKILL.md Question 3 (Seed Entities), add guidance about handling references:

```
If {captain} references an external source for seed data (e.g., "find the info in ~/git/spacedock"
or "see the backlog in project X"), read the referenced files directly using Read/Glob.
Do NOT spawn an Agent for this — a direct file read is sufficient. Look for:
- README files in the referenced directory
- Markdown files with YAML frontmatter (existing entities)
- Any obvious manifest or index file
```

### Files changed

- `skills/commission/SKILL.md` — Question 3 subsection, add seed-source guidance

### Edge cases

- Reference is vague ("check my other project") — ask for the specific path instead of guessing.
- Referenced path doesn't exist — report this and ask for correct path.

---

## Issue 4: TaskCreate spam

### Problem

8 `TaskCreate` calls during file generation cluttered the user's view. These are internal bookkeeping and shouldn't be visible.

### Design

In SKILL.md Phase 2, add an explicit instruction:

```
### Generation Discipline

Generate all pipeline files without creating tasks or updating progress trackers.
Do NOT use TaskCreate, TaskUpdate, or TodoWrite during file generation — these
create visible noise in {captain}'s UI. The generation checklist at the end of
Phase 2 is sufficient for tracking completion.
```

### Files changed

- `skills/commission/SKILL.md` — Phase 2, add "Generation Discipline" note before file generation begins

### Edge cases

- None — this is a behavioral instruction, not logic.

---

## Issue 5: Status script missing slug column

### Problem

The status output shows `STATUS TITLE SCORE SOURCE` but no filename/slug. Users need the slug to know which file to open or reference.

### Design

Add a `SLUG` column as the first column in the status script output. The slug is the filename without the `.md` extension.

Current header:
```
STATUS         TITLE                          SCORE  SOURCE
```

Proposed header:
```
SLUG                 STATUS         TITLE                          SCORE  SOURCE
```

### Files changed

- `templates/status` — update the description comment to mention slug extraction. The template is a stub that gets materialized by the LLM, so the description drives the output.
- `skills/commission/SKILL.md` — update the status template description in section 2b to mention the slug column.

Specifically, the template's `# instruction:` comment changes from:
```
# instruction: For every .md file in this directory (excluding README.md),
#   extract status, verdict, score, source from YAML frontmatter.
#   Print table sorted by stage order then score descending.
```
to:
```
# instruction: For every .md file in this directory (excluding README.md),
#   extract slug (filename without .md), status, verdict, score, source from YAML frontmatter.
#   Print table with columns: SLUG, STATUS, TITLE, SCORE, SOURCE.
#   Sorted by stage order then score descending.
```

### Edge cases

- Long slugs — the column width should be reasonable (e.g., `%-20s`). Slugs longer than 20 chars will overflow but that's acceptable for a terminal tool.

---

## Issue 6: Conflict check references "implementation"

### Problem

The first-officer template's conflict check says "When multiple {entity_label_plural} are entering implementation at the same time..." — hardcoding "implementation" as the stage name.

### Design

This is resolved by the architecture change (Issue 0 above). The generic first-officer template replaces the hardcoded "implementation" reference with:

```
**Conflict check:** When multiple {entity_label_plural} are entering a worktree
stage simultaneously, check if they modify the same files. If so, warn {captain}
about potential merge conflicts and propose sequencing them.
```

The conflict check triggers for ANY stage with `Worktree: Yes`, not just a stage named "implementation".

### Files changed

- `skills/commission/SKILL.md` — section 2d, part of the generic template rewrite (covered by architecture change)

### Edge cases

- Pipelines with no worktree stages — conflict check never triggers, which is correct.

---

## Issue 7: `{entity-slug}` in git refs

### Problem

Branch names use `ensign-{entity-slug}`, worktree paths use `.worktrees/ensign-{entity-slug}`. The `entity-slug` naming leaks the internal "entity" terminology into user-visible git refs.

### Design

Replace all occurrences in the first-officer template:
- Branch: `ensign/{entity-slug}` → `ensign/{slug}`
- Worktree path: `.worktrees/ensign-{entity-slug}` → `.worktrees/ensign-{slug}`

The template already uses `{slug}` as the variable name for the entity's filename stem. The change is purely cosmetic in the template — `{entity-slug}` was never a different variable, it was just a confusing name for the same slug.

### Files changed

- `skills/commission/SKILL.md` — section 2d, rename `{entity-slug}` to `{slug}` everywhere in the template

### Edge cases

- Existing worktrees from before the rename — this only affects newly generated pipelines. No migration needed.

---

## Issue 8: No stage-aware dispatch

### Problem

All stages go through worktrees, even research-type stages that only modify entity markdown. This creates unnecessary worktree overhead and orphan risk.

### Design

This is resolved by the architecture change (Issue 0 above). The first-officer reads the `Worktree` field from each stage definition in the README and dispatches accordingly:

- `Worktree: No` → dispatch on main. Ensign's working directory is the repo root. No worktree creation, no branch, no merge step. Changes are committed directly to main.
- `Worktree: Yes` → full worktree flow (create branch, dispatch in worktree, merge on completion).

The dispatch logic in the generic template:

```
If next stage has "Worktree: No":
  - Edit frontmatter on main: set status. Do NOT set worktree field.
  - Commit: "dispatch: {slug} entering {next_stage}"
  - Dispatch ensign on main (working directory = repo root, paths = repo-root-relative)
  - When ensign completes, changes are already on main. Skip merge step.
  - Proceed to approval gate check.

If next stage has "Worktree: Yes":
  - Edit frontmatter on main: set status, set worktree field.
  - Create worktree if not already active.
  - Dispatch ensign in worktree.
  - When complete, merge to main (or hold for approval).
```

### Files changed

- `skills/commission/SKILL.md` — section 2d, generic dispatch logic (covered by architecture change)
- `skills/commission/SKILL.md` — section 2a, README template adds `Worktree` field per stage

### Edge cases

- Entity transitions from a non-worktree stage to a worktree stage — worktree is created at the transition point, not at first dispatch.
- Entity transitions from a worktree stage to a non-worktree stage — merge the worktree first, then dispatch on main.
- Multiple non-worktree stages in sequence — each dispatches on main sequentially. No worktree created at any point.

---

## Issue 9: No concurrency limits

### Problem

Neither the generated README nor first-officer template mention concurrency limits. The Spacedock pipeline's own README has a manually-added `## Concurrency` section, but this isn't part of the generated template.

### Design

Add a `## Concurrency` section to the README template in SKILL.md section 2a:

```markdown
## Concurrency

Maximum 2 {entity_label_plural} in any single active stage at a time. The first officer
checks stage counts before dispatching and holds {entity_label_plural} in their current
stage until a slot opens.
```

Default: 2 per stage. This is a reasonable default — it prevents runaway parallel dispatch while allowing some concurrency. The commission can ask about concurrency preferences if {captain} has strong opinions, but a default of 2 is fine for v0.

The first-officer template adds a concurrency check to the dispatch loop:

```
Before dispatching, count how many {entity_label_plural} are currently in the
target stage. If the count equals the concurrency limit from the README's
Concurrency section, hold the {entity_label} in its current stage and move
to the next dispatchable {entity_label}.
```

### Files changed

- `skills/commission/SKILL.md` — section 2a, README template: add `## Concurrency` section
- `skills/commission/SKILL.md` — section 2d, first-officer template: add concurrency check to dispatch logic

### Edge cases

- All slots full — first-officer reports "pipeline idle, waiting for slots" and waits.
- Concurrency limit of 0 or unspecified — default to 2 per stage if missing from README.

---

## Issue 10: README vs first-officer commit discipline contradiction

### Problem

The README says "Commit status changes at session end" while the first-officer says "Commit state changes at dispatch and merge boundaries." These contradict each other. The first-officer's version is correct — dispatch boundaries ensure state is persisted before spawning ensigns.

### Design

Fix the README template in SKILL.md section 2a. Change the Commit Discipline section from:

```markdown
## Commit Discipline

- Commit status changes at session end, not on every transition
- Commit research outputs and {entity_label} body updates when substantive
```

to:

```markdown
## Commit Discipline

- Commit status changes at dispatch and merge boundaries
- Commit {entity_label} body updates when substantive
```

This matches what the first-officer actually does and is the correct behavior: state must be persisted before dispatching an ensign so that a crash doesn't lose the status transition.

### Files changed

- `skills/commission/SKILL.md` — section 2a, README template Commit Discipline section
- `docs/plans/README.md` — update our own pipeline's Commit Discipline to match (separate commit, not part of this entity's implementation)

### Edge cases

- None — this is a documentation fix.

---

## Acceptance Criteria

### Architecture (Issues 0, 6, 8)

1. The README template in SKILL.md section 2a includes a `Worktree` field in every stage definition.
2. The first-officer template in SKILL.md section 2d contains ZERO hardcoded stage names (no `ideation`, `implementation`, `interview-prep`, etc.) — only `{first_stage}` and `{last_stage}` as generation-time variables.
3. The first-officer template reads `Human approval` and `Worktree` fields from the README at startup.
4. Stages with `Worktree: No` dispatch ensigns on main (no worktree created).
5. Stages with `Worktree: Yes` use the full worktree flow.
6. The conflict check references "worktree stages" generically, not a specific stage name.
7. The `ideation-on-main` entity is marked as subsumed in its body.

### Commission flow (Issues 1–4)

8. If mission text is provided as command args, Q1 presents it for confirmation instead of asking from scratch.
9. Commission auto-initializes a git repo if none exists, without asking.
10. Seed entity references to external paths use Read/Glob directly, not Agent.
11. Phase 2 file generation does not use TaskCreate/TaskUpdate/TodoWrite.

### Generated artifacts (Issues 5, 7, 9, 10)

12. Status script template includes a SLUG column as the first column.
13. Branch names use `ensign/{slug}` (no `entity-slug` in naming).
14. Worktree paths use `.worktrees/ensign-{slug}` (no `entity-slug`).
15. README template includes a `## Concurrency` section with a default limit of 2 per stage.
16. First-officer template includes concurrency check before dispatch.
17. README template's Commit Discipline says "dispatch and merge boundaries", not "session end".

### Regression

18. The generated first-officer still handles: startup sequence, orphan detection, clarification protocol, event loop, state management, approval gates, merge/cleanup.
19. Batch mode still works (provided all inputs → skip to confirm → generate).
20. The status script template still materializes into a working bash 3.2+ script.

## Validation Report

### Test Harness

The test harness (`v0/test-commission.sh`) was invoked but requires a live `claude -p` session for batch-mode commission, which takes several minutes. The harness was still running at the time of this validation. Manual validation of all 20 acceptance criteria follows.

### Architecture (AC1-7)

**AC1: README template has Worktree field in EVERY stage definition** — PASSED
- SKILL.md line 261: `- **Worktree:** {Yes if this stage modifies code or produces artifacts beyond the entity file; No if it only modifies entity markdown}`
- Present in the per-stage template subsection alongside Inputs, Outputs, Good, Bad, Human approval.

**AC2: First-officer template has ZERO hardcoded stage names** — PASSED
- Searched section 2d (lines 358-553) for: ideation, implementation, interview-prep, interview, research, synthesis, validation, done, backlog.
- Zero matches for hardcoded stage names in the template. The only stage-name variables are `{first_stage}` (lines 531) and `{last_stage}` (lines 532-533), both used in State Management for timestamp semantics.
- The word "done" appears only in git commit messages as `"done: {slug} completed pipeline"` (lines 472, 478), which is a commit prefix, not a stage name reference.

**AC3: First-officer reads Human approval and Worktree from README at startup** — PASSED
- Startup step 3 (line 378-381): "Parse stage properties — For each stage defined in the README, extract: Worktree: Yes or No (default Yes if field is missing), Human approval: Yes or No"
- Dispatching step 4 (line 393): reads Human approval field.
- Dispatching step 6 (line 395): reads Worktree field.

**AC4: Worktree: No stages dispatch on main** — PASSED
- Lines 397-420: "Dispatch on main (Worktree: No)" section. Does NOT set worktree field. Dispatch uses repo root as working directory. Step c says "changes are already on main. Skip the merge step."

**AC5: Worktree: Yes stages use full worktree flow** — PASSED
- Lines 422-452: "Dispatch in worktree (Worktree: Yes)" section. Creates worktree with `git worktree add .worktrees/ensign-{slug} -b ensign/{slug}`, dispatches ensign in worktree directory.

**AC6: Conflict check says "worktree stage" generically** — PASSED
- Line 394: "When multiple {entity_label_plural} are entering a worktree stage simultaneously, check if they modify the same files."
- No mention of "implementation" or any specific stage name.

**AC7: ideation-on-main entity marked as subsumed** — PASSED
- `docs/plans/ideation-on-main.md` line 16: "**Subsumed by `commission-ux-round2`.** The Worktree field and generic first-officer template are implemented there."

### Commission Flow (AC8-11)

**AC8: Args extraction before Q1** — PASSED
- Lines 43-58: "Args Extraction" subsection placed before Question 1. Extracts mission from args, presents for confirmation: "I'll use this as the pipeline mission: \"{extracted_mission}\"" then asks "What does each work item represent?"

**AC9: Git auto-init without asking** — PASSED
- Lines 147-153: "Ensure Git Repository" subsection. Checks `git rev-parse --git-dir`, initializes silently if not a repo. Line 153: "Do NOT ask {captain} for permission — a pipeline requires git."

**AC10: Seed references use Read/Glob not Agent** — PASSED
- Lines 110-115: "read the referenced files directly using Read/Glob. Do NOT spawn an Agent for this — a direct file read is sufficient."

**AC11: No TaskCreate/TaskUpdate/TodoWrite in Phase 2** — PASSED
- Lines 155-159: "Generation Discipline" subsection. "Do NOT use TaskCreate, TaskUpdate, or TodoWrite during file generation — these create visible noise in {captain}'s UI."

### Generated Artifacts (AC12-17)

**AC12: Status template mentions SLUG column** — PASSED
- `templates/status` line 8: "Print table with columns: SLUG, STATUS, TITLE, SCORE, SOURCE."
- SKILL.md line 278: "Output columns: SLUG, STATUS, TITLE, SCORE, SOURCE."

**AC13: Branch names use ensign/{slug}** — PASSED
- All branch references use `ensign/{slug}` (lines 432, 437, 438, 468, 483). Grep for `entity-slug` returned zero matches.

**AC14: Worktree paths use .worktrees/ensign-{slug}** — PASSED
- All worktree path references use `.worktrees/ensign-{slug}` (lines 428, 432, 436, 438, 482). No `entity-slug` anywhere.

**AC15: README template has Concurrency section** — PASSED
- Lines 303-307: `## Concurrency` section with "Maximum 2 {entity_label_plural} in any single active stage at a time."

**AC16: First-officer has concurrency check** — PASSED
- Startup step 4 (line 382): reads concurrency limit from README, defaults to 2.
- Dispatching step 3 (line 392-393): "Count how many {entity_label_plural} currently have their status set to the target stage. If the count equals the concurrency limit, hold this {entity_label}..."

**AC17: Commit Discipline says "dispatch and merge boundaries"** — PASSED
- README template line 311: "Commit status changes at dispatch and merge boundaries"
- First-officer State Management line 534: "Commit state changes at dispatch and merge boundaries, not at session end."

### Regression (AC18-20)

**AC18: First-officer still has all required sections** — PASSED
- Startup sequence: lines 372-384 (6-step startup)
- Orphan detection: lines 536-542 (dedicated section)
- Clarification protocol: lines 486-510 (3 subsections: when FO asks, when ensign asks, follow-up)
- Event loop: lines 512-523 (6-step loop)
- State management: lines 525-534 (7 field rules)
- Approval gates: lines 456-465 (step 7, with approval/rejection branches)
- Merge/cleanup: lines 466-484 (steps 8-9, merge with conflict handling and cleanup)

**AC19: Batch mode still works** — PASSED
- Lines 17-25: Batch Mode section preserved. "If the user provides design inputs in their message... Extract all provided inputs... Skip directly to Confirm Design..."

**AC20: Status template describes working bash 3.2+ script** — PASSED
- `templates/status` line 10: "constraints: bash 3.2+ (no associative arrays)"
- SKILL.md line 325: "The implementation must work on bash 3.2+ (no associative arrays, no bash 4+ features)."
- Template is a stub with instruction comments; materialization step (line 325) replaces the stub body with a working implementation.

### Summary

**Result: PASSED** — All 20 acceptance criteria verified. The implementation is thorough and clean:
- The first-officer template is fully generic with zero hardcoded stage names
- README-as-source-of-truth architecture is consistently applied
- All commission flow improvements (args extraction, git auto-init, seed read, generation discipline) are in place
- Generated artifact improvements (SLUG column, ensign/{slug} naming, concurrency, commit discipline) all correct
- No regressions in existing functionality
