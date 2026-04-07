---
id: 091
title: TeamCreate failure causes duplicate agent dispatch
status: ideation
source: CL — observed in recce-gtm session, 3x duplicate agents per entity
started: 2026-04-06T00:00:00Z
completed:
verdict:
score: 0.8
worktree:
issue:
pr:
---

# TeamCreate failure causes duplicate agent dispatch

When TeamCreate fails (e.g., "Already leading team X"), the first officer retries team setup but also dispatches Agent calls in the same tool-call message. Since Claude Code executes all tool calls in a message in parallel, the Agent calls run regardless of the TeamCreate failure. Each retry spawns another batch of agents, producing duplicates that all write to the same entity files.

## Observed behavior

From a recce-gtm discovery-outreach session:

1. FO dispatches agents with `team_name` — agents spawn as `spacedock-ensign-{slug}-draft`
2. Team expires. FO tries TeamCreate, gets "Already leading team" error
3. FO batches TeamDelete + TeamCreate + Agent calls in same message — TeamCreate fails again, but agents spawn as `ensign-{slug}-draft`
4. FO retries again — more agents spawn as `@ensign-{slug}`
5. Result: 3 copies of each agent running simultaneously, all hitting the same entity files

## Root cause

The `claude-first-officer-runtime.md` has no guidance for:
- What to do when TeamCreate fails mid-session
- That team lifecycle calls and Agent dispatch calls must never share a tool-call message (since parallel execution means failure of one doesn't prevent the others)

## The fix

Two changes to `references/claude-first-officer-runtime.md`:

1. **Team Creation section**: Add TeamCreate failure recovery — "Already leading team" → TeamDelete in its own turn, then retry TeamCreate in a subsequent turn. Other failures → fall back to bare mode. Block all Agent dispatch until team setup resolves.

2. **Dispatch Adapter section**: Add explicit sequencing rule — team lifecycle calls (TeamCreate, TeamDelete) and Agent dispatch calls must NEVER appear in the same tool-call message.
