---
title: Stage-specific worktree requirements in pipeline schema
status: backlog
source: testflight-004
started:
completed:
verdict:
score: 0.65
worktree:
---

Stages have properties beyond just ordering — human-approval gates on certain transitions, and whether work happens on main or in an isolated worktree. Currently the pipeline README defines stages as a flat list with `Human approval: Yes/No` noted in prose. The worktree requirement isn't declared at all — it's hardcoded in the first-officer dispatch logic.

Both of these are stage-level properties that should be declarable in the README schema, so the commission skill can generate correct first-officer behavior for any pipeline configuration.

Discovered when ideation was unnecessarily running in worktrees. A crashed session left an orphaned worktree requiring manual cleanup — work that would have been safely on main if the stage declared `worktree: false`.

## Stage properties to formalize

| Property | Current state | Goal |
|----------|--------------|------|
| Human approval gate | Noted in prose per stage | Declared in stage definition, first-officer reads it |
| Worktree isolation | Hardcoded for all dispatches | Declared per stage, first-officer creates worktree only when needed |

## What to fix

The commission skill's SKILL.md template and README schema need to support per-stage properties:

- README stage definitions: add structured fields for `approval_required` and `worktree` (or similar)
- SKILL.md template (section 2d): first-officer reads these properties from the README rather than hardcoding which stages need approval or worktrees
- Generated first-officer agent: dispatch logic branches on stage properties instead of stage names
