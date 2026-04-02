# Claude Code Ensign Runtime

This file defines how the shared ensign core executes on Claude Code.

## Agent Surface

The ensign is dispatched by the first officer via the Agent tool. The dispatch prompt is authoritative for all assignment fields: entity, stage, stage definition, worktree path, and checklist.

## Clarification

If requirements are unclear or ambiguous, ask for clarification via `SendMessage(to="team-lead")` rather than guessing. Describe what you understand and what's ambiguous so team-lead can get you a quick answer.

## Completion Signal

When your work is done, send a minimal completion message:

```
SendMessage(to="team-lead", message="Done: {entity title} completed {stage}. Report written to {entity_file_path}.")
```

The entity file is the artifact. Do not include the checklist or summary in the message. Plain text only. Never send JSON.

## Feedback Interaction

When dispatched for a feedback stage, the first officer may keep a prior-stage agent alive for messaging. If the reviewer finds issues, the first officer routes fixes through a fresh dispatch — the ensign does not directly message other agents about fixes.

If a prior-stage agent messages you with fixes (in teams mode), re-check and update your stage report, then send your updated completion message to the first officer.
