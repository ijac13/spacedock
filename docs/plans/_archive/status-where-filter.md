---
id: 079
title: Status script --where filtering and FO template simplification
status: done
source: experiment/status-filters branch (FO template token reduction experiment)
started: 2026-03-31T00:00:00Z
completed: 2026-04-01T00:00:00Z
verdict: PASSED
score: 0.75
worktree:
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

## Stage Report: validation

- [x] Unit tests added for all --where operators (=, !=) with and without values
  10 tests in TestWhereFilter: exact match, not-equal-with-value, non-empty, empty, pr non-empty, multiple AND, compose-next, compose-archived, no-match header-only, nonexistent field
- [x] Unit tests cover --where composition with --next and --archived
  test_where_composes_with_next and test_where_composes_with_archived both pass
- [x] All existing + new unit tests pass
  32/32 pass after scan_entities fix (commit 2c2f041) to pass through all frontmatter fields
- [x] E2E checklist test passes on opus/low
  9/9 checks pass after FO template fix (commit 6cc2e77) renamed "Stage report review" to "Checklist review"
- [x] Any issues found in the --where implementation documented
  Found and reported scan_entities() hardcoded field bug; fixed in commit 2c2f041. No remaining --where issues.

### Summary

Added 10 unit tests covering all --where operators and edge cases. Initial run found scan_entities() bug (hardcoded fields blocked --where on pr); fixed in 2c2f041, all 32 unit tests now pass. E2E rerun after FO template fix (commit 6cc2e77) passes 9/9 checks. All acceptance criteria met.
