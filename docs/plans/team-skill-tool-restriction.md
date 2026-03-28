---
id: 067
title: Investigate and work around Skill tool unavailability for team-spawned agents
status: ideation
source: session debugging 2026-03-28
started: 2026-03-28T12:00:00Z
completed:
verdict:
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

## Root cause: team lead tool inheritance

**Confirmed.** Team members inherit their available tools from the team lead's declared `tools:` set. When the FO declared a restricted `tools:` list without Skill, all team-spawned agents lost Skill.

The `tools:` frontmatter IS enforced for the team lead agent — it restricts the tool set, and that restriction propagates to all team members. This is different from the behavior reported in GitHub issues about `tools:` being "advisory" for regular subagents.

**Fix:** Remove the `tools:` line from the first-officer agent definition. Without an explicit `tools:` list, the FO inherits the full tool set, and team members inherit it in turn.

- Template fixed in `93e2a5d` (removed `tools:` from `templates/first-officer.md`)
- Deployed file fixed in `d860543` (removed `tools:` from `.claude/agents/first-officer.md`)

## Related GitHub issues

- [#29441](https://github.com/anthropics/claude-code/issues/29441) — Agent `skills:` frontmatter not preloaded for team-spawned teammates
- [#25834](https://github.com/anthropics/claude-code/issues/25834) — Plugin agent `skills:` frontmatter silently fails
- [#19077](https://github.com/anthropics/claude-code/issues/19077) — Sub-agents can't create sub-sub-agents (`tools:` not enforced)

## Fix

The fix is simply removing the `tools:` line from the first-officer agent definition. No workaround needed — this was a configuration bug, not a platform limitation.

Template and deployed file are both fixed. Existing commissioned projects need a refit to pick up the template change.

## Remaining work

1. **Test in a fresh session** — confirm team-spawned ensigns get Skill after the fix
2. **Review ensign.md `tools:` declaration** — does the ensign's own `tools:` frontmatter matter for team-spawned agents, or does only the team lead's declaration count? If the ensign's list is also enforced, it could independently restrict tools. Currently it includes Skill, so not blocking, but worth understanding.
3. **Refit guidance** — existing commissioned projects still have the old FO with `tools:` restriction. The refit skill should handle this.

## Stage Report: ideation

- [x] Problem statement clarified with evidence from testing
  Root cause identified: FO's `tools:` frontmatter restriction propagates to team members. Cross-project JSONL log comparison (email-triage vs spacedock) confirmed the mechanism.
- [x] Proposed approach with rationale (which workaround option, or a new one)
  Not a workaround — direct fix: remove `tools:` from FO agent definition. Already applied in template (93e2a5d) and deployed file (d860543).
- [x] Acceptance criteria defined — what does "done" look like
  Done = (1) fresh session confirms team-spawned ensigns get Skill, (2) ensign `tools:` behavior understood, (3) refit handles propagation to existing projects.
- [x] Open questions resolved or explicitly deferred
  Deferred: whether ensign's own `tools:` frontmatter independently restricts team-spawned agents (not blocking since it already includes Skill).
- [x] CL has been consulted and their input incorporated
  CL participated directly in the session, confirmed the root cause via JSONL log analysis, and applied the fix commits.

### Summary

The Skill tool unavailability for team-spawned agents was caused by the first-officer's explicit `tools:` frontmatter omitting Skill. Team members inherit the team lead's declared tool set, so the restriction propagated. The fix is removing `tools:` from the FO definition so it inherits the full set. Template and deployed file are both fixed. Remaining work is testing in a fresh session and ensuring the refit skill propagates the fix to existing projects.
