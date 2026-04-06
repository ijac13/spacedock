---
id: 090
title: PR merge mod should push main before creating PRs
status: ideation
source: CL — observed PR conflicts from unpushed main state commits
started: 2026-04-06T00:00:00Z
completed:
verdict:
score: 0.65
worktree:
issue:
pr:
---

# PR merge mod should push main before creating PRs

The FO commits entity state changes (status, worktree, pr fields) to local main throughout a session. The `pr-merge` mod's merge hook pushes the worktree branch and creates a PR, but doesn't ensure origin/main is up to date first. This causes PR conflicts when the branch was created from an earlier main and both sides modified entity files.

Observed in PRs #35 and #36 — both had conflicts in `docs/plans/` entity files because origin/main was behind local main's state commits.

The fix: the merge hook should `git push origin main` before pushing the branch. This ensures origin/main has all the frontmatter state changes, so the PR branch's rebase/merge is clean.
