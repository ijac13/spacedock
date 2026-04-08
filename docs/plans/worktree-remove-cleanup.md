---
id: 096
title: Document git worktree remove in cleanup references
status: validation
source: CL — FO used rm -rf instead of git worktree remove, leaving stale tracking entries
started: 2026-04-07T21:37:58Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-worktree-remove-cleanup
issue: "#45"
pr:
---

# Document git worktree remove in cleanup references

The shared core's "Merge and Cleanup" section says "Remove the worktree" but doesn't specify `git worktree remove`. An FO used `rm -rf`, leaving stale entries in git's worktree tracking.

## Acceptance Criteria

1. `references/first-officer-shared-core.md` "Merge and Cleanup" section explicitly says `git worktree remove {path}` and `git branch -d {branch}`
2. `references/code-project-guardrails.md` "Git and Worktrees" section includes a rule against filesystem deletion for worktrees
3. All existing tests still pass

## Stage Report

1. DONE — `references/first-officer-shared-core.md` line 139: replaced "Remove the worktree and delete the temporary branch" with explicit `git worktree remove {path}` and `git branch -d {branch}` commands.
2. DONE — `references/code-project-guardrails.md` line 11: added rule "Remove worktrees with `git worktree remove`, not filesystem deletion (`rm -rf`). Filesystem deletion leaves stale tracking entries in git."
3. DONE — 84 tests passed (0 failures). Ran via `uv run --with pytest pytest tests/ --ignore=tests/fixtures`.

## Stage Report — validation

1. DONE — AC1 verified: `references/first-officer-shared-core.md` line 139, "Merge and Cleanup" step 6 reads: "Remove the worktree with `git worktree remove {path}` and delete the temporary branch with `git branch -d {branch}` after successful merge or deliberate discard." Both commands are explicitly specified.
2. DONE — AC2 verified: `references/code-project-guardrails.md` line 11, "Git and Worktrees" section includes: "Remove worktrees with `git worktree remove`, not filesystem deletion (`rm -rf`). Filesystem deletion leaves stale tracking entries in git."
3. DONE — AC3 verified: independently ran `uv run --with pytest pytest tests/ --ignore=tests/fixtures` — 84 passed, 0 failures, 16 warnings (all PytestCollectionWarning, not test failures).
4. PASSED — All 3 acceptance criteria met. Changes are minimal, correctly scoped to the two reference files, and do not break existing tests.
