---
title: Refit Command
status: implementation
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
