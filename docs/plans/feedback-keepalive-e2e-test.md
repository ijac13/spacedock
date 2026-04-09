---
id: 106
title: E2E test for feedback-to keepalive — FO must not kill implementation agent during validation
status: backlog
source: CL — observed FO prematurely shutting down implementation ensign when entering validation (feedback-to stage)
started:
completed:
verdict:
score: 0.85
worktree:
issue:
pr:
---

The FO's shared core says: when the next stage has `feedback-to` pointing at the completed stage, keep the completed agent alive. The FO violated this rule by shutting down the implementation ensign when advancing to validation (which has `feedback-to: implementation`).

The static content test in `test_reuse_dispatch.py` (line 207) checks that the keepalive rule *exists in the contract text*, but no E2E test verifies the FO actually follows it at runtime.

## What to build

A PTY-based E2E test using `scripts/test_lib_interactive.py` (`InteractiveSession`) that:

1. Sets up a workflow fixture with at least: implementation (worktree) → validation (worktree, fresh, feedback-to: implementation) → done (terminal)
2. Seeds an entity ready for implementation dispatch
3. Starts an interactive claude session with the spacedock first-officer
4. Lets the FO dispatch the implementation ensign
5. Waits for the implementation ensign to complete
6. Observes the FO advancing to validation — at this point, the FO should dispatch a fresh validation agent BUT keep the implementation agent alive
7. Asserts: the implementation agent was NOT sent a shutdown request before or during validation dispatch
8. Clean up

## How to verify keepalive

After the FO dispatches validation, inspect the session logs (via `InteractiveSession.get_subagent_logs()` or raw JSONL) for:
- The implementation agent should still be in the team members list (read `~/.claude/teams/{team}/config.json`)
- No `shutdown_request` message should appear in the FO's output targeting the implementation agent between the implementation completion and validation dispatch
- Alternatively: scan the FO's output stream for `shutdown_request` — it should NOT appear for the implementation agent name

## Test fixture

Use or adapt `tests/fixtures/rejection-flow/` as the base — it already has a feedback-to stage. The fixture needs:
- A simple 3-stage pipeline: implementation → validation (feedback-to: implementation) → done
- A seed entity with enough content that the ensign can complete quickly (minimal real work)

## Acceptance criteria

1. Test file exists at `tests/test_feedback_keepalive.py`
2. Test uses `InteractiveSession` from `scripts/test_lib_interactive.py`
3. Test sets up a workflow with a `feedback-to` stage
4. Test verifies the FO does NOT shut down the implementation agent when dispatching validation
5. Test passes when the FO follows the keepalive rule
6. Test fails when the FO prematurely shuts down the implementation agent
