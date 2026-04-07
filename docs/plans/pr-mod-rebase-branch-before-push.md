---
id: 092
title: PR merge mod should rebase branch on main before pushing
status: ideation
source: "CL — observed in PR #38 (091), follow-up to PR #37 (090)"
started: 2026-04-07T00:00:00Z
completed:
verdict:
score: 0.65
worktree:
issue:
pr:
---

# PR merge mod should rebase branch on main before pushing

Follow-up to task 090 (PR #37). The mod now pushes main before the branch, but the branch itself may be based on a stale main — causing conflicts even though origin/main is up to date.

This happens when another PR merges on GitHub during the same session, and the FO pulls those changes into local main. The worktree branch was forked from an earlier main, so it diverges from the now-updated origin/main.

Observed in PR #38 (091): PR #37 (090) merged on GitHub mid-session. Local main was rebased to include it, but the 091 branch was still based on pre-merge main. After pushing main and the branch, GitHub marked PR #38 as conflicting.

## The fix

Add a rebase step to the merge hook's "On approval" block, between pushing main and pushing the branch:

1. `git push origin main` (already there from 090)
2. `git rebase main` on the worktree branch ← **new**
3. `git push origin {branch}` (already there)

The rebase is a no-op when the branch is already up to date with main.
