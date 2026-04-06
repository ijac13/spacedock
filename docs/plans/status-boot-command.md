---
id: 089
title: Status script --boot flag for FO startup
status: backlog
source: CL — FO startup operator errors (missed mod registration via glob, manual PR checks)
started:
completed:
verdict:
score: 0.8
worktree:
issue:
pr:
---

# Status script --boot flag for FO startup

## Problem

The first officer's startup procedure requires multiple deterministic file/git scanning steps that it currently performs manually via glob patterns, grep, and bash pipelines. This is error-prone — in the session that spawned this task, the FO missed mod registration entirely because it used the wrong glob pattern (`_mods/*.md` with a `path` parameter instead of `{workflow_dir}/_mods/*.md` from the working directory).

Current FO startup steps that are pure deterministic scanning:

1. **Mod discovery** — scan `_mods/*.md` for `## Hook:` headings, register by lifecycle point
2. **Next sequential ID** — scan active + archive for highest ID
3. **Orphaned worktree detection** — cross-reference entity `worktree` fields against `git worktree list`
4. **PR state checking** — `gh pr view` for entities with non-empty `pr` field and non-terminal status
5. **Dispatchable entities** — already handled by `--next`

Each of these is a separate tool call the FO can get wrong. The status script already parses README frontmatter and entity frontmatter — it should do all of this in one reliable call.

## Proposed approach

Add a `--boot` flag to the status script that outputs all startup information in one call:

```
$ python3 skills/commission/bin/status --workflow-dir docs/plans --boot
```

### Output sections

**Mods** — scan `{workflow_dir}/_mods/*.md`, extract `## Hook: {point}` headings, report hooks grouped by lifecycle point (startup, idle, merge) in alphabetical order by mod filename.

```
MODS
startup: pr-merge
idle: pr-merge
merge: pr-merge
```

If `_mods/` doesn't exist or has no mods: `MODS: none`

**Next ID** — scan active entities and `_archive/` for highest numeric ID, report next available.

```
NEXT_ID: 089
```

**Orphaned worktrees** — entities with non-empty `worktree` field, cross-referenced against `git worktree list`. Report whether the worktree directory actually exists and whether the branch exists.

```
ORPHANS
ID     SLUG                           WORKTREE                                    DIR_EXISTS  BRANCH_EXISTS
086    gate-rejection-feedback-routing .worktrees/ensign-gate-rejection-feedback    yes         yes
054    session-debrief                .worktrees/ensign-054-session-debrief         yes         yes
058    terminology-experiment         .worktrees/ensign-terminology-exp             yes         yes
```

If no orphans: `ORPHANS: none`

**PR state** — entities with non-empty `pr` field and non-terminal status. Runs `gh pr view` for each. If `gh` is unavailable, reports that and skips.

```
PR_STATE
ID     SLUG                           PR       STATE
085    agent-boot-skill-preload       #29      MERGED
```

If no PR-pending entities: `PR_STATE: none`
If `gh` unavailable: `PR_STATE: gh not available`

**Dispatchable** — same as existing `--next` output.

```
DISPATCHABLE
ID     SLUG                           CURRENT              NEXT                 WORKTREE
```

### Implementation notes

- Pure Python 3 stdlib except for `gh` (subprocess call, gracefully skipped if missing)
- `git worktree list` via subprocess for orphan cross-referencing
- Mod scanning uses `glob.glob()` on `{workflow_dir}/_mods/*.md` — no LLM glob patterns involved
- `## Hook:` extraction is line-by-line text scanning, same approach as frontmatter parsing
