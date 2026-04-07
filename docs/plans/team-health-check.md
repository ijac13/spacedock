---
id: 093
title: Team health check before dispatch
status: ideation
source: "CL — observed in session 2026-04-07, team config.json missing while team still active in memory"
started: 2026-04-07T00:00:00Z
completed:
verdict:
score: 0.75
worktree:
issue:
pr:
---

# Team health check before dispatch

The FO should verify team health before dispatching agents, not just at startup. Observed failure mode: team directory exists with `inboxes/` but `config.json` is missing. This creates an inconsistent state:

- **"Already leading team"** — in-memory session state knows we created it
- **"Team does not exist"** on Agent dispatch — dispatch checks `config.json`, finds nothing
- **SendMessage works** — routes via inboxes, doesn't need config.json

Result: can message existing agents but can't dispatch new ones. The 091 sequencing fix (TeamDelete → TeamCreate) doesn't help here because the FO doesn't know the team is broken until a dispatch fails.

## Observed behavior

1. Team `generic-tinkering-lake` created at session start, agents dispatched successfully
2. Hours later, `config.json` disappeared (possibly cleaned up by a test run or timing issue)
3. Agent dispatch failed with "Team does not exist"
4. TeamCreate failed with "Already leading team"
5. SendMessage to existing agents still worked

## Proposed fix

Add a team health check to the dispatch flow in `claude-first-officer-runtime.md`:

1. Before dispatching agents, verify `config.json` exists for the current team
2. If missing: TeamDelete (clears in-memory state) → TeamCreate → resume dispatch
3. This check should happen per-dispatch, not just at startup, since the config can disappear mid-session
