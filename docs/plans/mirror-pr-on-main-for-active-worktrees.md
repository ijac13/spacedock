---
id: 135
title: Mirror PR metadata on main for active worktree entities
status: ideation
source: FO observation during task 131 PR handling on 2026-04-12
started: 2026-04-12T20:25:00Z
completed:
verdict:
score: 0.72
worktree: .worktrees/spacedock-ensign-mirror-pr-on-main-for-active-worktrees
issue:
pr:
---

## Problem Statement

Task 131 established the ownership rule for active worktree-backed entities: once an entity has an active worktree, the live stage/report/state transitions belong in the worktree copy, not on `main`. That avoids merge collisions, but it also exposed one narrow discovery problem for `pr:`:

- if `pr:` exists only in the worktree copy, fresh startup on `main` cannot reliably discover PR-pending entities
- worktrees are local and ephemeral, while a PR is durable remote state
- startup/idle handling needs `pr:` visibility on `main` even when other active state remains worktree-owned

This task should therefore be read as a general ownership clarification for active worktree-backed state, with `pr:` as the narrow mirrored exception on `main`.

## Proposed Approach

1. Define the ownership rule in the FO/shared workflow contract:
   - for worktree-backed entities, stage/status/report/body updates stay in the worktree copy
   - `pr:` remains visible on `main` as the one mirrored field needed for startup/discovery
2. Update `status` routing so ordinary active-state writes continue to resolve to the worktree copy, while `--set {slug} pr=...` mirrors onto `main` without moving the rest of the active state.
3. Document the boundary explicitly so future workflow changes do not reintroduce `main`-side writes for active worktree entities by accident.
4. Add regression coverage proving that `pr:` is mirrored on `main` while non-`pr` active-state fields continue to resolve to the worktree copy.

## Acceptance Criteria

1. The first-officer/shared workflow contract explicitly states that active worktree-backed stage/status/report/body state is owned by the worktree copy, with `pr:` as the only mirrored `main` field.
   Test: static content check on the shared-core/workflow-contract text.
2. `status --set {slug} pr=#NN` updates `main` for a worktree-backed entity without shifting the rest of the active state off the worktree copy.
   Test: targeted status-script regression using a main entity plus active worktree copy.
3. Ordinary active-state updates for worktree-backed entities still resolve to the worktree copy and do not land on `main`.
   Test: existing active-worktree status regression remains green, plus a focused no-main-write assertion for a non-`pr` field.
4. Startup/idle discovery can rely on `main` for `pr:` visibility without reintroducing general active-state collisions on `main`.
   Test: `status --boot` / `PR_STATE` behavior stays correct with mirrored `pr:` and worktree-owned stage state.

## Bounded Implementation Surfaces

- `skills/first-officer/references/first-officer-shared-core.md`
- `skills/commission/bin/status`
- `docs/plans/README.md`
- `tests/test_status_script.py`

## Test Plan

- targeted `tests/test_status_script.py` regression for mirrored `pr:` versus non-`pr` active-state routing
- the relevant existing active-worktree status regression suite, to prove no broad `main`-side writes regress
- a narrow startup/PR-state smoke check if `status --boot` needs explicit coverage for `PR_STATE`

## Stage Report: ideation

- [x] Clarified the boundary as general active worktree ownership, not just a `pr:` mirroring quirk
  The body now states that active stage/status/report/body state stays in the worktree copy, with `pr:` as the narrow exception on `main`.
- [x] Tightened the proposed approach and acceptance criteria
  The task now calls out routing, discovery, and no-main-write behavior separately so the ownership model is operationally testable.
- [x] Kept the change scoped to the entity body on `main`
  No frontmatter or workflow README content was edited.
- [ ] SKIP: Executed runtime tests
  This is an ideation-stage refinement of the task text only; no code paths were changed.

### Summary

Task 135 is now framed as the active worktree ownership rule: active stage/status/report/body state belongs in the worktree copy, and `pr:` is the only mirrored field on `main` for discovery. The acceptance criteria and test plan now distinguish `pr:` mirroring from ordinary active-state routing so the operator intent is explicit and measurable.
