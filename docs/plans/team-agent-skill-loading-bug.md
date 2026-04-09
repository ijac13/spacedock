---
id: 107
title: "Team agents silently lose skills and system prompt — Claude Code #30703"
status: backlog
source: "CL investigation — confirmed from session logs"
started:
completed:
verdict:
score:
worktree:
issue:
pr:
---

## Known Issue

Claude Code #30703: when agents are spawned as team members (with `team_name`), the `skills` frontmatter and markdown body (system prompt) from the agent `.md` file are silently ignored. Only `model` and `disallowedTools` work. Still broken as of v2.1.97.

## Impact on Spacedock

Confirmed from session JSONL logs: dispatched ensigns (`Agent(subagent_type="spacedock:ensign", team_name="...")`) never load the `spacedock:ensign` skill. Zero Skill tool calls, zero system-reminder blocks. The ensign operates purely from the FO's dispatch prompt.

What ensigns are missing without their operating contract:
- Captain-direct-communication protocol
- Behavioral guardrails and constraints
- Boot sequence and skill loading instructions

What still works:
- All stage work — the dispatch prompt carries stage definition, checklist, worktree instructions, entity context
- Tool usage — Read, Edit, Bash, etc. work fine
- Completion protocol — SendMessage back to FO works (learned from dispatch prompt)

## Observation

This effectively proves the ensign agent file (`agents/ensign.md`) is not contributing anything to team-dispatched ensigns. All ensign behavior comes from the dispatch prompt. This raises the question: do we need the ensign agent at all, or can we dispatch with a generic `subagent_type` and rely entirely on the prompt?

## Workarounds (from #30703 comments)

A `SubagentStart` hook can inject agent definition content as `additionalContext` on every teammate turn. This is a community workaround, not an official fix. See the hook implementation in #30703's latest comment.

## Decision

Deferred — tackling later. The current setup works because the dispatch prompt is self-contained.
