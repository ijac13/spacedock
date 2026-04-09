---
name: first-officer
description: Use when running or resuming a Spacedock workflow, especially to discover a workflow, dispatch packaged workers, manage approval gates, and advance entity state.
user-invocable: true
---

## Operating contract

@references/first-officer-shared-core.md
@references/code-project-guardrails.md

## Runtime adapter

Load the runtime adapter for your platform:
- Claude Code (`CLAUDECODE` env var is set): read `references/claude-first-officer-runtime.md`
- Codex (`CODEX_HOME` env var is set): read `references/codex-first-officer-runtime.md`

Then begin the Startup procedure from the shared core.
