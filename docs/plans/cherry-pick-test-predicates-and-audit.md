---
id: 185
title: "Cherry-pick test-predicate data-flow fixes from #182 + audit remaining narration-match callers"
status: backlog
source: "carved out of #182 — test-predicate data-flow fixes are sound and independently mergeable. Captain also asked: check if other tests carry the same incorrect-expectation pattern. Known offender per debrief: tests/test_gate_guardrail.py."
started:
completed:
verdict:
score: 0.7
worktree:
issue:
pr:
mod-block:
---

## Why this matters

PR #117 (entity #182) replaced brittle `entry_contains_text(...)` narration-matching predicates with data-flow assertions (poll the archived entity body / `### Feedback Cycles` section). The approach is correct: asserting on what the workflow actually produced is robust across FO verbosity changes, model-version swaps, and idle-timing variance.

The captain flagged that the same brittle pattern likely exists elsewhere. A grep confirms: `tests/test_gate_guardrail.py` uses `entry_contains_text` on FO narration at lines 55 and 64. The sibling tests (`test_fo_stream_watcher.py` uses the helper in its own unit tests — out of scope; that's testing the helper itself).

## Scope

1. Cherry-pick the test-predicate-only portions from the #182 branch:
   - `9c59d143` — standing-teammate test predicate (clean; whole commit is test change)
   - `ab238078` — standing-teammate test archive polling (clean; whole commit is test change)
   - The `tests/test_feedback_keepalive.py` portion of `e40ff353` ONLY — that commit mixed a test change with prose mitigations. Cherry-pick with `--no-commit`, reset the `skills/` changes, commit only the test file change.
2. Consider bumping the polling timeout from 300s → 420s per the independent reviewer's note (preserves the old total-budget headroom; the 392s failure window seen on opus-4-7 is close to 300s).
3. Audit `tests/test_gate_guardrail.py` for the same brittle-predicate pattern. Convert narration matches to data-flow assertions where a workflow artifact exists to assert against. File follow-up if any case can't be converted.
4. Verify static suite + targeted live runs on opus-4-6 (our pinned default) for each modified test. Full-suite greening on opus-4-7 is a sibling task (#186) — out of scope here.

## Out of scope

- Any prose mitigations in `skills/first-officer/references/claude-first-officer-runtime.md` (those are from #182's rejected scope).
- `claude-team` narrowing (that's a sibling task #184).
- Greening the whole suite on opus-4-7 (that's #186).

## Cross-references

- #182 — source branch; being rejected for scope drift
- #184 — sibling cherry-pick (claude-team narrowing)
- #186 — downstream "green full suite on opus-4-7" task
- Independent review of PR #117 — confirmed the predicate-change philosophy is sound
