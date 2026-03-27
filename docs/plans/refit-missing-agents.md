---
id: 056
title: Refit skill does not regenerate ensign or lieutenant agents
status: implementation
source: CL
started: 2026-03-27T08:00:00Z
completed:
verdict:
score:
worktree: .worktrees/ensign-refit-agents
---

The refit skill (`skills/refit/SKILL.md`) regenerates the first-officer and status script but completely ignores the ensign agent and any lieutenant agents. After a refit, `.claude/agents/ensign.md` stays stale — it still has the old version stamp and old content even when `templates/ensign.md` has changed.

## What needs to change

1. Add ensign regeneration to refit Phase 2 classification table and Phase 3 execution
2. Add lieutenant regeneration — scan the README frontmatter for stages with `agent:` properties, regenerate each referenced lieutenant from its template
3. Both should follow the same pattern as the first-officer: sed from template, show diff, ask captain to confirm

## Acceptance Criteria

- [ ] Refit regenerates `.claude/agents/ensign.md` from `templates/ensign.md`
- [ ] Refit regenerates lieutenant agents referenced in README stage definitions from their templates
- [ ] Both show diffs and ask captain for confirmation before replacing
- [ ] Version stamps are updated on regenerated agents
- [ ] Agents not referenced by any stage (orphaned lieutenants) are reported but not deleted
