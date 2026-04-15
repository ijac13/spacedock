---
id: 160
title: "haiku FO compresses multi-stage dispatch — spawns 1 Agent() when the workflow requires 2 (work + review)"
status: backlog
source: "PR #97 (entity #149) claude-live CI, 2026-04-15 — tests/test_dispatch_names.py::test_dispatch_names 1/8 checks failed"
started:
completed:
verdict:
score: 0.55
worktree:
issue:
pr:
---

Under haiku, the FO's dispatch loop collapses a "work then review" two-stage flow into a single dispatch. `test_dispatch_names` expects at least 2 Agent() calls for the two-stage pipeline fixture; the haiku FO produces exactly 1. Opus and claude-live-bare pass the same assertion. Sibling to #158 (haiku skips `git rebase main` in pr-merge hook) — both are instances of haiku compressing multi-step FO flows into single-step shortcuts.

## Evidence

PR #97 CI run `24469421236`, job `claude-live` (haiku default):

```
[multi-stage pipeline runtime checks]
  PASS: entity reached done status
  PASS: entity advanced past backlog (status: done)
  FAIL: multiple dispatches occurred (got 1 — expected >=2 for work + review)
  PASS: entity has completed timestamp

=== test_dispatch_names ===
  AssertionError: 1 of 8 checks failed in test_dispatch_names
```

Same test passed on `claude-live-opus` (opus completed both dispatches correctly) and was deselected from `claude-live-bare`.

## Current workaround

Xfailed on the #149 branch with `@pytest.mark.xfail(strict=False, reason="pending #160 — haiku FO compresses multi-stage dispatch; see docs/plans/haiku-fo-multi-dispatch-compression.md")`. Strict=False because opus/bare XPASS is the correct success shape, not a regression.

## Likely root cause area

The FO's dispatch-decision prose for multi-stage pipelines — specifically the logic in `first-officer-shared-core.md` around `## Dispatch` and `## Completion and Gates` that should trigger a second dispatch for the review stage after the work stage completes. Haiku under the current prose density is collapsing the decision into "work completed → done" without recognizing the review stage.

## Proposed direction

Same family as #158's rebase-skip fix: either tighten the prose so haiku can't skip the sequence, or fold the multi-stage decision into a single helper invocation. Resolving both haiku-compression issues (#158 + #160) may share a common pattern — worth thinking about umbrella scope, but keep them as separate tasks for now since fix locations differ (pr-merge mod vs FO dispatch loop).

## Context

- Blocked #149 PR #97 from a clean live matrix; unblocked via xfail.
- Related: #158 (pr-merge rebase-skip).
