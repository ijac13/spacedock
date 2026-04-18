---
id: 188
title: "Convert test filesystem-polling loops to FOStreamWatcher event-driven predicates"
status: ideation
source: "captain observation during #185 CI triage — the 300s polling loops cherry-picked from #182's e40ff353 are a regression from the event-driven FOStreamWatcher pattern. Same work should be expressible as stream predicates on FO-emitted tool_use events."
started: 2026-04-18T03:50:49Z
completed:
verdict:
score: 0.5
worktree:
issue:
pr:
mod-block:
---

## Problem

`FOStreamWatcher` (`scripts/test_lib.py:1079`-ish) tails `fo-log.jsonl` as the FO subprocess writes it and fires caller-supplied lambda predicates when matching events arrive. Event-driven, no polling. The mid-run milestones in the live-CI tests use this shape correctly via `w.expect(lambda, timeout_s=N, label=...)`.

Three tests currently use a **filesystem-polling** shape at end-of-test instead:

1. `tests/test_standing_teammate_spawn.py` — polls for `_archive/001-echo-roundtrip.md` containing `ECHO: ping`, 300s deadline.
2. `tests/test_feedback_keepalive.py` — polls for `### Feedback Cycles` in the entity body, 300s deadline.
3. `tests/test_gate_guardrail.py` — post-hoc narration re.search after `expect_exit(420s)`; relies on Phase-3 helpers rather than a stream predicate.

All three introduced in the #182 / #185 cherry-pick chain as a workaround because `expect_exit(300s)` was unreliable on opus-4-7 (the FO subprocess didn't always exit cleanly within the deadline). Filesystem polling bypassed that by asserting directly on the artifact the FO produced, then calling `w.proc.terminate()`.

The problem: the artifacts are written by the FO via `Edit` / `Write` tool_use events which ARE observable in the `fo-log.jsonl` stream. The streaming watcher can match on them directly. Filesystem polling introduces dead time, depends on filesystem-sync timing, and doesn't benefit from the watcher's timeout/label/error-message ergonomics.

## Proposed fix

Convert each filesystem-polling loop to a `w.expect(...)` streaming-watcher predicate, then terminate the subprocess. Shape per call site:

```python
w.expect(
    lambda e: tool_use_matches(e, "Edit", file_path=str(entity_file))
              and "### Feedback Cycles" in e.get("input", {}).get("new_string", ""),
    timeout_s=300,
    label="Feedback Cycles recorded",
)
w.proc.terminate()
```

Predicate details per call site will vary (Write vs Edit, exact file path, content fragment to match). The streaming watcher's `tool_use_matches` helper already handles the tool-name + input-field matching.

## Acceptance criteria

Each AC names its verification method.

**AC-1 — All three test files use `w.expect` for the terminal signal.**
Test method: grep `tests/test_standing_teammate_spawn.py tests/test_feedback_keepalive.py tests/test_gate_guardrail.py` for `time.monotonic() +` or `while time.monotonic()` patterns — zero matches.

**AC-2 — Each converted predicate matches the same artifact the polling loop matched.**
Test method: diff the before/after test file; the predicate's match content must still assert on `ECHO: ping` (standing-teammate), `### Feedback Cycles` (feedback-keepalive), and the gate-guardrail artifact. No weakening of the verdict.

**AC-3 — Live claude suite passes on opus-4-6.**
Test method: `make test-live-claude` runs green serial + parallel tiers.

**AC-4 — Live claude-bare suite passes on claude-haiku-4-5.**
Test method: `make test-live-claude` also exercises the bare-mode path. Confirm `test_feedback_keepalive` passes on bare-mode.

**AC-5 — Budget honest.**
Test method: the converted predicates should not require raising the existing 300s/420s timeouts to pass; if any timeout needs to increase, document why in the stage report.

## Out of scope

- Any changes to `FOStreamWatcher` itself.
- Any changes to `skills/first-officer/references/*` (no prose mitigations).
- Changes to mid-run watchers that already use `w.expect` — they're already correct.
- Any opus-4-7 work — that's #186's territory.

## Cross-references

- **#182** — source of the filesystem-polling regression (cherry-picked from its `e40ff353` commit; since rejected and archived REJECTED)
- **#185** — cherry-picked the regression forward; will be the landing point whose cleanup this entity owns
- **#186** — opus-4-7 greening; independent of this entity
- `scripts/test_lib.py` — `FOStreamWatcher` + `tool_use_matches` live here

## Test plan

- **Static:** `make test-static` — free, <30s.
- **Live:** `make test-live-claude` (both tiers) — ~$15-27, ~15m.
- **Implementation wallclock:** ~1hr for the three conversions + one live validation pass.
- **Total budget:** ~$20-30, ~1-2hrs.

## Cost/benefit note

Low urgency. The current polling loops work (all three green on opus-4-6 per #185 validation). Value is code hygiene: event-driven shape matches the mid-run watchers, cuts dead time, improves failure-mode error messages. Worth doing when the fleet is quieter — not a blocker.
