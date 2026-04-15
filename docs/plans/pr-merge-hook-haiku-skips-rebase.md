---
id: 158
title: "pr-merge hook: haiku-driven FO skips `git rebase main` step before pushing branch"
status: backlog
source: "CL + FO inspection on 2026-04-15 of PR #94 claude-live CI failure in test_rebase_branch_before_push"
started:
completed:
verdict:
score:
worktree:
issue:
pr:
---

Under haiku, the FO's pr-merge merge-hook execution compresses the "push main → rebase branch → push branch" sequence into "push main → push branch" — the `git rebase main` step is silently skipped. This regresses the behavior `pr-mod-rebase-branch-before-push` originally shipped and leaves remote branches stale against their target.

## Evidence

From PR #94 run `24466375038` (claude-live job, 2026-04-15 16:37 UTC, spacedock-ensign/push-main-entity fixture):

```
git-push-log.txt:
  1776271227.739815034 git push origin main
  1776271227.772526760 git push origin spacedock-ensign/push-main-entity   # 33 ms after main, no rebase
  1776271277.876924307 git push origin main
  1776271292.455350892 git push origin --delete spacedock-ensign/push-main-entity
```

FO stats: `claude-haiku-4-5-20251001` on 125/125 turns, 170s wallclock, 5.67M cache read.

`tests/test_rebase_branch_before_push.py::test_rebase_branch_before_push` asserts two post-conditions on the remote branch:
- `other-PR commit is ancestor of branch (rebased before push)` → **FAIL**
- `remote branch contains other-pr-merged.txt (from main via rebase)` → **FAIL**

The push ordering ("main before branch") still passes because the timestamps are correct — it's just the rebase step in between that is missing.

The same test passes on `claude-live-opus` and `claude-live-bare` in the same run, narrowing the regression to haiku under the current mod wording.

## Second symptom (from the same run)

FO also ran `git push origin --delete spacedock-ensign/push-main-entity` after the PR was merged. The FO shared core explicitly forbids this: *"Do NOT delete the remote branch (`git push origin --delete ...`) while a PR is still pending — the PR reviewer needs that branch on the remote. Remote-branch cleanup is the PR merge's responsibility, not the FO's."* Not the failing test's assertion, but it's another haiku-era merge-flow drift that belongs in the same fix window.

## Proposed shape

Option A (cheapest): tighten `_mods/pr-merge.md` wording so the rebase step is impossible to skip — e.g., rewrite as a numbered sequence that the FO must echo back, or fold the three steps into a single helper script invocation (`scripts/pr-merge-push.sh {branch}`) that performs push-main → rebase → push-branch as one atomic hook action.

Option B (more robust): ship a small helper script and have the mod instruct the FO to invoke it instead of sequencing three git commands itself. Same idea, stronger enforcement.

Whichever we pick, the acceptance criterion is: `test_rebase_branch_before_push` passes on haiku in CI, and the unrelated "delete remote branch while PR pending" behavior stops too.

## Context

- Blocking #148 from merging green — currently being handled by xfailing `test_rebase_branch_before_push` on this task as the follow-up.
- `pr-mod-rebase-branch-before-push` (archived) is the original task that added the rebase step; the mod wording survived that ship but isn't haiku-proof.
- Related but distinct:
  - `#152 pr-merge-mod-ci-awareness` — the *CI-observability* gap after validator sign-off
  - `#156 codex-merge-hook-live-e2e-timeout-before-archive` — a Codex-specific archive-completion timeout
