---
id: 095
title: Remove LATEST_DEBRIEF from status --boot output
status: implementation
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
