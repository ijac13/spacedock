---
id: 151
title: "claude-team build: entity path translation drops workflow_dir subpath"
status: backlog
source: "FO dry-run of helper for #148 implementation dispatch, 2026-04-14 — exposed a path-mangling bug"
started:
completed:
verdict:
score: 0.70
worktree:
issue:
pr:
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
