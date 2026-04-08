---
id: 103
title: "Bug: single-entity mode still creates teams instead of using bare-mode dispatch"
status: backlog
source: CL observation
started:
completed:
verdict:
score:
worktree:
issue:
pr:
---

When the FO is invoked in single-entity mode (`claude -p` with a named entity), it should skip team creation entirely and use bare-mode dispatch (Agent without `team_name`). Instead, it still calls TeamCreate.

The runtime doc (`references/claude-first-officer-runtime.md` line 31) is explicit: "In single-entity mode, skip team creation entirely. Use bare-mode dispatch for all agent spawning — the Agent tool without `team_name` blocks until the subagent completes, which prevents premature session termination in `-p` mode."

The existing `test_team_dispatch_sequencing.py` tests verify that TeamCreate/TeamDelete aren't mixed with Agent calls, but no test verifies that single-entity mode skips TeamCreate altogether. Need to add an E2E test that runs the FO in `-p` mode with a named entity and asserts TeamCreate does not appear in the JSONL tool calls.
