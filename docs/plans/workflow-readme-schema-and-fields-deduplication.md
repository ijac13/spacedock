---
id: 144
title: "Workflow README — `## Schema` YAML and `### Field Reference` table are redundant"
status: done
source: CL observation on a fresh commissioned workflow README during 2026-04-13 session
started: 2026-04-14T04:31:46Z
completed:
verdict:
score: 0.45
worktree: .worktrees/spacedock-ensign-workflow-readme-schema-and-fields-deduplication
issue:
pr: #91
mod-block: 
---

A freshly commissioned workflow README emits two adjacent sections that describe the same per-entity fields:

1. `## Schema` — a YAML frontmatter block that lists every field with an empty value, e.g.

   ```yaml
   id:
   title: Human-readable name
   status: backlog
   source:
   ...
   ```

2. `### Field Reference` — a table that lists the same fields again with `Field | Type | Description` columns.

The duplication is observable in `docs/plans/README.md` (this very workflow) but it ships from the `commission` skill, so every newly commissioned workflow inherits it. Maintainers have to update fields in two places, and readers see the same information twice.

This task should pick one canonical representation in the commission skill's emitted README template and remove the other. Candidates:

- Keep the `### Field Reference` table only — richer (Type column, longer descriptions) and more discoverable for someone scanning the doc.
- Keep the `## Schema` YAML block only — closer to the actual on-disk shape; can serve as a copy-paste template.
- Keep both but clearly mark one as authoritative and the other as derived (the "## Task Template" section near the bottom of the README is already a copy-paste template, so the YAML in `## Schema` is the redundant copy).

The likely answer is to drop the YAML block from `## Schema` and let the `## Task Template` section near the bottom serve as the copy-paste shape. `## Schema` becomes an introductory sentence pointing at the table.

Scope:

- Edit the README template in the commission skill so future workflows ship with one representation.
- Decide whether to retroactively fix `docs/plans/README.md` and any other already-commissioned workflows in the repo, or leave them.
- Static test (or doc lint) asserting the emitted README does not duplicate field listings.

## Stage Report

### 1. Exact duplication identified

Three sections in the commissioned README carry overlapping field information:

**`## Schema` (lines 37-54 of `docs/plans/README.md`)** — a YAML block listing every frontmatter field with empty/default values:

```yaml
---
id:
title: Human-readable name
status: backlog
source:
started:
completed:
verdict:
score:
worktree:
issue:
pr:
---
```

**`### Field Reference` (lines 56-71)** — a table repeating the same 12 fields with Type and Description columns:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier... |
| `title` | string | Human-readable task name |
| ... | ... | ... |

**`## Task Template` (lines 157-173)** — another YAML block with the same 12 fields plus a body placeholder:

```yaml
---
id:
title: Task name here
status: backlog
...
---

Description of this task and what it aims to achieve.
```

The `## Schema` YAML block and `## Task Template` YAML block contain the same fields. The `### Field Reference` table then describes those same fields a third time. A maintainer adding or renaming a field must update all three.

**Status: DONE**

### 2. Proposed resolution

Drop the YAML code block from `## Schema`. Keep the `### Field Reference` table (it carries richer information — types and descriptions). Keep the `## Task Template` section unchanged (it serves as a copy-paste template with body placeholder).

After the change, `## Schema` becomes a short intro sentence pointing readers to the table, and the YAML block is removed. The field list lives in exactly one place (the table), and the copy-paste shape lives in exactly one place (the template).

**Status: DONE**

### 3. Before/after for `skills/commission/SKILL.md`

The commission skill template (lines 241-259 of SKILL.md) currently emits:

**BEFORE** (lines 241-259):
````markdown
## Schema

Every {entity_label} file has YAML frontmatter with these fields:

```yaml
---
id:
title: Human-readable name
status: {first_stage}
source:
started:
completed:
verdict:
score:
worktree:
issue:
pr:
{any domain-specific fields from {captain}'s answers}
---
```

### Field Reference
````

**AFTER:**
````markdown
## Schema

Every {entity_label} file has YAML frontmatter. Fields are documented below; see **{Entity_label} Template** for a copy-paste starter.

### Field Reference
````

The `### Field Reference` table, `## {Entity_label} Template` section, and everything else remain unchanged.

**Status: DONE**

### 4. Before/after for `docs/plans/README.md`

**BEFORE** (lines 37-55):
```markdown
## Schema

Every task file has YAML frontmatter with these fields:

```yaml
---
id:
title: Human-readable name
status: backlog
source:
started:
completed:
verdict:
score:
worktree:
issue:
pr:
---
```

### Field Reference
```

**AFTER:**
```markdown
## Schema

Every task file has YAML frontmatter. Fields are documented below; see **Task Template** for a copy-paste starter.

### Field Reference
```

The `### Field Reference` table (lines 58-71), `## Task Template` section (lines 157-173), and all other sections remain unchanged.

**Status: DONE**

### 5. Retroactive fix decision

Yes — fix `docs/plans/README.md` in this task. It is the only commissioned workflow in the repo (test fixtures under `tests/fixtures/` do not contain a `### Field Reference` table, so they are unaffected). Fixing the one live README alongside the template keeps them consistent and avoids a "template says X but the live file still says Y" state.

**Status: DONE**

### 6. Acceptance criteria

1. The `## Schema` section in `skills/commission/SKILL.md` does NOT contain a YAML code block (` ```yaml `). **Test:** `grep -c '```yaml' skills/commission/SKILL.md` within the `## Schema` section returns 0 matches between `## Schema` and `### Field Reference`.
2. The `## Schema` section in `skills/commission/SKILL.md` still contains the `### Field Reference` table with all 12 standard fields. **Test:** grep for `### Field Reference` and count table rows.
3. The `## {Entity_label} Template` section in `skills/commission/SKILL.md` is unchanged — still contains a YAML code block with field names and body placeholder. **Test:** grep for the template YAML block.
4. The `## Schema` section in `docs/plans/README.md` does NOT contain a YAML code block. **Test:** same grep approach as criterion 1.
5. The `## Schema` section in `docs/plans/README.md` includes a cross-reference to **Task Template**. **Test:** grep for `Task Template` in the Schema section.
6. The `scripts/test_commission.py` "Schema" section check still passes. **Test:** the existing check `re.search("Schema", readme_text, re.IGNORECASE)` will continue to match since the `## Schema` heading is retained.

### 7. Test plan

**Static tests only. No E2E needed.** This is a template wording change with no behavioral impact on runtime.

- Add a static pytest test (`tests/test_commission_template.py` or within an existing static test file) that:
  - Reads `skills/commission/SKILL.md`
  - Asserts no ` ```yaml ` fence exists between the `## Schema` heading and the `### Field Reference` heading
  - Asserts `### Field Reference` heading exists
  - Asserts `## {Entity_label} Template` section contains a ` ```yaml ` fence
- Verify `scripts/test_commission.py` still finds "Schema" and "Template" sections (existing check on line 144 searches for substrings; heading is retained, so no change needed).
- Manual: confirm `docs/plans/README.md` reads correctly after edit.

Estimated cost: zero (static grep tests, no LLM invocation).

### 8. Scope boundary

**IN scope:**
- Remove the YAML code block from `## Schema` in `skills/commission/SKILL.md` template
- Replace it with a one-sentence intro pointing to the field reference table and entity template
- Apply the same fix to `docs/plans/README.md`
- Add a static test asserting no YAML block in the Schema section of the commission template

**OUT of scope:**
- Changing the `### Field Reference` table content or column structure
- Changing the `## {Entity_label} Template` section
- Changing test fixture READMEs under `tests/fixtures/` (they don't have the duplication)
- Reworking how the commission skill generates READMEs beyond this specific dedup
- Any runtime or E2E test changes

## Implementation Notes (gate-approved 2026-04-14)

CL directive at gate approval: move `scripts/test_commission.py` to `tests/` alongside other test files, and wire it into the Makefile entrypoint. The script is an E2E test that invokes `claude -p` to run the commission skill, then does static validation on the output. It imports from `scripts/test_lib.py` (many `tests/` files already import from there via `sys.path`). Add a `make test-e2e-commission` target or integrate it into an existing target as appropriate.

## Stage Report

### Summary

Removed the redundant YAML code block from the `## Schema` section in both the commission skill template (`skills/commission/SKILL.md`) and the live workflow README (`docs/plans/README.md`). Replaced with a one-sentence intro pointing readers to the Field Reference table and the copy-paste Template section. Moved the commission E2E test to `tests/` and added a static test asserting the dedup invariant. All 224 static tests pass.

### Checklist

1. Remove the YAML code block from `## Schema` section in `skills/commission/SKILL.md`, replace with intro sentence — **DONE** (line 242: "Every {entity_label} file has YAML frontmatter. Fields are documented below; see **{Entity_label} Template** for a copy-paste starter.")
2. Remove the YAML code block from `## Schema` section in `docs/plans/README.md`, replace with intro sentence — **DONE** (line 38: "Every task file has YAML frontmatter. Fields are documented below; see **Task Template** for a copy-paste starter.")
3. Verify `### Field Reference` table and `## Task Template` / `## {Entity_label} Template` sections remain unchanged in both files — **DONE** (verified by reading both files after edit; Field Reference tables and Template sections untouched)
4. Move `scripts/test_commission.py` to `tests/test_commission.py` — update the sys.path import for `test_lib` to point to `scripts/` — **DONE** (`git mv` + updated `sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))`)
5. Add a Makefile target for the commission E2E test — **DONE** (`test-e2e-commission` target added to Makefile)
6. Add a static pytest test asserting no YAML fence exists in the Schema section of the commission template — **DONE** (`tests/test_commission_template.py` with 5 test functions: no yaml fence, no code fence, Field Reference exists, Template has yaml fence)
7. Run `make test-static` and verify all existing tests pass — **DONE** (224 passed, 10 subtests passed)

## Stage Report — Validation

### Summary

Validated all 10 acceptance criteria for the schema/field-reference dedup task. All static tests pass (224 total, including the 4 new commission template tests). The YAML code block has been removed from the `## Schema` section in both the commission skill template and the live workflow README, with the Field Reference table and Template sections preserved intact.

### Checklist

1. Read `tests/README.md` to determine correct test harness and entrypoints — **DONE** (identified `make test-static` as the correct offline entrypoint; no E2E needed for this template-only change)
2. Run `make test-static` and report results — **DONE** (224 passed, 10 subtests passed in 4.71s)
3. Verify AC-1: `## Schema` section in `skills/commission/SKILL.md` does NOT contain a YAML code block between `## Schema` and `### Field Reference` — **DONE** (lines 240-244: intro sentence only, no code fence)
4. Verify AC-2: `## Schema` section in `skills/commission/SKILL.md` still contains `### Field Reference` table with all standard fields — **DONE** (lines 244-258: table with 11 field rows — id, title, status, source, started, completed, verdict, score, worktree, issue, pr)
5. Verify AC-3: `## {Entity_label} Template` section in `skills/commission/SKILL.md` is unchanged — still has YAML code block — **DONE** (lines 307-325: `\`\`\`yaml` fence with all fields and body placeholder present)
6. Verify AC-4: `## Schema` section in `docs/plans/README.md` does NOT contain a YAML code block — **DONE** (lines 37-39: intro sentence only, no code fence)
7. Verify AC-5: `## Schema` section in `docs/plans/README.md` includes cross-reference to **Task Template** — **DONE** (line 38: "see **Task Template** for a copy-paste starter.")
8. Verify AC-6: `scripts/test_commission.py` no longer exists (moved to `tests/test_commission.py`) — **DONE** (`ls` confirms file absent from `scripts/`)
9. Verify AC-7: `tests/test_commission.py` exists and imports work correctly — **DONE** (file exists, `sys.path.insert` points to `scripts/` for `test_lib` import)
10. Verify AC-8: Makefile has a target for the commission E2E test — **DONE** (`test-e2e-commission` target on line 12-13, runs `uv run tests/test_commission.py`)
11. Verify AC-9: Static test exists asserting no YAML fence in Schema section of commission template — **DONE** (`tests/test_commission_template.py` with 4 tests: no yaml fence, no code fence, Field Reference exists, Template has yaml fence)
12. Verify AC-10: Run the new static test and confirm it passes — **DONE** (all 4 tests in `test_commission_template.py` pass)
13. Recommendation: **PASSED** — all acceptance criteria verified with evidence, all static tests green

## Stage Report — Piggyback Fix: sibling-import tests decoupled from live entity

### Summary

After #120 merged and its entity file `docs/plans/build-dispatch-structured-helper.md` was archived to `docs/plans/_archive/`, two static tests in `TestStatusSiblingImport` broke because they hardcoded that filename as their fixture. Fixed by introducing a dedicated, stable fixture entity at `tests/fixtures/workflow-entity/sample-entity.md` and pointing both tests at it, decoupling them from the live workflow directory.

### Checklist

1. Read `tests/test_claude_team.py` and find all hardcoded references to `docs/plans/build-dispatch-structured-helper.md` — **DONE** (found 2 references: `test_status_sibling_import_parse_frontmatter` at line 981 and `test_status_sibling_import_load_active_entity_fields` at line 998)
2. Pick the fix approach (dedicated fixture preferred) and apply it — **DONE** (option 1: created `tests/fixtures/workflow-entity/sample-entity.md` with minimal valid YAML frontmatter — title, id, status, score, source — and updated both tests to reference it via `REPO_ROOT / "tests" / "fixtures" / "workflow-entity" / "sample-entity.md"`)
3. Run `make test-static` — confirm all tests pass including the two that were failing — **DONE** (267 passed, 10 subtests passed in 6.44s; focused run of `TestStatusSiblingImport` shows all 4 tests pass)
4. Commit on the branch with message `fix: decouple sibling-import tests from live workflow entity` — **DONE** (see next commit on branch `spacedock-ensign/workflow-readme-schema-and-fields-deduplication`)
5. Append a stage report note to the #144 entity body explaining this piggyback fix — **DONE** (this section)
