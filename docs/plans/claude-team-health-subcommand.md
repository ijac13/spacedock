---
id: 143
title: "claude-team health subcommand — replace raw `test -f` with a proper helper"
status: backlog
source: CL observation during 2026-04-13 session — asymmetry between reuse-eligibility (helper) and health-check (raw `test -f`)
started:
completed:
verdict:
score: 0.55
worktree:
issue:
pr:
---

Today the Claude runtime adapter prescribes two different ergonomic patterns for team-state checks:

- **Reuse eligibility:** `claude-team context-budget --name {team_name}` — real subcommand with JSON output.
- **Health check:** `test -f ~/.claude/teams/{team_name}/config.json` — raw Bash, no helper.

The asymmetry has two costs:

1. The raw `test -f` only proves the file exists. It cannot tell us that `config.json` is parseable, non-empty, or references the expected team. A corrupted or truncated file still passes.
2. Agents and test assertions must hardcode `~/.claude/teams/{team_name}/config.json` in multiple places (`claude-first-officer-runtime.md:46`, `tests/test_team_health_check.py:127`). Any future change to the team-state layout becomes a multi-file edit.

This task folds health-check into the existing helper: add `claude-team health --name {team_name}` as a sibling to `context-budget`. The subcommand should return exit 0 (healthy) / 1 (unhealthy) with JSON payload describing the failure mode when unhealthy. Update the runtime adapter and `test_team_health_check.py` to use the new helper instead of `test -f`.

Related:

- `test_team_health_check.py` currently FAILs on its "recovery sequence documented" assertion due to wording drift in the runtime adapter (`TeamDelete.*its own message.*TeamCreate.*its own message`) — that fix belongs to this task or task #134, TBD during ideation.
- Task #134 (runtime-specific-tests-on-pr) is already tracking live-E2E greening. This task is the upstream fix for one of the failures listed there.
