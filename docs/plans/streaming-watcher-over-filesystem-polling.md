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

`FOStreamWatcher` (`scripts/test_lib.py:1079`) tails `fo-log.jsonl` as the FO subprocess writes it and fires caller-supplied lambda predicates when matching events arrive. Event-driven, no polling. The mid-run milestones in the live-CI tests use this shape correctly via `w.expect(lambda, timeout_s=N, label=...)`.

Three tests currently bypass the watcher at end-of-test. Current-main re-audit (post-#185 merge):

1. `tests/test_standing_teammate_spawn.py:113-121` — filesystem-polling loop on `_archive/001-echo-roundtrip.md` containing `ECHO: ping`, 300s deadline. **Single signal.**
2. `tests/test_feedback_keepalive.py:214-224` — filesystem-polling loop with a **3-signal OR-gate** (`greeting.txt` exists OR entity/archive body contains `Feedback Cycles` OR fo-log shows any ensign `Agent` dispatch), 240s deadline. Fires on "impl data-flow signal."
3. `tests/test_feedback_keepalive.py:255-265` — filesystem-polling loop with a **3-signal OR-gate** (entity/archive body contains `Feedback Cycles` OR `greeting.txt` contains `Hello, World!` OR fo-log shows >=2 ensign `Agent` dispatches), 300s deadline. Fires on "feedback-cycle data-flow signal."
4. `tests/test_gate_guardrail.py:53` — NOT a filesystem-polling loop. Uses `w.expect_exit(timeout_s=420)` to wait for FO budget-exhaustion exit, then Phase 3 runs post-hoc `re.search` over FO text. The verdict is Phase-3 data-flow (entity status, archive absence) + narration checks on `fo_text_output`.

Sites 1-3 introduced in the #182 / #185 cherry-pick chain as a workaround for opus-4-7 flakiness (FO subprocess didn't reliably exit within deadline). Filesystem polling bypassed that by asserting directly on the artifact.

The artifacts from sites 1-3 are all written by the FO or a dispatched ensign via `Edit` / `Write` / `Agent` tool_use events observable in the `fo-log.jsonl` stream. The streaming watcher can match on them directly. Filesystem polling introduces dead time, depends on filesystem-sync timing, and forfeits the watcher's timeout/label/error-message ergonomics.

Site 4 is a different shape: `expect_exit(420)` is a long wait on process death, not a polling loop on an artifact. A stream predicate that fires on the gate-review signal and then calls `w.proc.terminate()` would cut ~300-400s of dead wait. However this is a second-order benefit — the current shape is correct, just slow. **#188 scope: optional conversion, lower priority than sites 1-3.**

## Proposed fix

Convert each filesystem-polling loop to a `w.expect(...)` streaming-watcher predicate, then terminate the subprocess.

### Design question: OR-gate predicates over mixed signal types

The #185 OR-gates fuse THREE heterogeneous signals:
- (a) filesystem-only — `greeting.txt` exists, `greeting.txt` contains `Hello, World!`
- (b) entity-body substring — grep `Feedback Cycles` in the entity/archive body
- (c) fo-log tool_use — ensign `Agent` dispatch count

`FOStreamWatcher.expect(predicate, ...)` already supports an OR-of-predicates cleanly: the caller's lambda can return `A(e) or B(e) or C(e)`. No watcher change needed. The real question: how to express signal (a) and signal (b) as stream predicates?

**Decision: convert ALL three signal types to their fo-log tool_use equivalents.** Rationale:
- `greeting.txt` is written by the implementation ensign. The ensign runs as a sub-`Agent` whose tool_use blocks are NOT emitted into the parent FO's `fo-log.jsonl` — the sub-agent's log is opaque from the parent stream. So "greeting.txt exists" CANNOT be observed via the FO stream today.
- `### Feedback Cycles` IS written by the FO itself via an `Edit`/`Write` tool_use on the entity body — directly observable.
- Ensign dispatch count IS an `Agent` tool_use in the FO stream — directly observable.

Given (a) is un-observable in the parent stream, the clean conversion is to **drop signal (a) and keep signals (b)+(c)**. The logical argument: if `greeting.txt` was written, the ensign ran; if the ensign ran, the FO dispatched it via `Agent` tool_use (signal c); therefore signal (c) is a strict superset of (a) at the FO-observable level. No verdict strength lost.

Alternative considered: **hybrid shape** where `w.expect(...)` fires on the primary stream signal, then a follow-up filesystem check confirms. Rejected — the whole point of #188 is to get off filesystem polling. Hybrid re-introduces the dead time we want to eliminate.

### Predicates per call site

**Site 1 — `test_standing_teammate_spawn.py:113-121` (single signal, archive body contains `ECHO: ping`):**

The archived entity body is written by the FO via `Edit` or `Write` tool_use on `_archive/001-echo-roundtrip.md` after the ensign reports back. The `ECHO: ping` content flows through the FO's edit. Predicate:

```python
archived = abs_workflow / "_archive" / "001-echo-roundtrip.md"
w.expect(
    lambda e: (
        tool_use_matches(e, "Edit", file_path=str(archived))
        or tool_use_matches(e, "Write", file_path=str(archived))
    ) and "ECHO: ping" in str(
        e.get("message", {}).get("content", [{}])[0].get("input", {}).get("new_string", "")
        or e.get("message", {}).get("content", [{}])[0].get("input", {}).get("content", "")
    ),
    timeout_s=300,
    label="archived entity body captured 'ECHO: ping'",
)
w.proc.terminate()
```

Note: `tool_use_matches` matches substring on a named input field. For `Edit` the field is `new_string`; for `Write` it's `content`. Implementation can wrap this in a small local helper to avoid the ternary `or` mess — see site 2 for the helper shape.

**Site 2 — `test_feedback_keepalive.py:214-224` (impl data-flow signal, 2-signal OR after dropping filesystem-only):**

```python
def _impl_signal_in_event(e: dict) -> bool:
    # Signal 1: FO Edit/Write on entity body containing "Feedback Cycles"
    for path in (entity_file, archive_file):
        if tool_use_matches(e, "Edit", file_path=str(path)):
            inp = _tool_input(e)
            if "Feedback Cycles" in inp.get("new_string", ""):
                return True
        if tool_use_matches(e, "Write", file_path=str(path)):
            inp = _tool_input(e)
            if "Feedback Cycles" in inp.get("content", ""):
                return True
    # Signal 2: any ensign Agent dispatch
    if tool_use_matches(e, "Agent", subagent_type="spacedock:ensign"):
        return True
    return False

w.expect(_impl_signal_in_event, timeout_s=240, label="implementation data-flow signal")
```

`_tool_input(e)` is a 3-line local helper that extracts `block.get("input", {})` from the first tool_use block — same shape as the existing `_agent_input_dict` in this test.

**Site 3 — `test_feedback_keepalive.py:255-265` (feedback-cycle signal, dropping filesystem-only; keeping signals (b) and (c)):**

```python
ensign_count = [0]

def _feedback_signal_in_event(e: dict) -> bool:
    # Signal 1: FO Edit/Write on entity body containing "Feedback Cycles"
    for path in (entity_file, archive_file):
        if tool_use_matches(e, "Edit", file_path=str(path)):
            if "Feedback Cycles" in _tool_input(e).get("new_string", ""):
                return True
        if tool_use_matches(e, "Write", file_path=str(path)):
            if "Feedback Cycles" in _tool_input(e).get("content", ""):
                return True
    # Signal 2: >=2 ensign dispatches observed
    if tool_use_matches(e, "Agent", subagent_type="spacedock:ensign"):
        ensign_count[0] += 1
        if ensign_count[0] >= 2:
            return True
    return False

w.expect(_feedback_signal_in_event, timeout_s=300, label="feedback-cycle data-flow signal")
w.proc.terminate()
```

Caveat: the `ensign_count` closure counts dispatches observed THIS call. The impl-dispatch signal (site 2) and feedback-dispatch signal (site 3) both increment. Since site 2 runs first, site 3's counter starts at 0. If site 2 matches on the ensign-dispatch signal (first dispatch), then by the time site 3's predicate starts, the first `Agent` tool_use has already been drained past site 2's `expect`. `FOStreamWatcher` reads sequentially — entries consumed by one `expect` are gone for the next. So site 3's counter sees dispatches starting from the second real dispatch — which is exactly what the current loop asserts. Semantics preserved.

**Site 4 — `test_gate_guardrail.py:53` (optional, de-scoped from #188's core):**

Current: `w.expect_exit(timeout_s=420)` waits for budget-exhaustion exit. Phase 3 is post-hoc checks on FO text + entity frontmatter. No filesystem polling.

Two options if we convert:
- **Early-terminate on gate-review signal:** watch for the FO's `SendMessage` to captain channel containing `gate review`, then `w.proc.terminate()`. Shaves ~300s.
- **Leave as-is:** the current shape isn't broken; #188's stated goal is replacing filesystem-polling loops. Site 4 is different.

**Recommendation: leave site 4 as-is for this entity**; if we want to speed up gate-guardrail, file it as a separate entity. This keeps #188 scope tight and lets it land cleanly without the Phase-3 narration-check refactor that an early-terminate predicate would entail (the current Phase 3 depends on the FO having emitted its full gate-review text; early termination might truncate that text).

## Acceptance criteria

Each AC names its verification method.

**AC-1 — Target test files use `w.expect` for the terminal signal; no `time.monotonic()` polling loops remain in sites 1-3.**
Test method: `grep -nE "time\\.monotonic\\(\\) \\+|while time\\.monotonic\\(\\)" tests/test_standing_teammate_spawn.py tests/test_feedback_keepalive.py` returns zero matches. `test_gate_guardrail.py` is out of scope (no filesystem-polling loop; see Proposed-fix site 4 note).

**AC-2 — Each converted predicate matches the same artifact the polling loop matched, at the same or stronger verdict level.**
Test method: diff the before/after test file. Site 1 predicate matches on `ECHO: ping` content inside an FO `Edit`/`Write` tool_use targeting `_archive/001-echo-roundtrip.md`. Site 2 predicate matches the OR of (FO Edit/Write on entity body with `Feedback Cycles`) OR (ensign `Agent` dispatch). Site 3 predicate matches the OR of (FO Edit/Write on entity body with `Feedback Cycles`) OR (>=2 ensign dispatches this expect call). Code review asserts the predicates cover every signal the OR-gate covered MINUS the filesystem-only `greeting.txt` signal, which is strictly subsumed by the ensign-dispatch signal (see Proposed fix decision).

**AC-3 — Live claude suite passes on the default pinned model.**
Test method: `make test-live-claude` runs green for both serial and parallel tiers on the model the repo is currently pinned to at the time #188 lands. As of drafting this is opus-4-6; after #186 lands the pin may be opus-4-7 — AC-3 adapts to whatever ships as the current pin.

**AC-4 — Live claude-bare suite passes on `claude-haiku-4-5`.**
Test method: `make test-live-claude --team-mode=bare` (or equivalent via env) exercises bare-mode path. Confirm `test_feedback_keepalive` passes on bare-mode claude-haiku-4-5 (respecting the existing `xfail` in that file — no regression past the xfail threshold).

**AC-5 — Opus-4-7 reliability parity or better.**
Test method: if #186 lands opus-4-7 as the CI pin, AC-3 implies opus-4-7 green. If #186 does not flip the pin, run `tests/test_standing_teammate_spawn.py` and `tests/test_feedback_keepalive.py` on opus-4-7 at least 3x and confirm green >= 2/3. The converted predicates fire on an earlier, more deterministic artifact than the filesystem-sync'd file, so opus-4-7 stability should improve, not regress.

**AC-6 — Budget honest.**
Test method: converted predicates do not require raising the 240s/300s timeouts. If any timeout needs to increase, document why in the stage report. (Expectation: timeouts can be LOWERED because event-driven firing eliminates the 1.0s sleep poll interval and filesystem-sync jitter.)

## Out of scope

- Any changes to `FOStreamWatcher` itself. Current OR-of-predicates capability (a caller lambda returning `A(e) or B(e) or C(e)`) is sufficient — no `expect_any_of` helper needed.
- Any changes to `skills/first-officer/references/*` or `skills/ensign/references/*` (no prose mitigations; this is test-code-only scope per dispatch).
- Changes to mid-run watchers that already use `w.expect` — they're already correct.
- Any opus-4-7 work — that's #186's territory.
- `test_gate_guardrail.py` conversion (site 4) — no filesystem-polling loop to remove; early-terminate optimization deferred to a follow-up entity if desired.

## Merge-order concern

#186 is currently in implementation on its own branch (opus-4-7 greening). Per AC-4 path (b) of #186, it may bump a timeout in `tests/test_feedback_keepalive.py`. If #186 changes predicate shape in that file, #188's rewrite of the same predicates would conflict.

**Resolution:** #186 lands first (time-sensitive unpin), #188 rebases onto main afterward. #188's implementation pilot reads the post-#186 version of `test_feedback_keepalive.py` as the starting point, not the pre-#186 version. Any timeout #186 bumped remains in the converted predicate unless AC-6 verification shows it can be lowered.

If #188 landed first by schedule accident, #186 would need to rebase; the converted predicates still assert on the same signals, so mechanical conflict resolution is straightforward.

## Cross-references

- **#182** — source of the filesystem-polling regression (cherry-picked from its `e40ff353` commit; since rejected and archived REJECTED)
- **#185** — cherry-picked the regression forward; will be the landing point whose cleanup this entity owns
- **#186** — opus-4-7 greening; independent of this entity
- `scripts/test_lib.py` — `FOStreamWatcher` + `tool_use_matches` live here

## Test plan

- **Static (AC-1, AC-2 code-shape checks):** `make test-static` — free, <30s. Verifies the grep-based AC-1 and file-diff-based AC-2 criteria.
- **Live claude (AC-3):** `make test-live-claude` both tiers on current pinned model — ~$12-20, ~10-15m.
- **Live claude-bare (AC-4):** `make test-live-claude` with team-mode=bare on claude-haiku-4-5 — ~$3-6, ~5m.
- **Opus-4-7 regression check (AC-5):** if opus-4-7 is not the pin, 3x runs of the two converted test files on opus-4-7 — ~$6-10.
- **Implementation wallclock:** ~1-1.5hr for site 1+2+3 conversions + local fast-suite green + live validation pass.
- **Total budget:** ~$20-35, ~1.5-2hrs. Slight upward revision from the seed's $20-30 to cover the AC-5 opus-4-7 regression check if it's not already implied by AC-3's pin.

No E2E test scaffolding changes needed — this work changes test bodies only, and the existing `make test-live-claude` invocation is the E2E verification.

## Cost/benefit note

Low urgency. The current polling loops work (all three sites green on opus-4-6 per #185 validation). Value is code hygiene: event-driven shape matches the mid-run watchers, cuts dead time (eliminates the 1.0s sleep-poll interval and filesystem-sync jitter), improves failure-mode error messages via the `label` kwarg. Worth doing when the fleet is quieter — not a blocker.

Secondary value: converting the OR-gate predicates to stream-level signals makes the tests' failure messages point at a specific missing tool_use rather than "no signal seen in 300s." This maps directly to the debugging pattern we've landed on — failures should name the signal, not the wall-clock.

## Stage Report (ideation)

### Summary
Re-audited the three sites on post-#185 main, restructured the spec around the actual shape (site 1 single-signal, sites 2-3 OR-gated 3-signal, site 4 not a polling loop at all). Made and justified the key design decision: convert OR-gated signals to fo-log tool_use equivalents where observable; drop filesystem-only signals that are subsumed by a stronger stream signal. Wrote concrete predicates per site. De-scoped site 4. Added merge-order note for #186. Expanded ACs from 5 to 6 and tied each to a specific verification.

### Checklist

1. **Read current entity body — DONE.** Seed had Problem + Proposed-fix shape + AC-1..AC-5 + Out-of-scope + Cost/benefit; all captured.

2. **Inspect each call site on current main — DONE.**
   - Site 1 (`test_standing_teammate_spawn.py:113-121`) confirmed: single-signal archive-polling loop, `_archive/001-echo-roundtrip.md`, 300s.
   - Site 2 (`test_feedback_keepalive.py:214-224`) confirmed: 3-signal OR-gate (greeting.txt, entity/archive body `Feedback Cycles`, ensign Agent dispatch), 240s.
   - Site 3 (`test_feedback_keepalive.py:255-265`) confirmed: 3-signal OR-gate (entity/archive body `Feedback Cycles`, greeting.txt contains "Hello, World!", >=2 ensign dispatches), 300s.
   - Site 4 (`test_gate_guardrail.py:53`) re-classified: NOT a filesystem-polling loop. Uses `expect_exit(420)` + post-hoc `re.search`. De-scoped from #188.
   - Grep confirmed: `tests/test_feedback_keepalive.py` 4 matches, `tests/test_standing_teammate_spawn.py` 2 matches, `tests/test_gate_guardrail.py` 0 matches on `time.monotonic()` patterns.

3. **Design concrete `w.expect(...)` predicates — DONE.** Wrote full predicate code per site in the Proposed-fix section. Uses `tool_use_matches(e, "Edit"|"Write", file_path=...)` with content-substring checks on `new_string`/`content` input fields. Sites 2 and 3 use named inner helpers that return bool over the OR of the signals.

4. **Critical design question (OR-gate expressibility) — DONE.** Decision: `FOStreamWatcher.expect(lambda e: A(e) or B(e) or C(e), ...)` handles OR natively with zero watcher changes. Filesystem-only signal (greeting.txt) is un-observable from the parent FO stream because sub-`Agent` tool_use blocks don't feed into `fo-log.jsonl`. Resolved by dropping that signal — it's strictly subsumed by the ensign-dispatch signal (if greeting.txt was written, the ensign ran; if the ensign ran, the FO dispatched it via Agent tool_use). No verdict strength lost. Documented rationale in Proposed-fix.

5. **Scope fence vs #186 — DONE.** Added Merge-order section. #186 lands first (time-sensitive unpin), #188 rebases. Any timeout #186 bumps in `test_feedback_keepalive.py` survives into the converted predicate unless AC-6 verification shows it can be lowered.

6. **Re-validate AC-1..AC-5 — DONE.** Restructured to AC-1..AC-6:
   - AC-1: scoped to sites 1-3 (excludes test_gate_guardrail.py since it has no polling loop).
   - AC-2: verdict-parity check, explicitly acknowledges dropping the greeting.txt filesystem-only signal with justification.
   - AC-3: made pin-agnostic ("whatever pin is current when #188 lands") to adapt to pre- or post-#186 state.
   - AC-4: bare-mode claude-haiku-4-5, respects existing xfail in test_feedback_keepalive.
   - AC-5: NEW — opus-4-7 reliability parity (3x run if not the pin).
   - AC-6: budget honesty (was AC-5 in seed, renumbered).

7. **Helper API consideration — DONE.** Decided against `expect_any_of([...])` helper. Current `FOStreamWatcher.expect` with an OR-returning lambda handles this cleanly. YAGNI. Documented in Out-of-scope.

8. **Revise ACs from step-2 audit — DONE.** Step 6 captures the revisions.

9. **Test plan cost + wallclock — DONE.** Refined to ~$20-35, ~1.5-2hrs (up from $20-30 to cover AC-5 opus-4-7 regression check). Broken down per AC.

10. **Commit updated body on main — DONE.** Committed as `38e7dd76` on main.

11. **Append Stage Report — DONE (this section).**
