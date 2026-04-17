---
id: 180
title: "Fix extra_args plumbing so workflow model_override reaches claude -p in live tests"
status: backlog
source: "from #177 implementation outcome (AC-3 BROKEN, 2026-04-17 session) — workflow input model_override=claude-opus-4-6 was silently dropped because tests/test_standing_teammate_spawn.py:72 hardcodes --model opus and ignores pytest's --model CLI option"
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

This task is the critical-path unblocker for the opus-4-7 cluster (#177, #178, #172):

- **#177** can't conclude its experiment until AC-3 (opus-4-6 negative control) actually runs on opus-4-6. Without that control, we cannot distinguish "boilerplate didn't fix opus-4-7" from "test broken on the stacked branch."
- **#178** can't merge until #177 either confirms the boilerplate works (currently falsified at low/medium per #177's AC-1/AC-2) or we have a clean recommendation in hand.
- **#172** can't reach Layer-3-green CI until claude-live-opus stops failing — which requires either #178 (currently falsified) or pinning opus-4-6 in CI workflow defaults — which requires this plumbing fix to land first so the pin can be proven to work.

## The bug

`tests/test_standing_teammate_spawn.py` at line 72 (and likely other live tests in the same file or neighbors) hardcodes:

```python
extra_args=["--model", "opus", "--effort", effort, "--max-budget-usd", "2.00"]
```

`tests/conftest.py:25,107` already exposes a `--model` pytest CLI option that propagates from `runtime-live-e2e.yml`'s `model_override` workflow input. The plumbing exists; the live test just doesn't consume it.

Result: any CI dispatch with `model_override=claude-opus-4-6` is silently downgraded to `--model opus`, which under Claude Code 2.1.111+ resolves to `claude-opus-4-7`. The model_override workflow input is currently a no-op for this test.

## Proposed fix

Replace the hardcoded `--model opus` in `tests/test_standing_teammate_spawn.py` `extra_args` lists with the value of pytest's `--model` option (defaulting to `opus` if unset, to preserve current behavior). Audit other live tests in `tests/` for the same hardcoding pattern and apply the same fix.

Once landed, re-dispatch #177's AC-3 and confirm the run's `fo-log.jsonl` `assistant.message.model` stamps show `claude-opus-4-6`.

## Out of Scope

- Changing the default model. The fix preserves `--model opus` as the default; only `model_override` cases change behavior.
- Investigating WHY opus-4-7 hallucinates (that's #177's surface).
- Deciding whether to pin opus-4-6 in CI (that's a follow-up after this lands and #177 re-runs cleanly).

## Cross-references

- #177 (opus-4-7 ensign hallucination scope) — this fix unblocks #177's AC-3 negative control
- #178 (tool-call-discipline boilerplate) — disposition depends on #177's clean rerun
- #172 (lazy-spawn) — merge waits on either #178 shipping or opus-4-6 pin landing, both downstream of this fix
- #176 (model_override workflow input) — this is the documented "extra_args plumbing follow-up" referenced in #176's design

## Test plan (for ideation to expand)

- Static test verifying any live test with `extra_args` containing `--model` sources from pytest's `--model` option.
- Re-dispatch of #177's AC-3 after the fix lands, with model stamp verification, as the live integration test.
