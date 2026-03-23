---
title: Rename pilot to ensign throughout
status: implementation
source: CL feedback
started: 2026-03-23T20:20:00Z
completed:
verdict:
score:
worktree: .worktrees/ensign-rename-and-test-fixes
---

"Pilot" doesn't fit the variety of stage work (ideation, implementation, validation). "Ensign" is a better match — junior officers assigned whatever task the ship needs.

## Scope

Rename all references to "pilot" (as a worker agent) to "ensign" across:

- `skills/commission/SKILL.md` — template text, first-officer template, pilot prompt → ensign prompt
- `agents/first-officer.md` — reference doc
- `.claude/agents/first-officer.md` — this project's local first-officer
- `v0/test-harness.md` — test documentation
- `v0/test-commission.sh` — test script assertions (any grep for "pilot")
- Worktree paths: `.worktrees/pilot-{slug}` → `.worktrees/ensign-{slug}`
- Branch names: `pilot/{slug}` → `ensign/{slug}`
- Agent names: `pilot-{slug}` → `ensign-{slug}`

Do NOT rename:
- "first officer" — stays as-is
- "captain" — stays as-is
- "pilot run" in Phase 3 of commission — this is the initial test run, not an agent role. Evaluate whether this should change too.
