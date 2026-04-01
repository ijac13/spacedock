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

## Stage Report: validation

- [x] Unit tests added for all --where operators (=, !=) with and without values
  10 tests in TestWhereFilter: exact match, not-equal-with-value, non-empty, empty, pr non-empty, multiple AND, compose-next, compose-archived, no-match header-only, nonexistent field
- [x] Unit tests cover --where composition with --next and --archived
  test_where_composes_with_next and test_where_composes_with_archived both pass
- [x] All existing + new unit tests pass
  32/32 pass after scan_entities fix (commit 2c2f041) to pass through all frontmatter fields
- [ ] FAIL: E2E checklist test passes on opus/low
  Rerun blocked by API rate limit ("You've hit your limit - resets 2am"). Commission phase (2/2 pass) completed but FO phase rejected at 99% 5-hour utilization. Template fix (commit 6cc2e77) is correct — "Checklist review" wording confirmed in templates/first-officer.md:84. Needs rerun after rate limit resets.
- [x] Any issues found in the --where implementation documented
  Found and reported scan_entities() hardcoded field bug; fixed in commit 2c2f041. No remaining --where issues.

### Summary

E2E rerun attempted but blocked by API 5-hour rate limit at 99% utilization. Commission phase succeeded (2/2 checks pass), confirming the template generates correctly. FO phase was rejected before it could start processing. The "Checklist review" fix in commit 6cc2e77 is verified present in templates/first-officer.md:84 but could not be validated end-to-end. Needs rerun after rate limit resets (2am PT).
