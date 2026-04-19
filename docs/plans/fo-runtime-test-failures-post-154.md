---
id: 198
title: "FO runtime behavior drifts surfaced after #154 cycle-1 (agent_captain, checklist, dispatch_completion)"
status: backlog
source: "PR #131 CI (#154 cycle-1 pre-merge) — after #154 removed the misattributed `pending #154` xfail markers from three tests that have no static FO content reads, each fails 1/N live against claude-live (and/or claude-live-opus)"
started:
completed:
verdict:
score: 0.55
worktree:
issue:
pr:
mod-block:
---

## Problem

Three tests were incorrectly marked `xfail` under `pending #154` by the #148 cycle-6 blanket marker pass. #154 verified none of them read `agents/first-officer.md` content directly; their failures are FO runtime-behavior drifts. This task tracks the three so they can be individually diagnosed and fixed or reclassified.

### `test_agent_captain_interaction` (1/4 FAIL)
- **Failing check**: `ensign was dispatched and produced subagent logs` (line 177)
- FO dispatches agents but no subagent logs found under `~/.claude/projects/<slug>/subagents/` — either the logging path changed, or the FO dispatch pattern no longer produces per-subagent logs in that location.

### `test_checklist_e2e` (1/9 FAIL)
- **Failing check**: `first officer performed checklist review` (line 125) — regex `r"checklist review|checklist.*complete|all.*items.*DONE|items reported"` misses in FO text output.
- After the subagent returns with `### Checklist` structured output, the FO is no longer performing (or emitting text describing) a checklist-review pass.

### `test_dispatch_completion_signal` (1/5 FAIL)
- **Failing check**: `first officer exited cleanly within timeout (no pre-fix hang)` (line 63) — FO exit code != 0 within budget.
- Team-mode dispatch completion-signal flow may be hanging or timing out; could be a regression of the original bug this test was built to catch.

## Out of scope for #154

All three tests have zero static `agents/first-officer.md` content reads; #154's content-home refresh is irrelevant to them. Restoring `pending #198` xfail with this task id tracks the real diagnosis work.

## Acceptance criteria (provisional)

- Each of the three tests individually passes on `make test-live-claude`, OR is surfaced with a narrower task id per test if the root causes diverge
- Subagent-log discovery path documented per `_find_subagent_logs` heuristic
- Checklist-review FO-output pattern refreshed against current FO output style
- Team-mode completion-signal flow verified no-hang on haiku + opus
