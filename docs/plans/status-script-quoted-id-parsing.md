---
id: 113
title: Status script misparses quoted YAML IDs
status: implementation
source: CL — observed agent workaround for ID sequencing, 2026-04-09
started: 2026-04-09T22:42:40Z
completed:
verdict:
score:
worktree: .worktrees/ensign-status-script-quoted-id-parsing
issue:
pr:
---

The status script's NEXT_ID calculation likely mishandles quoted vs unquoted IDs in YAML frontmatter. YAML treats `id: 001` as integer 1 and `id: "001"` as string "001" — if the script doesn't normalize these, it can miscalculate the next available ID or skip entities during scans.

Observed symptom: an agent saw existing entities going up to 010 and chose to start at 011, suggesting the ID sequence was misread (the actual next ID should have been much higher).

## Stage Report

### Checklist

1. **Identify all code paths in the status script that read or compare entity IDs** — DONE

   The status script (`skills/commission/bin/status`) has these code paths that use entity IDs:

   - **`parse_frontmatter()`** (line 46–65): Reads raw YAML frontmatter by splitting on `:`. Returns the value as-is, including any surrounding quotes. For `id: "084"`, it returns the string `"084"` (with literal quote characters).

   - **`compute_next_id()`** (line 294–309): Iterates all entities, calls `int(id_str)` on each. This is where the bug bites — `int('"084"')` raises `ValueError`, which is silently caught, so the entity is skipped entirely from the max-ID calculation.

   - **`print_status_table()`** (line 220–227): Prints `e['id']` directly. For quoted IDs, this displays `"084"` with literal quotes in the output column.

   - **`print_next_table()`** (line 230–273): Same display issue — prints `e['id']` directly.

   - **`scan_orphans()`** (line 312–347): Copies `e.get('id', '')` into the orphan dict. Display-only, but shows quoted value.

   - **`check_pr_states()`** (line 350–397): Copies `e.get('id', '')` into results dict. Display-only.

   - **`apply_filters()`** (line 587–616): String comparison via `--where`. For `--where id = 084`, the stored value `"084"` won't match `084` — you must include literal quotes in the filter value to match.

2. **Document which paths handle quoted vs unquoted IDs incorrectly** — DONE

   | Code path | Bug | Severity |
   |---|---|---|
   | `compute_next_id()` | `int('"084"')` raises ValueError, entity silently skipped from max-ID scan | **High** — can cause NEXT_ID to be wrong if the highest-numbered entity has a quoted ID |
   | `apply_filters()` | `--where id = 084` won't match entity with `id: "084"` | **Medium** — filter requires user to know internal quoting |
   | `print_status_table()` | Displays `"084"` with literal quotes in ID column | **Low** — cosmetic, but inconsistent |
   | `print_next_table()` | Same display issue | **Low** |
   | `scan_orphans()` | Same display issue | **Low** |
   | `check_pr_states()` | Same display issue | **Low** |

3. **Survey existing entity files for actual ID formats in use** — DONE

   Surveyed all 113 entity files across `docs/plans/` and `docs/plans/_archive/`.

   - **110 entities**: unquoted zero-padded IDs (e.g., `id: 036`, `id: 001`)
   - **1 entity with quoted frontmatter ID**: `_archive/unified-test-harness.md` has `id: "084"`
   - **2 entities with quoted IDs in body content only** (not frontmatter): `feedback-keepalive-e2e-test.md` and `restore-ensign-reuse.md` both have `id: "001"` inside fenced code blocks (test fixture examples) — these are not parsed by the status script and are not affected.

   Note: the `pr` field has a similar quoting inconsistency (`pr: "#28"` vs `pr: #54`), but that is out of scope for this task.

4. **Propose a fix approach that normalizes IDs consistently** — DONE

   **Approach: Strip quotes in `parse_frontmatter()`.**

   Add quote-stripping to `parse_frontmatter()` so that all values have surrounding `"` or `'` removed before being stored. This is the single normalization point — all downstream code paths automatically get clean values.

   Specifically, after `val = val.strip()` on line 62, add:
   ```python
   if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
       val = val[1:-1]
   ```

   **Why this approach:**
   - Fixes all affected code paths at once (compute_next_id, apply_filters, all display paths)
   - Matches YAML semantics — `id: "084"` and `id: 084` should produce the same value
   - The script already documents that it does manual YAML parsing (lines 15–17), so this is filling a gap in that parser
   - No risk of over-stripping: values like `"foo"bar"` are not valid YAML, and single-character strings can't match (length >= 2 guard)

   **Rejected alternatives:**
   - Stripping quotes only in `compute_next_id()`: fixes NEXT_ID but leaves filter and display bugs
   - Using PyYAML: the script explicitly avoids PyYAML dependency (line 36)
   - Normalizing IDs to integers: would lose zero-padding format info

5. **Define acceptance criteria with test plan** — DONE

   **AC1: `compute_next_id()` counts quoted IDs correctly.**
   - Test: Create a temp directory with two entity files, one with `id: 084` and one with `id: "085"`. Call `compute_next_id()` and assert it returns `"086"`.

   **AC2: `--where id = 084` matches entities regardless of YAML quoting.**
   - Test: Create entity files with `id: 084` and `id: "085"`. Run status with `--where 'id = 084'` and verify it returns exactly one match. Run with `--where 'id = 085'` and verify it also returns exactly one match.

   **AC3: Display output shows IDs without literal quote characters.**
   - Test: Create entity file with `id: "084"`. Run status and capture output. Assert the ID column shows `084` not `"084"`.

   **AC4: Other quoted frontmatter values (like `pr: "#28"`) are also stripped.**
   - Test: Create entity file with `pr: "#28"`. Parse frontmatter and assert `pr` field is `#28` not `"#28"`.

   **AC5: Unquoted values are unchanged.**
   - Test: Create entity file with `id: 084`. Parse frontmatter and assert `id` field is `084`.

   **Test approach:** Unit tests in a new or existing test file that exercise `parse_frontmatter()` directly and `compute_next_id()` with fixture files in a temp directory. No E2E tests needed — the bug is purely in string handling within a single function. Estimated complexity: low (< 30 minutes).
