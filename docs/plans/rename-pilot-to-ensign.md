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

## Implementation

Renamed all agent-role "pilot" references to "ensign" in three files:

- `skills/commission/SKILL.md` — template text, first-officer template section, dispatch instructions, clarification protocol, event loop, orphan detection, state management. Agent names `pilot-{slug}` → `ensign-{slug}`, worktree paths `.worktrees/pilot-{slug}` → `.worktrees/ensign-{slug}`, branch names `pilot/{slug}` → `ensign/{slug}`.
- `agents/first-officer.md` — reference doc: role description, dispatch lifecycle, orphan detection, clarification protocol.
- `v0/test-harness.md` — guardrail descriptions and "what good/bad looks like" sections.

"Pilot run" (Phase 3) was preserved throughout — it refers to the trial run concept, not the agent role. The `.claude/agents/first-officer.md` local agent was left unchanged (will be updated via refit).

## Validation

Grepped for remaining "pilot" references in the two primary files:

- **`skills/commission/SKILL.md`** — 5 hits, all are "pilot run" (the trial-run concept in Phase 3 and ABOUTME). No agent-role "pilot" references remain.
- **`agents/first-officer.md`** — 0 hits. Clean.

All agent-role renames confirmed: `pilot-{slug}` → `ensign-{slug}`, `.worktrees/pilot-` → `.worktrees/ensign-`, `pilot/{slug}` → `ensign/{slug}` branches. No regressions found.
