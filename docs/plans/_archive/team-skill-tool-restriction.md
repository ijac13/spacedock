---
id: 067
title: Investigate and work around Skill tool unavailability for team-spawned agents
status: done
source: session debugging 2026-03-28
started: 2026-03-28T12:00:00Z
completed: 2026-03-28T23:48:00Z
verdict: PASSED
score: 0.80
worktree:
issue:
pr:
---

Team-spawned subagents (dispatched with `team_name` or auto-joined via `name` parameter from a team lead) do not receive the Skill tool. This prevents ensigns from invoking superpowers skills (TDD, brainstorming, etc.) during workflow execution.

## Findings

Initial evidence (documented in `docs/research-skill-tool-team-restriction.md`):

| Spawn config | Has Skill? |
|---|---|
| `ensign` + `team_name` | No |
| `ensign` — no `name`, no `team_name` | **Yes** |
| `general-purpose` + `team_name` | No |

Further investigation revealed the root cause is NOT team membership itself. It is the first-officer's `tools:` frontmatter restricting the inherited tool set:

- **email-triage project:** FO has no `tools:` restriction (or includes Skill). Team-spawned agents with `general-purpose` + `team_name` DO get Skill. Same dispatch pattern that failed in spacedock.
- **spacedock project:** FO had `tools: Agent, TeamCreate, SendMessage, Read, Write, Edit, Bash, Glob, Grep` (no Skill). Team-spawned agents did NOT get Skill.
- Confirmed via JSONL log comparison between the two projects.

## Root cause: intersection model for tool inheritance

**Confirmed.** Team members receive the **intersection** of the team lead's tool set and their own `tools:` declaration. When the FO declared a restricted `tools:` list without Skill, team-spawned agents lost Skill even though their own `tools:` included it.

Live confirmation of intersection model: after removing `tools:` from the FO (giving it the full set), a team-spawned ensign with `tools: Read, Write, Edit, Bash, Glob, Grep, SendMessage, Skill` gained Skill but lacked Agent — because Agent is not in the ensign's `tools:` list.

**Fix:** Remove `tools:` from ALL agent templates (not just the FO). Behavioral instructions govern agent roles, not tool restrictions. This avoids the intersection trap and eliminates template maintenance burden for new tools.

- FO template fixed in `93e2a5d` (removed `tools:` from `templates/first-officer.md`)
- FO deployed fixed in `d860543` (removed `tools:` from `.claude/agents/first-officer.md`)
- Remaining: remove `tools:` from ensign, validator, and pr-lieutenant templates and deployed agents

## Related GitHub issues

- [#29441](https://github.com/anthropics/claude-code/issues/29441) — Agent `skills:` frontmatter not preloaded for team-spawned teammates
- [#25834](https://github.com/anthropics/claude-code/issues/25834) — Plugin agent `skills:` frontmatter silently fails
- [#19077](https://github.com/anthropics/claude-code/issues/19077) — Sub-agents can't create sub-sub-agents (`tools:` not enforced)

## Fix

Remove `tools:` from all agent definitions (templates and deployed). The FO is already fixed. Remaining agents: ensign, validator, pr-lieutenant.

Existing commissioned projects pick up template changes via refit (out of scope for 067).

## Implementation

1. Remove `tools:` from `templates/ensign.md`, `templates/validator.md`, `templates/pr-lieutenant.md`
2. Remove `tools:` from `.claude/agents/ensign.md`, `.claude/agents/validator.md`, `.claude/agents/pr-lieutenant.md`
3. Update research doc to reflect corrected root cause (intersection model)
4. Verify in a fresh session that team-spawned ensigns get the full tool set

## Acceptance criteria

- All agent templates and deployed agent files have no `tools:` frontmatter
- Research doc reflects the intersection model as root cause
- Fresh session confirms team-spawned agents get Skill (and other tools previously missing)

## Stage Report: ideation

- [x] Remaining work items resolved or clearly scoped for implementation
  Three items scoped: (1) remove `tools:` from ensign/validator/pr-lieutenant templates and deployed agents, (2) update research doc, (3) verify in fresh session. Refit propagation confirmed out of scope — handled by refit skill.
- [x] Acceptance criteria updated if needed based on brainstorm findings
  Updated to reflect removing `tools:` from ALL agents (not just FO) and the intersection model discovery.
- [x] Open questions from the entity addressed
  Tool inheritance model confirmed as intersection (live evidence: ensign has Skill but not Agent). Refit propagation scoped to refit skill. Research doc corrected in this session. CL decided to remove `tools:` from all agents rather than maintaining per-agent allowlists.

### Summary

Brainstorm with CL resolved three open questions and expanded the fix scope. The intersection model for tool inheritance was confirmed by live observation (this ensign has Skill but not Agent, matching the intersection of the FO's full set and the ensign's declared `tools:`). CL decided to remove `tools:` from all agent templates — behavioral instructions govern roles, not tool restrictions. Research doc updated to reflect corrected root cause. Implementation is now clearly scoped: remove `tools:` from three remaining templates and deployed agents, then verify.

## Stage Report: implementation

- [x] `tools:` removed from ensign, validator, and pr-lieutenant templates
  Removed `tools:` line from frontmatter in `templates/ensign.md`, `templates/validator.md`, `templates/pr-lieutenant.md`
- [x] Research doc updated to reflect intersection model as root cause
  `docs/research-skill-tool-team-restriction.md` already contains the corrected root cause (updated during ideation); verified no stale content remains
- [x] All changes committed to the worktree branch
  Committed to `ensign-067-tool-restriction` branch

### Summary

Removed `tools:` frontmatter from the three remaining agent templates (ensign, validator, pr-lieutenant). The first-officer template was already fixed in commit 93e2a5d. The research doc already reflected the intersection model as root cause from the ideation phase — no further updates needed. Deployed agents under `.claude/agents/` were not modified per agent rules; they will pick up changes via refit.
