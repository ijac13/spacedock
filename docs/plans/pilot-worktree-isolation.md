---
title: Pilot Worktree Isolation
status: ideation
source: commission seed
started:
completed:
verdict:
score: 16
---

## Problem

In v0 shuttle mode, only one pilot runs at a time, so there are no git conflicts. But in v1 starship mode, multiple pilots will work on different entities in parallel. If they all operate on the same working tree, they'll step on each other's files — merge conflicts, dirty state, lost work. Worktree isolation is the foundation for safe parallel execution.

## Proposed Approach

1. **Each pilot gets its own git worktree.** When the first officer dispatches a pilot, it creates a worktree: `git worktree add .worktrees/pilot-{slug} -b pilot/{slug}` based on the current branch. The pilot operates entirely within that worktree.

2. **First officer manages worktree lifecycle.** Create on dispatch, merge or clean up on completion. If a pilot fails, the worktree stays for inspection.

3. **Pipeline directory is shared state.** The entity .md files are the pipeline's state machine. Pilots read the entity file from the main tree, do their work in the worktree, then update the entity frontmatter in the main tree. This avoids merge conflicts on the pipeline metadata itself.

4. **Worktree directory convention:** `.worktrees/` at the repo root, gitignored. Branch naming: `pilot/{entity-slug}`.

5. **v0 impact: minimal.** This is a design-only entity for now. Implementation is deferred to v1. The design should be solid enough that v1 can implement it without redesign.

## Acceptance Criteria

- [ ] Design document covers: worktree creation, branch naming, lifecycle management, shared state handling
- [ ] Addresses the merge conflict problem for parallel pilots
- [ ] Defines how pilots interact with pipeline state (entity files) vs working files
- [ ] Considers failure modes: pilot crashes mid-work, worktree left dirty
- [ ] Does not require v0 code changes — this is design prep for v1

## Scoring Breakdown

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Edge | 4 | Key differentiator for starship mode |
| Fitness | 3 | Important for v1, not needed for v0 |
| Parsimony | 3 | Git worktrees are the right primitive but lifecycle is complex |
| Testability | 3 | Can test worktree creation, harder to test full parallel scenario |
| Novelty | 3 | Git worktrees are well-known but applying them to agent isolation is less explored |
