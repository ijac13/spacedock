---
id: 156
title: "Codex merge-hook live E2E can stall before archive completes after hook/resume flow"
status: backlog
source: "Local verification on 2026-04-15 while stabilizing #148 Codex live tests"
started:
completed:
verdict:
score: 0.58
worktree:
issue:
pr:
---

Local Codex runs of `tests/test_merge_hook_guardrail.py` show that the merge hook itself fires and the cleanup side effects happen, but the with-hook path can still time out before the entity archives cleanly enough for the live test to call the run successful.

## Observed Evidence

- The initial Codex with-hook run times out at `360s`.
- The resume-only Codex merge/cleanup run times out at `240s`.
- `_merge-hook-fired.txt` exists and contains `merge-hook-entity`.
- Worktree cleanup passes after the hook path.
- Temporary branch cleanup passes after the hook path.
- The no-mods fallback passes.
- The with-hook entity can still be left at status `work` or `done` instead of archived when the timeout fires.

## Problem Statement

The remaining red is no longer "merge hook didn't run." It is a bounded-stop / archive-completion problem on the Codex path:

1. The live test wants a clean bounded stop after merge hook plus archive outcome.
2. The FO can reach the hook side effects and cleanup side effects but still miss archival before the timeout.
3. The resume path does not yet converge reliably enough to treat the with-hook path as stable.

## Desired Outcome

- The Codex with-hook path reaches a deterministic bounded stop after merge-hook execution and archive cleanup.
- If the observable terminal side effects already prove success, the live test's stop condition / exit handling should accept that state instead of failing solely on launcher timeout.
- `tests/test_merge_hook_guardrail.py` should pass without special local-only handling once the with-hook archive path is stable.
