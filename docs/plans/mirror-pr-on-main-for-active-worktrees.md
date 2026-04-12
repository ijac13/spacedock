---
id: 135
title: Mirror PR metadata on main for active worktree entities
status: backlog
source: FO observation during task 131 PR handling on 2026-04-12
started:
completed:
verdict:
score: 0.72
worktree: .worktrees/spacedock-ensign-mirror-pr-on-main-for-active-worktrees
issue:
pr: #83
---

## Problem Statement

Task 131 established that once an entity is worktree-backed, active stage/report state should live in the worktree copy rather than on `main`. That avoids merge collisions, but it exposed a discovery problem for `pr:`:

- if `pr:` exists only in the worktree copy, fresh startup on `main` cannot reliably discover PR-pending entities
- worktrees are local and ephemeral, while a PR is durable remote state
- startup/idle handling needs `pr:` visibility on `main` even when other active state remains worktree-owned

The workflow contract should explicitly make `pr:` a mirrored orchestration field on `main` for active worktree entities, while leaving stage-progress/body/report ownership with the worktree copy.

## Proposed Approach

1. Define the ownership rule in the FO/shared workflow contract:
   - active stage/report state for worktree-backed entities is worktree-owned
   - `pr:` is the narrow exception and should be mirrored on `main`
2. Update `status` so ordinary active-state updates still resolve to the worktree copy, but `--set {slug} pr=...` mirrors onto the main copy for discoverability.
3. Document the rule in the workflow README/schema so startup behavior is not implicit.
4. Add regression coverage proving that `pr:` is mirrored on `main` while other active-state fields continue to resolve to the worktree copy.

## Acceptance Criteria

1. The first-officer/shared workflow contract explicitly states that `pr:` is mirrored on `main` for active worktree entities.
   Test: static content check on the shared-core/workflow-contract text.
2. `status --set {slug} pr=#NN` updates the main copy even when the entity is currently worktree-backed.
   Test: targeted status-script regression using a main entity plus active worktree copy.
3. Ordinary active-state updates for worktree-backed entities still resolve to the worktree copy.
   Test: existing active-worktree status regression remains green.
4. Startup/PR discovery can rely on `main` for `pr:` visibility without reintroducing general active-state collisions on `main`.
   Test: `status --boot` / `PR_STATE` behavior stays correct with mirrored `pr:` and worktree-owned stage state.

## Bounded Implementation Surfaces

- `skills/first-officer/references/first-officer-shared-core.md`
- `skills/commission/bin/status`
- `docs/plans/README.md`
- `tests/test_status_script.py`

## Test Plan

- targeted `tests/test_status_script.py` regression for mirrored `pr:`
- full `tests/test_status_script.py`
- any narrow startup/PR-state regression needed for `status --boot`
