---
id: 088
title: Restore initialPrompt to shipped first-officer agent
status: ideation
source: CL — 085 stripped initialPrompt during skill preloading simplification
started: 2026-04-06T17:45:00Z
completed:
verdict:
score:
worktree:
issue:
pr:
---

# Restore initialPrompt to shipped first-officer agent

Task 085 (agent boot via skill preloading) simplified `agents/first-officer.md` to a thin wrapper with `skills:` frontmatter but dropped the `initialPrompt` field in the process. Without it, `claude --agent spacedock:first-officer` waits for user input instead of auto-starting.

The previous value was:

```yaml
initialPrompt: "Report workflow status."
```

This needs to be restored to the shipped agent file so the first officer auto-starts when invoked via `claude --agent`.
