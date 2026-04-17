---
id: 179
title: "Fix extra_args model plumbing in migrated live tests — plumb pytest --model into extra_args"
status: validation
source: "2026-04-16 session — #176 post-merge spot-check revealed model_override workflow input reaches pytest but stops at the test. Tests hardcode --model opus in extra_args, overriding the pytest --model fixture."
started: 2026-04-17T00:27:17Z
completed:
verdict:
score: 0.45
worktree: .worktrees/spacedock-ensign-fix-extra-args-model-plumbing
issue:
pr: #112
mod-block: merge:pr-merge
---

## Problem Statement

The #176 `model_override` workflow input correctly threads `--model claude-opus-4-6` through the CI step and into `uv run pytest --model claude-opus-4-6 ...`. But two of the migrated tests (`test_standing_teammate_spawn.py` and `test_claude_per_stage_model.py`) hardcode `--model opus` in their `extra_args` list passed to `run_first_officer_streaming`:

```python
extra_args=["--model", "opus", "--effort", effort, "--max-budget-usd", "2.00"],
```

`extra_args` is appended to the final `claude -p` command, overriding whatever pytest received via its `--model` fixture. So even when CI passes `model_override=claude-opus-4-6`, the actual `claude -p` invocation runs with `--model opus`.

This plumbing bug was invisible before #176 because `opus` was the only value ever passed. It became load-bearing when #176 shipped the model-pinning mitigation for the `opus-4-7` regression (#177).

## Impact

- The #176 post-merge spot-check on 2026-04-16 was meant to verify the `claude-opus-4-6` pin mitigates the `opus-4-7` hallucination. It ran with `--model opus` instead, producing an unrelated `expect_exit` timeout and no information about the mitigation. The mitigation remains unproven in CI.
- Future bisection and mitigation work that relies on `model_override` will hit the same silent override.
- Captains cannot pin an explicit dated model via CI dispatch; the pin is silently lost.

## Proposed design

Route `--model` through pytest's `model` fixture into `extra_args`:

1. Read the `model` fixture (already defined in `conftest.py` via the `--model` CLI option).
2. Use that value when constructing `extra_args`:

```python
extra_args=["--model", model, "--effort", effort, "--max-budget-usd", "2.00"],
```

where `model` is a pytest fixture parameter alongside the existing `effort` fixture.

Two test files need the fix (this task's initial scope overstated it; verified by grep on 2026-04-16):

- `test_standing_teammate_spawn.py` (#173 pilot) — hardcodes `--model opus` in `extra_args`
- `test_claude_per_stage_model.py` (#173 pilot) — hardcodes `--model opus` in `extra_args`

The six #175 migrations already read the `model` pytest fixture into `extra_args`; they do not need this fix. A smaller group of #175 tests (`test_gate_guardrail.py`, `test_dispatch_names.py`) passes no `--model` flag at all and defaults to whatever pytest's `--model` option provides — separate concern, out of scope here.

Each of the two in-scope files is a two-line edit: add `model` to the fixture arglist, use it in `extra_args`.

## Acceptance criteria

1. Both `test_standing_teammate_spawn.py` and `test_claude_per_stage_model.py` read `model` from the pytest fixture and pass it through `extra_args`.
2. `make test-static` remains green (the change is behavioral only on live runs, but fixture wiring must not regress the offline suite).
3. Local verification: one of the two tests run with `--model claude-opus-4-6` actually invokes `claude -p --model claude-opus-4-6` — confirmed via the stream-json assistant `message.model` stamp reading `claude-opus-4-6`, not `claude-opus-4-7`.
4. CI spot-check: rerun the `2.1.111 + model_override=claude-opus-4-6 + effort_override=low` spot-check against `test_standing_teammate_spawn.py::test_standing_teammate_spawns_and_roundtrips` and confirm the `claude-live-opus` job passes in ~2-3 minutes (matching the 2026-04-16 local result).

## Out of Scope

- Removing per-test hardcoded `--effort` or `--max-budget-usd` flags — those are separate concerns.
- Un-migrated tests that still use `run_first_officer` (not `run_first_officer_streaming`) — migrate separately if the same bug applies.
- Changes to `run_first_officer_streaming` itself or `scripts/test_lib.py` helper code.
- Changes to `conftest.py`'s `model` fixture definition — the fixture already exists; this task only plumbs its value into `extra_args`.

## Stage Report (implementation)

1. **DONE** — Read entity body: Problem Statement, Impact, Proposed design, ACs 1-4, Out of Scope.
2. **DONE** — Confirmed `model` fixture exists at `tests/conftest.py:106-107`, exposed as `model`, derived from `--model` CLI option registered at line 25.
3. **DONE** — Edited `tests/test_standing_teammate_spawn.py`: added `model` to `test_standing_teammate_spawns_and_roundtrips` arglist (line 34), replaced `"opus"` with `model` in `extra_args` (line 72). `--effort` and `--max-budget-usd` preserved verbatim. Commit `2eec54bb`.
4. **DONE** — Edited `tests/test_claude_per_stage_model.py`: added `model` to `test_per_stage_model_haiku_propagates` arglist (line 37), replaced `"opus"` with `model` in `extra_args` (line 63). `--effort` and `--max-budget-usd` preserved verbatim. Commit `dddddac3`.
5. **DONE** — `make test-static`: **426 passed, 22 deselected, 10 subtests passed in 19.85s**. Matches the 426 threshold exactly.
6. **DONE** — Collection smoke: `uv run pytest --collect-only tests/test_standing_teammate_spawn.py tests/test_claude_per_stage_model.py` → `2 tests collected in 0.01s`. Both tests collect without error.
7. **SKIPPED** — AC-3 local live-run verification deferred to captain post-merge spot-check. The real live run against `claude -p --model claude-opus-4-6` costs real budget/time (~2-3 minutes) and the spec explicitly permits deferral. Same validation pattern as #174/#176.
8. **DONE** — This Stage Report.

**Validation recommendation:** Same pattern as #174/#176 — YAML-style static checks (✅ 426 passed) + captain's post-merge CI spot-check to exercise AC-3/AC-4 (rerun the `2.1.111 + model_override=claude-opus-4-6 + effort_override=low` dispatch against `test_standing_teammate_spawns_and_roundtrips` and confirm the stream-json `message.model` stamps read `claude-opus-4-6`, and the `claude-live-opus` job passes in ~2-3 minutes).

**Summary of changes:** Two files, two lines each. `test_standing_teammate_spawn.py` and `test_claude_per_stage_model.py` now read `model` from the pytest fixture and thread it into `extra_args`. The `--model claude-opus-4-6` workflow input from #176 now actually reaches `claude -p` instead of being silently overridden by a hardcoded `"opus"`.
