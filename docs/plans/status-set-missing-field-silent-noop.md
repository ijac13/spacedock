---
id: 122
title: "status --set silently no-ops when target field is missing from frontmatter"
status: validation
source: FO observation during 118 merge hook execution (2026-04-10)
score: 0.70
worktree: .worktrees/spacedock-ensign-status-set-missing-field
started: 2026-04-10T21:24:08Z
completed:
verdict:
issue:
pr:
---

`skills/commission/bin/status --set {slug} {field}={value}` reports success and echoes the intended field=value pair to stdout, but does NOT write anything to the entity file when the target `{field}` is not already present in the YAML frontmatter. The file is unchanged, `git diff` is empty, and the only signal is the stdout echo (which looks identical to a successful write).

## Repro

1. Seed an entity with minimal frontmatter — no `pr`, no `worktree`, no `started`, etc.:

   ```yaml
   ---
   id: 999
   title: Minimal seed
   status: backlog
   source: test
   score: 0.5
   ---

   Body content.
   ```

2. Run `status --set minimal-seed pr=#42`.
3. Stdout shows `pr: #42`.
4. `git diff docs/plans/minimal-seed.md` → empty.
5. The `pr` field is never added to the frontmatter.

Contrast with the "field already exists" case:

1. Seed with empty placeholder fields:

   ```yaml
   ---
   id: 999
   title: Minimal seed
   status: backlog
   source: test
   score: 0.5
   pr:
   worktree:
   started:
   completed:
   verdict:
   issue:
   ---
   ```

2. Run `status --set minimal-seed pr=#42`.
3. Stdout shows `pr: #42`.
4. `git diff` shows the `pr:` line populated.
5. Success.

## Observed impact

This bit the FO twice in a single session (2026-04-10) on task 118:

1. **Fast-track to implementation.** FO ran `status --set 118 status=implementation worktree=.worktrees/... started`. Output showed all three fields set. The subsequent commit (`cf25065`) recorded `1 file changed, 1 insertion(+), 1 deletion(-)` — only 1 line changed. The worktree and started values were silently dropped; only `status` actually updated because only `status` existed in the frontmatter. FO didn't notice at the time because the stdout was deceptive.

2. **Merge hook PR field.** After 118 validation passed and PR #64 was created, FO ran `status --set 118 pr=#64`. Output showed `pr: #64`. `git add` + `git commit` reported "nothing added to commit". FO dug in, found the frontmatter had no `pr:` field, and had to manually Edit the file to add all six standard workflow fields (`worktree`, `started`, `completed`, `verdict`, `issue`, `pr`) before the commit could record the `pr: #64` write.

Both cases conformed to the same failure pattern: minimal seed → status --set reports success → file unchanged.

## Why this is bad

- **Silent data loss.** The FO writes what it thinks is state into a file that never received it. Downstream logic (orphan detection, PR-pending scans, dispatchable queries) sees a different state than the FO believes.
- **Misleading output.** The stdout echo looks identical to a successful write. There is no way to distinguish "wrote to file" from "target field absent, discarded" without a post-hoc `git diff`.
- **Couples seeds to a hidden schema.** Every seed file must include empty placeholder versions of every field the FO might later want to set. If a seed is missing a field, later `--set` calls on that field are no-ops. This is undocumented; it's implicit knowledge from reading existing seeds (115's seed happens to include all six placeholders; 118's seed I wrote minimal and got bitten).

## Fix options

The ideation stage should pick one:

1. **Add missing fields automatically.** When `--set` targets a missing field, the tool adds the field to the frontmatter in-place with the specified value. Probably the most ergonomic.
2. **Error loudly when the field is missing.** `status --set` exits non-zero with a clear error message ("field 'pr' not present in entity frontmatter; seed may be missing required placeholder fields; run `commission` to regenerate"). This forces the seeder to fix the schema.
3. **Emit a complete frontmatter template at seed time.** Commission and refit always write the full standard field set (even empty) into every new entity file. Combined with (2) for defense-in-depth, this gives both loud errors AND prevents the common case from occurring.
4. **Echo only what was actually written.** If the write was a no-op, stdout echoes nothing (or echoes with a warning prefix). Minimum viable fix: the tool doesn't LIE about success.

The captain should decide between (1) "add fields on demand" and (2+3) "enforce a canonical schema". They have different implications for workflow schema flexibility.

## Scope

1. Reproduce the bug against a fresh fixture (or use the observed 2026-04-10 evidence; the fix is straightforward).
2. Apply the chosen fix to `skills/commission/bin/status` (Python script).
3. Update `skills/commission/SKILL.md` if the fix changes the documented contract (e.g., the seed template section needs updating).
4. Add unit tests for the fix in a new `tests/test_status_set_missing_field.py` (or similar) covering: missing-field write, present-field write, combined missing-and-present write, error message contents if option 2 is picked.
5. No runtime adapter changes needed — this is a commission/status tool bug, not an FO runtime bug.

## Acceptance Criteria

1. Given a seed with minimal frontmatter (missing `pr` field), running `status --set slug pr=#N` either (a) writes the field to the file, or (b) exits non-zero with a clear error message. It must NOT silently no-op.
   - Test: new unit test asserts the chosen behavior end-to-end.
2. The FO seeding a new entity with minimal frontmatter does not suffer silent data loss on subsequent `status --set` calls for standard workflow fields (`pr`, `worktree`, `started`, `completed`, `verdict`, `issue`).
   - Test: integration check; optional if AC-1's unit test is sufficient.
3. The fix does not break existing behavior on seeds with complete frontmatter.
   - Test: existing `status --set` test coverage (if any) stays green; add a regression test for the present-field path.
4. `skills/commission/SKILL.md` and the workflow README template (if applicable) are updated if the seed schema becomes stricter.
   - Test: manual inspection.

## Test Plan

- Unit tests in `tests/test_status_set_missing_field.py` covering the four cases in the fix options section.
- Integration run: seed a fresh test entity with minimal frontmatter in a temp workflow directory, run `status --set` against each standard field, verify either write or error.
- No E2E needed — this is a tool-level bug, not a runtime behavior.

## Out of scope

- Refactoring `status` into a proper library with a tested API surface — too broad. The fix is surgical.
- Reworking commission's seed template to explicitly list placeholder fields (that's a different task — here the fix is on the status tool's `--set` code path).
- Adding type coercion or field validation beyond the specific "does this field exist" check.

## Related

- Task 115 `fo-dispatch-template-completion-signal` — whose seed I wrote WITH all six placeholder fields, which is why 115's `status --set` calls worked without issue. This is the accidental-correctness precedent.
- Task 118 `pr-merge-mod-rich-body-template` — whose seed I wrote minimally, which is where I hit the bug twice.
- Task 121 `fo-context-aware-reuse` — adjacent FO reliability concern, tangential.
- The minimal seed pattern was written because the FO Write Scope rule says "new entity files — seed task creation (frontmatter + brief description body)" without specifying which fields are required. Seeds should probably have a canonical schema.

## Stage Report: implementation

**Approach:** Option 1 — add missing fields automatically. When `--set` targets a field not present in the frontmatter, insert it before the closing `---`.

**Root cause:** `update_frontmatter()` in `skills/commission/bin/status` (line 574) iterates only over existing frontmatter lines and rewrites matches. Fields not already present are silently ignored — `resolved` dict contains the intended values but they are never written.

**Fix (8 lines changed in `skills/commission/bin/status`):**
- Track which resolved fields were actually written during the existing-line rewrite loop (`written` set).
- After the loop, compute `missing = [f for f in resolved if f not in written]`.
- Insert each missing field as `{field}: {value}` before the closing `---` line, incrementing `fm_end` to keep the insertion point correct for multiple missing fields.

**Tests added (`tests/test_status_set_missing_field.py`, 5 tests):**
1. `test_set_missing_field_inserts_it` — core bug fix: missing `pr` field is inserted.
2. `test_set_existing_field_still_works` — regression: existing field update path unchanged.
3. `test_set_mixed_existing_and_missing_fields` — mixed: `status` (existing) + `pr` + `worktree` (missing) all written.
4. `test_set_missing_field_preserves_body` — body content after frontmatter is intact.
5. `test_set_missing_field_preserves_existing_fields` — unmodified fields (id, title, status) are untouched.

**Test results:**
- New tests: 5/5 passed (2 failed before fix, confirming bug).
- Existing `test_status_script.py`: 66/66 passed (no regressions).
- Static suite `test_agent_content.py`: 18/18 passed.

**Commits:**
- `2d11d2e` — test: add failing tests for --set with missing frontmatter field
- `166ecb1` — fix: update_frontmatter inserts fields missing from frontmatter

## Stage Report: validation

**Validator:** Claude (ensign worker)

**Verification performed:**

1. **Diff inspection:** 3 commits on branch (`2d11d2e`, `166ecb1`, `aca4884`). Changed files: `skills/commission/bin/status` (8-line fix), `tests/test_status_set_missing_field.py` (149 lines, 5 tests), `docs/plans/status-set-missing-field-silent-noop.md` (stage report). Two phantom diffs on unrelated plan files from main advancing. Scope is clean.

2. **Fix logic review:** The fix tracks written fields in a `set`, computes missing fields after the rewrite loop, and inserts them before the closing `---` with correct `fm_end` increment for multiple inserts. Edge cases verified: empty frontmatter (all fields inserted), special YAML characters (matches existing behavior), empty values (works), insertion order (stable, follows `resolved` dict order).

3. **New tests:** 5/5 passed.
4. **Existing status tests:** 66/66 passed, no regressions.
5. **Static suite:** 18/18 passed.
6. **Manual repro:** Created temp entity with only `id`, `title`, `status`. Ran `status --set task-x pr=#99`. Confirmed `pr: #99` inserted before closing `---`, body preserved, existing fields untouched.

**Per-AC verdicts:**

- **AC1** (missing field written or errors loudly): PASS — `pr=#99` on a seed missing `pr` inserts the field. Confirmed via test and manual repro.
- **AC2** (existing behavior not broken): PASS — 66/66 existing tests pass; `test_set_existing_field_still_works` confirms update path.
- **AC3** (SKILL.md / README template updated if schema stricter): N/A — fix is additive (auto-inserts missing fields), schema is not stricter.
- **AC4** (tests cover four cases): PASS — 5 tests cover: insertion of missing field, existing field update, mixed fields, body preservation, existing field preservation.

**Recommendation: PASSED**
