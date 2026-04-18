---
id: 185
title: "Cherry-pick test-predicate data-flow fixes from #182 + audit remaining narration-match callers"
status: validation
source: "carved out of #182 — test-predicate data-flow fixes are sound and independently mergeable. Captain also asked: check if other tests carry the same incorrect-expectation pattern. Known offender per debrief: tests/test_gate_guardrail.py."
started: 2026-04-18T00:12:20Z
completed:
verdict:
score: 0.7
worktree: .worktrees/spacedock-ensign-cherry-pick-test-predicates-and-audit
issue:
pr: #123
mod-block: 
---

## Problem statement

PR #117 (entity #182) landed the right philosophy: replace brittle `entry_contains_text(...)` predicates that match FO narration prose with data-flow assertions that poll a workflow artifact (archived entity body, `### Feedback Cycles` section, etc.). Narration-matching predicates were already known-flaky on opus-4-6 (they passed by coincidence of verbose narration) and became outright-failing on opus-4-7, which narrates less.

Two blockers prevented clean landing of that work:

1. PR #117 mixed sound test-predicate fixes with rejected prose mitigations in `skills/first-officer/references/claude-first-officer-runtime.md` (Variant A, and the session-re-entry / feedback-to keepalive clauses). The prose portion is out of scope per captain.
2. An audit of other callers of `entry_contains_text` against FO narration had not been done — `tests/test_gate_guardrail.py` is the known offender, but the suite needed a full sweep.

This task carves out the test-only subset, cleanly cherry-picks it onto main, completes the audit, and converts at-risk callers to data-flow assertions where possible.

## Proposed approach

### Cherry-pick plan

From branch `spacedock-ensign/diagnose-opus-4-7-fo-regression`:

| Commit    | Split needed?                | Action                                                                                                                                                                                                                                                                                                                              |
|-----------|------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 9c59d143  | No — clean                   | Plain `git cherry-pick 9c59d143`. Whole commit is `tests/test_standing_teammate_spawn.py`: M5 watcher replaced with post-exit archive-content check; `expect_exit` bumped to 480s.                                                                                                                                                    |
| ab238078  | No — clean                   | Plain `git cherry-pick ab238078`. Whole commit is `tests/test_standing_teammate_spawn.py`: replace `expect_exit` with archive-polling loop + explicit `w.proc.terminate()`; M1 timeout 60s→120s.                                                                                                                                      |
| e40ff353  | YES — split required         | `git cherry-pick -n e40ff353`, then `git restore --staged --worktree skills/first-officer/references/claude-first-officer-runtime.md docs/plans/diagnose-opus-4-7-fo-regression.md` to drop the rejected prose mitigations and the diagnosis-doc edits. Commit only `tests/test_feedback_keepalive.py` — the `expect_exit(300s)` → polling-for-`### Feedback Cycles` + `w.proc.terminate()` change. |

Commit message for the split e40ff353 change should not reference the rejected prose mitigations — it should describe only the test-predicate change, mirroring the 9c59d143 / ab238078 wording.

### Timeout-bump decision (reviewer's 300s → 420s suggestion)

**Decision:** Do NOT bump to 420s. The polling deadline is already 300s, and the semantics of the polling loop differ from the old `expect_exit(300s)`:

- Old `expect_exit(300s)` waited for FO subprocess exit, which opus-4-7 was not reliably emitting within 300s (392s observed failure window was an exit-wallclock, not an artifact-write wallclock).
- New polling waits for the entity body to contain `### Feedback Cycles`. The artifact is written by the validation ensign well before FO teardown; the artifact-write wallclock is bounded by the ensign's work, not by FO subprocess-exit cleanliness.
- The 4/5 opus-4-7 PASS result on e40ff353 was measured against the 300s polling deadline, not a 420s one — evidence confirms 300s is sufficient for the artifact path.

If post-merge runs show the polling-deadline pattern timing out (not the FO exit pattern), revisit. Do not pre-emptively pad.

### Audit of remaining `entry_contains_text` callers

A grep across the repo yields three files with callers:

| File                                    | Line(s)      | Caller role                                                                                          | Classification              | Action                                                                                                                                                                                                                                                                                                                                                                  |
|-----------------------------------------|--------------|------------------------------------------------------------------------------------------------------|-----------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `tests/test_standing_teammate_spawn.py` | 14, 113      | Mid-run M2 watcher for "ECHO: ping" in team-inbox ToolResult entries (not narration)                 | Already data-flow            | No change. The predicate matches a `user` tool_result `content` text, which is the actual routed message payload — that IS the data flow. Distinct from the M5 watcher (which was narration-based and is the one being fixed by 9c59d143/ab238078).                                                                                                                         |
| `tests/test_fo_stream_watcher.py`       | 22, 235, 361-365 | Two roles: (a) line 235 is a unit test of the watcher scaffold itself using a dummy narration match; (b) lines 361-365 are self-tests of `entry_contains_text` as a pure function | Self-test of the helper     | No change. Out of scope per the seed body. Removing or converting these would erase the helper's unit-test coverage.                                                                                                                                                                                                                                                    |
| `tests/test_gate_guardrail.py`          | 17, 55, 64   | Two mid-run `w.expect(...)` watchers with `timeout_s=240` / `120` matching FO narration prose (`r"gate review|recommend approve|recommend reject"`, `r"gate|approval|approve|waiting for.*decision"`) | NEEDS CONVERSION            | See below                                                                                                                                                                                                                                                                                                                                                               |

### `tests/test_gate_guardrail.py` conversion spec

The two mid-run watchers at lines 54-69 serve two purposes: (a) fail-fast signal that the FO reached the gate, (b) bound wallclock so the test doesn't run to the budget cap.

The test's actual verdict lives in Phase 3 via `check_gate_hold_behavior` (entity status stays non-`done`, entity not archived) plus the Phase-3 `re.search` on `fo_text_output` for the gate-review keywords. Phase 3 already enforces the narration match as a *final* check, so removing the mid-run narration watchers does not weaken coverage — the narration match still runs post-hoc against the captured FO text log.

**Proposed conversion:**

- Replace both mid-run `w.expect(entry_contains_text(...))` blocks with a single polling loop (300s total deadline) that watches for either:
  - `entity_file`'s frontmatter `status` moving off `work` into anything else AND back / entity becoming locked, OR (more robustly)
  - the FO-log file containing a gate-related `SendMessage` tool_use to the captain channel (this is a tool-call artifact, not narration prose).
- The simplest, least-invasive data-flow signal: poll for the fo-log.jsonl containing an assistant `tool_use` entry with `name == "SendMessage"` AND `input.to` matching the team lead/captain channel. This is the workflow's actual gate-review delivery mechanism and is narration-free.
- After the polling loop succeeds, keep `w.expect_exit(timeout_s=180)` as-is (or replace with `w.proc.terminate()` following the #182 pattern — TBD during implementation once the signal lands).

**Fallback if the tool_use approach is too coupled to FO internals:** poll `entity_file`'s mtime / frontmatter for any change, then rely on Phase 3's existing `check_gate_hold_behavior` + re.search narration check for the final verdict. This weakens the mid-run fail-fast signal but preserves the final behavioral assertion, and is acceptable if the tool_use signal isn't stable across runtimes.

### Acceptance criteria

Each criterion below pairs with its test.

1. **AC-1 (cherry-pick correctness):** After the cherry-pick, `git log main` shows three new commits corresponding to 9c59d143, ab238078, and the test-only portion of e40ff353. No change to `skills/first-officer/references/claude-first-officer-runtime.md`. Verified by `git diff main~3 main -- skills/` returning empty and `git diff main~3 main -- tests/` matching the union of the three test-file diffs from the source branch.
2. **AC-2 (static suite green):** `pytest -m "not live_claude and not live_codex"` reports the same pass count as before the cherry-pick (currently 426/426). Verified by running the command.
3. **AC-3 (standing-teammate test passes on opus-4-6):** `pytest tests/test_standing_teammate_spawn.py -m live_claude` with `CLAUDE_MODEL=claude-opus-4-6` passes on a single live run. Verified by running it.
4. **AC-4 (feedback-keepalive test passes on opus-4-6):** `pytest tests/test_feedback_keepalive.py -m live_claude` with `CLAUDE_MODEL=claude-opus-4-6` passes on a single live run. Verified by running it.
5. **AC-5 (gate-guardrail conversion — data-flow assertion):** The two mid-run `entry_contains_text` calls are removed from `tests/test_gate_guardrail.py`. Their replacement asserts on a workflow artifact (fo-log tool_use entry or entity frontmatter mutation). Verified by `grep -n entry_contains_text tests/test_gate_guardrail.py` returning empty.
6. **AC-6 (gate-guardrail test passes on opus-4-6 live):** `pytest tests/test_gate_guardrail.py -m live_claude` with `CLAUDE_MODEL=claude-opus-4-6` passes. Verified by running it.
7. **AC-7 (audit documented):** The audit table above is preserved in the Stage Report or a follow-up section, so the next sweeper has a record of "what we checked and classified as already-fine."

### Test plan

| Test                                         | Type         | Runtime    | Est. cost     |
|----------------------------------------------|--------------|------------|---------------|
| `git diff` verification (AC-1)               | Static       | —          | Free          |
| `pytest -m "not live_claude and not live_codex"` (AC-2) | Static suite | Local      | ~30s, free    |
| `tests/test_standing_teammate_spawn.py` (AC-3) | Live Claude | opus-4-6   | ~$1.50, ~7m   |
| `tests/test_feedback_keepalive.py` (AC-4)     | Live Claude | opus-4-6   | ~$1.00, ~3m   |
| `tests/test_gate_guardrail.py` (AC-6)         | Live Claude | opus-4-6   | ~$1.00, ~3m   |

Total worst-case live-run cost: ~$4. Opus-4-7 live runs are NOT required for merge — sibling task #186 owns "green full suite on opus-4-7."

E2E live runs are required (not just static) because the point of the conversion is robustness against runtime-narration variance, which only shows up under real model output. Static pyflakes-level checks cannot verify that the polling predicate fires within the deadline.

## Scope

(kept from seed, with audit results folded in)

1. Cherry-pick 9c59d143, ab238078, and the `tests/test_feedback_keepalive.py` portion of e40ff353 onto main. Drop the `skills/` changes from e40ff353.
2. Convert `tests/test_gate_guardrail.py` lines 54-69 from narration-match watchers to a data-flow polling assertion.
3. Validate per AC-1..7 above.

## Out of scope

- Any prose mitigations in `skills/first-officer/references/claude-first-officer-runtime.md` (rejected from #182).
- Variant A prose changes from #182.
- `claude-team` narrowing — sibling task #184.
- Full-suite green on opus-4-7 — sibling task #186.
- Refactoring `entry_contains_text` itself, or adding a new data-flow helper to `scripts/test_lib.py` (YAGNI — per-caller inline polling is sufficient for three call sites).

## Cross-references

- #182 — source branch; rejected for scope drift
- #184 — sibling cherry-pick (claude-team narrowing)
- #186 — downstream "green full suite on opus-4-7" task
- PR #117 — the merged-then-partially-rejected PR these fixes originated in
- Independent reviewer of #117 — flagged the 300s→420s timeout bump (decision above: not adopted, with reasoning)

### Feedback Cycles

**Cycle 1 — 2026-04-18, captain-directed scope expansion mid-merge.**

During CI on PRs #107 (#172) and #122 (#183), `test_feedback_keepalive` on `claude-live-bare` failed with:

```
test_lib.StepTimeout: Step 'implementation ensign dispatched' did not match within 180s.
```

Root cause (from CI logs, run 24592781341 job 71916879865 and run 24592907925 job 71917261650): in bare mode on `claude-haiku-4-5`, the FO observes the validation REJECTED report, reads the entity body, and **applies the feedback fix itself via direct Bash+Edit on `greeting.txt`** instead of dispatching a fresh implementation ensign. The file gets updated to `Goodbye, World!` and the `### Feedback Cycles` entry gets recorded, but no `Agent` tool_use fires → the mid-run watcher times out at 180s.

This is the same anti-pattern #185 already addresses for the *end-of-test* signal (narration / tool_use match → data-flow assertion on entity artifact). The mid-run `'implementation ensign dispatched'` watcher was NOT touched in the original #185 scope. Captain directed folding the fix in rather than filing a separate entity.

**Scope expansion for this cycle:**

- Replace the mid-run `'implementation ensign dispatched'` watcher in `tests/test_feedback_keepalive.py` with a data-flow assertion. Suggested approach: poll for any of (a) `### Feedback Cycles` appearing in the entity body, (b) `greeting.txt` contents changing to the validation-expected value, (c) an `Agent` tool_use for implementation — whichever happens first. Any of these indicates the feedback cycle is being processed, whether the FO dispatched or inline-edited.
- AC-8 added: verify no mid-run `'implementation ensign dispatched'` watcher remains (grep `tests/test_feedback_keepalive.py`).
- AC-9 added: re-run `test_feedback_keepalive` on a bare-mode path locally against `claude-haiku-4-5` (the failing model) and confirm PASS.

**No prose mitigations.** Fix is test-side only. Do NOT edit `skills/first-officer/references/*`.

## Stage Report (ideation)

1. **Read the seed entity body** — DONE. Read `/Users/clkao/git/spacedock/docs/plans/cherry-pick-test-predicates-and-audit.md` at its pre-ideation state; preserved the Cross-references, Out-of-scope items, and Scope bullets while expanding the approach section.
2. **Inspect commits 9c59d143, ab238078, e40ff353** — DONE. `git show --stat` confirms 9c59d143 and ab238078 touch only `tests/test_standing_teammate_spawn.py`. e40ff353 touches three files: `tests/test_feedback_keepalive.py` (test-only change — keep), `skills/first-officer/references/claude-first-officer-runtime.md` (rejected prose — drop), `docs/plans/diagnose-opus-4-7-fo-regression.md` (diagnosis narration — drop, not relevant to this entity's plan). Split is prescribed in the cherry-pick-plan table, not performed.
3. **Read `tests/test_gate_guardrail.py` lines 55, 64** — DONE. Both are mid-run `w.expect(entry_contains_text(...))` watchers matching FO narration prose (`gate review|recommend approve|recommend reject` and `gate|approval|approve|waiting for.*decision`). They are NOT data-flow — conversion specified in the "Conversion spec" section. Target predicate: poll fo-log.jsonl for an assistant `SendMessage` tool_use entry routing a gate review to the captain channel. Fallback specified.
4. **Broader audit of `entry_contains_text` callers** — DONE. Three files contain callers: `test_standing_teammate_spawn.py` (line 113 — already data-flow against a tool_result payload, keep), `test_fo_stream_watcher.py` (lines 235 + 361-365 — self-test of the helper, out of scope per seed), `test_gate_guardrail.py` (lines 55, 64 — needs conversion, spec above). No other offenders found. Classification table is recorded in the approach section.
5. **Write ideation body** — DONE. Problem statement, cherry-pick plan with explicit e40ff353 split, audit findings, acceptance criteria AC-1..7 each with a test, test plan with runtime/cost estimates.
6. **300s → 420s timeout decision** — DONE. Decision: NOT adopted. Reasoning recorded: the polling semantics differ from `expect_exit`, the artifact-write wallclock is bounded by ensign work (not FO teardown), and the 4/5 opus-4-7 PASS result was measured against 300s. Revisit only if post-merge shows polling-deadline timeouts.
7. **Commit the updated body on main** — PENDING (next step; will commit with the body changes before signaling completion).
8. **Append Stage Report** — DONE (this section).

### Summary

Ideation produced a concrete cherry-pick plan (with explicit e40ff353 split), a completed audit of all `entry_contains_text` callers (one needs conversion, two are fine), a conversion spec for `test_gate_guardrail.py` with a primary approach and fallback, seven acceptance criteria each paired with its test, and a timeout-bump decision (not adopted, with reasoning). Implementation is ready to start.
