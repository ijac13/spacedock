---
id: 117
title: FO DISPATCH IDLE GUARDRAIL flake on haiku — premature ensign shutdown in nested test
status: ideation
source: Validator observation during 115 validation (run 1 of test_dispatch_completion_signal.py)
started: 2026-04-11T04:45:04Z
completed:
verdict:
score: 0.70
worktree:
issue:
pr:
---

During validation of task 115, the validator ensign observed a flake in `tests/test_dispatch_completion_signal.py` when run on the haiku model: run 1 failed, run 2 passed cleanly. Investigation showed the failure is **not** caused by the 115 fix but by an independent FO behavior issue.

## What was observed

- **Run 1 (FAILED):** wallclock 72s, FO exited cleanly (exit 0), the dispatched ensign's prompt did carry the `SendMessage(to="team-lead", ...)` completion-signal instruction (verified via `agent-prompts.txt`), but at event ~65 in `fo-log.jsonl` the FO tore down the team without waiting for the ensign's SendMessage. The entity remained at `status: work`. The ensign had already written its deliverable to the worktree before being killed.
- **Run 2 (PASSED):** wallclock 260s, exit 0, all 5 checks green, entity archived without manual captain intervention.

## Why this matters

The DISPATCH IDLE GUARDRAIL in `skills/first-officer/references/claude-first-officer-runtime.md` explicitly tells the FO to ignore idle notifications and wait for an explicit completion message. The validator confirmed the guardrail wording is correct. The failure mode is that **haiku does not reliably honor the guardrail** — after dispatching the ensign and going into "Standing by", the FO ran a few Bash/Read cycles and then decided to tear down the team early, despite no completion message having arrived.

This is orthogonal to 115's template fix. 115 was about "the ensign has no instruction to SendMessage on completion." 117 is about "the FO, on haiku, decides to give up waiting too early even when the guardrail says not to."

## Hypotheses to explore in ideation

1. **Guardrail wording is not strong enough for haiku.** The current wording might need tightening or explicit examples.
2. **Haiku exhibits different idle-tolerance behavior than sonnet/opus.** The guardrail was likely authored with larger models in mind.
3. **Idle notification frequency** may be high enough on haiku that the model loses the "don't react" invariant over many repeated events.
4. **Tool-use cycles between dispatch and completion** (FO running Bash/Read while waiting) may be eroding the wait posture on haiku in a way it does not on larger models.

## Why track separately from 115

- 115 is a narrow template fix; the PR should not be held up by a model-reliability investigation
- The flake is reproducible only on haiku under the nested test harness; it does not affect interactive sessions on opus/sonnet where the captain watches the FO
- The fix surface is likely different — probably FO runtime reference wording, possibly a hook, possibly an upstream Claude Code behavior issue

## Scope for ideation

- Reproduce the flake deterministically (how often does it fire? what triggers it?)
- Inspect the `fo-log.jsonl` from a failing run to understand the exact decision path that led to early teardown
- Decide remediation: stronger guardrail wording, explicit "wait until SendMessage" instruction in the dispatch flow, a watchdog check before teardown, or an upstream Claude Code fix
- Scope should NOT expand to the broader telemetry/watchdog idea — that is a separate direction

## Related

- Task 115 `fo-dispatch-template-completion-signal` — the validator surfaced this while verifying 115. 115's fix is correct and complete; this is a sibling issue, not a prerequisite.
- `skills/first-officer/references/claude-first-officer-runtime.md` — the DISPATCH IDLE GUARDRAIL section is the most likely fix surface.
