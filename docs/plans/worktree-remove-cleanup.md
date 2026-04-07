---
id: 096
title: Document git worktree remove in cleanup references
status: implementation
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
