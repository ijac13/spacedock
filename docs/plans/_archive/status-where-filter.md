---
id: 079
title: Status script --where filtering and FO template simplification
status: validation
source: experiment/status-filters branch (FO template token reduction experiment)
started: 2026-03-31T00:00:00Z
completed:
verdict:
score: 0.75
worktree: .worktrees/pr-19-test
pr: "#19"
---

Add `--where "field op [value]"` filtering to the status script template.
Supports `=`, `!=` operators with optional values. Multiple `--where` clauses
AND together. Composable with `--next` and `--archived`.

Uses the new filter to simplify first-officer template prose:
- Orphan detection: replace 25-line prose + decision table with `status --where "worktree !="`
- PR-pending check: replace manual scanning prose with `status --where "pr !="`

## Implementation (PR #19)

- `templates/status`: added `parse_where_filters()` and `apply_filters()` functions
- `templates/first-officer.md`: simplified orphan detection (step 6) and PR-pending check (event loop step 1)
- Template word count: 3,035 (down from 3,251 baseline) — -6.6% reduction
- Branch: `experiment/status-filters`

## Acceptance Criteria

1. `status --where "status = backlog"` returns only entities with status backlog
2. `status --where "worktree !="` returns entities with non-empty worktree
3. `status --where "pr !="` returns entities with non-empty pr field
4. Multiple `--where` clauses AND correctly
5. `--where` composes with `--next` and `--archived`
6. Unit tests cover all --where operators and edge cases
7. E2E test suite passes with modified FO template
