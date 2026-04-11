---
id: 123
title: "Status tool as workflow-op CLI — fix --where, expose custom fields, unify mutation paths"
status: ideation
source: "External FO feedback (GTM + experiment pipelines) during 2026-04-10 session"
score: 0.75
worktree:
started: 2026-04-11T00:40:18Z
completed:
verdict:
issue:
pr:
---

## Problem statement

`skills/commission/bin/status` is the primary programmatic interface between the first officer and workflow state, but today it is a half-tool with three load-bearing pain points observed during the 2026-04-10 session:

1. **`--where` has a silent usability bug.** The parser splits the `--where` argument on whitespace, so `--where "status=watching"` (no spaces, SQL-like form users reach for first) is parsed as a presence check on a field literally named `status=watching` and silently returns zero rows. The working form is `--where "status = watching"` with spaces around the operator — undocumented and unintuitive. Reproduced locally on 2026-04-10 against a two-entity fixture: spaced form returns the row, unspaced form returns empty. The GTM FO workflow's silence-watcher mod already encodes a `grep -l "^status: watching$"` workaround, which is the tell: someone already tripped on this and routed around the tool.

2. **Custom frontmatter fields are invisible in the default viewer.** The table hard-codes `ID / SLUG / STATUS / TITLE / SCORE / SOURCE`. Workflows like discovery-outreach define custom fields (`last-outbound-at`, `nudge-count`, `outcome`) that the status tool cannot display, forcing FOs into inline Python to eyeball schema-specific state. `--where` already reads custom fields correctly (parser is generic); only the viewer is schema-blind.

3. **Archive moves bypass the tool.** Archiving is a bare `mv entity.md _archive/entity.md` + commit dance. No single command encapsulates the move, there is no place to attach side-effects (e.g., stamp an `archived:` timestamp), and the operation is not discoverable via `--help`.

Task 122 (`status-set-missing-field-silent-noop`) already landed and fixed the silent-no-op on `status --set` for missing frontmatter fields. That task is closed in `_archive/` with verdict PASSED. This task (123) inherits the remaining three gaps above and does not re-open anything 122 shipped.

Meta-note on scope: the three gaps share a single owner (the Python script), a single test harness (`tests/test_status_script.py`), and a single type of fix (small, surgical, stdlib-only). They belong in one pass so the FO gets "the status tool is reliable now" as one atomic improvement rather than three trickle releases.

## Proposed approach

Evolve `status` into the primary workflow-op CLI for the two surfaces the FO legitimately touches: **frontmatter** (read, query, write) and **archive moves**. Body writes stay with `Edit` (worker-owned). Mod file edits stay with dispatched workers (scaffolding scope). Not a rewrite — a surgical pass on the existing Python script that preserves the stdlib-only, no-PyYAML constraint.

Terminology note: throughout this task "fields" means YAML frontmatter keys. "Columns" refers only to the visual layout of the default output table. CLI flags that expose frontmatter keys are named `--fields` and `--all-fields`.

### 1. Fix `--where` (operator parsing)

**Root cause:** `parse_where_filters()` does `where_arg.split(None, 1)` — split on whitespace — so a single-token input with no spaces collapses into a bare field name and the filter degrades to `(field, '!=', None)` (presence check). There is no error, just silent zero matches.

**Fix:** make the parser tolerant of the three natural forms that users actually type:

| User types                    | Parses as                        | Meaning                   |
|-------------------------------|----------------------------------|---------------------------|
| `status=watching`             | `(status, =, watching)`          | equality                  |
| `status = watching`           | `(status, =, watching)`          | equality (spaces allowed) |
| `status != done`              | `(status, !=, done)`             | negation                  |
| `status!=done`                | `(status, !=, done)`             | negation                  |
| `pr !=`                       | `(pr, !=, None)`                 | presence (non-empty)      |
| `pr =`                        | `(pr, =, None)`                  | absence (empty)           |
| `completed`                   | ERROR                            | ambiguous, see below      |

**Operators in scope:** `=` (equality) and `!=` (negation). Both must work with and without surrounding whitespace. Presence/absence is expressed via `field !=` and `field =` with no RHS value. No other operators (`<`, `>`, `LIKE`, regex) — YAGNI.

**Bare-field form:** the current code accepts `--where "completed"` and treats it as `(completed, !=, None)` — i.e., "field is non-empty". This is confusing because it looks like a truthiness check but is actually a presence check, and it is the code path that the buggy `status=watching` form accidentally falls into. The refined design **rejects bare field names** with a clear error: `--where requires an operator: use 'field = value', 'field != value', 'field !=' (non-empty), or 'field =' (empty)`. This closes the silent-zero-rows hazard at the parser level. Bare-field is rare (existing tests use `worktree !=` and `pr !=`, not `worktree` alone), so the breakage surface is minimal, and the error points at the right fix.

**Custom fields:** `--where` already works on custom frontmatter fields because `parse_frontmatter()` returns every key and `apply_filters()` does a plain dict lookup. The fix is parser-only; no code change is needed on the filter-application side to support custom fields. The test plan below adds explicit coverage to prevent regression.

**Invalid syntax:** any input the parser cannot classify (empty string, unknown operator, bare field) exits non-zero with a specific error message naming the problem and showing the four valid forms. No silent degradation.

### 2. `--fields` and `--all-fields` (custom-field output)

**Flag names (per captain directive):**
- `--fields field1,field2,...` — explicit comma-separated list of extra frontmatter fields to append to the default set.
- `--all-fields` — append every non-empty frontmatter field found across the scanned entities, minus the default set (to avoid duplicating `ID / SLUG / STATUS / TITLE / SCORE / SOURCE`).

**Output semantics:** both flags **append** to the default column set; they do not replace it. Rationale: replacement creates backcompat risk for any caller that greps the default columns, and append is strictly more informative. If a future need emerges for replacement, it can be added as `--only-fields` without breaking this contract. Out of scope for 123.

**Column ordering:**
- Default columns in their current order, followed by
- Extra fields in the order the user listed them (for `--fields`), or
- Extra fields in sorted order (for `--all-fields`) — sorted, not insertion-order, because scan order depends on filesystem and is not user-meaningful.

**Missing / empty field rendering:** empty string (same as existing empty-field rendering). No `-`, no `null`, no `(empty)`. Consistent with how the default table already shows empty `score` or `source`.

**Nonexistent field behavior:**
- `--fields nonexistent` — the column appears in the output with an empty value for every row. No error. Rationale: schemas evolve, and erroring on a key that simply does not appear in any entity yet (because the field was just introduced) is hostile. Consistency with `--where` on a nonexistent field, which already matches-as-empty.
- `--all-fields` on an empty workflow produces only the default columns (no extras to append).

**Conflicting flags:**
- `--fields` and `--all-fields` together → error (`--fields and --all-fields are mutually exclusive`).
- `--fields` / `--all-fields` with `--next` → extras are appended to the `--next` table as well, same append semantics. The FO frequently wants `--next --fields pr` to see PR state alongside dispatchable entities.
- `--fields` / `--all-fields` with `--boot` → error (`--boot emits a fixed multi-section format and does not accept --fields`). `--boot`'s structure is contractual; do not perturb it.
- `--fields` / `--all-fields` with `--set` → error (`--set does not produce a table`).

**Column width handling:** the current default table uses fixed `%-6s %-30s %-20s %-30s %-8s %s` widths. Extra fields use a sensible fixed width (20 chars for general fields, truncating with `…` if longer, to match the existing truncation-free default). This avoids a reflow of the default columns and keeps the implementation simple. If a value is longer than the column width, it is truncated with a trailing `…`. Full-width rendering is out of scope.

### 3. `--archive` subcommand

**Command shape:** `status --archive <slug>` (single flag with argument, matches the existing `--set <slug>` pattern). Rejected alternative: `status archive <slug>` as a subcommand — would require restructuring the entire argparse/hand-rolled parser surface, which is out of scope for a surgical pass.

**Behavior:**
1. Resolve `{workflow_dir}/{slug}.md`. If missing, error: `entity not found: {slug}.md`. Exit non-zero.
2. Ensure `{workflow_dir}/_archive/` exists (create if missing).
3. If `{workflow_dir}/_archive/{slug}.md` already exists, error: `already archived: {slug}.md` and exit non-zero. Idempotency is "already-there means stop, do not clobber."
4. Before moving, update the entity's frontmatter with `archived: <ISO-8601 UTC timestamp>`. Use the same `update_frontmatter()` path that `--set` uses — this is the "unify mutation paths" piece. The insert-if-missing behavior from task 122 means seeds without an `archived` placeholder still work.
5. Move the file via `os.rename()` (atomic on POSIX when source and destination are on the same filesystem, which `_archive/` always is).
6. Print `archived: {workflow_dir}/_archive/{slug}.md` to stdout on success.

**Interaction with `completed`:** `--archive` does **not** touch the `completed` field. `completed` is a task-lifecycle stamp set by the FO when a stage finishes (see `TIMESTAMP_FIELDS`); archival is a separate concept (the entity is removed from the active view) and the two can diverge (you might archive a task that never reached "done"). This keeps the semantic boundary between "task finished its work" and "task file moved out of the default view" clean.

**Does `--archive` check status?** No. The FO is the authority on when to archive; the tool enforces only the file-level invariants (file exists, archive directory writable, destination clear, frontmatter updatable). Hard-coding a "refuse to archive unless status=done" check would couple the tool to a specific workflow schema, which is exactly the coupling this task is trying to reduce.

**Schema flexibility:** the new `archived:` field is inserted unconditionally. Workflows that do not care about archival timestamps can ignore it. Workflows that do care can query it via `--where "archived !="`.

**Git semantics:** `--archive` moves the file but does **not** run `git add` / `git commit`. Commit remains the caller's responsibility (FO or human). Rationale: the tool stays pure file-level, callers retain control over commit messages and whether to batch archive moves with other changes. This matches the existing `--set` contract.

## 122 + 123 Landing Strategy

**Decision: land 123 independently. Task 122 is already closed.**

Task 122 shipped on 2026-04-10 (`pr: #67`, `verdict: PASSED`) and sits in `docs/plans/_archive/status-set-missing-field-silent-noop.md`. The seed description for 123 was written before 122 landed and still says "consider merging", but the situation has changed. Options (a) and (b) from the dispatch prompt are moot because there is nothing left to merge; only option (c) — land 123 independently — is actionable.

Concrete implications for 123:
- 123 can rely on 122's `update_frontmatter()` insert-if-missing behavior. The `--archive` side-effect (stamping `archived:`) reuses that path and does not need to re-derive it.
- 123's test suite can assume a `pr`-less seed is a valid input (because 122 made it so), which simplifies the `--archive` test fixtures.
- No release coordination needed. 123 can ship whenever it is ready.

## Scope

1. **Fix `--where` parser.** Accept `field=value`, `field = value`, `field!=value`, `field != value`, `field =`, `field !=`. Reject bare field names with a clear error listing the four valid forms. Operators in scope: `=` and `!=` only. Works on default and custom frontmatter fields (no code change needed beyond the parser — the filter layer is already generic).
2. **Add `--fields` flag.** `status --fields last-outbound-at,nudge-count` appends those fields as extra columns after the default set, preserving user-specified order. Missing fields render as empty. Nonexistent fields render as empty (no error).
3. **Add `--all-fields` flag.** `status --all-fields` appends every non-empty frontmatter field found across the scanned entities (minus the default set), in sorted order.
4. **Mutual exclusion.** `--fields` and `--all-fields` are mutually exclusive. `--fields` / `--all-fields` with `--boot` errors. `--fields` / `--all-fields` with `--set` errors. `--fields` / `--all-fields` with `--next` is allowed and appends to the next-table output.
5. **Add `--archive <slug>` subcommand.** Moves `{workflow_dir}/{slug}.md` to `{workflow_dir}/_archive/{slug}.md`, creating `_archive/` if missing, stamping `archived: <timestamp>` in frontmatter before the move, erroring on missing source or existing destination. Does not touch `completed`. Does not run git.
6. **Unit tests for every new behavior.** Extend `tests/test_status_script.py` (not a new file — the test module is already organized by flag, and new cases belong with their siblings).
7. **Update the status tool's header docstring.** The `instruction:` and `--where` behavior blocks at the top of `skills/commission/bin/status` must document the refined syntax, the `--fields` / `--all-fields` semantics, and the `--archive` subcommand. The rest of the skill scaffolding is out of scope (not touched in this task).

## Out of scope

- Rewriting status in another language or introducing PyYAML.
- Turning status into a full query language (`AND`/`OR`/`<`/`>`/`LIKE`/regex). `=` and `!=` only.
- Making status mutate body content — `Edit` stays with workers in worktrees.
- Editing mod files — stays with dispatched workers (scaffolding).
- `--only-fields` (replace default columns). Append-only for now.
- Column-width DSL / formatting flags.
- Git operations in `--archive` (commit, stage, branch). Caller's responsibility.
- Status-based gating on `--archive` (e.g., "refuse unless status=done"). Workflow-schema coupling.
- Revisiting task 122 — it is closed.
- Touching `skills/first-officer/` references to teach the FO about the new flags. The FO already uses `status --where` via its shared core; documentation alignment belongs to a later docs-sweep task, not to this implementation task.

## Acceptance Criteria

Each criterion names a specific test hook that will verify it. Unit tests live in `tests/test_status_script.py` unless noted.

**AC1 — `--where` accepts unspaced equality.** `status --where "status=watching"` returns the same result set as `status --where "status = watching"`, for both default (`status`) and custom (`last-outbound-at`) fields.
- Test: `TestWhereOption::test_equality_no_spaces` — fixture with two entities, run both spacing forms, assert identical output.
- Test: `TestWhereOption::test_equality_no_spaces_custom_field` — same but on a custom field.

**AC2 — `--where` accepts unspaced negation.** `status --where "status!=done"` returns the same result set as `status --where "status != done"`.
- Test: `TestWhereOption::test_negation_no_spaces`.

**AC3 — `--where` presence/absence still works.** `status --where "pr !="` returns entities with non-empty `pr`; `status --where "pr ="` returns entities with empty `pr`. Regression test — existing tests already cover this; no new test needed.
- Test: existing `TestWhereOption::test_non_empty_filter`, `test_empty_filter`, `test_non_empty_pr_field` must remain green.

**AC4 — `--where` rejects bare field names loudly.** `status --where "completed"` exits non-zero with an error message naming the four valid forms.
- Test: `TestWhereOption::test_bare_field_errors` — asserts non-zero exit, asserts stderr contains each of `field = value`, `field != value`, `field !=`, `field =`.

**AC5 — `--where` rejects unknown operators.** `status --where "status ~ watching"` exits non-zero with an error.
- Test: `TestWhereOption::test_unknown_operator_errors`.

**AC6 — `--fields` appends requested fields in order.** `status --fields pr,worktree` adds `PR` and `WORKTREE` columns after `SOURCE`, in that order, for each row. Fields not in the frontmatter render empty.
- Test: `TestFieldsOption::test_fields_appends_in_order` — fixture with mixed entities, assert header contains the new columns after `SOURCE` in order.
- Test: `TestFieldsOption::test_fields_missing_renders_empty`.

**AC7 — `--fields` accepts custom frontmatter fields.** `status --fields last-outbound-at` includes the custom field as a column, populated from frontmatter.
- Test: `TestFieldsOption::test_fields_custom_field_populated`.

**AC8 — `--fields` nonexistent field does not error.** `status --fields made-up-field` exits 0 and renders an empty column.
- Test: `TestFieldsOption::test_fields_nonexistent_no_error`.

**AC9 — `--all-fields` appends every non-empty custom field in sorted order.** Over a fixture with two entities that together carry `last-outbound-at` and `nudge-count` (custom), `--all-fields` appends those columns sorted alphabetically after the default set, and does not duplicate any default column.
- Test: `TestFieldsOption::test_all_fields_sorted_dedup`.

**AC10 — `--fields` and `--all-fields` are mutually exclusive.** Both flags together exit non-zero with a specific error.
- Test: `TestFieldsOption::test_fields_and_all_fields_conflict`.

**AC11 — `--fields` works with `--next`.** `status --next --fields pr` appends `pr` to the next-table output.
- Test: `TestFieldsOption::test_fields_composes_with_next`.

**AC12 — `--fields` / `--all-fields` with `--boot` errors.** Both flags combined with `--boot` exit non-zero.
- Test: `TestFieldsOption::test_fields_incompatible_with_boot`, `test_all_fields_incompatible_with_boot`.

**AC13 — `--fields` / `--all-fields` with `--set` errors.** Both flags combined with `--set` exit non-zero.
- Test: `TestFieldsOption::test_fields_incompatible_with_set`.

**AC14 — `--archive` moves the file and stamps `archived:`.** `status --archive my-slug` moves `my-slug.md` to `_archive/my-slug.md`, creates `_archive/` if missing, inserts/updates `archived: <timestamp>` in the frontmatter, and prints the new path.
- Test: `TestArchiveOption::test_archive_moves_and_stamps` — asserts the source file is gone, the destination exists, the destination's frontmatter contains an ISO-8601 `archived:` line, `_archive/` is created.

**AC15 — `--archive` errors on missing source.** `status --archive no-such-slug` exits non-zero with `entity not found`.
- Test: `TestArchiveOption::test_archive_missing_source_errors`.

**AC16 — `--archive` errors on existing destination.** Pre-seed `_archive/my-slug.md`, run `status --archive my-slug`, assert non-zero with `already archived`, assert both files still exist unchanged.
- Test: `TestArchiveOption::test_archive_existing_destination_errors`.

**AC17 — `--archive` does not touch `completed`.** Entity with `completed: 2026-01-01T00:00:00Z` survives archive; entity without `completed` does not have one added.
- Test: `TestArchiveOption::test_archive_preserves_completed`.

**AC18 — `--archive` does not run git.** After the move, `git status` in the fixture directory reports the move as an untracked change / deleted file (i.e., the tool did not auto-commit).
- Test: `TestArchiveOption::test_archive_does_not_commit` — fixture uses a `git init`'d tmpdir, asserts `git status --porcelain` shows the move as pending.

**AC19 — Default behavior unchanged.** `status` with no new flags produces identical output to the pre-change version.
- Test: the existing `TestDefaultStatus`, `TestNextOption`, `TestArchivedOption`, `TestSetOption`, `TestBootOption` test classes must all stay green without modification.

**AC20 — Header docstring documents the new surface.** The `instruction:` block at the top of `skills/commission/bin/status` mentions `--where` syntax (with and without spaces), `--fields`, `--all-fields`, and `--archive`.
- Test: `TestStatusDocstring::test_docstring_mentions_new_flags` — a static check that greps the script header for the four flag names and the phrase "with or without spaces". Low-cost correctness check that the implementer did not forget the docs.

## Test Plan

**Harness:** extend `tests/test_status_script.py`. The existing file already substitutes template variables, runs the script as a subprocess in a temp workflow dir, and has one test class per flag. New tests add three classes:

- `TestWhereOption` — 2 new tests (unspaced equality, unspaced negation, bare-field error, unknown-operator error). Existing `TestWhereOption` tests stay as regression coverage.
- `TestFieldsOption` — 10 new tests covering AC6-AC13.
- `TestArchiveOption` — 5 new tests covering AC14-AC18.
- `TestStatusDocstring` — 1 new test for AC20.

**Estimated count:** ~18 new tests, all unit-level subprocess tests against fixture directories. Each test runs in <100ms (no git operations except the one `test_archive_does_not_commit` which does a local `git init` in a tmpdir). Full suite impact: negligible.

**Cost/complexity:** low. The hardest piece is the `--where` parser refactor (maybe 30 lines changed), the easiest is the docstring check. No new dependencies, no fixtures beyond what tmpdir + small frontmatter strings already provide.

**E2E needed?** No. **Confirmed, not overruled.** Justification:
- All three gaps are pure CLI-tool behavior — no runtime, no worker dispatch, no inter-agent messaging.
- The existing status-script tests are subprocess-level (they exec the real Python script against real fixture directories), which is the right granularity for shell-tool correctness. They exercise the actual argv path, the actual file I/O, and the actual stdout format. There is no additional signal an E2E run would provide.
- The FO integration already has E2E coverage via the broader workflow suite; as long as the default-output and `--boot` paths stay green (AC19), that integration is protected by regression, not by new tests.
- `--archive` interacts with the filesystem and could in principle warrant an E2E, but the interaction is bounded to one file move + one frontmatter edit, both in a tmpdir. A subprocess-level test with `os.path.exists()` assertions gives the same coverage as an E2E at a fraction of the cost.

**Manual verification** (after tests pass):
1. Run the updated `status --where "status=watching"` against the live `docs/plans/` workflow — confirm non-zero rows returned. Contrast with a `grep -l "^status: watching$"` count.
2. Run `status --all-fields` against `docs/plans/` — visually scan for the custom fields the workflow uses.
3. Run `status --archive <slug>` on a test entity in a throwaway branch — confirm file moves, `archived:` line added, `git status` shows pending change without auto-commit.

**Regression surface:** the entire existing test suite. Must stay green. `--boot` in particular is contractual (`first-officer-shared-core.md` calls it at startup); its output format must not change.

## Edge cases considered

Listed explicitly so the implementation stage has a checklist; most are deferred to the implementation's judgment if they are not in the ACs:

1. **Values with spaces in `--where`.** `--where "title = My Task"` — the current parser uses `split(None, 1)` for the first token (field) and relies on remainder handling. The refined parser must carve out the operator from the joined string, then treat the remainder as the literal value (whitespace preserved). Implementation approach: find `!=` or `=` in the argument string, split on the first occurrence, strip both sides; the RHS may contain anything. Test `TestWhereOption::test_value_with_spaces`.
2. **Values with `=` in them.** `--where "slug = my=weird=slug"` — split on first `=`, RHS can contain more `=`. Same applies for `!=`. Test: optional; defer unless the implementation finds real workflows with `=` in values.
3. **Case sensitivity of field names.** YAML is case-sensitive. `--where` and `--fields` must match fields exactly as they appear in the frontmatter. `Status=watching` does NOT match `status: watching`. Documented in the `--where` error message and header docstring, no case-insensitive mode. Test: `TestWhereOption::test_field_name_case_sensitive`.
4. **Case sensitivity of values.** `--where "status = Watching"` does NOT match `status: watching`. Same rationale. No new test required — falls out of the existing equality path.
5. **Empty value on equality.** `--where "pr = "` — currently parses as absence (empty). The refined parser must preserve this. Test: existing `test_empty_filter` covers this; verify it still passes.
6. **Nonexistent field in `--where`.** Already documented and tested (`test_where_on_nonexistent_field`). No change.
7. **Nonexistent field in `--fields`.** Renders empty, no error. AC8.
8. **Conflicting flags.** Enumerated above (`--fields` + `--all-fields`, `--boot` + `--fields`, `--set` + `--fields`). ACs 10, 12, 13.
9. **`--fields` output ordering for duplicate requests.** `status --fields pr,pr` — implementation may dedupe or render twice. Recommendation: dedupe (once per field), but do not error. Low priority; test is optional.
10. **`--all-fields` with no entities.** Produces only default columns, no error, exits 0.
11. **`--all-fields` deduping against defaults.** If a custom field is named `status` or `id`, it is already a default — do not re-add it. Sorted order applies only to the non-default remainder.
12. **Long values in `--fields` output.** Truncation with `…` at the column width (20). Explicitly out of test scope; document as known limitation.
13. **`--archive` on an entity with an existing `archived:` field.** Update in place (reuse `update_frontmatter()` overwrite path). No error. Test: covered by AC14 phrasing ("inserts/updates").
14. **`--archive` with an archive destination on a different filesystem.** `os.rename()` may fail with `EXDEV`. For workflow directories this is essentially never the case (everyone's `_archive/` is a subdirectory of the workflow dir), but the implementation should fall back to `shutil.move()` if it wants to be safe. Recommendation: start with `os.rename()`, catch `OSError` and fall back. Low priority.
15. **`--archive` with a symlinked entity file.** Follow the symlink? Move the symlink? Recommendation: move whatever `os.path.exists()` sees — do not add symlink-handling complexity. Defer to implementation.
16. **Slug collisions.** Two entities with the same slug in different directories — not possible under the single-workflow-dir scan model. Not a concern for 123.
17. **Concurrent `--archive` calls.** Not addressed. The FO is single-threaded per workflow; concurrency is not a use case.
18. **Trailing whitespace in frontmatter values.** `parse_frontmatter()` already strips. No change.
19. **Frontmatter field names with dashes or underscores.** `last-outbound-at` contains dashes; `parse_frontmatter()` already handles them. Verify in `test_fields_custom_field_populated`.
20. **Empty `--fields` argument.** `status --fields ""` — error, `--fields requires a comma-separated list of field names`.

## Related

- **Task 122** `status-set-missing-field-silent-noop` — CLOSED as of 2026-04-10, PR #67, verdict PASSED. 123 inherits the insert-if-missing behavior that 122 shipped. See "122 + 123 Landing Strategy" above.
- **Task 121** `fo-context-aware-reuse` — FO reliability work from the same session, tangential; no shared files.
- **GTM FO external feedback (2026-04-10):** listed `--where` filter fix as their #2 priority after 122. Custom-fields viewer was a separate papercut of similar weight. Both addressed by 123.
- **Experiment FO external feedback (2026-04-10):** meta-theme was "prose where there should be structure." The status tool is one of the few places already structured, so this task stays within the structured zone and adds more structure (queryable custom fields) rather than less.
- `skills/first-officer/references/first-officer-shared-core.md` — documents `status --where`, `--boot`, `--next` as the FO's primary query interface. Any future docs-sync task should align this reference with the 123 changes; 123 itself does not touch the reference.

## Stage Report

### ideation — DONE

1. **Read entity body and status tool source.** DONE. Read `docs/plans/status-tool-as-workflow-op-cli.md`, `skills/commission/bin/status` (full 745 lines), `tests/test_status_script.py` (full `--where` suite at lines 447-608 plus default/next/boot sections), and `docs/plans/_archive/status-set-missing-field-silent-noop.md`. Also reproduced the `--where` bug locally against a two-entity fixture (`/tmp/wf-test/`) to confirm the parser hypothesis before writing the fix design.

2. **Refined entity body.** DONE. Rewrote the problem statement to name the three gaps with concrete root causes, replaced the handwavy "Design direction" with a worked-through "Proposed approach" covering all three, and produced 20 testable acceptance criteria.

3. **`--where` design decision.** DONE. Operators in scope: `=` and `!=`, with and without surrounding whitespace. Presence via `field !=` and `field =`. Bare field names (e.g., `completed`) now **error loudly** — this closes the silent-zero-rows hazard that masquerades as "filter returns nothing." Works identically on default and custom fields (the filter layer is already generic; fix is parser-only). Invalid syntax exits non-zero with a message naming the four valid forms. Recorded in "Proposed approach §1" and ACs 1-5.

4. **`--fields` / `--all-fields` design decision.** DONE. `--fields a,b,c` (explicit list, user-order) and `--all-fields` (every non-empty frontmatter field, sorted, deduped against defaults). Both **append** to the default column set — never replace. Missing/empty/nonexistent fields render as empty string (no error). Mutually exclusive with each other; incompatible with `--boot` and `--set`; compose with `--next`. Column width fixed at 20 chars with `…` truncation for overflow. Recorded in "Proposed approach §2" and ACs 6-13.

5. **`--archive` subcommand design decision.** DONE. Shape: `status --archive <slug>` (single flag with argument, matches `--set`). Side-effects: stamps `archived: <ISO-8601 UTC>` via the `update_frontmatter()` path that 122 fixed, then `os.rename()` to `_archive/`. Errors on missing source (`entity not found`) and on existing destination (`already archived`). Does NOT touch `completed` (separate concept from archival). Does NOT run git (caller's responsibility, matches `--set`). Does NOT gate on status (tool stays schema-agnostic). Recorded in "Proposed approach §3" and ACs 14-18.

6. **122 + 123 landing strategy.** DONE. Recommendation: **(c) land 123 independently. 122 is already closed** (PR #67, verdict PASSED, in `_archive/`). Options (a) "merge 122 into 123" and (b) "land back-to-back" are moot because 122 already shipped on 2026-04-10. 123 inherits 122's insert-if-missing behavior in `update_frontmatter()` and reuses it for the `--archive` frontmatter side-effect. Recorded in the dedicated "122 + 123 Landing Strategy" section.

7. **Refined acceptance criteria.** DONE. 20 ACs, each naming a specific test case by class and method name. No AC without a test hook.

8. **Test plan.** DONE. ~18 new tests in `tests/test_status_script.py`, organized into three new test classes (`TestWhereOption` additions, `TestFieldsOption`, `TestArchiveOption`) plus one static docstring check (`TestStatusDocstring`). **E2E not needed, confirmed not overruled**, with four-bullet justification: pure tool behavior, existing subprocess-level harness is the right granularity, FO integration is protected by AC19 regression, `--archive` filesystem interaction is bounded to tmpdir `os.path.exists()` assertions.

9. **Edge-case inventory.** DONE. 20 edge cases enumerated: values with spaces, values with `=`, case sensitivity of field names AND values (separately), empty values, nonexistent fields in both `--where` and `--fields`, conflicting flags, duplicate `--fields` entries, `--all-fields` deduping against defaults and handling empty workflows, long-value truncation, `--archive` on pre-archived fields, `EXDEV` cross-filesystem fallback, symlinks, slug collisions, concurrency, trailing whitespace, dash/underscore field names, empty `--fields` argument.

10. **Terminology audit.** DONE. Grepped the refined body for the literal string "column":
    - Total occurrences of "column" (case-insensitive): 29.
    - Every occurrence refers to the **visual output column** in the default or extended table — not to the CLI flag mechanism.
    - Zero occurrences of the old `--col` + `umns` flag name in the design sections (scope, proposed approach, acceptance criteria, test plan, edge cases). The only places the old flag name is mentioned are here in this audit bullet and in the summary, both in a meta-reference explaining that the flag was renamed.
    - `--fields` and `--all-fields` used consistently throughout scope, acceptance criteria, test plan, and edge cases.

11. **Commit.** DONE via follow-up bash call below. Message: `ideation: status-tool-as-workflow-op-cli — refined scope, acceptance criteria, test plan`. Frontmatter preserved byte-for-byte. No files outside `docs/plans/status-tool-as-workflow-op-cli.md` touched.

### Summary

Three design decisions landed: (1) `--where` parser accepts both spaced and unspaced forms for `=` and `!=`, rejects bare field names loudly, works uniformly on custom fields (fix is parser-only, filter layer already generic); (2) `--fields` / `--all-fields` append (never replace) to the default columns, with `--fields` taking an explicit comma-separated list in user order and `--all-fields` taking every non-empty frontmatter key in sorted deduped order, both compose with `--next`, both error with `--boot` and `--set`; (3) `--archive <slug>` stamps `archived:` via the `update_frontmatter()` path and `os.rename()`s into `_archive/`, leaving `completed` alone and not running git. Task 122 is already closed so 123 lands independently, inheriting the insert-if-missing behavior 122 shipped. 20 acceptance criteria, each with a named test hook; ~18 new subprocess-level unit tests; E2E not needed and confirmed not overruled. Terminology directive applied: "fields" used consistently for the CLI mechanism, "column" used only for the visual table layout, and the prior flag name (`--` + `columns`) does not appear in the design sections. One item left explicitly open for the implementation stage: whether to dedupe duplicate `--fields` entries (AC doesn't require it; recommendation is to dedupe silently).

One flag for the first officer: the original seed says "fix `--where` filter returns zero rows for valid queries" as if the filter were broken. It is not — it is a UX bug where the parser accepts SQL-like syntax that users naturally type, silently misclassifies it, and produces wrong results. The refined ACs name the real behavior (`test_equality_no_spaces`) rather than the reported symptom. The GTM FO's `grep` workaround was correct defense, but the bug is a parser UX issue, not a correctness issue in the filter engine.
