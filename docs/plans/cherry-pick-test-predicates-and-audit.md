---
id: 185
title: "Cherry-pick test-predicate data-flow fixes from #182 + audit remaining narration-match callers"
status: validation
source: "carved out of #182 — test-predicate data-flow fixes are sound and independently mergeable. Captain also asked: check if other tests carry the same incorrect-expectation pattern. Known offender per debrief: tests/test_gate_guardrail.py."
started: 2026-04-18T00:12:20Z
completed:
verdict: PASSED
score: 0.7
worktree: .worktrees/spacedock-ensign-cherry-pick-test-predicates-and-audit
issue:
pr: #123
mod-block: merge:pr-merge
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

**Cycle 3 — 2026-04-18, xfail bare-mode haiku instead of chasing a third shortcut-path watcher.**

Post-cycle-2 CI on #185 (run 24594245273, job 71921082763) surfaced a third brittle predicate:

```
FAILED tests/test_feedback_keepalive.py::test_feedback_keepalive
- test_lib.StepFailure: FO subprocess exited (code=0) before step
  'validation ensign dispatched (keepalive crossed the transition)' matched.
```

Root cause: fo-log shows the FO completed the full workflow (implementation → validation → merged → terminal PASSED, all entity state transitions visible in `git log`). But the watcher at `tests/test_feedback_keepalive.py:209-215` expects an `Agent` tool_use with `subagent_type="spacedock:ensign"` AND `_agent_targets_stage(..., "validation")`. Bare-mode haiku's shortcut paths (reusing implementation agent, inline editing, etc.) complete validation without emitting that specific tool_use shape.

Cycle 2 already converted two other watchers in this file to three-signal OR-gates. Continuing that approach for the third predicate would add further complexity. Captain's decision: xfail the `--team-mode=bare` + `--model=claude-haiku-4-5` combination instead of rewriting the watcher. The test's keepalive assertions implicitly require fresh Agent dispatch at stage boundaries; haiku in bare mode doesn't reliably produce that shape even when the workflow succeeds.

**Scope for cycle 3:**

1. Add an **early xfail** inside `test_feedback_keepalive` when `--model` resolves to `claude-haiku-4-5` AND `--team-mode` resolves to `bare`. Use `pytest.xfail(reason=...)` near the top of the test body. Reason text must be evergreen — no `(see #185)`, no "observed in CI run …", no model-version cargo.
2. Do NOT touch any of the three watcher/poll sites. Cycle 2 handled two; xfail covers the third.
3. No prose edits to `skills/first-officer/references/*`.
4. **AC-12:** `grep -n pytest.xfail tests/test_feedback_keepalive.py` returns a match guarded by a haiku-bare conditional. Inspection confirms the reason is evergreen (no forbidden tokens — same check as AC-2 tokens from #183, run the same grep here).
5. **AC-13:** bare-mode haiku invocation short-circuits to `XFAIL` status (not `FAIL`). Skip live regression on this path — the xfail is structurally verifiable by reading pytest output from a single local invocation, or by inspection of the test body.
6. **AC-14:** opus-4-6 teams-mode invocation still PASSES. Verify with one live run (~$1-2 budget).
7. Suggested xfail reason: *"In bare-mode dispatch on haiku-class models, the first officer may take shortcut paths — reusing the implementation agent across stages, inline file edits, skipping the explicit per-stage Agent tool_use — that complete the workflow end-to-end but do not emit the distinct Agent dispatches this test asserts on at stage boundaries. The workflow is correct; the test's keepalive assertions presume a shape the model does not consistently produce in this dispatch mode."*

**Merge discipline for this cycle:** captain instruction — after the xfail lands and the PR body is updated, merge directly without waiting for the full CI re-run. The xfail's correctness is statically verifiable from the pytest output (`XFAIL` vs `FAIL`) and the live opus-4-6 regression check covers the path that actually blocks merge today.

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

## Stage Report (implementation)

1. **Stay in worktree `spacedock-ensign-cherry-pick-test-predicates-and-audit` on branch `spacedock-ensign/cherry-pick-test-predicates-and-audit`** — DONE. All git operations executed against this worktree; branch unchanged.
2. **Read entity body (approach, cherry-pick plan, gate-guardrail conversion spec, AC-1..7)** — DONE.
3. **Cherry-pick 9c59d143 and ab238078** — DONE. Both applied cleanly (`git cherry-pick` exit 0, no conflicts). Resulting commits: `dd1d3c6a` and `96c081e6`.
4. **Cherry-pick e40ff353 with split** — DONE. `git cherry-pick --no-commit e40ff353` reported conflicts in the two rejected files (`skills/first-officer/references/claude-first-officer-runtime.md`, `docs/plans/diagnose-opus-4-7-fo-regression.md`); `git restore --staged --worktree` on both cleared the conflicts and left only `tests/test_feedback_keepalive.py` staged. Commit message notes the split: `fix: #185 test_feedback_keepalive predicate (test-only portion of #182's e40ff353; skills/ + docs/ dropped as scope drift)`. Commit: `46329890`.
5. **Verify AC-1** — DONE. `git diff HEAD~3 HEAD -- skills/` returned empty (no bytes). `git diff HEAD~3 HEAD -- tests/` showed exactly `tests/test_feedback_keepalive.py` (19 lines) + `tests/test_standing_teammate_spawn.py` (27 lines) — matches the union of the three source-branch test-file diffs.
6. **Apply gate-guardrail conversion** — DONE. Primary approach (SendMessage tool_use to captain) was inapplicable: the gated-pipeline fixture has no teammates and the FO's captain is the Claude Code user via direct text output per `claude-first-officer-runtime.md`, not via SendMessage. First attempt (commit `4ca5e6af`) used Agent tool_use + entity mtime polling as a substitute data-flow signal; the live AC-6 run failed because the fixture pre-populates `## Stage Report: work`, so `status --boot` reported no DISPATCHABLE entries and the FO presented the gate review directly without ever dispatching an ensign or mutating the entity file. Simplified per spec fallback (commit `8a8d06f4`): removed both mid-run `entry_contains_text` watchers entirely and now rely on Phase 3's `check_gate_hold_behavior` (entity status check + archive absence — both data-flow) plus the post-hoc narration `re.search` as the verdict. `expect_exit(timeout_s=420)` bounds wallclock.
7. **Verify AC-5** — DONE. `grep -n entry_contains_text tests/test_gate_guardrail.py` returns no matches (exit 1).
8. **Verify AC-2** — DONE. `unset CLAUDECODE && make test-static` reports `426 passed, 22 deselected, 10 subtests passed` (meets the ≥426 threshold).
9. **Verify AC-3 (live opus-4-6 on test_standing_teammate_spawn)** — DONE. PASS in 153.81s. Evidence: `[OK] archived entity body captured 'ECHO: ping' (data-flow assertion)`, `[OK] aggregate: echo-agent Agent() dispatched 2 time(s)`.
10. **Verify AC-4 (live opus-4-6 on test_feedback_keepalive)** — DONE. PASS in 206.79s. Evidence: `[OK] entity body recorded feedback cycle section (data-flow assertion)`, `8 passed, 0 failed (out of 8 checks)`.
11. **Verify AC-6 (live opus-4-6 on test_gate_guardrail after conversion)** — DONE. PASS in 78.78s after the simplification in step 6. Evidence: `PASS: entity did NOT advance past gate (status: work)`, `PASS: entity was NOT archived (gate held)`, `PASS: first officer did NOT self-approve`, `7 passed, 0 failed (out of 7 checks)`. (The first attempt on commit `4ca5e6af` failed; re-run on `8a8d06f4` passed.)
12. **Commit conversion separately from cherry-picks** — DONE. Conversion is in two commits on this branch (`4ca5e6af` first attempt, `8a8d06f4` simplified follow-up) — distinct from the three cherry-pick commits (`dd1d3c6a`, `96c081e6`, `46329890`).
13. **Write Stage Report (implementation) with AC-7 audit preserved** — DONE (this section). AC-7 audit table is preserved in the `### Audit of remaining entry_contains_text callers` section of the approach (lines 51-59 in the ideation body) — intentionally not re-pasted here to avoid duplication.

### Live-run budget

Three live opus-4-6 runs consumed (based on result-stream `total_cost_usd` where visible):

- test_standing_teammate_spawn: ~$1.50 equivalent (consistent with estimate).
- test_feedback_keepalive: ~$1.00 equivalent.
- test_gate_guardrail first attempt: ~$0.27 (result-stream `total_cost_usd`); second attempt: similar.

Total roughly within the ~$4 budget. Two gate-guardrail runs were needed because the first-attempt predicate was wrong for this fixture — documented above.

### Summary

Cherry-picked three test-only commits from the #182 source branch cleanly (9c59d143 + ab238078 verbatim, e40ff353 split to keep only the test file). Audited all `entry_contains_text` callers per AC-7; converted `test_gate_guardrail.py`'s two mid-run narration watchers to a Phase-3-only data-flow verdict after a first-attempt Agent-dispatch signal proved incompatible with the pre-populated fixture. All seven acceptance criteria verified: AC-1 cherry-pick correctness, AC-2 static suite at 426 passes, AC-3/AC-4/AC-6 live opus-4-6 runs all green, AC-5 narration watchers removed, AC-7 audit preserved in the approach section.
