---
id: 033
title: First-officer graceful degradation without agent teams
status: backlog
source: testflight sd11-test observation
started:
completed:
verdict:
score: 0.80
worktree:
---

The generated first-officer requires CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 (research preview, v2.1.32+). Without teams, TeamCreate and SendMessage don't exist, so the first-officer's current dispatch pattern fails at startup step 1.

## Findings from sd11-test

- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=0` disabled teams for `claude -p` commission (no TeamCreate/Agent/SendMessage in tool calls)
- But `claude -p --agent first-officer` still had teams available — the env var may not propagate to agent mode, or agent mode enables teams automatically
- The commission skill itself doesn't need teams (it's file generation + Bash)
- The first-officer needs teams for: TeamCreate (step 1), Agent with team_name (dispatch), SendMessage (shutdown_request, redo feedback)

## What works without teams (from release notes)

- Agent() tool exists as parent-child subagent dispatch (v1.0.60+)
- Subagent output returns to parent context when the subagent completes
- `isolation: "worktree"` works without teams (v2.1.49)
- Background agents work without teams (v2.0.60)

## Degraded mode design

Without teams, the first-officer could still function:

1. Skip TeamCreate entirely (no team to create)
2. Dispatch ensigns via Agent() WITHOUT team_name — ensign runs as a subagent, output returns to first-officer context when done
3. No SendMessage for completion — the first-officer sees the ensign's output directly when the Agent() call returns
4. No SendMessage for shutdown — ensign exits naturally when its Agent() call completes
5. No SendMessage for redo — dispatch a new Agent() with feedback appended to the prompt

The trade-off: without teams, ensigns can't run in parallel. Each Agent() call blocks until the ensign completes. The first-officer processes one entity at a time instead of dispatching multiple ensigns and handling completion messages asynchronously.

## What needs to change

The first-officer template should detect whether teams are available and branch:
- If TeamCreate succeeds: current team-based dispatch (parallel, async)
- If TeamCreate fails or isn't available: fall back to sequential subagent dispatch (Agent() without team_name, blocking)

Or: make sequential dispatch the default and only use teams when explicitly enabled. This would make the first-officer work everywhere out of the box.
