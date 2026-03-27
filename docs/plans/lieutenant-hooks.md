---
id: 060
title: Lieutenant hooks — lieutenants inject behavior into the first officer
status: backlog
source: CL
started:
completed:
verdict:
score:
worktree:
---

Currently the PR-aware merge and startup PR detection are hardcoded in the first-officer template. This means every workflow gets PR-related logic in its first officer whether or not it uses a PR lieutenant. The first officer shouldn't know about GitHub PRs — that knowledge belongs to the pr-lieutenant.

## Proposed model

Lieutenants can declare "hooked" behaviors that the first officer reads and adopts at runtime. The first officer's startup checks which lieutenants are in duty (referenced by stages in the README), reads their agent files, and picks up any hooks they declare.

For example, the pr-lieutenant would declare:
- **Startup hook:** scan entities with non-empty `pr` field, check PR state via `gh`
- **Merge hook:** if entity has `pr` field set, check PR state instead of local merge

The first officer doesn't have any PR-specific instructions. It just knows how to read lieutenant hooks and execute them.

## Benefits

- First officer stays generic — no domain-specific logic baked in
- New lieutenants can inject behavior without modifying the first-officer template
- Workflows without PR lieutenants get a simpler first officer
- Follows the same principle as the lieutenant design: methodology belongs in the agent, not the orchestrator
