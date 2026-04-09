---
id: 111
title: Status script reports worktree branches as missing when they exist
status: ideation
source: FO boot anomaly — 2026-04-09
started: 2026-04-09T22:00:38Z
completed:
verdict:
score:
worktree:
issue:
pr:
---

The `status --boot` ORPHANS section reports `BRANCH_EXISTS: no` for entities whose branches actually exist both as local branches and as git worktrees.

Observed during boot:
- 088 restore-initial-prompt: `BRANCH_EXISTS: no`, but `git branch --list` shows `spacedock-ensign/restore-initial-prompt` and `git worktree list` confirms the worktree is linked to that branch.
- 058 terminology-experiment: `BRANCH_EXISTS: no`, but `git branch --list` shows `ensign/terminology-exp` and `git worktree list` confirms it.

The branch detection logic in `skills/commission/bin/status` likely checks for the branch in a way that misses worktree-linked branches (e.g., checking `.git/refs/heads/` directly instead of using `git branch --list`, or a path-construction mismatch between the worktree field and the actual branch name).
