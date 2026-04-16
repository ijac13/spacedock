---
id: 179
title: "Fix extra_args model plumbing in migrated live tests — plumb pytest --model into extra_args"
status: backlog
source: "2026-04-16 session — #176 post-merge spot-check revealed model_override workflow input reaches pytest but stops at the test. Tests hardcode --model opus in extra_args, overriding the pytest --model fixture."
started:
completed:
verdict:
score: 0.45
worktree:
issue:
pr:
---

## Problem Statement

The #176 `model_override` workflow input correctly threads `--model claude-opus-4-6` through the CI step and into `uv run pytest --model claude-opus-4-6 ...`. But the migrated tests (`test_standing_teammate_spawn.py`, `test_claude_per_stage_model.py`, and the six tests from #175) hardcode `--model opus` in their `extra_args` list passed to `run_first_officer_streaming`:

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

Eight test files need the same change:

- `test_standing_teammate_spawn.py` (pilot)
- `test_claude_per_stage_model.py` (pilot)
- `test_gate_guardrail.py` (#175)
- `test_merge_hook_guardrail.py` (#175)
- `test_feedback_keepalive.py` (#175)
- `test_team_dispatch_sequencing.py` (#175)
- `test_dispatch_names.py` (#175)
- `test_rebase_branch_before_push.py` (#175)

Each is a two-line edit: add `model` to the fixture arglist, use it in `extra_args`.

## Acceptance criteria

1. All eight migrated tests read `model` from the pytest fixture and pass it through `extra_args`.
2. `make test-static` remains green (the change is behavioral only on live runs, but fixture wiring must not regress the offline suite).
3. Local verification: one of the eight tests run with `--model claude-opus-4-6` actually invokes `claude -p --model claude-opus-4-6` — confirmed via the stream-json assistant `message.model` stamp reading `claude-opus-4-6`, not `claude-opus-4-7`.
4. CI spot-check: rerun the `2.1.111 + model_override=claude-opus-4-6 + effort_override=low` spot-check against `test_standing_teammate_spawn.py::test_standing_teammate_spawns_and_roundtrips` and confirm the `claude-live-opus` job passes in ~2-3 minutes (matching the 2026-04-16 local result).

## Out of Scope

- Removing per-test hardcoded `--effort` or `--max-budget-usd` flags — those are separate concerns.
- Un-migrated tests that still use `run_first_officer` (not `run_first_officer_streaming`) — migrate separately if the same bug applies.
- Changes to `run_first_officer_streaming` itself or `scripts/test_lib.py` helper code.
- Changes to `conftest.py`'s `model` fixture definition — the fixture already exists; this task only plumbs its value into `extra_args`.
