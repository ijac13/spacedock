---
title: Refit Command
status: validation
source: commission seed
started: 2026-03-22T00:00:00Z
worktree: .worktrees/pilot-refit-command
completed:
verdict:
score: 15
---

## Problem

As Spacedock evolves, pipelines commissioned with older versions fall behind. The status script might gain features, the README template might improve, the first-officer agent prompt might get smarter. Users need a way to upgrade their pipelines without losing their customizations — custom stages, modified scoring rubrics, additional schema fields. Manual upgrades are error-prone and tedious.

Today, the commission skill (`skills/commission/SKILL.md`) generates three scaffolding files that are stamped with `commissioned-by: spacedock@{version}`:

1. **`{dir}/README.md`** — pipeline schema, stage definitions, scoring rubric, entity template. Heavily customized by users (stages, fields, quality criteria are all domain-specific).
2. **`{dir}/status`** — bash view script. Purely mechanical — extracts YAML frontmatter fields and prints a table. Users rarely modify it beyond tweaking column widths.
3. **`{project_root}/.claude/agents/first-officer.md`** — agent prompt with dispatch logic, worktree isolation, orphan detection. Contains pipeline-specific values (mission, stages, approval gates, paths) woven into a standard structural template.

Entity files (`{dir}/*.md` except README) are user data and must never be touched by refit.

The version stamp (implemented in `record-spacedock-version-used-for-the-commission`) is the prerequisite that makes intelligent upgrading possible. Without it, refit cannot know what the original scaffolding looked like.

## Proposed Approach

### Skill definition

A new `/spacedock refit` skill at `skills/refit/SKILL.md`, registered in `plugin.json`:

- **Trigger phrases:** "refit a pipeline", "upgrade a pipeline", "update pipeline scaffolding"
- **Input:** Pipeline directory path (required). The skill detects the pipeline by looking for a README.md with a `commissioned-by: spacedock@` stamp.
- **Output:** Updated scaffolding files, with a summary of what changed and what was left alone.

### Phase 1: Discovery

1. Read `{dir}/README.md` and extract the version stamp from `<!-- commissioned-by: spacedock@X.Y.Z -->`.
2. Read `{dir}/status` and extract the version stamp from `# commissioned-by: spacedock@X.Y.Z`.
3. Read `{project_root}/.claude/agents/first-officer.md` and extract from YAML frontmatter `commissioned-by: spacedock@X.Y.Z`.
4. Read `.claude-plugin/plugin.json` to get the current Spacedock version.
5. If all stamps match the current version: "Pipeline is already up to date." Exit.
6. If no stamps found: enter degraded mode (see "No Version Stamp" below).

### Phase 2: Classify files by upgrade strategy

Each scaffolding file gets one of three upgrade strategies:

| File | Strategy | Rationale |
|------|----------|-----------|
| `status` | **Replace** | Mechanical script. No user-meaningful customizations. The only pipeline-specific content is the stage names in `STAGE_ORDER` / `stage_order()` and the `valid status values` comment — both are derived from the README, which refit reads. |
| `first-officer.md` | **Regenerate** | The template structure (dispatch logic, worktree isolation, orphan detection, event loop) is standard. The pipeline-specific values (mission, stages, approval gates, paths) are extracted from the existing README. Regenerating from the current template with those values produces correct output. |
| `README.md` | **Show diff** | Users customize stages, schema fields, quality criteria, scoring rubric. A three-way merge is too fragile for markdown prose. Instead, show the user what changed in the template and let them decide. |

### Phase 3: Execute upgrades

#### Status script (replace)

1. Extract pipeline-specific values from the current README: stage names and their order.
2. Generate a new status script using the current template from SKILL.md, filling in the extracted values.
3. Preserve the executable bit.
4. Replace the file.

#### First-officer agent (regenerate)

1. Extract pipeline-specific values from the current README and existing first-officer:
   - Mission (from README title / first-officer heading)
   - Pipeline directory (from the `Pipeline Path` section)
   - Stage list (from README stage sections)
   - Approval gates (from README stage sections, checking `Human approval: Yes`)
   - Team name (from the directory basename)
2. Generate a new first-officer using the current template from SKILL.md with extracted values.
3. Replace the file.

**Edge case:** If the user added custom sections to the first-officer (e.g., extra dispatch rules, custom state management), those additions are lost. Mitigate by:
- Showing a diff of the old vs new first-officer before replacing.
- Asking CL for confirmation if the old file differs structurally from what the template would have produced at the stamped version.

#### README (show diff)

1. Show the user what sections changed in the README template between their commissioned version and the current version. Since the commission skill is a prompt template (not versioned code), the practical approach is:
   - Generate what the current template *would* produce for this pipeline (using extracted values).
   - Diff that against the user's current README.
   - Present the diff to CL, highlighting which differences are likely "template improvements" vs "user customizations."
2. CL decides what to adopt. Refit does not auto-modify the README.

### Phase 4: Finalize

1. Update all version stamps to the current version.
2. Show a summary of changes made.
3. Suggest committing: `git commit -m "refit: upgrade pipeline scaffolding to spacedock@X.Y.Z"`.

### No Version Stamp (degraded mode)

For pipelines commissioned before version stamping was implemented:

1. Inform the user that no version stamp was found, so the original baseline cannot be determined.
2. Offer two options:
   - **Stamp only:** Add version stamps to existing files without changing anything else. This establishes a baseline for future refits.
   - **Full refit with review:** Generate what the current templates would produce and show a full diff for every scaffolding file. CL reviews and approves each change manually.
3. Never auto-replace files without a version stamp — the risk of overwriting customizations is too high.

### Dependency: version recording

This feature depends on `record-spacedock-version-used-for-the-commission` (now PASSED). All new pipelines get version stamps. The degraded mode handles pre-stamp pipelines.

### Dependency: relative paths

The `relative-paths-in-generated-configs` entity is related but not blocking. Refit should work with both absolute and relative paths. If the relative-paths change lands first, refit regeneration simply uses relative paths in output. If it hasn't landed, refit produces absolute paths (matching current behavior).

## Acceptance Criteria

- [ ] Design covers: detection of commissioned version, per-file upgrade strategy, conflict resolution
- [ ] Defines which files are "replace" vs "regenerate" vs "show diff for user review"
- [ ] Handles the case where no version stamp exists (degraded mode with stamp-only option)
- [ ] Does not modify entity files
- [ ] Skill definition is drafted (trigger phrases, inputs, outputs, interactive flow)
- [ ] Addresses the edge case of user-customized first-officer files
- [ ] Specifies how pipeline-specific values are extracted from existing files for regeneration

## Open Questions (Resolved)

- **Q: Should refit support partial upgrades (e.g., only upgrade the status script)?** A: Not in v1. The skill upgrades all scaffolding files in one pass. Users can decline README changes interactively, and they're shown a diff for first-officer changes before replacement. Partial upgrade adds complexity without clear benefit — if you're refitting, you want everything current.

- **Q: Should refit create a backup of replaced files?** A: No. The pipeline is in a git repo (commission ensures this). The user can `git diff` or `git checkout` to recover. Adding backup files clutters the directory.

- **Q: How does refit know what the original template looked like for a given version?** A: It doesn't need to. The three-way diff idea (original seed proposal) is over-engineered for this context. Since the commission skill is a prompt template (not versioned code with tagged releases), there's no practical way to reconstruct "what version 0.1.0 would have generated." Instead, refit uses a simpler strategy: regenerate from the *current* template with *extracted* pipeline-specific values, and classify files by how safe they are to replace. This avoids the need for template versioning entirely.

- **Q: What if the user renamed the first-officer agent file?** A: Refit looks for `{project_root}/.claude/agents/first-officer.md` (the canonical location). If it's not there, skip agent upgrade and warn the user.

- **Q: Should refit handle stage additions/removals in the README?** A: No. Stage changes are user customizations. Refit upgrades scaffolding infrastructure (script logic, agent dispatch patterns), not pipeline semantics. If the user added stages, those will appear in the regenerated status script and first-officer because refit extracts stages from the current README.

## Implementation Summary

Created `skills/refit/SKILL.md` — the `/spacedock refit` skill definition. The skill follows the four-phase structure from the design:

- **Phase 1 (Discovery):** Reads all three scaffolding files, extracts version stamps, compares against current Spacedock version from plugin.json.
- **Phase 2 (Classification):** Presents the per-file upgrade strategy (status=replace, first-officer=regenerate with diff review, README=show diff only) and gets CL's confirmation.
- **Phase 3 (Execution):** Extracts pipeline-specific values from existing README, generates updated files using the commission templates, shows diffs before all replacements, and requires explicit approval for first-officer and README changes.
- **Phase 4 (Finalize):** Updates version stamps, shows summary, suggests commit.
- **Degraded mode:** Offers stamp-only or full-refit-with-review when no version stamps are found.

Skill registration: Skills are auto-discovered by convention (`skills/*/SKILL.md`), matching the existing commission skill pattern. No changes to `plugin.json` needed.

Files created:
- `skills/refit/SKILL.md` — the skill prompt (complete with embedded status script template for regeneration)

## Scoring Breakdown

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Edge | 3 | Non-destructive upgrades are table stakes for mature tools |
| Fitness | 3 | Important for longevity, not urgent for v0 |
| Parsimony | 2 | Three-way diff is inherently complex |
| Testability | 3 | Can test with known before/after states |
| Novelty | 4 | Applying three-way merge to agent prompt templates is interesting |

## Validation Report

Validated against acceptance criteria by reading the implemented skill at `skills/refit/SKILL.md` (252 lines) and cross-referencing against the design in this entity file.

### Criterion 1: Design covers detection of commissioned version, per-file upgrade strategy, conflict resolution

**PASSED.** Phase 1 (Discovery) in the skill covers version stamp extraction from all three files:
- README: `<!-- commissioned-by: spacedock@X.Y.Z -->` (SKILL.md line 31)
- Status: `# commissioned-by: spacedock@X.Y.Z` (line 32)
- First-officer: YAML frontmatter `commissioned-by: spacedock@X.Y.Z` (line 33)
- Current version from `plugin.json` (line 39)

Per-file strategy is in Phase 2 (lines 49-71) with the classification table. Conflict resolution: README uses show-diff-only (line 57, "Too risky to auto-replace"), first-officer requires explicit y/n confirmation (line 173), status shows diff before replacing (line 146-151).

### Criterion 2: Defines which files are "replace" vs "regenerate" vs "show diff for user review"

**PASSED.** Phase 2 classification table (lines 53-57):
- `status` = Replace
- `first-officer.md` = Regenerate (with diff review)
- `README.md` = Show diff (manual review)

This matches the design exactly. The skill presents this table to CL and waits for confirmation before proceeding (line 71).

### Criterion 3: Handles the case where no version stamp exists (degraded mode with stamp-only option)

**PASSED.** Degraded Mode section (lines 219-243) covers:
- Detection: Phase 1 Step 4 routes to degraded mode when no stamps found (line 44)
- Two options presented: stamp-only (line 232-238) and full refit with review (line 240-242)
- Stamp-only adds stamps without modifying content
- Full refit shows diff for every file and requires explicit CL approval per file
- Safety rule: "Never auto-replace without a version stamp" (line 249)

### Criterion 4: Does not modify entity files

**PASSED.** Multiple explicit safeguards:
- Opening paragraph: "Entity files are never touched — only the scaffolding infrastructure: the status script, the first-officer agent, and the README." (line 11)
- Safety Rules section: "Never modify entity files — only scaffolding (status, first-officer, README)." (line 248)
- The skill operates exclusively on the three named scaffolding files throughout all phases.

### Criterion 5: Skill definition is drafted (trigger phrases, inputs, outputs, interactive flow)

**PASSED.** The YAML frontmatter (lines 3-7) provides:
- `name: refit`
- `description:` includes trigger phrases: "refit a pipeline", "upgrade a pipeline", "update pipeline scaffolding"
- `user-invocable: true`

Input: Pipeline directory path, requested in Phase 1 Step 1 (line 22). Output: Updated scaffolding files with summary (Phase 4, lines 198-216). Interactive flow: four sequential phases with explicit CL confirmation gates at Phase 2 (line 71), Phase 3b first-officer replacement (line 173), and Phase 3c README review (lines 188-193).

### Criterion 6: Addresses the edge case of user-customized first-officer files

**PASSED.** Phase 3b (lines 175-178) includes an explicit warning mechanism:
> "Warning: The existing first-officer has custom sections that aren't in the standard template. These will be lost if you replace it: {list of custom section headings}"

The skill shows a diff before replacement (line 166-168) and requires explicit y/n confirmation (line 173). The design's open question about renamed agent files is also addressed: refit looks at the canonical path and skips with a warning if not found (design line 129, implemented via "If a file doesn't exist, note it as missing and skip it" at SKILL.md line 35).

### Criterion 7: Specifies how pipeline-specific values are extracted from existing files for regeneration

**PASSED.** Phase 3 "Extract pipeline-specific values from README" section (lines 78-91) explicitly lists:
1. Mission — from `# {title}` heading (line 81)
2. Stages — from `## Stages` section, each `### \`{stage_name}\`` subsection (lines 82-85), including stage name, inputs, outputs, good, bad, and approval gate detection
3. Schema fields — from `## Schema` section's YAML block (line 86)
4. Entity description — from the first paragraph after H1 (line 87)
5. Pipeline absolute path — from existing first-officer's `## Pipeline Path` section (line 91)

Phase 3b (lines 155-162) further specifies the full list of values extracted for first-officer regeneration: mission, pipeline directory, stage list, approval gates, team name, stages as comma-separated list, first and last stage.

### Additional Observations

**Implementation summary accuracy:** The implementation summary (entity lines 133-146) claims the skill follows the four-phase structure — confirmed. It claims the status script template is embedded — confirmed (SKILL.md lines 101-143). It claims skills are auto-discovered by convention — this matches the commission skill pattern (both live under `skills/*/SKILL.md`), so no `plugin.json` changes needed. Verified `plugin.json` has no skills array.

**Design fidelity:** The skill faithfully implements all four phases from the design, including the "show diff before all replacements" approach (even for status script, which the design classified as "replace"). This is actually stricter than the design required — the skill always shows diffs, per its Safety Rules (line 250: "Always show diffs — even for 'replace' strategy files").

**No issues found.**

### Recommendation: PASSED

All seven acceptance criteria are met with specific evidence in the implementation. The skill is well-structured, follows the design faithfully, and includes appropriate safety guardrails.
