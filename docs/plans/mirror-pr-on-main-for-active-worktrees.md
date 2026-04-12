---
id: 135
title: Mirror PR metadata on main for active worktree entities
status: validation
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

This task should therefore be read as a general ownership clarification for active worktree-backed state, with the first-officer/shared workflow contract as the target surface and `pr:` as the narrow mirrored exception on `main`.
In concrete terms, transitions like `implementation -> validation` for a worktree-backed entity should update the worktree copy rather than committing that active-stage change on `main`.

## Proposed Approach

1. Define the ownership rule in the first-officer/shared workflow contract:
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
   Test: existing active-worktree status regression remains green, plus a focused no-main-write assertion for a non-`pr` field such as a stage/status transition to `validation`.
4. Startup/idle discovery can rely on `main` for `pr:` visibility without reintroducing general active-state collisions on `main`.
   Test: `status --boot` / `PR_STATE` behavior stays correct with mirrored `pr:` and worktree-owned stage state.

## Bounded Implementation Surfaces

- `skills/first-officer/references/first-officer-shared-core.md`
- `skills/commission/bin/status`
- `tests/test_status_script.py`
- `tests/test_agent_content.py`

## Test Plan

- targeted `tests/test_status_script.py` regression for mirrored `pr:` versus non-`pr` active-state routing
- a static-content assertion in `tests/test_agent_content.py` that the first-officer/shared contract carries the ownership rule
- the relevant existing active-worktree status regression suite, to prove no broad `main`-side writes regress

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

## Stage Report: implementation

- [x] Updated the shared ensign contract for worktree-owned active state with the `pr:` mirror exception
  Verified in `skills/ensign/references/ensign-shared-core.md` under `## Worktree Ownership`.
- [x] Routed `status --set` so ordinary active-state writes stay on the worktree copy while `pr:` mirrors to `main`
  Implemented in `skills/commission/bin/status` with separate main mirroring for `pr`.
- [x] Added regression coverage for validation-stage routing and `pr:` mirroring
  `tests/test_status_script.py` now covers `status=validation` staying off `main` and `pr=#42` landing on both copies.
- [x] Verified the behavior and contract text in the worktree checkout
  `tests/test_status_script.py`: 92/92 passed; `tests/test_agent_content.py`: 29/29 passed.

### Summary

Worktree-backed entities now keep ordinary active-state writes in the worktree copy, while `pr:` is mirrored back to `main` for startup/discovery. The shared-core contract and the status script both reflect that split, and the regression tests cover the validation transition plus the mirrored PR write.

## Stage Report: implementation (cycle 2)

- [x] Clarified the task body to target the first-officer shared workflow contract and removed `docs/plans/README.md` from the bounded implementation surfaces
  Updated `docs/plans/mirror-pr-on-main-for-active-worktrees.md` so AC1 and the test plan point at `skills/first-officer/references/first-officer-shared-core.md` plus `tests/test_agent_content.py`.
- [x] Added the ownership rule to the first-officer shared core
  `## Worktree Ownership` now states that worktree-backed active stage/status/report/body state lives in the worktree copy, `pr:` is mirrored on `main`, and `implementation -> validation` does not land on `main`.
- [x] Updated static-content coverage for the FO/shared-core wording
  `tests/test_agent_content.py` now checks the new `## Worktree Ownership` section and the exact ownership-rule phrasing required by AC1.
- [x] Verified the requested test set in the worktree
  `unset CLAUDECODE && uv run --with pytest pytest tests/test_agent_content.py tests/test_status_script.py -q` => `124 passed in 3.40s`.

### Summary

The task body, first-officer shared-core contract, and static-content tests now align with the clarified AC: worktree-backed active state stays in the worktree copy, and `pr:` is the mirrored exception on `main`. The requested pytest run passed cleanly in the worktree.

## Stage Report: validation

- [x] AC1: the first-officer/shared workflow contract explicitly states that active worktree-backed stage/status/report/body state is owned by the worktree copy, with `pr:` as the only mirrored `main` field.
  The worktree checkout adds `## Worktree Ownership` in [first-officer-shared-core.md](/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-mirror-pr-on-main-for-active-worktrees/skills/first-officer/references/first-officer-shared-core.md:154) and aligns the ensign shared core at [ensign-shared-core.md](/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-mirror-pr-on-main-for-active-worktrees/skills/ensign/references/ensign-shared-core.md:22).
- [x] AC2: `status --set {slug} pr=#NN` updates `main` for a worktree-backed entity without shifting the rest of the active state off the worktree copy.
  `test_set_updates_active_worktree_copy_not_main` keeps `main` at `implementation` while the worktree copy moves to `done`; `test_pr_state_with_pr` covers mirrored PR visibility in `PR_STATE`.
- [x] AC3: ordinary active-state updates for worktree-backed entities still resolve to the worktree copy and do not land on `main`.
  The same regression asserts the non-`pr` status write updates only the worktree copy, not `main`, and the status script test suite passed end-to-end.
- [x] AC4: startup/idle discovery can rely on `main` for `pr:` visibility without reintroducing general active-state collisions on `main`.
  `--boot`/`PR_STATE` coverage in [test_status_script.py](/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-mirror-pr-on-main-for-active-worktrees/tests/test_status_script.py:1017) and [test_status_script.py](/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-mirror-pr-on-main-for-active-worktrees/tests/test_status_script.py:1128) verifies PR discovery and section ordering; `pr`-only mirroring avoids `main` collisions.

### Summary

Validated the branch in the feature worktree with `unset CLAUDECODE && uv run --with pytest pytest tests/test_agent_content.py tests/test_status_script.py -q` and got `124 passed in 3.30s`. The shared contract now makes worktree ownership explicit, and the status regressions confirm `pr:` is mirrored on `main` while ordinary active-state writes remain worktree-owned.

Recommendation: PASSED
Assessment: The acceptance criteria are satisfied in the feature worktree. AC1 is covered by the explicit `## Worktree Ownership` contract, and AC2 through AC4 are exercised by the status-script regressions that separate mirrored `pr:` handling from ordinary active-state routing.
Counts: 4 done, 0 skipped, 0 failed
