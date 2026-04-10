---
id: 126
title: "claude-team context-budget reports stale tokens for dead ensigns — use peak, not last turn"
status: backlog
source: "FO observation during 2026-04-10 session — running claude-team against dead zombies from this session"
score: 0.80
worktree:
started:
completed:
verdict:
issue:
pr:
---

`skills/commission/bin/claude-team context-budget` reads `resident_tokens` from the **last assistant turn** in the subagent jsonl. When an ensign dies mid-turn (context overflow, tool error), the final logged turn has zero-valued usage fields. The script reports `resident_tokens: 0` and `reuse_ok: true` for an ensign that actually hit 170k+ and is dead in the water.

## Empirical evidence

Tested against three zombies in the current session's team config immediately after task 121 merged:

| Ensign | Turns | Last turn | Max across all turns | Peak % | Current script says |
|---|---|---|---|---|---|
| `116-impl` (dead from cycle-2 at 200k+) | 165 | **0** (0%) | **174,808** (87.4%) | above threshold | `reuse_ok: true` ❌ |
| `116-impl-cycle3` (dead at context limit) | 111 | **0** (0%) | **170,668** (85.3%) | above threshold | `reuse_ok: true` ❌ |
| `125-impl` (alive, completed normally) | 204 | 83,761 (41.9%) | 83,761 (41.9%) | under threshold | `reuse_ok: true` ✓ |

The two dead ensigns both peaked over 85% but the script reports them as safe to reuse. This is exactly the failure mode the 60% rule was supposed to catch.

## Root cause

The script's internal logic (from task 121's implementation):

> Extract resident tokens: last assistant-role entry's `usage` block → `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`.

When an ensign's turn errors out (e.g., context overflow), Claude Code logs a final assistant entry with all usage fields set to zero. The script's "last assistant entry" heuristic picks up this zero-valued turn and reports it as the current context state.

## Fix

Two approaches tested, both give identical correct results on all three zombies:

**(a) Max across all turns.** Scan every assistant turn with a usage block and return the maximum `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`.

**(b) Last non-zero turn.** Scan backward from the end and return the first turn with non-zero usage.

**Recommendation: approach (a).** It's theoretically correct (the context budget is about peak high-water-mark, not current) and robust against future failure modes where an anomalous turn might log partial usage instead of zero. Approach (b) relies on the assumption that resident tokens grow monotonically, which is true in practice today but not guaranteed in edge cases (cache eviction, long-running sessions).

## Scope

1. Update `skills/commission/bin/claude-team` `context-budget` subcommand to track the maximum resident tokens across all assistant turns in the jsonl, not the last turn.
2. Update the 15 existing unit tests in `tests/test_claude_team.py` to cover the new semantics. Add at least three new tests:
   - Fixture with a zero-usage final turn after a high peak → should return the peak, not zero
   - Fixture with monotonically increasing usage → max equals last (regression)
   - Fixture with an early peak and later lower values (simulating cache eviction) → max wins
3. No changes to the FO shared core or runtime adapter — the interface stays the same, only the internal computation changes.

## Acceptance criteria

1. `claude-team context-budget --name {dead-ensign-name}` on a dead ensign with a zero-usage final turn reports the peak `resident_tokens` from earlier turns, not zero.
   - Test: new unit test with a fixture jsonl ending in a zero-usage turn.
2. `claude-team context-budget` on a normally-operating ensign (monotonic growth) still reports the same value as before — last turn = max.
   - Test: existing fixture tests continue to pass unchanged.
3. The 60% threshold decision uses the peak value.
   - Test: fixture with peak at 65% and final turn at 30% → `reuse_ok: false`.
4. All 15 existing `test_claude_team.py` tests still pass (regression).
5. `test_agent_content.py` static assertions still pass (no interface change).

## Test plan

- Unit tests only. The fix is a one-function change in the script.
- No E2E needed.
- No changes to prose documentation — the runtime adapter already says "resident tokens" without specifying "last turn" vs "peak", so the semantics change is internal to the script.

## Out of scope

- Changing the threshold from 60%.
- Adding additional subcommands to `claude-team`.
- Changing the JSON output shape.
- Dispatch-time monitoring (continuous context tracking during a dispatch) — this task is specifically about fixing the one-shot query semantics.

## Related

- **Task 121** `fo-context-aware-reuse` (just landed) — this task fixes a latent bug in 121's implementation that would have made the 60% rule ineffective for dead ensigns, which is one of the two main failure modes the rule exists to address.
- **Task 125** `entity-body-accumulation-anti-pattern` (just landed) — tangential; 125 reduces the rate of context overflow, 121 detects when it's happening, 126 ensures 121's detection is accurate.
- **Session empirical data 2026-04-10** — three zombies in the team config gave identical test results for both fix approaches, validating the direction.
