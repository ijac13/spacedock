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

## Also in scope — green `test_team_health_check.py`

This task must leave `test_team_health_check.py` passing. As of 2026-04-13 the test FAILs on one assertion on **both haiku and opus/low** (i.e., a static-text regression, not a model flake):

- **`recovery sequence documented`** (`tests/test_team_health_check.py:134`): the regex `r"TeamDelete.*its own message.*TeamCreate.*its own message"` does not match the actual prose in `skills/first-officer/references/claude-first-officer-runtime.md:16`, which says `Call TeamDelete in its own message ... Then call TeamCreate in a subsequent message.` The two halves are asymmetric — only TeamDelete says "in its own message."

Fix direction (resolve during ideation):

1. If `claude-team health` replaces the `test -f` pattern entirely, then the health-check paragraph in the runtime adapter will be rewritten anyway. Make sure the rewrite either preserves the symmetric "in its own message" wording that the existing test expects, or updates the test regex alongside the prose.
2. The other six assertions in `test_team_health_check.py` (AC1–AC5 + bare-mode fallback + single-entity skip) currently pass. Do not regress them when swapping in the new subcommand.

Reproduction: `unset CLAUDECODE && uv run tests/test_team_health_check.py --runtime claude --model {haiku|opus} --effort low`. Logs from the 2026-04-13 run are in `/tmp/spacedock-e2e-logs/test_team_health_check*.log`.

Related:

- Task #134 (runtime-specific-tests-on-pr) is already tracking live-E2E greening. This task is the upstream fix for `test_team_health_check.py`'s recovery-sequence failure (failure B in the 2026-04-13 green-up list).
