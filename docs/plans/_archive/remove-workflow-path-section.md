---
id: 053
title: Remove redundant Workflow Path section from first-officer template
status: done
source: CL
started: 2026-03-27T07:02:00Z
completed: 2026-03-27T07:22:00Z
verdict: PASSED
score:
worktree:
---

The `## Workflow Path` section in `templates/first-officer.md` is redundant. The workflow directory path (`__DIR__`) is already baked into every startup step, dispatch call, and status invocation throughout the generated first-officer agent. A dedicated section that restates "paths are relative to `docs/foo/`" adds nothing.

The only consumer of this section is `skills/refit/SKILL.md`, which reads it to find the workflow directory. Refit should extract the path from elsewhere (e.g., the README read in startup, or an argument) rather than requiring a dedicated section in the first-officer.

## What needs to change

1. Remove `## Workflow Path` from `templates/first-officer.md`
2. Update `skills/refit/SKILL.md` to extract the workflow path without depending on a `## Workflow Path` section
3. Update test expectations that check for this section

## Analysis

### Confirming redundancy

The `## Workflow Path` section (lines 94-98 of `templates/first-officer.md`) contains:

```
## Workflow Path

All paths are relative to the repo root: `__DIR__/`

The README at `__DIR__/README.md` is the single source of truth for schema, stages, and quality criteria.
```

The `__DIR__` placeholder appears in 6 other locations throughout the template — line 11 (identity statement), line 18 (read README), line 19 (run status), line 76 (archive), line 83 (scan for IDs), and line 96/98 (the section itself). Every instruction that touches a file already uses the fully-resolved `__DIR__` path. The section adds no information that isn't already present at every call site.

### How refit currently uses it

`skills/refit/SKILL.md` line 90 says:

> Also extract from the existing first-officer (if present):
> - **Workflow absolute path** — from the `## Workflow Path` section.

However, this extracted value is never actually used. In Phase 3, step 3b (line 109), refit uses `{dir}` — the path the user provided in Phase 1, Step 1 — as the workflow directory for regeneration. The `## Workflow Path` extraction is a vestigial instruction: it tells refit to read a value that it already has and never references again.

### Proposed fix for refit

Remove the `## Workflow Path` extraction instruction entirely (line 89-90). Refit already has `{dir}` from Phase 1. No alternative extraction method is needed — the user-provided path is the canonical source.

### Files that need updating

1. **`templates/first-officer.md`** — Remove the `## Workflow Path` section (lines 94-98).
2. **`skills/refit/SKILL.md`** — Remove lines 89-90 (the "Also extract from the existing first-officer" instruction that reads `## Workflow Path`).
3. **`scripts/test-commission.sh`** line 190 — Remove `"Workflow Path|workflow path|WORKFLOW PATH"` from the keyword grep loop.
4. **`scripts/test-harness.md`** line 138 — Remove the `Workflow Path` bullet from the first-officer verification checklist.

No other files reference `## Workflow Path` in a way that requires changes (archived task files are historical records, and `docs/plans/remove-workflow-path-section.md` is this task itself).

## Acceptance criteria

1. The `## Workflow Path` section is absent from `templates/first-officer.md`
2. `skills/refit/SKILL.md` does not reference `## Workflow Path` — and continues to use `{dir}` from Phase 1 for all path needs
3. `scripts/test-commission.sh` no longer checks for "Workflow Path" in the first-officer
4. `scripts/test-harness.md` no longer lists "Workflow Path" as a required section
5. All other first-officer content (identity line, startup, dispatch, state management) is unchanged
6. Running `scripts/test-commission.sh` passes (no regressions from keyword removal)

## Stage Report: ideation

- [x] Confirmed `## Workflow Path` is redundant (path already baked into every __DIR__ reference)
  `__DIR__` appears in 6 locations outside the section itself (lines 11, 18, 19, 76, 83 of the template)
- [x] How refit currently extracts the path from this section
  SKILL.md line 90 extracts it, but step 3b (line 109) uses `{dir}` from Phase 1 instead — the extracted value is never referenced
- [x] Proposed alternative for refit to find the workflow path
  No alternative needed — simply remove the extraction instruction; `{dir}` from Phase 1, Step 1 is already the canonical source
- [x] Test files and other references that need updating
  `scripts/test-commission.sh:190` (keyword grep) and `scripts/test-harness.md:138` (checklist bullet)
- [x] Acceptance criteria written
  Six criteria covering template, refit skill, both test files, no-regression, and preservation of other content

### Summary

The `## Workflow Path` section is confirmed redundant: every instruction in the first-officer already embeds the resolved `__DIR__` path. The refit skill extracts the path from this section but never uses the extracted value — it relies on `{dir}` from Phase 1 instead. The fix is a clean removal from four files with no need for an alternative extraction mechanism.

## Stage Report: implementation

- [x] `## Workflow Path` section removed from `templates/first-officer.md`
  Removed lines 94-98 (the section header, path statement, and README reference)
- [x] Refit skill no longer references `## Workflow Path`
  Removed the "Also extract from the existing first-officer" block (lines 89-90) from `skills/refit/SKILL.md`
- [x] `test-commission.sh` keyword check updated (Workflow Path removed)
  Removed `"Workflow Path|workflow path|WORKFLOW PATH"` from the keyword grep loop at line 190
- [x] `test-harness.md` checklist updated (Workflow Path removed)
  Removed the "Workflow Path" bullet from the first-officer verification checklist at line 138
- [x] All changes committed
  Commit 7daf633 on branch `ensign/remove-workflow-path`

### Summary

Removed the redundant `## Workflow Path` section from the first-officer template and all references to it across the codebase. Four files changed with a net removal of 10 lines. All other first-officer content (identity, startup, dispatch, state management, clarification) is untouched.

## Stage Report: validation

- [x] Test harness passes with no regressions (count should be lower than previous 61 since Workflow Path check was removed)
  `test-commission.sh` reports 60 passed, 0 failed (down from 61 — the removed Workflow Path keyword check accounts for the difference)
- [x] `## Workflow Path` absent from `templates/first-officer.md`
  `grep "Workflow Path" templates/first-officer.md` returns no matches; confirmed by full file read (93 lines, sections: Identity, Startup, Dispatch, Completion/Gates, Merge/Cleanup, State Management, Clarification)
- [x] `skills/refit/SKILL.md` does not reference Workflow Path
  `grep "Workflow Path" skills/refit/SKILL.md` returns no matches
- [x] `test-commission.sh` and `test-harness.md` no longer check for Workflow Path
  `grep "Workflow Path" scripts/test-commission.sh` and `grep "Workflow Path" scripts/test-harness.md` both return no matches
- [x] PASSED recommendation
  All six acceptance criteria verified; test suite passes with expected count reduction; all other first-officer content preserved intact

### Summary

All validation checks pass. The test harness runs clean at 60/60 (down from 61 due to the removed Workflow Path keyword check). Grep confirms "Workflow Path" is absent from all four target files. The first-officer template retains all other sections unchanged. Recommendation: PASSED.
