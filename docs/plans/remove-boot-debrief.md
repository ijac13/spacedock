---
id: 095
title: Remove LATEST_DEBRIEF from status --boot output
status: validation
source: CL — debrief info at boot is redundant with other --boot sections
started: 2026-04-07T21:37:57Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-remove-boot-debrief
issue: "#44"
pr:
---

# Remove LATEST_DEBRIEF from status --boot output

`status --boot` includes a `LATEST_DEBRIEF` section that reports the most recent debrief filename. The FO then reads and summarizes the full debrief at startup for "session continuity."

In practice, everything useful for dispatch decisions (PR state, orphans, dispatchable entities) is already covered by other `--boot` sections. The debrief read adds latency to startup for information the FO doesn't act on.

## Acceptance Criteria

1. `status --boot` no longer outputs a LATEST_DEBRIEF section
2. `references/first-officer-shared-core.md` startup step no longer mentions reading/summarizing debriefs
3. Existing tests updated to reflect removed debrief output
4. All existing tests pass after changes

## Stage Report

1. Remove LATEST_DEBRIEF output from `skills/commission/bin/status` --boot code path — DONE. Removed `find_latest_debrief` function and its invocation in `print_boot`.
2. Remove the LATEST_DEBRIEF bullet from `references/first-officer-shared-core.md` Startup section (step 4 boot output parsing) — DONE. Also updated the `--boot` summary sentence in the Status Viewer section.
3. Update any tests in `tests/test_status_script.py` that assert on --boot output containing debrief info — DONE. Removed `test_latest_debrief` and `test_latest_debrief_none` tests. Updated `test_section_order` and `test_dispatchable_matches_next` to remove LATEST_DEBRIEF references.
4. Run all existing tests and confirm they pass — DONE. 62 tests pass, 0 failures.
