---
id: 103
title: "Bug: single-entity mode still creates teams instead of using bare-mode dispatch"
status: implementation
source: CL observation
started: 2026-04-08T19:16:08Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-single-entity-skips-team-creation
issue:
pr: #51
---

When the FO is invoked in single-entity mode (`claude -p` with a named entity), it should skip team creation entirely and use bare-mode dispatch (Agent without `team_name`). Instead, it still calls TeamCreate.

The runtime doc (`references/claude-first-officer-runtime.md` line 31) is explicit: "In single-entity mode, skip team creation entirely. Use bare-mode dispatch for all agent spawning — the Agent tool without `team_name` blocks until the subagent completes, which prevents premature session termination in `-p` mode."

The existing `test_team_dispatch_sequencing.py` tests verify that TeamCreate/TeamDelete aren't mixed with Agent calls, but no test verifies that single-entity mode skips TeamCreate altogether. Need to add an E2E test that runs the FO in `-p` mode with a named entity and asserts TeamCreate does not appear in the JSONL tool calls.

## Stage Report

### 1. Write E2E test for single-entity mode team creation skip — DONE

Created `tests/test_single_entity_team_skip.py` with 5 checks:
- TeamCreate does NOT appear in tool calls
- Agent calls do NOT have `team_name` parameter
- At least one Agent dispatch occurred (sanity check)
- TeamDelete does NOT appear in tool calls
- Status script runs without errors

### 2. Run E2E test — document whether bug is confirmed or not — DONE

Bug is **NOT confirmed**. The FO already correctly handles single-entity mode:
- TeamCreate was absent from all tool calls
- The single Agent dispatch used bare mode (no `team_name`)
- The entity was processed (1 Agent dispatch occurred)
- All 5 checks passed on haiku with low effort, ~70s wallclock

### 3. If confirmed: implement fix — SKIPPED

Bug was not confirmed. The existing instruction at `references/claude-first-officer-runtime.md` line 31 is sufficient — the FO correctly skips team creation in single-entity mode.

### 4. If fixed: re-run test to verify — SKIPPED

No fix was needed. The initial test run already verified correct behavior.

### 5. Commit all changes on the worktree branch — DONE

Test file and stage report committed on `spacedock-ensign/single-entity-skips-team-creation`.
