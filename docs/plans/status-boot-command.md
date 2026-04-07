---
id: 089
title: Status script --boot flag for FO startup
status: validation
source: CL — FO startup operator errors (missed mod registration via glob, manual PR checks)
started: 2026-04-07T00:00:00Z
completed:
verdict:
score: 0.8
worktree: .worktrees/spacedock-ensign-status-boot-command
issue:
pr:
---

# Status script --boot flag for FO startup

## Problem

The first officer's startup procedure requires multiple deterministic file/git scanning steps that it currently performs manually via glob patterns, grep, and bash pipelines. This is error-prone — in the session that spawned this task, the FO missed mod registration entirely because it used the wrong glob pattern (`_mods/*.md` with a `path` parameter instead of `{workflow_dir}/_mods/*.md` from the working directory).

Current FO startup steps that are pure deterministic scanning:

1. **Mod discovery** — scan `_mods/*.md` for `## Hook:` headings, register by lifecycle point
2. **Next sequential ID** — scan active + archive for highest ID
3. **Orphaned worktree detection** — cross-reference entity `worktree` fields against `git worktree list`
4. **PR state checking** — `gh pr view` for entities with non-empty `pr` field and non-terminal status
5. **Dispatchable entities** — already handled by `--next`

Each of these is a separate tool call the FO can get wrong. The status script already parses README frontmatter and entity frontmatter — it should do all of this in one reliable call.

## Proposed approach

Add a `--boot` flag to the status script that outputs all startup information in one call:

```
$ python3 skills/commission/bin/status --workflow-dir docs/plans --boot
```

### Output sections

**Mods** — scan `{workflow_dir}/_mods/*.md`, extract `## Hook: {point}` headings, report hooks grouped by lifecycle point (startup, idle, merge) in alphabetical order by mod filename.

```
MODS
startup: pr-merge
idle: pr-merge
merge: pr-merge
```

If `_mods/` doesn't exist or has no mods: `MODS: none`

**Next ID** — scan active entities and `_archive/` for highest numeric ID, report next available.

```
NEXT_ID: 089
```

**Orphaned worktrees** — entities with non-empty `worktree` field, cross-referenced against `git worktree list`. Report whether the worktree directory actually exists and whether the branch exists.

```
ORPHANS
ID     SLUG                           WORKTREE                                    DIR_EXISTS  BRANCH_EXISTS
086    gate-rejection-feedback-routing .worktrees/ensign-gate-rejection-feedback    yes         yes
054    session-debrief                .worktrees/ensign-054-session-debrief         yes         yes
058    terminology-experiment         .worktrees/ensign-terminology-exp             yes         yes
```

If no orphans: `ORPHANS: none`

**PR state** — entities with non-empty `pr` field and non-terminal status. Runs `gh pr view` for each. If `gh` is unavailable, reports that and skips.

```
PR_STATE
ID     SLUG                           PR       STATE
085    agent-boot-skill-preload       #29      MERGED
```

If no PR-pending entities: `PR_STATE: none`
If `gh` unavailable: `PR_STATE: gh not available`

**Dispatchable** — same as existing `--next` output.

```
DISPATCHABLE
ID     SLUG                           CURRENT              NEXT                 WORKTREE
```

### Implementation notes

- Pure Python 3 stdlib except for `gh` (subprocess call, gracefully skipped if missing)
- `git worktree list` via subprocess for orphan cross-referencing
- Mod scanning uses `glob.glob()` on `{workflow_dir}/_mods/*.md` — no LLM glob patterns involved
- `## Hook:` extraction is line-by-line text scanning, same approach as frontmatter parsing

## Boot Sequence Observations (2026-04-07 session)

Actual FO startup consumed ~16 tool calls across 6 parallel batches. Breakdown:

1. **Mod discovery** (2 calls) — Glob `_mods/*.md` + Read each file for `## Hook:` headings. Pure deterministic scanning, easily moved to the script.

2. **Debrief discovery** (2 calls) — Glob `_debriefs/*.md` + Read latest file. The glob/sort is deterministic; reading the content still requires a Read call. The `--boot` output could report the latest debrief filename so the FO only needs one Read.

3. **Orphan worktree detection** (1 call) — `status --where "worktree !="` works but doesn't cross-reference against `git worktree list` or filesystem existence. The FO has to trust that the worktree path in frontmatter is still valid.

4. **PR state checking** (9 calls — biggest bottleneck) — `--where "pr !="` returns entity rows but the `pr` field isn't in the output columns. The FO had to Read 4 entity files individually just to extract PR numbers, then run `gh pr view` for each. Moving PR extraction + `gh pr view` into the script eliminates 8 of 9 calls.

5. **Dispatchable** (1 call) — `status --next` already handled.

6. **Full status for reporting** (1 call) — `status` for the captain report.

### Key insight

The `--boot` flag should collapse steps 1–5 into a single call. The FO's startup would become:
1. `status --boot` (1 call)
2. Read latest debrief if filename reported (1 call)
3. Act on PR_STATE results (advance merged PRs — edit + archive + commit)
4. Report to captain

That's 2 tool calls for information gathering instead of ~15.

## Stage Report

### 1. Problem statement — DONE

The FO startup sequence on 2026-04-07 consumed ~16 tool calls across 6 sequential/parallel batches to gather deterministic information that a script could compute:

- **Mod discovery** (2 calls): Glob `_mods/*.md` + Read each file for `## Hook:` headings. The FO has previously used wrong glob patterns for this, causing missed mod registration.
- **Debrief discovery** (2 calls): Glob `_debriefs/*.md` + Read latest. The glob/sort is deterministic; only reading content requires a Read call.
- **Orphan detection** (1 call): `status --where "worktree !="` finds entities with worktrees but doesn't validate whether the worktree directory or branch actually exist on disk.
- **PR state checking** (9 calls — biggest bottleneck): `--where "pr !="` returns rows but the `pr` field isn't in output columns. The FO had to Read 4 entity files to extract PR numbers, then run `gh pr view` for each. This is 8 unnecessary calls.
- **Dispatchable** (1 call): `status --next` — already handled.
- **Full status** (1 call): For captain reporting.

The core problem: the status script already parses all frontmatter fields but only exposes a subset. Each startup step is pure deterministic scanning that the FO performs unreliably via ad-hoc tool calls.

### 2. Proposed approach — DONE

Add `--boot` flag to `skills/commission/bin/status` that outputs all sections in one call. The output uses a section-based format with labeled headers:

**MODS section** — Scan `{workflow_dir}/_mods/*.md`, extract `## Hook: {point}` headings from each file, group by lifecycle point. Output format:
```
MODS
startup: pr-merge
idle: pr-merge
merge: pr-merge
```
If no mods directory or no mods: `MODS: none`

**NEXT_ID section** — Scan active entities + `_archive/` for highest numeric ID, report next available:
```
NEXT_ID: 094
```

**ORPHANS section** — Entities with non-empty `worktree` field, cross-referenced against `git worktree list` output and filesystem existence checks:
```
ORPHANS
ID     SLUG                           WORKTREE                                    DIR_EXISTS  BRANCH_EXISTS
086    gate-rejection-feedback-routing .worktrees/ensign-gate-rejection-feedback    yes         yes
```
If none: `ORPHANS: none`

**PR_STATE section** — Entities with non-empty `pr` and non-terminal status. Runs `gh pr view` for each:
```
PR_STATE
ID     SLUG                           PR       STATE
085    agent-boot-skill-preload       #29      MERGED
```
If none: `PR_STATE: none`. If `gh` unavailable: `PR_STATE: gh not available`

**DISPATCHABLE section** — Same output as existing `--next`:
```
DISPATCHABLE
ID     SLUG                           CURRENT              NEXT                 WORKTREE
```

**LATEST_DEBRIEF section** — Report the filename of the most recent debrief file (by sorted filename), so the FO only needs one Read call:
```
LATEST_DEBRIEF: 2026-04-07-01.md
```
If none: `LATEST_DEBRIEF: none`

Implementation constraints:
- Pure Python 3 stdlib except `gh` (subprocess, gracefully skipped) and `git worktree list` (subprocess)
- Mod scanning via `glob.glob()` — no LLM glob patterns
- `## Hook:` extraction is line-by-line text scanning, same as frontmatter parsing
- `--boot` requires stages block (same as `--next`)
- `--boot` is incompatible with `--next`, `--archived`, and `--where` (it produces its own composite output)

### 3. Acceptance criteria — DONE

| # | Criterion | Test method |
|---|-----------|-------------|
| AC1 | `--boot` outputs a MODS section listing hooks grouped by lifecycle point | Unit test: create `_mods/` with a mod file containing `## Hook: startup` and `## Hook: idle`, verify output |
| AC2 | MODS section shows `MODS: none` when no mods exist | Unit test: no `_mods/` directory, verify output |
| AC3 | `--boot` outputs NEXT_ID with the next sequential ID across active + archive | Unit test: entities with IDs 001, 003 + archived 002, verify NEXT_ID: 004 |
| AC4 | `--boot` outputs ORPHANS section with DIR_EXISTS and BRANCH_EXISTS columns | Unit test: mock `git worktree list` output, create entities with worktree fields, verify cross-referencing (subprocess can be tested by checking output format; filesystem existence can be tested with temp dirs) |
| AC5 | ORPHANS shows `ORPHANS: none` when no entities have worktree fields | Unit test: entities without worktree, verify output |
| AC6 | `--boot` outputs PR_STATE with PR number and state for PR-pending entities | Unit test: requires mocking `gh pr view` subprocess call; create entity with `pr: #19` and non-terminal status, verify output format |
| AC7 | PR_STATE gracefully handles missing `gh` | Unit test: ensure `gh` not on PATH in test env, verify `PR_STATE: gh not available` |
| AC8 | PR_STATE skips entities in terminal status | Unit test: entity with `pr: #19` and `status: done`, verify it doesn't appear |
| AC9 | `--boot` outputs DISPATCHABLE section (same as `--next`) | Unit test: reuse existing `--next` test data, verify DISPATCHABLE section matches |
| AC10 | `--boot` outputs LATEST_DEBRIEF with most recent debrief filename | Unit test: create `_debriefs/` with files, verify latest reported |
| AC11 | LATEST_DEBRIEF shows `LATEST_DEBRIEF: none` when no debriefs exist | Unit test: no `_debriefs/` directory, verify output |
| AC12 | `--boot` errors if README lacks stages block | Unit test: use README without stages, verify error exit |
| AC13 | `--boot` is incompatible with `--next`, `--archived`, `--where` | Unit test: verify error message when combined |
| AC14 | All sections appear in deterministic order: MODS, NEXT_ID, ORPHANS, PR_STATE, DISPATCHABLE, LATEST_DEBRIEF | Unit test: full `--boot` run, verify section order in output |

### 4. Test plan — DONE

**Test type:** Unit tests in `tests/test_status_script.py`, extending the existing test class pattern.

**Approach:** Add a new `TestBootOption` test class following the same pattern as `TestNextOption`. Tests use `tempfile.TemporaryDirectory()` for isolation, `make_pipeline()` and `entity()` helpers for fixture creation.

**Subprocess mocking for `gh` and `git worktree list`:**
- For `gh pr view` tests: set PATH to exclude `gh` for the "unavailable" test; for state tests, use a wrapper script in the temp dir that returns canned JSON
- For `git worktree list`: similar wrapper script approach, or test the output format without actually calling git (since the cross-referencing logic is the interesting part)
- Alternative: extract the subprocess calls into testable functions and unit test the parsing logic separately from the subprocess calls

**Estimated scope:**
- ~14 test methods in one new test class
- No E2E tests needed — this is deterministic file scanning with well-defined output format, testable entirely with unit tests and temp directories
- Mod scanning, debrief discovery, and next-ID calculation are pure filesystem operations — straightforward to test
- PR_STATE and ORPHANS involve subprocess calls but can be tested with PATH manipulation and wrapper scripts

**Cost/complexity:** Medium. The implementation adds ~150-200 lines to the status script (new functions for each section + `--boot` dispatch in `main()`). Tests add ~200-250 lines. The most complex parts are the `gh` subprocess mocking and `git worktree list` parsing, but these follow established patterns in the codebase.

## Reviewer Assessment

### Design soundness

The `--boot` flag design is solid. It follows the existing pattern of `--next` (parse stages, compute derived data, print structured output) and extends it cleanly. Six specific observations:

1. **Good fit with existing architecture.** The status script already parses all frontmatter fields and has the `parse_stages_block` / `scan_entities` infrastructure. Each new section (MODS, NEXT_ID, ORPHANS, PR_STATE, DISPATCHABLE, LATEST_DEBRIEF) is an independent function that reads the same entity list. No architectural changes needed.

2. **NEXT_ID needs to include `_archive/` scanning.** The design says "scan active entities and `_archive/` for highest numeric ID" — but the existing `main()` only scans `_archive/` when `--archived` is passed. The `--boot` path must unconditionally scan both directories for ID calculation. This is noted in the design but should be explicit in the implementation notes as a divergence from the default code path.

3. **Terminal status definition for PR_STATE.** The design says "non-terminal status" but the script determines terminality from the stages block, not from a hardcoded list. This means `--boot` must require the stages block (same as `--next`). AC12 covers this, which is correct.

4. **ORPHANS cross-referencing is well-scoped.** Checking `DIR_EXISTS` (filesystem) and `BRANCH_EXISTS` (from `git worktree list` output) is the right granularity. The design does not attempt to check remote branch existence, which would add latency and complexity for little value.

5. **DISPATCHABLE section reuse.** The design says "same as existing `--next` output" which means it should call `print_next_table` or equivalent. This is clean — no code duplication.

6. **LATEST_DEBRIEF is a good addition** not in the original problem statement. It eliminates the FO's debrief glob+sort step.

### Test plan sufficiency

The 14 acceptance criteria are testable. A few concerns:

1. **Subprocess mocking strategy needs refinement.** The test plan proposes "wrapper script in the temp dir" for `gh` and `git worktree list`, but the existing test suite runs the status script as a subprocess via `run_status()`. To inject a fake `gh` or `git`, the test would need to either (a) prepend a temp dir with a fake `gh` script to PATH in the subprocess env, or (b) refactor the status script to accept subprocess commands as arguments. Option (a) is more consistent with the existing test approach and avoids modifying the script's interface for testability. The test plan should be explicit about option (a).

2. **AC4 (ORPHANS with DIR_EXISTS/BRANCH_EXISTS)** is the most complex test. It requires: creating entity files with worktree paths, creating some of those directories (to test `DIR_EXISTS: yes/no`), and providing fake `git worktree list` output (to test `BRANCH_EXISTS: yes/no`). The test plan acknowledges this but should note that the temp dir must contain the worktree paths for the `yes` cases.

3. **AC7 (gh not available)** — the test plan says "ensure `gh` not on PATH in test env." This is achievable by passing a modified `env` to `subprocess.run` with a PATH that excludes directories containing `gh`. The existing `run_status` helper already customizes env, so this is feasible.

4. **AC13 (incompatibility with --next, --archived, --where)** — should test each incompatible combination individually, not just one. That is 3 test methods minimum (boot+next, boot+archived, boot+where). The AC says "verify error message when combined" (singular), but this should be 3 separate assertions.

5. **Missing negative test for MODS.** AC1 tests a mod with hooks. AC2 tests no mods. But there is no criterion for a mod file that exists in `_mods/` but contains no `## Hook:` headings. This is an edge case worth covering — should it be silently skipped, or reported with zero hooks?

6. **Missing test for multiple mods.** AC1 uses one mod file. The MODS output format groups hooks by lifecycle point with mod names listed. With multiple mods registering for the same hook point, the output needs to show all of them (e.g., `startup: pr-merge, auto-label`). A test with 2+ mod files would verify this.

### Gaps

1. **MODS output format ambiguity for multiple mods.** The example shows `startup: pr-merge` but does not show the format when multiple mods register for the same lifecycle point. Should it be comma-separated? One line per mod? This needs to be specified.

2. **NEXT_ID edge case: non-numeric IDs.** The design assumes numeric IDs (sequential). If an entity has a non-numeric ID (or no ID), the scan should skip it gracefully. The design does not address this. The real pipeline uses `id-style: sequential` so this is unlikely but worth a defensive note.

3. **ORPHANS: what counts as an orphan?** The design says "entities with non-empty `worktree` field, cross-referenced against `git worktree list`." But entities with an active worktree are not orphans — they are actively worked. An orphan would be an entity whose worktree directory does not exist or whose branch is missing. The current design reports ALL entities with worktree fields and lets the FO interpret the DIR_EXISTS/BRANCH_EXISTS columns. This is fine for boot output, but the section name "ORPHANS" is misleading — it is really "WORKTREES." Consider renaming to `WORKTREES` to avoid confusion, or filtering to only show entries where `DIR_EXISTS=no` or `BRANCH_EXISTS=no`.

4. **`gh pr view` failure modes beyond "not available."** What happens if `gh` is available but returns an error for a specific PR (e.g., 404, network timeout, auth failure)? The design only covers "gh unavailable." A per-PR error state (e.g., `STATE: error`) would be more robust than silently skipping or crashing.

5. **No `--boot` output to stderr.** The design specifies all output on stdout. Progress indicators for slow operations (like multiple `gh pr view` calls) might be useful on stderr but are not required. Just noting this as a known tradeoff.

6. **LATEST_DEBRIEF sorting.** The design says "most recent debrief file (by sorted filename)." The existing debrief files follow a `YYYY-MM-DD-NN.md` naming convention that sorts lexicographically. This is fine as long as the convention holds, but the design should note this assumption explicitly.

## Stage Report

### Checklist

1. Add `--boot` flag to `skills/commission/bin/status` with all 6 output sections — **DONE**. Added `print_boot()` orchestrator plus `scan_mods()`, `compute_next_id()`, `scan_orphans()`, `check_pr_states()`, `find_latest_debrief()` functions. All output sections: MODS, NEXT_ID, ORPHANS, PR_STATE, DISPATCHABLE, LATEST_DEBRIEF.
2. Implement mod discovery scanning `_mods/*.md` for `## Hook:` headings — **DONE**. `scan_mods()` uses `glob.glob()` on `{workflow_dir}/_mods/*.md`, reads line-by-line for `## Hook:` prefixes, groups by lifecycle point with mod names in alphabetical order. Comma-separated for multiple mods on the same hook point (reviewer refinement #1, #6).
3. Implement NEXT_ID calculation across active + archive entities — **DONE**. `compute_next_id()` scans active entities and `_archive/` directory unconditionally, finds highest numeric ID (skipping non-numeric), returns zero-padded next ID.
4. Implement ORPHANS with cross-referencing against `git worktree list` and filesystem checks — **DONE**. `scan_orphans()` runs `git worktree list --porcelain`, extracts branch names, checks `os.path.isdir()` for DIR_EXISTS. Section name kept as ORPHANS per reviewer refinement #2.
5. Implement PR_STATE with `gh pr view` subprocess calls and graceful fallbacks — **DONE**. `check_pr_states()` checks PATH for `gh` availability, runs `gh pr view` per PR, returns per-PR ERROR state on failure (reviewer refinement #3).
6. Implement LATEST_DEBRIEF section — **DONE**. `find_latest_debrief()` scans `_debriefs/*.md`, returns last filename by lexicographic sort.
7. Flag incompatibility with `--next`, `--archived`, `--where` — **DONE**. Three separate checks in `main()`, each produces an error message with "incompatible" and exits non-zero.
8. Write unit tests in `tests/test_status_script.py` covering AC1-AC14 (including reviewer's additions) — **DONE**. Added `TestBootOption` class with 19 test methods: AC1-AC14 (with AC13 split into 3 separate tests per reviewer refinement #4) plus mod with no hooks (#5), multiple mods same hook (#6), and per-PR error handling (#3). Uses PATH prepend with fake shell scripts for subprocess mocking per reviewer refinement #7.
9. All existing tests still pass — **DONE**. All 33 pre-existing tests pass unchanged.
10. All new tests pass — **DONE**. All 19 new tests pass. Total: 52 tests, 0 failures.
