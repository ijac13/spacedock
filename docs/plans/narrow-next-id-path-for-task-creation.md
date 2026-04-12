---
id: 139
title: Narrow next-id path for task creation
status: validation
source: FO observation during interactive filing on 2026-04-12
score: 0.57
started: 2026-04-12T18:20:42Z
completed: 
verdict: 
worktree: .worktrees/spacedock-ensign-narrow-next-id-path-for-task-creation
issue:
pr:
---

The first officer currently reaches for `skills/commission/bin/status --boot` to learn the next available sequential entity id before filing a new task. That works, but it is broader than necessary: `--boot` also gathers mods, orphan worktrees, PR state, and dispatchable entities. In an interactive session this adds avoidable output and encourages the FO to use a startup-oriented command for ordinary task creation.

The shipped `status` script does not currently expose a narrow `--next-id` mode. Its source advertises support for the default table, `--archived`, `--next`, and `--boot`, and the CLI implementation contains no `--next-id` flag. As a result, the FO either has to overuse `--boot` or reimplement next-id discovery ad hoc.

This task should define and implement a narrow, explicit path for task creation. The likely direction is a `status --next-id` mode that prints only the next sequential id across the active workflow and `_archive/`, plus corresponding first-officer guidance to use that mode when filing new entities instead of a full startup scan.

## Problem Statement

Task creation currently pays for a broader status scan than it needs. The first officer only needs the next sequential entity id, but the available command for that information is bundled into `--boot`, which is designed for startup diagnostics. That creates two problems:

1. It makes interactive task filing noisier and slower than necessary.
2. It teaches the FO to use a bootstrap command for a narrow, routine operation.

The result is a brittle workflow habit: the FO either leans on `--boot` for a single value or recreates the id scan in another place. Both are avoidable. The desired state is a dedicated `status --next-id` path that reports only the next id, while the broader `--boot` path remains available for startup inventory.

## Proposed Approach

Add a narrow CLI mode in `skills/commission/bin/status` that computes the next sequential id from the active workflow and `_archive/`, then prints just that value. Keep the existing `--boot` output intact so startup diagnostics do not regress. The new mode should be explicit, quiet, and deterministic so it is safe for direct use during task creation.

The runtime guidance change should follow the implementation, not precede it. Update the first-officer shared core and both runtime adapters to tell the FO to use `status --next-id` when filing a new entity, while reserving `--boot` for startup and troubleshooting. That keeps the guidance aligned with the narrow command and avoids leaving a stale instruction path in the docs.

Bounded design:

1. Extend the status script with a standalone `--next-id` branch that shares the existing next-id calculation logic but emits only the value.
2. Preserve `--boot` as the broad startup path, including its current NEXT_ID section, so existing startup behavior does not change.
3. Update first-officer runtime guidance to prefer `--next-id` for seed task creation and to stop describing `--boot` as the normal way to fetch the next id.
4. Keep the change local to the workflow tooling and guidance files; do not change stage semantics, entity schema, or dispatch logic.

Rejected alternatives:

1. Keep using `--boot` and add a note to the docs. That reduces confusion only on paper and leaves the overbroad command in place.
2. Add a new helper script outside `status`. That duplicates logic and creates a second source of truth for id discovery.
3. Teach the FO to parse the `NEXT_ID` line out of `--boot`. That still relies on the broad startup path and keeps the unnecessary output.

## Acceptance Criteria

1. `status --next-id` prints only the next sequential id, with no table headers or unrelated boot sections. Test method: run the CLI against a fixture workflow with ids in both the active directory and `_archive/`, then assert stdout is a single id line and the exit code is zero.
2. `status --next-id` uses the same id scan as `--boot`, including archived entities. Test method: construct a fixture where the highest id exists only in `_archive/`, then verify `--next-id` returns the incremented value.
3. `--boot` keeps its current behavior and still reports NEXT_ID alongside the other startup sections. Test method: run the existing boot path on a representative fixture and assert the expected section names are still present.
4. First-officer guidance points task creation to `status --next-id` and no longer frames `--boot` as the routine id source. Test method: inspect the updated shared-core and runtime adapter text with targeted grep assertions or a focused doc test.
5. The change does not alter unrelated status modes. Test method: run the current status-script test coverage for default table output, `--next`, and `--archived`, and confirm they still pass without needing E2E coverage.

## Test Plan

The risk is localized: one CLI path and a few guidance references. This does not call for E2E tests. A proportional plan is:

1. Add focused unit or CLI tests for `--next-id` output and archive-aware id calculation.
2. Reuse existing status-script coverage to confirm `--boot`, `--next`, and the default table still behave as before.
3. Add lightweight text assertions for the first-officer guidance updates so the docs and runtime adapters mention the new narrow command.

Estimated cost is low to moderate. The command logic is small, the shared id scan already exists, and the guidance updates are straightforward text edits. The only subtlety is keeping `--boot` behavior stable while introducing a new output mode, so the tests should emphasize output shape and id source parity.

## Stage Report: ideation

1. Expand the seed into a full problem statement for adding a narrow `status --next-id` path for task creation. - DONE
2. Propose a bounded design covering both implementation and FO/runtime guidance changes. - DONE
3. Define concrete acceptance criteria with a test method for each. - DONE
4. Write a proportional test plan. - DONE

### Summary

The task is now scoped as a narrow CLI addition plus aligned first-officer guidance updates. The body describes the current overuse of `--boot`, the proposed `--next-id` path, the non-goals, and a test plan that stays proportional to the change.

## Stage Report: implementation

- [x] Implement a narrow `status --next-id` path that prints only the next sequential id.
  `status --next-id` now exits before table rendering; verified with a fixture containing active and archived ids (`010` output only).
- [x] Preserve `--boot` behavior and NEXT_ID reporting.
  `python3 /Users/clkao/git/spacedock/.worktrees/spacedock-ensign-narrow-next-id-path-for-task-creation/tests/test_status_script.py` passed 91 tests, including the existing `--boot` NEXT_ID and section-order coverage.
- [x] Update FO/shared/runtime guidance to use `--next-id` for task creation instead of `--boot`.
  Updated `skills/first-officer/references/first-officer-shared-core.md`, `skills/first-officer/references/claude-first-officer-runtime.md`, and `skills/first-officer/references/codex-first-officer-runtime.md` in the worktree.
- [x] Add targeted tests for `--next-id` output/behavior and guidance references.
  Added `TestNextIdOption` in `tests/test_status_script.py` plus content assertions in `tests/test_agent_content.py`.
- [x] Run the relevant verification and record concrete evidence.
  Verified with `python3 /Users/clkao/git/spacedock/.worktrees/spacedock-ensign-narrow-next-id-path-for-task-creation/tests/test_status_script.py` and `uv run --with pytest pytest /Users/clkao/git/spacedock/.worktrees/spacedock-ensign-narrow-next-id-path-for-task-creation/tests/test_agent_content.py -k 'next_id_for_task_creation or covers_all_behavioral_sections'`, both passing.

### Summary

Implemented a dedicated `--next-id` CLI mode that reuses the existing id scan but suppresses all other output. The broader `--boot` flow remains intact, and the first-officer guidance now points task creation at the narrow command instead of the startup scan.

## Stage Report: validation

- [x] Verify the implementation against the acceptance criteria with concrete evidence.
  `skills/commission/bin/status` now has a standalone `--next-id` branch, and the tests assert the narrow output shape plus archive-aware ID calculation. The guidance checks also confirm the first-officer docs point task creation at `status --next-id`.
- [x] Re-run the relevant tests and record actual outcomes.
  `python3 /Users/clkao/git/spacedock/.worktrees/spacedock-ensign-narrow-next-id-path-for-task-creation/tests/test_status_script.py` passed `91` tests. `uv run --with pytest pytest /Users/clkao/git/spacedock/.worktrees/spacedock-ensign-narrow-next-id-path-for-task-creation/tests/test_agent_content.py -k 'next_id_for_task_creation or covers_all_behavioral_sections'` passed `2` tests.
- [x] Confirm the new `--next-id` path and the guidance updates are both covered by tests with clear purpose.
  `tests/test_status_script.py:416-438` covers `--next-id` output and archived IDs. `tests/test_status_script.py:880-896` covers `--boot` NEXT_ID parity. `tests/test_agent_content.py:377-385` covers the shared-core and runtime guidance updates.
- [x] Recommend PASSED or REJECTED with precise evidence.
  PASSED. The narrow CLI path works, the archive-inclusive ID scan is verified, `--boot` still reports `NEXT_ID`, and the runtime guidance now prefers `status --next-id` for new task creation.
- [x] Commit your validation work in the assigned worktree before reporting completion.
  Commit will be created after this report is written.

### Summary

Validation passed. The worktree contains the intended narrow `--next-id` path, the broader `--boot` flow still behaves as before, and the guidance tests explicitly cover the new task-creation instruction. The evidence is localized and sufficient for acceptance.

### Recommendation

PASSED
