---
id: 101
title: "FO incorrectly enters single-entity mode during normal interactive dispatch"
status: ideation
source: CL observation — seen 3x in Claude Code, 1x in Codex
started: 2026-04-09T15:24:00Z
completed:
verdict:
score: 0.8
worktree:
issue:
pr:
---

The FO enters single-entity mode during normal interactive sessions when the user mentions a specific entity. Single-entity mode is designed for non-interactive `-p` invocations. In interactive sessions, the FO should use the standard event loop with team support.

## Observations

**Codex:** The Codex FO resolved entity 087 (already in implementation) and announced single-entity mode, treating it as if the user had asked to process that specific entity in pipe mode.

**Claude Code (3 occurrences):** The FO misapplies single-entity mode when the user names a specific entity to work on. The FO's own self-diagnosis from the latest occurrence:

> "I misapplied single-entity mode. The shared core says 'when the user names a specific entity → single-entity mode' but the Claude runtime clarifies its purpose: bare-mode dispatch to 'prevent premature session termination in -p mode.' This is an interactive session — I should have created a team and dispatched with team_name like normal."

The practical impact: bare-mode dispatch blocks until the ensign completes, preventing concurrent dispatch of other entities. The FO loses team capabilities.

## Root cause

The shared core's trigger condition is too broad: "When the user names a specific entity and asks to process it through the workflow, switch into single-entity mode." In interactive sessions, users routinely name entities ("let's work on 057", "dispatch 104") without intending single-entity mode. The trigger should be scoped to non-interactive invocations only.

## Possible fix

The Claude runtime already has the right intent: "In single-entity mode, skip team creation entirely. Use bare-mode dispatch for all agent spawning — the Agent tool without team_name blocks until the subagent completes, which prevents premature session termination in -p mode."

The fix should tighten the trigger in the shared core: single-entity mode activates only when the session is non-interactive (e.g., invoked via `-p` flag), not when the user names an entity in conversation.
