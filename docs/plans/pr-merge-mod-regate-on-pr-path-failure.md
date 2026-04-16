---
id: 163
title: "pr-merge mod: PR-path failure must re-gate instead of auto-falling back to local merge"
status: backlog
source: "Captain + FO review on 2026-04-16 during task #142 — approved PR path hit a rebase conflict and still landed through local merge"
started:
completed:
verdict:
score: 0.64
worktree:
issue:
pr:
---

The current `pr-merge` hook says that after the captain approves push/PR creation, the FO should push `main`, rebase the worktree branch onto `main`, push the branch, and create a PR. If any of those steps fail, the mod currently says to “report to the captain and fall back to local merge.”

That fallback is too permissive. Approval for “push it” is approval for the PR path, not blanket approval for a local merge. If the PR path fails because of a rebase conflict, auth problem, missing `gh`, or PR-creation error, the FO should stop and re-gate with explicit choices instead of continuing to merge locally.

## Concrete failure seen in #142

Task `142` hit exactly this problem on 2026-04-16:

- the captain approved the PR summary with `push it`
- `git push origin main` succeeded
- `git rebase main` on the worktree branch failed with a content conflict in the entity file
- the current hook text allowed a fallback to local merge
- the FO completed a local merge and terminalized the entity without a fresh captain decision on that fallback path

The rebase conflict itself was legitimate: `main` had the FO-owned `### Feedback Cycles` update while the worktree branch had implementation and validation stage reports in the same tail region of the task file. A direct merge also conflicted; it only completed after manual resolution. The bug is not “rebase failed.” The bug is that PR-path failure crossed the gate into local-merge authority.

## Desired direction

Tighten the `pr-merge` merge hook contract so PR-path failure re-gates instead of auto-falling back:

1. Captain approves draft PR summary.
2. FO attempts the PR path (`push main`, `rebase`, `push branch`, `gh pr create`).
3. If any of those steps fail, FO reports the failure and stops at a fresh gate.
4. Captain must explicitly choose one of:
   - resolve and continue PR path
   - local merge instead
   - abort / leave branch and worktree pending

The hook should no longer treat PR-path approval as implied approval for local merge.

## Related context

- Active sibling task: `#152` `pr-merge mod: detect CI failure on PR and route back to implementation`
- Active sibling task: `#158` `pr-merge hook: haiku-driven FO skips git rebase main step before pushing branch`
- This task is about captain approval boundaries and fallback semantics, not about rebase reliability itself
