---
title: Team state recovery on startup
status: implementation
source: testflight-005
started: 2026-03-24T16:00:00Z
completed:
verdict:
score: 0.75
worktree: .worktrees/ensign-team-state-recovery
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

## Validation Report

All six criteria checked against commit `6f8a9f3`:

| Criterion | Result |
|-----------|--------|
| Project-scoped team name | PASS — Startup step 1 uses `{project_name}-{dir_basename}` for both TeamCreate and the cleanup `rm -rf` path |
| Try-then-recover | PASS — TeamCreate is attempted first; cleanup and retry only happen on failure, not preemptively |
| Agent dispatch templates | PASS — Both "Worktree: No" (line ~415) and "Worktree: Yes" (line ~447) Agent() calls use `team_name="{project_name}-{dir_basename}"` |
| {project_name} variable | PASS — Derived in Confirm Design (Phase 1) as basename of git repo root via `git rev-parse --show-toplevel`, with cwd fallback |
| No .claude/agents/ changes | PASS — `git diff` shows only `skills/commission/SKILL.md` modified |
| Test harness | PASS — 42/42 confirmed |

**Verdict: PASSED** — All criteria satisfied. The implementation correctly scopes team names to avoid cross-project collisions and uses try-then-recover (not preemptive cleanup) for stale team state.
