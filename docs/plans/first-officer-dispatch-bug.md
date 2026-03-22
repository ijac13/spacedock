---
title: First Officer Dispatch Bug
status: ideation
source: testflight-001
started:
completed:
verdict:
score:
---

## Problem

During testflight-001, the first officer spawned 3 agents all typed as `first-officer` instead of dispatching pilots as `subagent_type="general-purpose"`. The Claude Code UI showed:

```
@first-officer: 0 tool uses · 44.8k tokens    (coordinator — did nothing)
@first-officer: 38 tool uses · 53.3k tokens   (did ideation work)
@first-officer: 39 tool uses · 55.6k tokens   (did ideation work)
```

The first officer is supposed to be a DISPATCHER that never does stage work itself. Instead it cloned itself, wasting tokens on duplicate agent prompts and confusing the team UI.

Additionally, the first officer sent 3 redundant status reports while waiting at the approval gate instead of reporting once and staying idle.

## Evidence

Session logs in `testflight-001/` — main session + 4 subagent JSONL files.

## Proposed Fix

1. Make the first-officer prompt more explicit: "You MUST use `subagent_type='general-purpose'` when dispatching pilots. NEVER use `subagent_type='first-officer'`."
2. Add a "report once then wait" instruction for approval gates — no re-reporting the same state.
3. Consider whether the dispatch template in the first-officer should be a verbatim code block rather than pseudocode, to reduce misinterpretation.

## Acceptance Criteria

- [ ] First officer dispatches pilots as `subagent_type="general-purpose"` with distinct names like `pilot-{slug}`
- [ ] Only one first-officer agent appears in the team UI
- [ ] First officer reports pipeline state once at an approval gate, then waits without re-reporting
- [ ] Validated in testflight-002
