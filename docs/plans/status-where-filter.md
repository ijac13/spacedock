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
- [ ] FAIL: All existing + new unit tests pass
  31/32 pass. test_non_empty_pr_field FAILS: scan_entities() only extracts hardcoded fields (id, status, title, score, source, worktree) — pr field is never in the entity dict, so --where "pr !=" always returns empty. This is a real implementation bug.
- [ ] FAIL: E2E checklist test passes on opus/low
  8/9 checks pass. The "first officer performed checklist review" check failed — FO used "Stage report review: 4 done, 0 skipped, 0 failed" phrasing instead of matching the test regex (checklist review|checklist.*complete|all.*items.*DONE|items reported). This is an LLM output phrasing variance, not a --where bug.
- [x] Any issues found in the --where implementation documented
  Bug: scan_entities() hardcodes extracted fields — --where can only filter on slug/id/status/title/score/source/worktree. Acceptance criterion #3 (pr != filter) cannot work without fixing scan_entities to extract all frontmatter fields or at least add pr.

### Summary

Added 10 unit tests covering all --where operators and edge cases. Found one implementation bug: scan_entities() only extracts a fixed set of fields, so --where filtering on arbitrary frontmatter fields like pr does not work. The E2E test had one soft failure due to LLM phrasing variance in the checklist review step. Recommendation: REJECTED — the pr field filtering bug means acceptance criterion #3 is not met.
