---
id: 053
title: Remove redundant Workflow Path section from first-officer template
status: ideation
source: CL
started: 2026-03-27T07:02:00Z
completed:
verdict:
score:
worktree:
---

The `## Workflow Path` section in `templates/first-officer.md` is redundant. The workflow directory path (`__DIR__`) is already baked into every startup step, dispatch call, and status invocation throughout the generated first-officer agent. A dedicated section that restates "paths are relative to `docs/foo/`" adds nothing.

The only consumer of this section is `skills/refit/SKILL.md`, which reads it to find the workflow directory. Refit should extract the path from elsewhere (e.g., the README read in startup, or an argument) rather than requiring a dedicated section in the first-officer.

## What needs to change

1. Remove `## Workflow Path` from `templates/first-officer.md`
2. Update `skills/refit/SKILL.md` to extract the workflow path without depending on a `## Workflow Path` section
3. Update test expectations that check for this section
