---
id: 052
title: Replace "pipeline" with "workflow" where appropriate
status: implementation
source: CL
started: 2026-03-27T06:20:00Z
completed:
verdict:
score:
worktree: .worktrees/ensign-pipeline-to-workflow
---

Audit the codebase for uses of "pipeline" and replace with "workflow" where it refers to the user-facing concept. Spacedock creates workflows, not pipelines — the term "pipeline" is an implementation detail (the stages form a pipeline), but the user-facing abstraction is a "workflow."

Scope includes templates, skills, agent files, README, and generated output. Internal variable names and code comments that refer to the processing pipeline mechanism may be fine to keep.

## Audit

560 total occurrences of "pipeline" (case-insensitive) across 66 files. The bulk are in archived task files (docs/plans/_archive/) which are historical records and out of scope.

### Files Requiring Changes (user-facing, templates, agent definitions)

**1. `templates/first-officer.md` (6 occurrences) — CHANGE**
- Line 3: `description: Orchestrates the __MISSION__ pipeline` → `workflow`
- Line 6: `initialPrompt: "Report pipeline status."` → `workflow status`
- Line 11: `the first officer for the __MISSION__ pipeline` → `workflow`
- Line 76: `git commit -m "done: {slug} completed pipeline"` → `workflow`
- Line 92: `Report pipeline state ONCE` → `workflow state`
- Line 94: `## Pipeline Path` — **KEEP** (see Edge Cases)

**2. `templates/ensign.md` (3 occurrences) — CHANGE**
- Line 3: `description: Executes pipeline stage work for __MISSION__` → `workflow stage work`
- Line 10: `stage work for the __MISSION__ pipeline` → `workflow`
- Line 18: `Where the pipeline lives` → `Where the workflow lives`

**3. `templates/status` (2 occurrences) — CHANGE**
- Line 3: `ABOUTME: Pipeline status viewer` → `Workflow status viewer`
- Line 6: `# goal: Show one-line-per-{entity_label} pipeline overview` → `workflow overview`

**4. `AGENTS.md` (5 occurrences) — CHANGE**
- Line 3: `## Self-hosted pipeline boundaries` → `workflow boundaries`
- Line 5: `its own pipeline` → `its own workflow`
- Line 13: `pipeline artifacts` → `workflow artifacts`
- Line 14: `pipeline schema` → `workflow schema`
- Line 18: `pipeline config` / `pipeline infrastructure` → `workflow config` / `workflow infrastructure`

**5. `README.md` (1 occurrence) — CHANGE**
- Line 92: `Research pipelines` → `Research workflows`

**6. `.claude-plugin/plugin.json` (1 occurrence) — KEEP**
- `"pipeline"` in keywords array — keep for SEO/discoverability alongside `"workflow"`

**7. `scripts/release.sh` (6 occurrences) — CHANGE**
- Lines 69-74: `SELF_HOSTED_PIPELINE` variable and echo messages. The variable name is internal (keep or rename, low priority), but echo messages like `"REFIT: Self-hosted pipeline"` are user-facing → `workflow`
- Line 109: `pipeline state changes` in changelog prompt — this refers to internal state changes, could stay, but "workflow state changes" is more consistent

**8. `.claude/agents/first-officer.md` (live instance, 6 occurrences) — SKIP (updated via refit)**
This is a generated file. After templates are updated, running `/spacedock refit docs/plans` will regenerate it. Do NOT edit directly.

**9. `.claude/agents/ensign.md` (live instance, 3 occurrences) — SKIP (updated via refit)**
Same as above — generated from template.

**10. `docs/plans/status` (live instance, 6 occurrences) — SKIP (updated via refit)**
Same — generated from template. The ABOUTME and goal comments will be updated when refit runs.

**11. `skills/refit/SKILL.md` (1 occurrence) — KEEP as-is**
- Line 90: `from the ## Pipeline Path section` — this references a section heading in the first-officer template. See Edge Cases below.

### Test Files — Categorized

**12. `tests/test_status_script.py` (30 occurrences) — CHANGE (internal naming)**
- `run_status(pipeline_dir)` function parameter and `make_pipeline()` function name
- `PIPELINE_DIR` env var usage
- `test_empty_pipeline` test name
- `# Test Pipeline` in test data strings
- These are internal test names. Renaming to `workflow_dir` / `make_workflow` / etc. is straightforward but large. Could be done as follow-up.

**13. `tests/test-gate-guardrail.sh` (16 occurrences) — PARTIAL CHANGE**
- References to fixture directory `gated-pipeline` — see Edge Cases
- User-facing echo messages and comments → `workflow`
- `git commit -m "setup: gated pipeline fixture"` → `gated workflow fixture`

**14. `tests/fixtures/gated-pipeline/` (directory + 3 files) — EDGE CASE**
- Directory name, README title, status ABOUTME
- Renaming the directory means updating all references in test scripts

**15. `scripts/test-commission.sh` (25 occurrences) — CHANGE**
- `PIPELINE_DIR` variable → `WORKFLOW_DIR`
- User-facing check names and echo messages
- `multi-pipeline` entity name in test data — this is test fixture content, not user-facing

**16. `scripts/test-harness.md` (10 occurrences) — CHANGE**
- Documentation references to `Pipeline Path` section
- Test descriptions mentioning "pipeline"

**17. `scripts/test-checklist-e2e.sh` (6 occurrences) — CHANGE**
- Comments and echo messages: "Commission test pipeline" → "Commission test workflow"
- `git commit -m "commission: initial pipeline"` → `initial workflow`

### Archived Task Files — OUT OF SCOPE

All files under `docs/plans/_archive/` are historical records of completed/rejected tasks. These should not be retroactively edited — they document decisions made using the terminology of their time.

### Active Task Files — MOSTLY OUT OF SCOPE

- `docs/plans/pipeline-catalog.md` — uses "pipeline" extensively but as the entity's own subject matter (discussing pipeline export). The title itself is about pipelines. This is content, not terminology to mechanically rename.
- `docs/plans/github-issue-pr-workflow.md` — same situation, discusses pipeline integration as a concept
- `docs/plans/commission-compile-targets.md` — 1 occurrence, refers to "pipeline definition"
- `docs/plans/session-briefing-testflight-005.md` — historical context

### `## Pipeline Path` Section Header — SPECIAL CASE

The `## Pipeline Path` heading in `templates/first-officer.md` (line 94) is referenced by:
1. `skills/refit/SKILL.md` line 90 — refit extracts the workflow path from this section
2. `scripts/test-harness.md` — test checks for this section
3. Multiple archived task files discuss it

**Decision needed:** Rename to `## Workflow Path`? If yes, refit SKILL.md reference must also change. If no, leave as internal structural name. Leaning toward **rename** since this heading appears in the generated first-officer visible to users.

## Acceptance Criteria

1. All user-facing prose in `templates/first-officer.md` uses "workflow" instead of "pipeline" (except `## Pipeline Path` pending decision)
2. All user-facing prose in `templates/ensign.md` uses "workflow"
3. `templates/status` ABOUTME and goal use "workflow"
4. `AGENTS.md` uses "workflow" for the user-facing concept
5. `README.md` uses "workflow" consistently (the one remaining "pipelines" → "workflows")
6. `scripts/release.sh` user-facing echo messages use "workflow"
7. Test files updated to use "workflow" terminology in user-facing strings (variable names are lower priority)
8. `## Pipeline Path` section heading resolved (renamed or explicitly kept with rationale)
9. Archived task files (`docs/plans/_archive/`) are NOT modified
10. Generated live instances (`.claude/agents/`, `docs/plans/status`) are NOT directly edited — updated via refit after template changes
11. No functional behavior changes — this is a terminology-only rename

## Edge Cases

1. **`## Pipeline Path` section header** — Referenced by refit skill and tests. If renamed, all references must update atomically. See decision point above.

2. **`PIPELINE_DIR` env var in status script** — Used in `templates/status` (line with `os.environ.get('PIPELINE_DIR')`) and `tests/test_status_script.py`. This is an internal variable name. Renaming it is a functional change that requires updating tests. Could be done here or as follow-up.

3. **`gated-pipeline` fixture directory** — Renaming means updating `tests/test-gate-guardrail.sh` (16 references), plus the fixture files themselves. Low user impact since these are test internals.

4. **`plugin.json` keywords** — `"pipeline"` should stay alongside `"workflow"` for discoverability. Users searching for "pipeline" tools should still find Spacedock.

5. **Variable names in test scripts** — `PIPELINE_DIR`, `make_pipeline()`, `pipeline_dir` are internal. Renaming is cleaner but increases diff size. Could be split into a follow-up.

6. **`git commit -m "done: {slug} completed pipeline"` in first-officer template** — This is a generated commit message users will see in their git log. Should become "completed workflow".

7. **`docs/plans/pipeline-catalog.md` title** — This task IS about pipelines (the export/compile concept). The title should stay. However, if the broader project renames "pipeline" → "workflow", this task's title might need updating too. Depends on CL's intent.

8. **`release.sh` variable name `SELF_HOSTED_PIPELINE`** — Internal bash variable. Low priority to rename, but the echo messages around it are user-facing.

## Stage Report: ideation

- [x] Full audit of "pipeline" occurrences across the codebase with file counts
  560 occurrences across 66 files. Categorized by file with counts above.
- [x] Categorization: which stay "pipeline" vs become "workflow," with rationale
  Templates/AGENTS.md/README.md → change. Archived tasks → keep. Generated instances → skip (updated via refit). plugin.json keyword → keep for SEO.
- [x] List of files requiring changes
  7 source files to change directly, 5 test files, 3 to skip (refit-managed), ~45 archived files out of scope. See detailed list above.
- [x] Acceptance criteria written
  11 criteria covering templates, docs, scripts, test files, generated instances, and non-functional constraints.
- [x] Edge cases identified
  8 edge cases documented: Pipeline Path section header, PIPELINE_DIR env var, fixture directory naming, plugin.json keywords, test variable names, commit messages, pipeline-catalog task title, release.sh variables.

### Summary

Audited all 560 occurrences of "pipeline" across 66 files. The core changes affect 7 source files (3 templates, AGENTS.md, README.md, release.sh, and the Pipeline Path decision). Test files add ~5 more files with mostly variable/function name renames. The key design decision is whether to rename `## Pipeline Path` to `## Workflow Path` — leaning yes since it appears in generated output, but it requires coordinated updates to refit SKILL.md. Archived task files and generated live instances are explicitly out of scope.

## Stage Report: implementation

- [x] Templates updated: `templates/first-officer.md`, `templates/ensign.md`, `templates/status` — all user-facing "pipeline" to "workflow"
  All 11 occurrences across the three template files updated. Verified zero remaining "pipeline" in templates/.
- [x] Docs updated: `AGENTS.md`, `README.md` — "pipeline" to "workflow" in user-facing prose
  AGENTS.md: 5 occurrences (section heading, body text). README.md: 1 occurrence ("Research pipelines" to "Research workflows").
- [x] `scripts/release.sh` — user-facing echo messages updated
  Variable renamed `SELF_HOSTED_PIPELINE` to `SELF_HOSTED_WORKFLOW`, echo messages and changelog prompt updated. 4 changes total.
- [x] `## Pipeline Path` renamed to `## Workflow Path` in first-officer template, with `skills/refit/SKILL.md` reference updated atomically
  Both files updated in the same commit. Refit SKILL.md line 90 now reads `## Workflow Path`.
- [x] Test files updated where practical: `scripts/test-commission.sh`, `scripts/test-harness.md`, `scripts/test-checklist-e2e.sh`, `tests/test-gate-guardrail.sh`
  test-commission.sh: PIPELINE_DIR to WORKFLOW_DIR (all occurrences), Pipeline Path grep to Workflow Path. test-harness.md: 7 prose references updated. test-checklist-e2e.sh: ABOUTME, echo messages, commit messages, claude prompt updated. test-gate-guardrail.sh: ABOUTME, comments, commit message, claude prompt updated. Fixture directory name `gated-pipeline/` and entity name `multi-pipeline` preserved as internal identifiers. Fixture README and status ABOUTME updated.

### Summary

Renamed all user-facing "pipeline" to "workflow" across 13 files (3 templates, 2 docs, 1 script, 1 skill, 4 test files, 2 fixture files). The `## Pipeline Path` heading was renamed to `## Workflow Path` with a coordinated update to the refit SKILL.md reference. Internal identifiers like the `gated-pipeline` fixture directory name and `multi-pipeline` entity name were preserved. No functional changes — all modifications are terminology-only. Archived task files and generated live instances were not touched per the audit plan.
