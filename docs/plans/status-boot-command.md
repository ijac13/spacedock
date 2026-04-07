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

## Boot Sequence Observations (2026-04-07 session)

Actual FO startup consumed ~16 tool calls across 6 parallel batches. Breakdown:

1. **Mod discovery** (2 calls) — Glob `_mods/*.md` + Read each file for `## Hook:` headings. Pure deterministic scanning, easily moved to the script.

2. **Debrief discovery** (2 calls) — Glob `_debriefs/*.md` + Read latest file. The glob/sort is deterministic; reading the content still requires a Read call. The `--boot` output could report the latest debrief filename so the FO only needs one Read.

3. **Orphan worktree detection** (1 call) — `status --where "worktree !="` works but doesn't cross-reference against `git worktree list` or filesystem existence. The FO has to trust that the worktree path in frontmatter is still valid.

4. **PR state checking** (9 calls — biggest bottleneck) — `--where "pr !="` returns entity rows but the `pr` field isn't in the output columns. The FO had to Read 4 entity files individually just to extract PR numbers, then run `gh pr view` for each. Moving PR extraction + `gh pr view` into the script eliminates 8 of 9 calls.

5. **Dispatchable** (1 call) — `status --next` already handled.

6. **Full status for reporting** (1 call) — `status` for the captain report.

### Key insight

The `--boot` flag should collapse steps 1–5 into a single call. The FO's startup would become:
1. `status --boot` (1 call)
2. Read latest debrief if filename reported (1 call)
3. Act on PR_STATE results (advance merged PRs — edit + archive + commit)
4. Report to captain

That's 2 tool calls for information gathering instead of ~15.
