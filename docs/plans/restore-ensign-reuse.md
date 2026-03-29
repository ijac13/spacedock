---
id: 075
title: Restore ensign reuse across stages (fresh field support)
status: backlog
source: user report during 0.3.0 → 0.8.2 upgrade
started:
completed:
verdict:
score: 0.75
worktree:
---

The `fresh` field in stage definitions is effectively dead in the 0.8.2 FO template. The template always dispatches a new agent per stage (`name="{agent}-{slug}-{stage}"`). The old FO (0.3.0) had explicit reuse logic: advance ensigns via SendMessage by default, `fresh: true` opted into a new agent.

## User report

> Old FO (0.3.0) had explicit reuse logic:
> - Reuse if: next stage has the same worktree mode AND next stage does NOT have `fresh: true`
> - Fresh dispatch if: worktree mode changes, or `fresh: true` is set on the stage
>
> New FO (0.8.2) always dispatches fresh — every stage gets a new agent. There's no `fresh` field support. The only cases where an agent stays alive are feedback-to loops and gate redo.

## Impact

- `fresh: true` in stage definitions is a no-op — misleading for users who set it
- Ensigns lose ambient context between stages (they re-read entity files from scratch)
- Extra file reads and lost context vs. the old reuse behavior
- For many workflows this is fine (entity file carries context), but for workflows with rich ambient state between stages it's a regression

## What the current template does

- Dispatch section step 7: always `Agent(name="{agent}-{slug}-{stage}", ...)` — new agent per stage
- Completion: "If no gate, shut down the agent" (with 068's keep-alive exception for feedback-to)
- No code path checks the `fresh` property on the next stage

## What needs to change

The FO template's completion/dispatch flow should check the next stage's `fresh` property:
- If `fresh: true` on next stage: shut down current agent, dispatch new one (current behavior)
- If `fresh: false` or unset, AND same worktree mode: advance the existing agent to the next stage via SendMessage instead of dispatching fresh
- If worktree mode changes between stages: always dispatch fresh (can't reuse across worktree boundaries)

This interacts with 068 (keep-alive for feedback-to) — the keep-alive logic is a special case of the general reuse pattern.
