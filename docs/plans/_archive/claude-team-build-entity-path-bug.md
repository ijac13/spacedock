---
id: 151
title: "claude-team build: entity path translation drops workflow_dir subpath"
status: done
source: "FO dry-run of helper for #148 implementation dispatch, 2026-04-14 — exposed a path-mangling bug"
started: 2026-04-14T21:03:21Z
completed: 2026-04-14T21:56:39Z
verdict: PASSED
score: 0.70
worktree: 
issue:
pr: #93
mod-block: 
---

## Problem

`skills/commission/bin/claude-team build` produces a dispatch-ready JSON whose `prompt` field contains an `Read the entity file at {path}` instruction. For worktree stages, the helper translates the main-branch `entity_path` input into a worktree-local path — but it drops the relative subpath between `workflow_dir` and the entity file.

**Reproduction:**

Input:
```json
{
  "schema_version": 1,
  "entity_path": "/abs/repo/docs/plans/live-e2e-pytest-harness.md",
  "workflow_dir": "/abs/repo/docs/plans",
  "stage": "implementation",
  "team_name": "some-team",
  "bare_mode": false,
  ...
}
```

Output prompt (relevant line):
```
Read the entity file at /abs/repo/.worktrees/{worker_key}-{slug}/live-e2e-pytest-harness.md
```

Expected output:
```
Read the entity file at /abs/repo/.worktrees/{worker_key}-{slug}/docs/plans/live-e2e-pytest-harness.md
```

The helper joins the worktree root directly with the entity filename, ignoring the `docs/plans/` relative component.

## Why it matters

When the dispatched ensign tries to follow that path, it reads a non-existent file and falls back to exploration to locate the real entity file. This wastes tokens and violates the "tell the ensign exactly where to look" contract of the structured dispatch. It also makes the helper output non-verbatim-forwardable in any serious sense: the FO would need to paper over the wrong path, which is exactly what the helper is meant to eliminate.

The bug is silent in test fixtures because those fixtures put the pipeline directory at the workflow-dir root (flat layout, relative path is empty). It only surfaces when the workflow directory is nested under the repo, as in `docs/plans/` in the real Spacedock repo.

## Root cause hypothesis

The helper's prompt-assembly logic computes the worktree-local entity path as `{worktree_root}/{basename(entity_path)}` instead of `{worktree_root}/{relative_path_from_repo_root_to_entity_path}`.

Find the prompt-assembly code in `skills/commission/bin/claude-team` (the `build` subcommand's prompt construction — look for the "Read the entity file at" string literal or for `entity_path` translation logic).

## Fix

Compute the worktree-local entity path as:

```python
git_root = find_git_root(entity_path)     # or passed in
rel = os.path.relpath(entity_path, git_root)
worktree_entity_path = os.path.join(worktree_root, rel)
```

This preserves any subpath (`docs/plans/`, `missions/active/`, etc.) between the repo root and the entity file.

## Acceptance criteria

1. **AC-1: Nested workflow dir produces correct path.** Helper input with `entity_path = /repo/docs/plans/task.md` and `workflow_dir = /repo/docs/plans` produces a prompt whose entity-file-read line references `.../.worktrees/.../docs/plans/task.md`.
   - Test: `test_build_entity_path_nested_workflow_dir` (pytest, `tests/test_claude_team.py`)
2. **AC-2: Flat workflow dir (current fixture layout) still works.** Helper input with `entity_path = /fixture/pipeline/task.md` and `workflow_dir = /fixture/pipeline` still produces `.worktrees/.../task.md` (no regression for the test-fixture shape).
   - Test: extend the existing `TestBuildWorktreeStage` case to explicitly assert the path shape, not just the presence of the read-entity line.
3. **AC-3: Non-worktree stages unaffected.** Helper input for a non-worktree stage (e.g., `ideation`) preserves the main-branch entity path in the prompt (no translation).
   - Test: `test_build_entity_path_non_worktree` (pytest)
4. **AC-4: Static suite green.** `make test-static` passes with the two new tests added.

## Test plan

| Test | Harness | Expectation | Cost |
|------|---------|-------------|------|
| `test_build_entity_path_nested_workflow_dir` | pytest | Nested-dir input → worktree path preserves subpath | free |
| `test_build_entity_path_non_worktree` | pytest | Ideation stage input → main path unchanged | free |
| Regression in `TestBuildWorktreeStage` | pytest | Existing case updated to assert exact path shape | free |
| `make test-static` | existing | All pass, count +2 or +3 | free |

No E2E needed; the bug is entirely in the helper's path-assembly function and fully covered by unit tests.

## Scope

**In:**
- Fix prompt-assembly entity-path translation in `skills/commission/bin/claude-team`'s `build` subcommand
- Fix the 63-char `name` length limit (Rule 7) — the Agent tool accepts longer names (e.g., 71 chars observed in `spacedock-ensign-fo-enforce-mod-blocking-at-runtime-implementation-cycle2`). Raise to a number that actually reflects filesystem / agent-tool constraints (e.g., 200) so real entity slugs don't trigger false refusals.
- Add pytest cases for both fixes
- Tighten existing worktree test to assert exact path (not just substring presence)

**Out of scope:**
- Other helper bugs (if any surface during investigation, file separately)
- Break-glass template — it uses `{entity_file_path}` placeholder which is FO-supplied; not affected
- Any Codex-side adapter work

## Additional AC (name length)

5. **AC-5: Longer entity slugs don't trip the length limit.** Helper input with a derived name of 71 chars (e.g., slug `fo-enforce-mod-blocking-at-runtime`, stage `implementation`) succeeds and emits a valid dispatch JSON.
   - Test: `test_build_long_derived_name` (pytest, `tests/test_claude_team.py`)

## Fast-track rationale

The bug is small, well-understood, and blocks clean dispatch for #148 (pytest migration) and any other task in the `docs/plans/` workflow shape. CL directive: skip ideation gate, go straight to implementation.

## Discovery history

- 2026-04-14: FO dry-run for #148 implementation dispatch exposed entity-path translation bug
- 2026-04-14: FO dry-run for #114 cycle 4 dispatch exposed 63-char name limit as over-restrictive (real entity slug + stage suffix exceeds the rule)

## Stage Report

### Summary
Fixed both bugs in `skills/commission/bin/claude-team` `build` subcommand:
- **Entity path translation** now computes `os.path.relpath(entity_path, git_root)` and joins onto the worktree root, preserving nested workflow subpaths like `docs/plans/`. Before: `{worktree_root}/{basename(entity_path)}`. After: `{worktree_root}/{rel_path_from_repo_root}`.
- **Name length limit** raised from 63 to 200 via the `NAME_MAX_LEN` constant. The rule-7 error message now interpolates the constant rather than hardcoding `63`.

### Checklist
1. **Read entity file for full spec** — DONE
2. **Fix path computation in prompt assembly** — DONE. `skills/commission/bin/claude-team:194-196` now uses `os.path.relpath(entity_path, git_root)`.
3. **Raise Rule 7 limit to 200** — DONE. `skills/commission/bin/claude-team:36` updated `NAME_MAX_LEN = 200`; error message at line 165 uses the constant.
4. **Dry-run verifies corrected subpath in output prompt** — DONE. Non-worktree dry-run against `docs/plans/claude-team-build-entity-path-bug.md` emits the untranslated main-branch path. Nested-workflow translation is covered end-to-end by `test_build_entity_path_nested_workflow_dir`, which constructs a `docs/plans/` fixture and asserts the exact worktree-local path.
5. **71-char derived name emits valid JSON** — DONE. `test_build_long_derived_name` asserts a 71-char derived name builds successfully.
6. **Pytest tests for all 5 ACs in tests/test_claude_team.py** — DONE:
   - `TestBuildEntityPathTranslation::test_build_entity_path_nested_workflow_dir` (AC-1)
   - `TestBuildWorktreeStage::test_build_worktree_stage_dispatch` extended to assert exact worktree path (AC-2)
   - `TestBuildEntityPathTranslation::test_build_entity_path_non_worktree` (AC-3)
   - `TestBuildValidationRules::test_build_long_derived_name` (AC-5)
   - `TestBuildValidationRules::test_build_very_long_name_still_rejected` (sanity bound)
   - `test_build_validation_rule_7_name_too_long` updated to use 220-char slug and assert "exceeds 200 characters" message.
7. **make test-static green** — DONE. 271 passed, 10 subtests passed (baseline 267; +4 new test functions, AC-2 extension within existing test).
8. **Commit on the branch** — DONE.

## Stage Report — validation

### Summary
Validated both fixes against all 5 acceptance criteria. Code change at `skills/commission/bin/claude-team:194-196` correctly computes `os.path.relpath(entity_path, git_root)` and joins it onto the worktree root, preserving nested workflow subpaths. `NAME_MAX_LEN` raised to 200 at line 36 and referenced in the Rule 7 error message at line 165. Static suite is green at 271 passed / 10 subtests passed; the six targeted tests (AC-1/2/3/5 + sanity bounds) pass individually. Real dry-runs against the live `docs/plans/` entities for `fo-enforce-mod-blocking-at-runtime` (implementation, worktree stage) and `claude-team-build-entity-path-bug` (ideation, non-worktree stage) match the expected prompt shapes exactly. Recommendation: **PASSED**.

### Checklist
1. **Read the entity file for the 5 ACs** — DONE. ACs 1–5 and the test-plan table at lines 70–107 inform what follows.
2. **Run `make test-static` — report pass/fail count; note regressions from baseline** — DONE. Result: `271 passed, 10 subtests passed in 70.26s`. Baseline per implementation stage report was 267 passed; delta +4 matches the 4 new test functions (`test_build_entity_path_nested_workflow_dir`, `test_build_entity_path_non_worktree`, `test_build_long_derived_name`, `test_build_very_long_name_still_rejected`). No regressions.
3. **Verify AC-1: Nested workflow dir produces correct path via a real `claude-team build` dry-run** — DONE. Input: `entity_path=/Users/clkao/git/spacedock/docs/plans/fo-enforce-mod-blocking-at-runtime.md`, `workflow_dir=/Users/clkao/git/spacedock/docs/plans`, `stage=implementation`, team mode. Output prompt's entity-read line: `Read the entity file at /Users/clkao/git/spacedock/.worktrees/spacedock-ensign-fo-enforce-mod-blocking-at-runtime/docs/plans/fo-enforce-mod-blocking-at-runtime.md for the full spec.` — the `docs/plans/` subpath is preserved as required. `test_build_entity_path_nested_workflow_dir` also passes in the pytest harness.
4. **Verify AC-2: Flat workflow dir still works** — DONE. `test_build_worktree_stage_dispatch` (at `tests/test_claude_team.py:709`) was extended (lines 728–733) to assert the exact worktree path `{tmp_path}/.worktrees/spacedock-ensign-wt-task/workflow/wt-task.md`. In this fixture the workflow dir is one level deep (`tmp_path/workflow`), so the relpath logic still produces the right shape — `workflow/wt-task.md` is preserved, no spurious subpath collapse. Test passes.
5. **Verify AC-3: Non-worktree stages preserve the main-path (no translation)** — DONE. Real dry-run with `stage=ideation` against `docs/plans/claude-team-build-entity-path-bug.md` emits: `Read the entity file at /Users/clkao/git/spacedock/docs/plans/claude-team-build-entity-path-bug.md for the current spec.` — no `.worktrees` substring anywhere in the prompt. `test_build_entity_path_non_worktree` passes and explicitly asserts `".worktrees" not in out["prompt"]`.
6. **Verify AC-4: Static suite green** — DONE. Covered by checklist item 2 — 271 passed, 0 failed, 0 errored.
7. **Verify AC-5: Longer derived name (e.g., 71 chars) succeeds — no exit 1 from validation rule** — DONE. Real dry-run with the #114 slug (`fo-enforce-mod-blocking-at-runtime`, stage `implementation`) yields `name=spacedock-ensign-fo-enforce-mod-blocking-at-runtime-implementation` (66 chars, well above the old 63-char cap) with exit code 0 and a valid JSON dispatch. The pytest `test_build_long_derived_name` exercises a 71-char name specifically and asserts success; `test_build_very_long_name_still_rejected` confirms the new 200-char cap still rejects pathological inputs. Both pass.
8. **PASSED/REJECTED recommendation with Assessment line** — DONE. See below.

### Assessment

8 done, 0 skipped, 0 failed.

Recommendation: **PASSED**. All 5 acceptance criteria verified with evidence from both targeted pytest runs and real `claude-team build` dry-runs against live repo entities. Static suite is green with +4 net tests and no regressions. The implementation matches the fix specified in the entity (lines 60–68): `os.path.relpath(entity_path, git_root)` joined onto the worktree root. `NAME_MAX_LEN` is now a named constant referenced in both the guard and the error message, matching the scope item at lines 94–95.

