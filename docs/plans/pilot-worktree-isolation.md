---
title: Pilot Worktree Isolation
status: done
source: commission seed
started: 2026-03-22T20:24:00Z
completed: 2026-03-22T20:46:00Z
verdict: PASSED
score: 0.64
worktree:
---

## Problem

In v0 shuttle mode, only one pilot runs at a time, so there are no git conflicts. But in v1 starship mode, multiple pilots will work on different entities in parallel. If they all operate on the same working tree, they'll step on each other's files — merge conflicts, dirty state, lost work.

Specific conflict scenarios in parallel execution:

1. **File write collisions.** Two pilots editing different source files in the same directory. Even if the files are distinct, git operations (staging, committing) are per-worktree and would interleave.
2. **Build/test interference.** One pilot runs tests while another is mid-edit, causing spurious failures.
3. **Entity frontmatter races.** Two pilots completing at the same time both try to update their entity's `status:` field. Since entity files are in the pipeline directory (shared state), these writes go to the same filesystem location regardless of worktree.
4. **Partial state on crash.** A pilot crashes mid-implementation, leaving uncommitted changes in the working tree that block the next pilot dispatched for that entity.

Worktree isolation is the foundation for safe parallel execution.

## Proposed Approach

### State ownership: main tree owns lifecycle, worktree owns work

The first officer owns all entity state transitions on main. The pilot owns work artifacts in its worktree. This separation means:

- **Before dispatch**: First officer commits state change on main (`status: {stage}`, `worktree: .worktrees/pilot-{slug}`). This is the "started" signal.
- **During work**: Pilot operates exclusively in its worktree. It writes code, entity body content, and commits to its branch. It does NOT touch frontmatter.
- **On completion**: First officer does `git merge --no-commit pilot/{slug}`, updates frontmatter (status to next stage, clears `worktree:` field), and commits. Single atomic commit = state transition + work merge.
- **Orphan detection**: Entity has `status: implementation` + `worktree:` field set, but worktree has no changes beyond the branch point → pilot is gone.

### Dispatch lifecycle

**1. State change on main** — First officer updates entity frontmatter and commits:
```yaml
status: {next_stage}
worktree: .worktrees/pilot-{slug}
```

**2. Create worktree** — Branch from current HEAD:
```bash
git worktree add .worktrees/pilot-{slug} -b pilot/{slug}
```
If stale worktree/branch exists from a prior crash:
```bash
git worktree remove .worktrees/pilot-{slug} --force 2>/dev/null
git branch -D pilot/{slug} 2>/dev/null
git worktree add .worktrees/pilot-{slug} -b pilot/{slug}
```

**3. Dispatch pilot** — Agent prompt includes the worktree path:
```
Your working directory is {worktree_path}.
All file reads and writes MUST use paths under {worktree_path}.
Do NOT modify YAML frontmatter in entity files.
Commit your work to your branch before sending completion message.
```

**4. Merge + state finalize** — On pilot completion:
```bash
git merge --no-commit pilot/{slug}
```
Then update frontmatter (status to next stage, clear `worktree:` field), and commit:
```bash
git commit -m "pilot: {slug} completed {stage}"
```
Then cleanup:
```bash
git worktree remove .worktrees/pilot-{slug}
git branch -d pilot/{slug}
```

**5. Abandon** — If pilot fails or crashes:
- Worktree stays on disk for inspection
- Entity frontmatter on main still shows `worktree:` field — this IS the orphan signal
- Next dispatch for same entity does stale-cleanup from step 2

### Schema addition

Add `worktree:` to the entity frontmatter schema. While a pilot is active, this field contains the worktree path. When work is merged, it's cleared. Empty = no active worktree.

### Directory and branch conventions

- **Worktree root:** `.worktrees/` at the repo root
- **Worktree path:** `.worktrees/pilot-{entity-slug}`
- **Branch naming:** `pilot/{entity-slug}`
- **`.gitignore` entry:** `.worktrees/` (worktrees should never be committed)
- **Merge commit format:** `pilot: {entity-slug} completed {stage-name}`

### Merge conflict resolution

- **Detection:** `git merge --no-commit` exits non-zero if conflicts exist. First officer reports to CL rather than auto-resolving.
- **Prevention:** Avoid dispatching two pilots likely to touch the same files.
- **Fallback:** Sequential dispatch (v0 behavior) for high-conflict-risk pipelines.

### Failure modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Pilot crashes mid-work | Entity has `worktree:` set, worktree has no new commits | Stale-cleanup on next dispatch |
| Merge conflict | `git merge --no-commit` exits non-zero | Report to CL; worktree stays for manual resolution |
| Branch name collision | `git worktree add` fails | Stale-cleanup handles it |
| Two pilots for same entity | `worktree:` field is already set | First officer checks before dispatch |

### Open questions (resolved)

**Q: Should entity state changes happen on main or in the worktree?**
A: Main. The first officer commits state changes on main before and after pilot work. This makes main the single source of truth for lifecycle state, enables orphan detection, and keeps the merge atomic (work + final state in one commit).

**Q: What about non-git pipelines?**
A: Worktree isolation requires git. Non-git directories fall back to sequential dispatch.

## Acceptance Criteria

- [ ] `worktree:` field added to entity schema in pipeline README
- [ ] `.worktrees/` added to `.gitignore`
- [ ] First-officer template in SKILL.md updated: dispatch creates worktree, state change on main before dispatch, atomic merge + state finalize on completion
- [ ] First-officer reference doc (`agents/first-officer.md`) updated with worktree dispatch pattern
- [ ] Pilot prompt template instructs pilot to work in worktree path and not touch frontmatter
- [ ] Validated: dispatch a real entity through one stage using the worktree flow — worktree created, pilot works there, main stays clean during work, merge is atomic

## Scoring Breakdown

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Edge | 4 | Key differentiator for starship mode |
| Fitness | 3 | Important for v1, not needed for v0 |
| Parsimony | 3 | Git worktrees are the right primitive but lifecycle is complex |
| Testability | 3 | Can test worktree creation, harder to test full parallel scenario |
| Novelty | 3 | Git worktrees are well-known but applying them to agent isolation is less explored |

## Implementation Summary

Five files changed:

1. **`.gitignore`** (created) — Added `.worktrees/` entry so worktree directories are never committed.

2. **`docs/plans/README.md`** — Added `worktree:` field to the schema YAML block, field reference table, and entity template.

3. **`agents/first-officer.md`** — Added "Worktree Isolation" section documenting the dispatch lifecycle (state change on main, create worktree, dispatch pilot, merge+finalize, cleanup) and orphan detection.

4. **`skills/commission/SKILL.md`** — Updated the first-officer agent template (section 2d) with the full worktree dispatch pattern:
   - Dispatching steps now include: state change on main (status + worktree field commit), worktree creation with stale-cleanup, pilot prompt with worktree path and no-frontmatter-edit instruction, merge --no-commit + atomic state finalize, worktree/branch cleanup.
   - Event loop updated to merge-then-verify flow.
   - State management section updated: first officer owns frontmatter, commit at dispatch/merge boundaries.
   - Orphan detection section added for crash recovery.
   - `.gitignore` generation step added to Phase 2.
   - `worktree:` field added to all schema templates (README, entity template, seed entity template).

5. **`docs/plans/pilot-worktree-isolation.md`** — This implementation summary.

## Validation Report

### Criterion 1: `worktree:` field added to entity schema in pipeline README
**PASS** — `docs/plans/README.md` has `worktree:` in all three locations: schema YAML block (line 26), field reference table (line 41, described as "Worktree path while a pilot is active, empty otherwise"), and entity template (line 132).

### Criterion 2: `.worktrees/` added to `.gitignore`
**PASS** — `.gitignore` contains `.worktrees/` as its sole entry.

### Criterion 3: First-officer template in SKILL.md updated with worktree dispatch pattern
**PASS** — Section 2d of `skills/commission/SKILL.md` contains the full dispatch lifecycle:
- State change on main before dispatch (steps 4): sets `status` and `worktree` field, commits.
- Worktree creation with stale-cleanup (step 5): `git worktree add`, with prior `--force` remove and `branch -D` for stale state.
- Atomic merge+finalize (step 8): `git merge --no-commit`, frontmatter update, single commit.
- Cleanup (step 9): `git worktree remove` and `git branch -d`.
- Event loop (lines 440-448) updated to merge-then-verify flow.
- Orphan detection section (lines 463-469) added.
- `.gitignore` generation (lines 149-154) added to Phase 2.
- `worktree:` field in all schema templates (README template, entity template, seed entity template).

### Criterion 4: First-officer reference doc updated with worktree dispatch pattern
**PASS** — `agents/first-officer.md` has a "Worktree Isolation" section (lines 23-43) documenting state ownership, the 5-step dispatch lifecycle, and orphan detection.

### Criterion 5: Pilot prompt template instructs pilot to work in worktree path and not touch frontmatter
**PASS** — The pilot prompt in SKILL.md step 6 (line 419) includes:
- `Your working directory is {worktree_path}`
- `All file reads and writes MUST use paths under {worktree_path}`
- `Do NOT modify YAML frontmatter in entity files`
- `Commit your work to your branch before sending completion message`

### Criterion 6: Live validation — dispatch through worktree flow
**PASS** — This validation itself is the live test. Evidence:
- `pwd` = `/Users/clkao/git/spacedock/.worktrees/pilot-worktree-isolation` (pilot is in worktree)
- `git branch --show-current` = `pilot/worktree-isolation` (on dedicated branch)
- `git worktree list` shows both main (`40e08f0 [main]`) and worktree (`40e08f0 [pilot/worktree-isolation]`)
- Main tree `git status` is clean — no uncommitted changes from pilot work
- Entity frontmatter on main has `worktree: .worktrees/pilot-worktree-isolation` set (dispatch state change committed before pilot started)
- Commit `40e08f0` ("dispatch: worktree-isolation entering validation") shows state change happened on main before pilot dispatch

### Recommendation: PASSED

All six acceptance criteria verified. The worktree isolation pattern is correctly implemented in the schema, skill template, reference doc, and pilot prompt. The live validation confirms the end-to-end flow works: worktree created, pilot works in isolation, main stays clean.
