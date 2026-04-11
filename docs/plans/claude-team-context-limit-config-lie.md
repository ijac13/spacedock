---
id: 131
title: "claude-team context-budget lies — reads [1m] from team config, runtime strips it"
status: implementation
source: "CL observation on a parallel session, 2026-04-11 — ensign at 85k resident tokens on bare claude-opus-4-6 reported as 7.4% of 1M when actual usage is 42.6% of 200k"
score: 0.80
worktree: .worktrees/spacedock-ensign-claude-team-context-limit-config-lie
started: 2026-04-11T06:53:32Z
completed:
verdict:
issue:
pr: #75
---

The `claude-team context-budget` subcommand in `skills/commission/bin/claude-team` derives an ensign's context limit from the **team config's declared model string**, not from the **runtime model observed in the subagent jsonl**. Claude Code's subagent dispatch pipeline strips the `[1m]` suffix at spawn time, so ensigns requested as `opus[1m]` actually run as bare `claude-opus-4-6` with a 200k context window. The script reads `opus[1m]` from `~/.claude/teams/{team}/config.json`, pattern-matches the `[1m]` substring, and returns `context_limit = 1_000_000`. The reported `usage_pct` is calculated against the wrong denominator, and `reuse_ok` returns `True` for ensigns that should fresh-dispatch.

## Evidence

Parallel-session finding on ensign `spacedock-ensign-spacedock-pipeline-hypothesis` (team `dataagentbench-harness`):

- `team config model: "opus[1m]"` — stored in `~/.claude/teams/dataagentbench-harness/config.json`.
- `jsonl distinct models seen: {'claude-opus-4-6'}` — every assistant turn in `agent-a13d61f7d7f37d0ec.jsonl` was served by bare `claude-opus-4-6`, no `[1m]` anywhere.
- `resident_tokens = 85179`.
- Script returns `usage_pct = 85179 / 1_000_000 = 8.5%`, `reuse_ok = True`.
- Reality: `usage_pct = 85179 / 200_000 = 42.6%`. Still under the 60% threshold but in the wrong ballpark; headroom is ~35k not ~915k.

## Bug location

`skills/commission/bin/claude-team`:

- Line 107 — `lookup_model()` returns `member.get("model")` from the team config JSON, which is the **requested** variant, not the running one.
- Line 122 — `context_limit_for_model()` pattern-matches `[1m]` in that string and returns `EXTENDED_CONTEXT_LIMIT`.
- Line 145 — `cmd_context_budget()` uses that limit as the denominator for `usage_pct`.

The authoritative source for what model is actually running is the same subagent jsonl that `extract_resident_tokens()` already reads. Each assistant entry has a model field (`claude-opus-4-6`, `claude-haiku-4-5-20251001`, etc.). If the config says `opus[1m]` but every jsonl assistant turn shows bare `claude-opus-4-6`, the runtime has stripped the suffix and the context limit is 200k.

## Impact

Any FO reuse decision that runs `context-budget` on an ensign that was requested with the `[1m]` suffix gets a false-positive `reuse_ok=True` when the real usage is 5× higher than reported. The concrete failure modes:

- **Ensign death from context overflow.** An ensign at real 65% usage (130k / 200k) reports as 13% (130k / 1M), gets reused, and overflows partway through its next stage. This is exactly the 116 cycle-2/cycle-3 failure mode that task 125 addressed — but 125 fixed **entity body accumulation** as one cause; this config-lie bug is a **second, independent contributor** to the same symptom.
- **Wrong reuse decisions across the board.** Not just overflow — even ensigns in the safer middle zone (30-60% real usage) get rubber-stamped for reuse when the FO should be weighing them more carefully.
- **Silent failure.** The script exits 0, returns a valid-looking JSON, and the FO follows the recommendation. Nothing surfaces the discrepancy unless someone independently reads the jsonl and notices the model mismatch.

## Proposed fix direction (ideation to refine)

Change `cmd_context_budget` to derive the model from the jsonl, not from the team config. Concretely:

1. `extract_resident_tokens` already walks the jsonl looking at assistant entries. Extend it (or add a parallel `extract_runtime_model`) to record the distinct model(s) seen.
2. Pass the runtime model to `context_limit_for_model` instead of the config-declared one.
3. If the runtime model is **multiple distinct values** across the jsonl (model swap mid-session), use the most recent one, or pick the smallest context window as the safe upper bound.
4. If the jsonl has no assistant entries yet (dispatch just happened, no turns logged), fall back to the team config (the current behavior) and emit a warning in the JSON output so callers know the reading is provisional.
5. Emit a warning field in the output JSON when the runtime model differs from the config-declared model. This surfaces the drift so FOs (and any other automation reading this script) can log it and file follow-ups.

Example drifted output:

```json
{
  "name": "spacedock-ensign-spacedock-pipeline-hypothesis",
  "resident_tokens": 85179,
  "model": "claude-opus-4-6",
  "config_declared_model": "opus[1m]",
  "config_drift_warning": "team config requested [1m] variant but runtime is bare — using bare context limit",
  "context_limit": 200000,
  "usage_pct": 42.6,
  "threshold_pct": 60,
  "reuse_ok": true
}
```

## Scope

- Fix `skills/commission/bin/claude-team` context-budget to read the runtime model from jsonl.
- Add a unit test (`tests/test_claude_team.py` already exists — extend it) that verifies: (a) a jsonl with bare `claude-opus-4-6` returns `context_limit=200000` even when team config says `opus[1m]`, (b) a jsonl with actual `claude-opus-4-6[1m]` (if that ever appears) returns 1M, (c) mixed-model jsonl picks the safe upper bound, (d) empty jsonl falls back to config with a warning.
- Emit the `config_drift_warning` field so drift is visible, not silent.
- **Do not** change the team config format or what Claude Code stores there. The config is a declaration of intent; the runtime is ground truth. Fix reads the runtime, leaves the config alone.

## Out of scope

- Fixing Claude Code's subagent dispatch pipeline to preserve the `[1m]` suffix (that's upstream).
- Changing how teams request models.
- Retroactively re-evaluating past reuse decisions.

## Acceptance Criteria (ideation to refine)

1. `claude-team context-budget` reports `context_limit` derived from the model observed in the subagent's jsonl, not from the team config.
2. When config-declared model ≠ runtime model, the output includes a `config_drift_warning` field naming both and explaining the choice.
3. Reuse decisions made against the bug's original failure case (85k resident on bare opus, config says `opus[1m]`) return `usage_pct ≈ 42.6`, not `8.5`, and `reuse_ok` reflects that real denominator.
4. `tests/test_claude_team.py` extends its context-budget coverage with the four scenarios above.
5. The existing 20 tests in `test_claude_team.py` remain green.
6. The FO's reuse path in `first-officer-shared-core.md` and `claude-first-officer-runtime.md` does not need updates — the contract is "`reuse_ok: false` → fresh-dispatch". The fix is entirely inside the script.

## Test Plan

- Extend `tests/test_claude_team.py` with fixture jsonls and corresponding team configs exercising the four scenarios (bare runtime vs declared [1m], actual [1m] runtime, mixed models, empty jsonl).
- Unit tests, no live claude invocation needed — the bug is pure script logic.
- E2E not needed. This is a bounded, deterministic script behavior.
- Manual verification against the original failure case (if the parallel session's jsonl is still on disk): run `claude-team context-budget --name spacedock-ensign-spacedock-pipeline-hypothesis` before and after the fix, verify the `usage_pct` jumps from 8.5 to ~42.6.

## Related

- **Task 125** `entity-body-accumulation-anti-pattern` — solved one half of the "ensigns die from context overflow" failure mode (entity body accumulation). This task solves the other half (wrong denominator in context budget check). Both are needed for the FO reuse path to be safe.
- **Task 121** `fo-context-aware-reuse` — the umbrella task for FO reuse reliability. This bug directly undermines 121's safety check.
- **Task 116** `readme-and-architecture-refresh` — the task that killed two impl ensigns from context overflow. Was likely a victim of BOTH 125's accumulation bug and this config-lie bug. Worth checking the 116 cycle-2/cycle-3 jsonls to see if the runtime model was bare there too.
- Session log from 2026-04-11 — parallel session (likely Codex FO or a separate Claude session) independently discovered this during a reuse-path postmortem, providing the empirical evidence cited above.

## Stage Report: implementation

### Summary

Fixed `claude-team context-budget` to derive the context limit from the runtime model observed in the subagent jsonl rather than from the team config's declared model string. Two files changed: `skills/commission/bin/claude-team` (new `extract_runtime_models()` function + updated `cmd_context_budget()`) and `tests/test_claude_team.py` (4 new test scenarios + `model` parameter added to fixture helper). All 24 tests pass (20 existing + 4 new). Status script smoke regression: 90/90.

The drift comparison uses context limit equality rather than string equality, because config stores short names (e.g. `opus[1m]`) while runtime uses full model IDs (e.g. `claude-opus-4-6[1m]`). A string comparison would false-positive on every run even when the context windows match.

### Checklist

1. **Read the entity seed** — DONE. Problem statement, ACs, test plan, edge cases all reviewed.
2. **Read `skills/commission/bin/claude-team`** — DONE. Confirmed bug at lines 107 (lookup_model returns config string), 122 ([1m] check), 145 (denominator).
3. **Read `tests/test_claude_team.py`** — DONE. 20 existing tests, subprocess-based pattern with `make_jsonl_fixture` and `make_team_config` helpers.
4. **Implement runtime-model extraction from jsonl** — DONE. `extract_runtime_models(jsonl_path) -> set[str]` walks assistant entries and collects `message.model` values.
5. **Update `cmd_context_budget`** — DONE. Prefers runtime model over config, with fallback + drift warning + fallback warning + mixed-models warning.
6. **Add four new tests** — DONE.
   - `test_config_1m_runtime_bare_uses_200k` — config `opus[1m]`, runtime bare → 200k, drift warning, `config_declared_model` present.
   - `test_config_1m_runtime_1m_uses_1m` — config `opus[1m]`, runtime `claude-opus-4-6[1m]` → 1M, no drift warning.
   - `test_mixed_models_uses_smallest_context` — two models in jsonl → picks smallest (200k), `mixed_models_warning` present.
   - `test_no_model_in_jsonl_falls_back_to_config` — no model field → uses config `opus[1m]` → 1M, `config_fallback_warning` present.
7. **pytest: 24/24 green** — DONE. `unset CLAUDECODE && uv run --with pytest python -m pytest tests/test_claude_team.py -q` → 24 passed.
8. **Status script regression: 90/90** — DONE. `unset CLAUDECODE && uv run tests/test_status_script.py` → 90 tests OK.
9. **AC verification:**
   - AC1 (context_limit from jsonl runtime model) — VERIFIED: `test_config_1m_runtime_bare_uses_200k` asserts `context_limit == 200000` when runtime is bare.
   - AC2 (config_drift_warning when models differ) — VERIFIED: `test_config_1m_runtime_bare_uses_200k` asserts `config_drift_warning` present and `config_declared_model == "opus[1m]"`.
   - AC3 (85k on bare opus → usage_pct ~42.6) — VERIFIED: `test_config_1m_runtime_bare_uses_200k` asserts `usage_pct == pytest.approx(42.6)`.
   - AC4 (four new test scenarios) — VERIFIED: all four listed in item 6 above.
   - AC5 (existing 20 tests green) — VERIFIED: 20 passed in the test run.
   - AC6 (no FO scaffolding changes needed) — VERIFIED: only `claude-team` and `test_claude_team.py` changed.
10. **Terminology check** — DONE. Grepped for stray 1M assumptions — none found. The fix is general: reads runtime model string, applies `context_limit_for_model()` to it.
11. **Commit on branch** — DONE. Single commit `2e7d59e` on `spacedock-ensign/claude-team-context-limit-config-lie`.
12. **Scope audit** — DONE. `git diff --name-only main...HEAD` shows exactly `skills/commission/bin/claude-team`, `tests/test_claude_team.py`, and this entity file.
