---
id: 104
title: Workflow discovery — analyze conversation history to recommend workflows
status: backlog
source: CL brainstorm during 057 ideation
started:
completed:
verdict:
score:
worktree:
issue:
pr:
---

What if the user doesn't know they need a workflow? Analyze a user's agent conversation history to discover recurring multi-step patterns and recommend structuring them as spacedock workflows.

## Data sources

- **AgentsView SQLite** (`~/.claude/agentsview/sessions.db`): Normalized database with sessions, messages, tool_calls (with skill names, subagent relationships), and insights. 1018 sessions across 19 projects in CL's data.
- **Raw Claude logs** (`~/.claude/projects/`): Session-level JSONL files.

## Pilot goal

Classify CL's own usage across projects to identify:
1. Recurring multi-step task patterns (same sequence of actions across sessions)
2. Manual orchestration patterns (user directing agent through steps)
3. Ad-hoc state tracking (TODO files, task lists, status checks)
4. Multi-agent coordination patterns (subagent spawning, team usage)
5. Review/approval gates the user imposes

From the classification, determine what approach a "workflow discovery" skill should take and what signals are most reliable.
