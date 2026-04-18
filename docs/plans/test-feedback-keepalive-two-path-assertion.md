---
id: 190
title: "Rewrite test_feedback_keepalive core assertion to cover both dispatch and inline-process FO paths"
status: validation
source: "PR #118 CI surfaced the third brittle watcher (tests/test_feedback_keepalive.py:219-224 post-#188) failing on non-bare claude-live opus-4-6, not just bare-mode haiku. #185 cycle 3 xfailed only the bare-mode haiku combination — the scope was too narrow. The underlying issue is architectural: the test's core assertion presumes per-stage fresh Agent dispatch, which some FO model/mode combinations don't consistently produce even when the workflow completes correctly."
started: 2026-04-18T16:56:26Z
completed:
verdict:
score: 0.7
worktree: .worktrees/spacedock-ensign-test-feedback-keepalive-two-path-assertion
issue:
pr: #132
mod-block: merge:pr-merge
---

## Why this matters

`tests/test_feedback_keepalive.py` is the keepalive-across-transition test. Its core assertion pattern:

1. **Mid-run watcher** at line 219-224 (post-#188 shift; was 209-215 when #190 was filed) — `w.expect(...)` matching `Agent` tool_use with `subagent_type="spacedock:ensign"` AND `_agent_targets_stage(..., "validation")`. Blocks until fresh validation ensign is dispatched.
2. **Post-watcher Tier-1 assertion** — "no shutdown SendMessage targets implementation agent between completion and validation dispatch." This anchors a time-window between two events.

**The problem:** some FO model/mode combinations (initially observed on bare-mode haiku-4-5; then on claude-live opus-4-6 in PR #118 CI run `24596336820`) take shortcut paths:
- Reuse the implementation agent for validation
- Inline-edit the feedback fix directly
- Complete the workflow via `status --set` + entity-body edits without dispatching a fresh validation ensign

When that happens, the workflow completes end-to-end correctly (entity reaches terminal PASSED; `greeting.txt` has the expected content; `### Feedback Cycles` section recorded), but the mid-run watcher never fires and the FO subprocess exits cleanly. Test reports FAILURE via `StepFailure: FO subprocess exited (code=0) before step 'validation ensign dispatched (keepalive crossed the transition)' matched`.

**Prior attempts:**
- **#185 cycle 3** added `pytest.xfail` for `--team-mode=bare AND --model=claude-haiku-4-5`. Scope too narrow — PR #118 CI proves the same failure mode hits non-bare opus-4-6.
- Simply OR-gating the watcher (adding "entity frontmatter status=validation" or "Stage Report: validation" signals) would **silently weaken the Tier-1 assertion** — there's no "between dispatch and completion" window when inline-processing.

## Proposed approach

Rewrite the assertion shape to **branch on the observed FO path**, preserving meaningful coverage for both:

**Path A — FO dispatched a fresh validation ensign (current assumption):**
- Verify `Agent` tool_use present with `subagent_type=spacedock:ensign` + stage=validation
- Verify NO `SendMessage` with `type=shutdown_request` targeting the implementation agent's name between impl completion and validation dispatch
- This is today's assertion.

**Path B — FO inline-processed the feedback fix:**
- Verify NO fresh validation `Agent` tool_use dispatched
- Verify the implementation agent is still the active teammate (no teardown observed)
- Verify the feedback fix actually landed: `greeting.txt` content matches the validation-requested value AND `### Feedback Cycles` section recorded AND entity reached terminal PASSED
- This is a different-but-meaningful assertion: "the FO completed the feedback cycle without unsafe state."

**Shape in code (rough):**

```python
# After impl completion (Tier-0 already verified), poll the stream for either path:
validation_signal = None
deadline = time.monotonic() + 240
while time.monotonic() < deadline:
    # Path A: fresh validation dispatch
    if any(tool_use_matches(e, "Agent", subagent_type="spacedock:ensign")
           and _agent_targets_stage(_agent_input_dict(e), "validation")
           for e in log.events()):
        validation_signal = "dispatch"
        break
    # Path B: inline-process evidence
    body = entity_file.read_text() if entity_file.is_file() else ""
    if ("### Feedback Cycles" in body
        and "Goodbye, World!" in (repo_root / "greeting.txt").read_text(errors="ignore")
        and re.search(r"status:\s*done", body, re.M)):
        validation_signal = "inline-process"
        break
    time.sleep(1.0)
else:
    raise AssertionError("Neither dispatch nor inline-process signal observed within 240s")

if validation_signal == "dispatch":
    # Run today's Tier-1 assertion: no shutdown SendMessage in the window
    assert_no_shutdown_between(impl_completion_event, validation_dispatch_event)
else:  # inline-process
    # Run Path-B assertion: impl agent still in team, no teardown
    assert_impl_agent_still_active_or_clean_completion(log)
```

The core test coverage isn't "did the FO dispatch?" — it's "did the FO complete the feedback cycle without breaking the implementation agent or workflow integrity?" Path-A and Path-B are two different ways to answer the same underlying question.

## Prerequisites

- **#188 likely lands first.** #188 converts the two polling loops (impl-dispatch, teardown) to `w.expect(...)` event-driven predicates — doesn't touch line 209-215. The third-watcher rewrite here is a separate surface.
- **#186 likely lands first.** #186's unpin flips CI default back to opus-4-7. This task's assertion shape must work on opus-4-6, opus-4-7, and haiku-4-5 equivalently.
- **Remove #185 cycle 3's xfail** as part of this task. The xfail becomes redundant once Path B is first-class.

## Acceptance criteria

Each AC names its verification method.

**AC-1 — Third watcher rewritten to two-path assertion.**
Test method: grep `tests/test_feedback_keepalive.py` for the old single-signal watcher label `'validation ensign dispatched (keepalive crossed the transition)'` — zero matches. New labels clearly identify which path fired.

**AC-2 — Tier-1 keepalive assertion conditionally applied.**
Test method: inspect the test body — the "no shutdown SendMessage between X and Y" assertion runs only when Path A is observed; Path B has its own assertion block.

**AC-3 — #185 cycle 3 xfail removed.**
Test method: grep `tests/test_feedback_keepalive.py` for `pytest.xfail` — zero matches. The `--team-mode=bare AND --model=claude-haiku-4-5` short-circuit is gone.

**AC-4 — Live green on all three target models.**
Test method: 3× runs each on opus-4-6, opus-4-7, claude-haiku-4-5 (bare mode). Every run PASSES via either Path A or Path B — no combination hits 240s timeout. Expected distribution varies per model but all must pass.

**AC-5 — Static suite still green.**
Test method: `make test-static` pass count ≥ baseline (current ~439).

**AC-6 — Budget.**
Test method: ~$25-40 total (9 live runs across 3 models) — tracked in stage report.

## Out of scope

- Changes to `skills/first-officer/references/*` — no prose mitigations.
- Making the FO always dispatch (path A forcing) — that's a different debate; this task accepts both paths as valid workflow completions.
- Changes to other tests — only `test_feedback_keepalive.py`.

## Cross-references

- **#182** — original brittle-predicate source (REJECTED; cherry-picks carved out)
- **#185** — cycle 3 added the narrow xfail this task removes
- **#186** — likely lands unpin before this task starts; may affect which model is the CI default
- **#188** — converts the other two polling loops in this same file; do NOT conflict
- **PR #118 CI run 24596336820 job 71926922426** — concrete evidence of the failure on opus-4-6 non-bare

## Stage Report

### Summary

Light verification pass. Ground-truth line numbers against current codebase (post-#188 merge) and fixed two references in the entity body. Proposed approach (Path A / Path B), ACs, and xfail target all validated — no logic changes needed.

### Checklist

1. **DONE — Line numbers updated, label confirmed.**
   `grep -n 'validation ensign dispatched' tests/test_feedback_keepalive.py` output:
   ```
   223:            label="validation ensign dispatched (keepalive crossed the transition)",
   225:        print("[OK] validation ensign dispatched — implementation agent survived the transition")
   ```
   The `w.expect(...)` block is now at lines 219-224 (not 209-215 as filed). #188's merge added a preceding `w.expect` for the "implementation data-flow signal" (lines 211-215), shifting the third watcher down by ~10 lines. Label string `'validation ensign dispatched (keepalive crossed the transition)'` is unchanged and still accurate. Updated two body references: `source:` frontmatter line (YAML value edit, not key rename) and the "Why this matters" list item.

2. **DONE — Path-A / Path-B signals grounded.**
   - **Path A (fresh validation Agent dispatch):** Matches existing predicate at line 220-221 (`tool_use_matches(e, "Agent", subagent_type="spacedock:ensign") and _agent_targets_stage(_agent_input_dict(e), "validation")`). This is observable in fo-log.jsonl as `tool_use` events with `name=Agent` and `input.subagent_type="spacedock:ensign"`. Confirmed: same predicate shape already used at line 207 and 220, proving the signal is streamable.
   - **Path B (inline-process evidence):** Three signals proposed —
     (a) `### Feedback Cycles` section in entity body (filesystem read, not stream event);
     (b) `greeting.txt` contains `Goodbye, World!` (the validation-requested content per keepalive-pipeline fixture);
     (c) `status: done` in entity frontmatter (terminal state).
     Signals (a) and (c) are filesystem polls — no fo-log events required. Signal (b) is the workflow-specific output the validation stage gates on. Grounding: the existing `_impl_signal_in_event` helper (line 195-209) already reads `Feedback Cycles` markers from entity Edit/Write tool_uses, so the signal is observable both in-stream (as Edit events) and on-disk (as eventual file state). Path B's filesystem-based approach is equivalent-or-stronger coverage.
     **No concrete CI fo-log artifact dump inspected** — grounding is by reading the predicate helpers already in the test file. Sufficient for ideation stage; implementation stage should verify against a real failing-run fo-log capture.

3. **DONE — xfail location confirmed.**
   `grep -n 'pytest.xfail' tests/test_feedback_keepalive.py` output:
   ```
   141:        pytest.xfail(
   ```
   Exactly one match. The xfail is guarded at line 140 by `if resolved_team_mode == "bare" and model == "claude-haiku-4-5":`. AC-3 ("grep `pytest.xfail` → zero matches") correctly targets this block. Implementation must remove lines 140-150 (the guard + `pytest.xfail(...)` call).

### Changes written

- Line 5 (frontmatter `source:` value): "209-215" → "219-224 post-#188"
- Line 20 (body bullet): same line-range update + parenthetical noting the shift

No YAML keys modified. No changes to agents/ or references/. No changes to proposed-approach logic.

### Ideation assessment

Entity is gate-ready. ACs follow #193 entity-level format with explicit `Test method:` clauses. Score 0.7 is appropriate — not >= 0.8 so staff review not triggered, but close enough that careful implementation is warranted. Main residual risk: Path-B's filesystem-based signals could race with FO teardown (entity body written, then status flipped). Implementation stage should verify signal-check order handles partial writes.
