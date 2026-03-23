---
title: Team state recovery on startup
status: backlog
source: testflight-005
started:
completed:
verdict:
score: 0.75
worktree:
---

The first officer should check for stale team state before calling TeamCreate. If a prior session crashed or was resumed, `~/.claude/teams/{team_name}/` may exist on disk with orphaned inbox files but no live team leader. TeamCreate then fails with conflicting errors ("already leading" from in-memory state vs "doesn't exist" from missing config.json).

## Problem

Observed in testflight-005: session used `--resume` after a crash. The team directory survived but had no config.json. The first officer's in-memory TeamCreate from session start conflicted with the corrupted on-disk state. All subsequent Agent spawns with `team_name` failed — couldn't create new team or use existing one.

## Proposed fix

Add to first-officer Startup step 1 (before TeamCreate):
1. Check if `~/.claude/teams/{dir_basename}/` exists
2. If it does, remove it (stale from prior session — all team members are dead)
3. Then call TeamCreate

This should go in both:
- `skills/commission/SKILL.md` — the first-officer template Startup section
- `.claude/agents/first-officer.md` — the local first-officer (via refit or manual edit)

## Note on local first-officer changes

Any semantic change to `.claude/agents/first-officer.md` that isn't in the SKILL.md template will be lost on refit. When making local changes, document them in a changelog section at the bottom of the file so future refits can re-apply them. This applies to: team state recovery, ideation-on-main worktree fix, ensign rename, and any other local-only patches.
