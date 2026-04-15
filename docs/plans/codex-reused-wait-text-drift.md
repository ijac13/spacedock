---
id: 161
title: "Codex reused-worker wait text assertion drifts on routed-feedback-fix case"
status: backlog
source: "PR #97 (entity #149) codex-live CI, 2026-04-15 — tests/test_codex_packaged_agent_e2e.py 1/26 checks failed"
started:
completed:
verdict:
score: 0.45
worktree:
issue:
pr:
---

`test_codex_packaged_agent_e2e` asserts that after a reused-worker feedback reflow, the Codex worker's wait text describes the routed feedback fix rather than only the original implementation. In PR #97's codex-live run the assertion fired even though the reused-worker flow itself appeared to complete normally (25/26 other checks PASSED). This is assertion drift on evidence shape, similar to the earlier stabilization in commit `d90fffc1 tests: stabilize codex live preflight and packaged reuse assertions`.

## Evidence

PR #97 CI run `24469421236`, job `codex-live`:

```
[reused-worker feedback reflow]
  PASS: reused worker is awaited after send_input on the same handle
  PASS: reused wait stays on the send_input target handle
  FAIL: reused wait describes the routed feedback fix rather than only the original implementation
  PASS: reused completion reports a new follow-up commit
  PASS: reused-worker follow-up does not spawn a replacement worker
```

Other 25 checks in `test_codex_packaged_agent_e2e` PASSED. Overall test failed because of this single check.

## Current workaround

Xfailed on the #149 branch with `@pytest.mark.xfail(strict=False, reason="pending #161 — codex reused-wait text drift; see docs/plans/codex-reused-wait-text-drift.md")`. Strict=False because a future text-stabilization or codex behavior change that makes the assertion pass should not break CI.

## Likely root cause area

The assertion's text matcher looks for language describing the "routed feedback fix" in the reused-worker wait annotation. The codex reused-worker flow appears to produce wait text that no longer includes that specific phrasing — either because the FO's codex-side feedback-rejection message template changed, or because codex's own wait-surface wording drifted.

## Proposed direction

Two options when this is picked up:

1. **Tighten the feedback reflow message template** in `codex-first-officer-runtime.md` so the routed message predictably carries a phrase the assertion can anchor on. Then update the assertion to match.
2. **Loosen the assertion** to match what the reflow currently produces, accepting that the precise phrasing will drift.

Option 1 is more robust long-term; option 2 is cheaper.

## Context

- Distinct from #156 (codex merge-hook archive stall timeout) and from #157 (Codex per-stage model, deferred follow-up) — this is about a specific reused-worker wait text assertion, not merge or model handling.
- Low urgency; xfail is correct tracking until someone revisits the codex feedback-reflow prose.
