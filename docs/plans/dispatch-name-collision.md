---
id: 051
title: First-officer must use unique ensign names per dispatch
status: implementation
source: https://github.com/clkao/spacedock/issues/1
started: 2026-03-27T05:50:00Z
completed:
verdict:
score:
worktree: .worktrees/ensign-dispatch-name-collision
---

When the first officer dispatches agents using the Agent tool, it reuses the same name (e.g., `{agent}-{slug}`) across sequential dispatches for the same entity. This causes shutdown request collisions: a pending `shutdown_request` sent to agent name `X` gets delivered to a newly spawned agent that reuses name `X`, killing it immediately.

## Reproduction

1. First officer dispatches `ensign-my-task` for stage A
2. Stage A completes. First officer sends `shutdown_request` to `ensign-my-task`
3. Before shutdown is fully processed, first officer dispatches a new agent with the **same name** `ensign-my-task` for stage B
4. The queued shutdown request arrives and the new agent approves it, terminating itself

## Root Cause

`SendMessage` routes by agent **name**, not agent ID. Shutdown requests queue and get delivered to whatever agent currently holds that name. Reusing a name before the previous shutdown completes causes the new agent to inherit the pending shutdown.

## Fix

The first-officer template dispatch should include the stage name in the agent name:

```
name="{agent}-{slug}-{stage}"
```

This ensures each dispatch gets a fresh name with no inherited shutdown requests.

## Affected File

`templates/first-officer.md` — the dispatch section where the agent name is set.

## Ideation Analysis

### Template audit — all places `{agent}-{slug}` appears in `templates/first-officer.md`

| Line | Context | Pattern | Needs stage suffix? |
|------|---------|---------|---------------------|
| 29 | Worktree path in frontmatter | `.worktrees/{agent}-{slug}` | No — worktrees are per-entity, one at a time |
| 29 | Branch name | `{agent}/{slug}` | No — branches are per-entity |
| 36 | **Agent dispatch name** | `name="{agent}-{slug}"` | **Yes — this is the collision point** |
| 75 | Merge — derives branch from worktree field | `{agent}/{slug}` | No — per-entity |
| 77 | Cleanup — worktree remove + branch delete | `.worktrees/{agent}-{slug}`, `{agent}/{slug}` | No — per-entity |

**Conclusion**: Only the dispatch `name=` on line 36 needs the stage suffix. Worktree paths and branch names are entity-scoped (one worktree per entity at a time), so they don't collide across stages.

### Edge cases considered

1. **Worktree naming** — Not affected. A worktree is created once per entity and reused across worktree stages. The worktree path is stored in the entity's frontmatter `worktree:` field, so the first officer reads it back — no name derivation needed.

2. **Merge/cleanup references** — Not affected. Merge derives the branch name from the `worktree` frontmatter field (line 75). Cleanup uses the same entity-scoped pattern. Neither references the dispatch agent name.

3. **Live first-officer at `.claude/agents/first-officer.md`** — This is a generated file, produced by the commission skill from `templates/first-officer.md`. It currently has the same bug (`name="ensign-{slug}"` on line 35). Fixing the template fixes all future commissions. Existing live first-officers get the fix via `refit`. This task should NOT directly edit `.claude/agents/first-officer.md`.

4. **Gate redo flow** — When a gate rejects with redo, the first officer sends feedback to the same agent (no new dispatch), so no name collision. Only fresh dispatches are affected.

5. **Stage names with special characters** — Stage names are defined in README frontmatter as YAML keys, which are typically simple identifiers (e.g., `ideation`, `implementation`, `validation`). No sanitization needed.

### Proposed change

In `templates/first-officer.md`, line 36:

```
- name="{agent}-{slug}",
+ name="{agent}-{slug}-{stage}",
```

Where `{stage}` is the `next_stage_name` variable already available in the dispatch context (it appears in the prompt on line 38).

Single-line change. No other files in this fix scope.

## Acceptance Criteria

1. `templates/first-officer.md` dispatch `name=` includes `{stage}` — pattern becomes `name="{agent}-{slug}-{stage}"`
2. No other naming patterns changed (worktree paths, branch names, merge/cleanup references remain `{agent}-{slug}`)
3. Existing test passes: `scripts/test-commission.sh` line 233 checks `grep -E 'name=.*\{.*stage'` on the generated first-officer
4. `.claude/agents/first-officer.md` is NOT directly edited (gets fix via refit)

## Stage Report: ideation

- [x] Problem statement confirmed with evidence from the template
  `templates/first-officer.md` line 36: `name="{agent}-{slug}"` reuses the same name across stages, causing shutdown_request collisions via SendMessage name-based routing
- [x] Fix approach defined with specific changes to `templates/first-officer.md`
  Single change on line 36: `name="{agent}-{slug}"` -> `name="{agent}-{slug}-{stage}"` using the existing `next_stage_name` variable
- [x] Edge cases considered (worktree naming, merge/cleanup, the live first-officer at `.claude/agents/first-officer.md`)
  Audited all 5 occurrences of `{agent}-{slug}` in the template; only dispatch name needs the suffix. Worktree/branch/merge/cleanup are entity-scoped and unaffected. Live first-officer gets fix via refit.
- [x] Acceptance criteria written (including the existing failing test)
  4 criteria covering template change, no-change guardrails, test-commission.sh line 233, and refit-only policy for live agent
- [x] No scope creep — fix is limited to the name collision bug
  Single-line change in one file. No new features, no worktree renaming, no branch renaming.

### Summary

Audited all occurrences of the `{agent}-{slug}` naming pattern in `templates/first-officer.md`. Confirmed the collision is dispatch-name-only (line 36) — worktree paths, branch names, and merge/cleanup references are entity-scoped and do not collide across stages. The fix is a single-line change adding `{stage}` to the dispatch name. The existing test at `scripts/test-commission.sh:233` already validates this pattern and will pass once the fix is applied.

## Stage Report: implementation

- [x] `templates/first-officer.md` dispatch `name=` changed to include `{stage}` for per-dispatch uniqueness
  Line 36 changed from `name="{agent}-{slug}"` to `name="{agent}-{slug}-{stage}"`
- [x] No other naming patterns changed (worktree paths, branch names, merge/cleanup references remain `{agent}-{slug}`)
  Verified lines 29, 30, 75, 77 still use `{agent}-{slug}` without stage suffix
- [x] `.claude/agents/first-officer.md` is NOT directly edited
  Only `templates/first-officer.md` was modified
- [x] All changes committed to the worktree
  All changes committed to ensign/dispatch-name-collision branch
- [x] E2E test at `tests/test-dispatch-names.sh` validates dispatch name uniqueness at runtime
  Commissions a no-gate pipeline (backlog->work->review->done), runs the first officer, parses stream-json log for Agent() calls, verifies all dispatch names are unique and include stage suffix. Fixture at `tests/fixtures/no-gate-pipeline/`. Budget cap $2.

### Summary

Applied the single-line fix to `templates/first-officer.md` line 36, changing the dispatch name pattern from `{agent}-{slug}` to `{agent}-{slug}-{stage}`. All 61 tests in `scripts/test-commission.sh` pass, including the specific guardrail check for stage-unique dispatch names. No other naming patterns were modified. Added E2E test `tests/test-dispatch-names.sh` with a no-gate pipeline fixture that runs the first officer through multiple stages and validates each Agent() dispatch used a unique name.
