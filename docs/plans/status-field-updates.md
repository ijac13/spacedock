---
id: 094
title: Status script entity field updates
status: validation
source: CL — observed FO using T00:00:00Z placeholder timestamps instead of real wallclock times
started: 2026-04-07T19:30:37Z
completed:
verdict:
score: 0.7
worktree: .worktrees/spacedock-ensign-status-field-updates
issue:
pr: "#43"
---

# Status script entity field updates

## Problem

The FO manually edits YAML frontmatter for state transitions (status changes, setting `started`, `completed`, `worktree`, etc.). This is error-prone — observed the FO using `T00:00:00Z` placeholder timestamps instead of capturing real wallclock times. The status script already parses all frontmatter fields but currently only reads them.

## Design space

Two approaches to explore in ideation:

1. **`--advance {slug} {stage}`** — purpose-built for the FO's most common operation. Updates `status`, auto-sets `started` with real timestamp if not already set. Simple, narrow scope.

2. **`--set {slug} {field}={value}`** — generic field modifier. Could handle any frontmatter field (`status`, `worktree`, `pr`, `verdict`, etc.) with auto-timestamping as a side effect of specific field changes. More flexible but needs rules about which fields trigger side effects.

The right answer may depend on how many FO frontmatter operations this would replace vs. how much implicit behavior is acceptable in a CLI tool.

## Stage Report

### 1. Problem statement — DONE

The FO performs four categories of frontmatter write operations, all via Edit tool calls with manually-constructed YAML values:

| Operation | Fields modified | When | Frequency |
|---|---|---|---|
| **Dispatch** | `status`, `worktree`, `started` | Entity moves to next stage | Every stage transition (~5x per entity lifecycle) |
| **Advance (reuse)** | `status` | Agent reused for next stage | Subset of dispatches where reuse conditions hold |
| **Merge/cleanup** | `completed`, `verdict`, clear `worktree` | Entity reaches terminal stage | Once per entity |
| **PR field** | `pr` | Merge hook sets PR number | Once per entity (when PR merge mod is active) |

**Error modes observed:**
- **Placeholder timestamps**: The FO uses `T00:00:00Z` instead of real wallclock times because it does not have reliable access to the current time when constructing Edit tool calls. This is the motivating problem — CL observed this directly.
- **Manual YAML construction**: Each Edit call requires the FO to construct the exact frontmatter line. Typos, wrong field names, or incorrect indentation can corrupt the entity file.
- **Inconsistent `started` setting**: The FO must remember to set `started` only on first dispatch beyond the initial stage. If it forgets, the field stays empty; if it re-sets it on later transitions, the original start time is overwritten.
- **Field clearing**: Clearing `worktree` at merge requires the FO to set it to empty string. The FO sometimes leaves stale worktree paths.

**Total Edit calls per entity lifecycle:** ~7 frontmatter edits (5 dispatch/advance + 1 merge cleanup + 1 PR field). Each is a manual YAML edit that could be a single CLI call.

### 2. Proposed approach — DONE

**Recommendation: `--set` with auto-timestamping rules**

Both approaches were evaluated:

#### Option A: `--advance {slug} {stage}`

```
status --workflow-dir {dir} --advance {slug} ideation
```

Pros:
- Simple, purpose-built for the most common operation (dispatch)
- Can encode all the implicit behavior (auto-set `started`, auto-set `worktree`) without ambiguity
- Fewer foot-guns — only does state transitions

Cons:
- Does not cover merge/cleanup operations (`completed`, `verdict`, clear `worktree`)
- Does not cover `pr` field setting
- Would need additional flags for each non-transition operation: `--complete`, `--set-pr`, etc.
- Narrow scope means the FO still needs Edit calls for non-transition fields

#### Option B: `--set {slug} {field}={value}`

```
status --workflow-dir {dir} --set {slug} status=ideation
status --workflow-dir {dir} --set {slug} worktree=.worktrees/ensign-foo
status --workflow-dir {dir} --set {slug} completed verdict=PASSED worktree=
```

Pros:
- Covers ALL frontmatter write operations with one interface
- Eliminates Edit tool calls entirely for frontmatter
- Multiple fields in one call reduces tool call count further
- Auto-timestamping can be a side-effect rule: setting a timestamp field without `=value` fills it with `now()`
- Field clearing is explicit: `worktree=` sets to empty

Cons:
- More surface area — the FO could set arbitrary fields
- Auto-timestamping rules need clear documentation
- Slightly more complex implementation

#### Why `--set` wins

The FO's frontmatter operations are not just state transitions. Merge/cleanup requires setting `completed`, `verdict`, and clearing `worktree` in one atomic edit. The `--advance` approach would cover ~70% of operations but still leave the FO doing manual Edit calls for the rest. `--set` covers 100%.

The auto-timestamping rule is simple and predictable: timestamp fields (`started`, `completed`) without an explicit `=value` get filled with `now()` in ISO 8601 format. All other fields require explicit values. This is minimal implicit behavior — the FO always knows what it is asking for.

#### Detailed design

**Syntax:**
```
status --workflow-dir {dir} --set {slug} {field}={value} [{field}={value} ...]
```

**Rules:**
1. `{slug}` identifies the entity file (`{slug}.md` in the workflow directory)
2. Each `{field}={value}` sets that frontmatter field to the given value
3. `{field}=` (empty value) clears the field
4. Timestamp fields (`started`, `completed`) with no `=` at all (bare field name) auto-fill with current UTC time in ISO 8601 format (`YYYY-MM-DDTHH:MM:SSZ`)
5. Non-timestamp fields without `=` are an error (ambiguous intent)
6. The entity file must exist; exit non-zero if not found
7. Fields not mentioned in the command are left unchanged
8. Output: the updated frontmatter fields on stdout (so the FO can verify the write without a subsequent Read)

**Example FO operations replaced:**

Dispatch:
```bash
# Before: 3 Edit calls
# After: 1 call
status --workflow-dir docs/plans --set my-task status=ideation worktree=.worktrees/ensign-my-task started
```

Merge cleanup:
```bash
# Before: 3 Edit calls (set completed, set verdict, clear worktree)
# After: 1 call
status --workflow-dir docs/plans --set my-task completed verdict=PASSED worktree=
```

PR field:
```bash
status --workflow-dir docs/plans --set my-task pr=#42
```

**Frontmatter rewriting approach:**

The status script already has `parse_frontmatter()` which reads fields line-by-line. The `--set` writer should use the same line-by-line approach:
1. Read the file
2. Walk through lines between `---` delimiters
3. For each line matching a target field, replace the value portion
4. Write the file back
5. Print the updated fields to stdout

This preserves field ordering, comments, and any non-frontmatter content in the file body.

### 3. Acceptance criteria — DONE

| # | Criterion | Test method |
|---|-----------|-------------|
| AC1 | `--set {slug} {field}={value}` updates the specified field in the entity's frontmatter | Unit test: create entity, run `--set`, re-parse frontmatter, verify field value |
| AC2 | Multiple `{field}={value}` pairs in one call update all specified fields atomically | Unit test: `--set slug status=ideation worktree=.worktrees/foo`, verify both changed |
| AC3 | `{field}=` (empty value) clears the field to empty | Unit test: entity with `worktree: .worktrees/foo`, run `--set slug worktree=`, verify empty |
| AC4 | Bare timestamp field name (`started`, `completed`) auto-fills with current UTC ISO 8601 time | Unit test: run `--set slug started`, parse the result, verify it matches `YYYY-MM-DDTHH:MM:SSZ` pattern and is within a few seconds of test execution time |
| AC5 | Bare non-timestamp field name is rejected with an error | Unit test: `--set slug status` (no `=`), verify non-zero exit and error message |
| AC6 | Entity file must exist; non-zero exit and error message if missing | Unit test: `--set nonexistent status=foo`, verify non-zero exit and error message |
| AC7 | Fields not specified in the command are preserved unchanged | Unit test: entity with `title: Foo`, `score: 0.8`, run `--set slug status=done`, verify title and score unchanged |
| AC8 | File body content below frontmatter is preserved unchanged | Unit test: entity with body text, run `--set slug status=done`, verify body text unchanged |
| AC9 | Updated fields are printed to stdout after write | Unit test: capture stdout from `--set slug status=done`, verify it contains `status: done` |
| AC10 | `--set` is incompatible with `--next`, `--archived`, `--boot`, and `--where` | Unit test: verify error message for each incompatible combination |
| AC11 | Timestamp auto-fill does NOT overwrite an existing value when `{field}=` syntax is not used | Unit test: entity with `started: 2026-01-01T00:00:00Z`, run `--set slug started`, verify original value is preserved (auto-fill only applies when field is currently empty) — **OR** the explicit value is overwritten. This requires a design decision. |
| AC12 | `--set` requires `--workflow-dir` or `PIPELINE_DIR` to locate entity files | Unit test: verify it finds entity files correctly |

**Design decision needed for AC11:** When the FO runs `--set slug started` and `started` already has a value, should it (a) skip and preserve the existing value, or (b) overwrite with `now()`? The shared core says "set `started:` when the entity first moves beyond the initial stage" — implying it should only be set once. Option (a) makes the tool enforce this rule implicitly. Option (b) makes it explicit — the FO must check before calling. Recommendation: **(a) skip if already set** — this eliminates one more error mode where the FO accidentally overwrites the original start time.

### 4. Test plan — DONE

**Test type:** Unit tests in `tests/test_status_script.py`, extending the existing test class pattern.

**Approach:** Add a new `TestSetOption` test class following the `TestNextOption` / `TestWhereFilter` pattern. Tests use `tempfile.TemporaryDirectory()`, `make_pipeline()`, and `entity()` helpers.

**Test methods (12, mapping to ACs):**

1. `test_set_single_field` — AC1
2. `test_set_multiple_fields` — AC2
3. `test_set_clear_field` — AC3
4. `test_set_timestamp_auto_fill` — AC4 (verify ISO 8601 pattern, check within tolerance)
5. `test_set_bare_non_timestamp_error` — AC5
6. `test_set_nonexistent_entity_error` — AC6
7. `test_set_preserves_unmodified_fields` — AC7
8. `test_set_preserves_body` — AC8
9. `test_set_prints_updated_fields` — AC9
10. `test_set_incompatible_flags` — AC10 (4 sub-assertions: --next, --archived, --boot, --where)
11. `test_set_timestamp_skip_if_already_set` — AC11 (assuming design decision (a))
12. `test_set_uses_workflow_dir` — AC12

**Estimated scope:**
- ~12 test methods in one new test class (~150-200 lines of test code)
- ~80-120 lines of implementation code in the status script (frontmatter writer function + `--set` parsing in `main()`)
- No E2E tests needed — all operations are file reads/writes with deterministic output, testable with temp directories
- No subprocess mocking needed (unlike `--boot`) — `--set` is pure file I/O plus `datetime.utcnow()`
- Time-sensitive test (AC4) uses a tolerance window rather than exact matching

**Cost/complexity:** Low-medium. Simpler than `--boot` because there are no subprocess calls to mock. The frontmatter rewriting is the only non-trivial part, and it follows the same line-by-line approach already used by `parse_frontmatter()`.

**Dependency on task 089:** None at the implementation level. `--set` and `--boot` are independent flags with separate code paths. The incompatibility check (AC10) references `--boot` but that is a one-line check in `main()`. If 089 lands first, the test for boot+set incompatibility can reference the real flag; if not, the test still works as long as the incompatibility check is present in the `--set` code path.

## Stage Report — implementation

1. Add `--set {slug} {field}={value}` flag to `skills/commission/bin/status` — **DONE**
2. Implement field=value setting for any frontmatter field — **DONE**
3. Implement field= (empty value) to clear fields — **DONE**
4. Implement bare timestamp auto-fill (started, completed) with skip-if-set behavior — **DONE**
5. Implement bare non-timestamp field rejection — **DONE**
6. Implement entity existence check — **DONE**
7. Implement stdout output of updated fields — **DONE**
8. Flag incompatibility with --next, --archived, --boot, --where — **DONE**
9. Write unit tests in tests/test_status_script.py covering AC1-AC12 — **DONE** (12 test methods in TestSetOption class)
10. All existing tests still pass — **DONE** (33 existing tests pass)
11. All new tests pass — **DONE** (12 new tests pass, 45 total)

**Files modified:**
- `skills/commission/bin/status` — added `parse_set_args()`, `update_frontmatter()`, `TIMESTAMP_FIELDS`, and `--set` handling in `main()` (~90 lines of implementation)
- `tests/test_status_script.py` — added `TestSetOption` class with 12 test methods (~230 lines of test code)

## Stage Report — validation

### Test run

All 45 tests pass (33 existing + 12 new `TestSetOption` tests):

```
tests/test_status_script.py::TestSetOption::test_set_single_field PASSED
tests/test_status_script.py::TestSetOption::test_set_multiple_fields PASSED
tests/test_status_script.py::TestSetOption::test_set_clear_field PASSED
tests/test_status_script.py::TestSetOption::test_set_timestamp_auto_fill PASSED
tests/test_status_script.py::TestSetOption::test_set_bare_non_timestamp_error PASSED
tests/test_status_script.py::TestSetOption::test_set_nonexistent_entity_error PASSED
tests/test_status_script.py::TestSetOption::test_set_preserves_unmodified_fields PASSED
tests/test_status_script.py::TestSetOption::test_set_preserves_body PASSED
tests/test_status_script.py::TestSetOption::test_set_prints_updated_fields PASSED
tests/test_status_script.py::TestSetOption::test_set_incompatible_flags PASSED
tests/test_status_script.py::TestSetOption::test_set_timestamp_skip_if_already_set PASSED
tests/test_status_script.py::TestSetOption::test_set_uses_workflow_dir PASSED
```

No existing tests regressed.

### Acceptance criteria

1. **AC1 — --set updates specified field**: DONE. `test_set_single_field` sets `status=ideation` and verifies the frontmatter value changed. Manual verification also confirms correct rewrite.
2. **AC2 — multiple fields updated atomically**: DONE. `test_set_multiple_fields` sets `status=ideation` and `worktree=.worktrees/ensign-foo` in one call, verifies both changed.
3. **AC3 — field= clears to empty**: DONE. `test_set_clear_field` sets `worktree=` on an entity with a non-empty worktree, verifies the field is empty afterward.
4. **AC4 — bare timestamp auto-fills with UTC ISO 8601**: DONE. `test_set_timestamp_auto_fill` calls `--set task-a started`, verifies the result matches `YYYY-MM-DDTHH:MM:SSZ` format and is within tolerance of test execution time. Manual verification confirmed real wallclock time is captured.
5. **AC5 — bare non-timestamp field rejected**: DONE. `test_set_bare_non_timestamp_error` calls `--set task-a status` (no `=`), verifies non-zero exit and error message referencing the field name.
6. **AC6 — nonexistent entity returns error**: DONE. `test_set_nonexistent_entity_error` calls `--set nonexistent status=done`, verifies non-zero exit and error message containing the slug.
7. **AC7 — unspecified fields preserved**: DONE. `test_set_preserves_unmodified_fields` sets only `status=done`, then verifies `title`, `score`, `source`, and `id` are unchanged.
8. **AC8 — file body preserved**: DONE. `test_set_preserves_body` reads the body before and after `--set`, verifies they are identical.
9. **AC9 — updated fields printed to stdout**: DONE. `test_set_prints_updated_fields` verifies stdout contains `status: done` after setting that field. Manual verification also shows bare timestamp auto-fill prints the resolved timestamp.
10. **AC10 — incompatible with --next, --archived, --boot, --where**: DONE. `test_set_incompatible_flags` tests all four flags, verifies non-zero exit and error message containing "cannot" for each.
11. **AC11 — timestamp auto-fill skips if already set**: DONE. `test_set_timestamp_skip_if_already_set` creates an entity with `started: 2026-01-01T00:00:00Z`, runs `--set task-a started`, verifies the original value is preserved. Manual verification also confirmed that stdout is empty (no fields resolved) and the file is unchanged.
12. **AC12 — --set uses workflow-dir to locate entities**: DONE. `test_set_uses_workflow_dir` uses `--workflow-dir` explicitly (no `PIPELINE_DIR` env var) and verifies the entity is found and updated.

### Implementation review notes

- `parse_set_args()` correctly separates slug from field arguments and handles the three forms: `field=value`, `field=` (clear), and bare timestamp field names.
- `update_frontmatter()` uses line-by-line rewriting that preserves field ordering and body content. It reads current values first to implement skip-if-set for timestamp fields.
- The `TIMESTAMP_FIELDS` set is defined at module level as `{'started', 'completed'}`, matching the design spec.
- Incompatibility checking in `main()` correctly detects all four flags (`--next`, `--archived`, `--boot`, `--where`).
- No regressions in existing functionality.

### Recommendation

**PASSED**
