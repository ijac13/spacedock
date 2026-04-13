---
id: 100
title: "status tool: add workflow directory discovery"
status: validation
source: CL observation — Codex startup uses raw rg for discovery
started: 2026-04-13T15:57:56Z
completed:
verdict:
score: 0.60
worktree: .worktrees/spacedock-ensign-status-workflow-discovery
issue:
pr: #85
---

The startup procedure (step 2) requires searching for README.md files with `commissioned-by: spacedock@` frontmatter to discover workflow directories. Every runtime (Claude Code, Codex) reimplements this as a raw grep/rg call before it can invoke `status --boot`.

Fold discovery into the status tool so there's a single entry point. Either a `--discover` flag that returns workflow directories, or make `--boot` auto-discover when `--workflow-dir` is omitted.

## Stage Report — ideation

### 1. Problem Statement

The first officer's startup sequence (shared core step 2) requires discovering workflow directories — finding `README.md` files with `commissioned-by: spacedock@` frontmatter. Today this logic exists only as prose in `first-officer-shared-core.md`: "search for README.md files whose YAML frontmatter contains `commissioned-by: spacedock@...`." Each runtime (Claude Code, Codex) must independently interpret this prose and reimplement discovery using raw `grep`/`rg` calls. This causes three problems:

1. **Duplication** — Two runtimes implement the same search with potentially divergent ignore lists, depth limits, and error handling.
2. **Fragility** — The prose specifies an ignore list (`.git`, `.worktrees`, `node_modules`, etc.) but there's no enforcement; a runtime can easily miss an entry or add inconsistent ones.
3. **Unreachable from tooling** — No script or programmatic interface exposes discovery, so other tools (future CLIs, dashboards) would need to reinvent it too.

The status script (`skills/commission/bin/status`) is the right home because it already owns workflow-directory-scoped queries (`--boot`, `--next`, `--where`). Adding discovery here gives all callers a single, tested entry point, and eliminates the need for runtimes to shell out to raw grep.

### 2. Current Discovery Call Sites

**Call site A — Shared core prose (`first-officer-shared-core.md`, line 8):**

```
2. Discover the workflow directory. Prefer an explicit user-provided path. Otherwise
   search for `README.md` files whose YAML frontmatter contains `commissioned-by:
   spacedock@...`. Ignore `.git`, `.worktrees`, `node_modules`, `vendor`, `dist`,
   `build`, and `__pycache__`.
```

This is instructional prose, not an invocation. Each runtime interprets it independently.

**Call site B — Codex runtime adapter (`codex-first-officer-runtime.md`, lines 11-18):**

```
## Workflow Target

- If the user gives an explicit workflow path, use it.
- If not, discover candidate workflows from the current repository.
- If multiple candidates exist, ask the user which workflow to manage.
```

The Codex runtime tells the agent to "discover candidate workflows" but does not specify a tool invocation — the agent uses raw `rg` or `grep`.

**Call site C — Claude runtime adapter (`claude-first-officer-runtime.md`):**

The Claude runtime does not mention discovery explicitly. It defers entirely to the shared core startup procedure. The agent interprets shared core step 2 and runs its own grep/rg.

### 3. Proposed Design: `--discover` Flag

**Primary design:** Add a `--discover` flag to the status script that searches for workflow directories from a given root.

**CLI surface:**

```
status --discover [--root <path>]
```

- `--discover`: Activates discovery mode. Incompatible with all other flags (`--boot`, `--next`, `--next-id`, `--archived`, `--where`, `--set`, `--archive`, `--fields`, `--all-fields`, `--workflow-dir`).
- `--root <path>`: Optional. The directory to start searching from. Defaults to `git rev-parse --show-toplevel` (git root of cwd). If not in a git repo, uses cwd.

**Output format:** One absolute path per line to stdout, sorted alphabetically. Each path is the *directory* containing the matching README.md (not the README.md path itself).

```
/Users/alice/project/docs/plans
```

For zero matches, output nothing and exit 0. For one match, output one line and exit 0. For multiple matches, output all lines and exit 0.

**Exit codes:**
- `0` — Success (zero, one, or many matches). The caller decides how to handle cardinality.
- `1` — Error (invalid arguments, `--root` path doesn't exist, etc.).

**Rationale for exit-0 on zero matches:** The caller (the first officer) already handles the "no workflow found" case with its own error messaging. Having the status script fail on zero results would force callers to distinguish "real error" from "no matches," which overcomplicates the interface.

**Alternatives considered:**

1. **Make `--boot` auto-discover when `--workflow-dir` is omitted** — Rejected because `--boot` already has a well-defined contract (scan a known directory). Overloading it with search semantics creates a confusing dual-mode interface.
2. **A separate `discover` script** — Rejected because it would add a new entry point to maintain. The status script already knows how to parse README frontmatter, and discovery is a natural pre-step to the queries it already serves.
3. **JSON output** — Rejected for the primary design. One-path-per-line is easier to consume from shell scripts and agent tool calls. JSON can be added later if needed.

### 4. Search Semantics

- **Search root:** Default is `git rev-parse --show-toplevel`. If that fails (not a git repo), use current working directory. Overridable with `--root`.
- **Ignore list:** `.git`, `.worktrees`, `node_modules`, `vendor`, `dist`, `build`, `__pycache__`, `tests`. Matches the shared core prose (line 8) plus `tests` to avoid false positives from test fixtures.
- **Max depth:** No hard limit. The ignore list handles common deep trees. If performance becomes an issue, a `--max-depth` flag can be added later (YAGNI).
- **Symlink handling:** Follow symlinks (Python `os.walk` default when using `followlinks=True`). Rationale: workflow directories may live in symlinked paths in monorepo setups. Use `os.path.realpath` to deduplicate results that resolve to the same physical directory.
- **Tie-break for multiple hits:** Alphabetical sort by absolute path. The caller (first officer) already has logic for "if multiple candidates, ask the user."
- **Matching rule:** Open each `README.md` found during the walk, call the existing `parse_frontmatter()` function, check if the `commissioned-by` field value starts with `spacedock@`. This reuses the existing parser and avoids regex duplication.

### 5. Before/After for Each Affected Surface

**Surface A — Status script (`skills/commission/bin/status`)**

*Before:* No `--discover` flag exists.

*After:* Add a `--discover` flag (with optional `--root`). Add a `discover_workflows(root)` function that walks the tree, opens README.md files, calls `parse_frontmatter()`, checks for `commissioned-by` starting with `spacedock@`, and returns sorted absolute directory paths. Add argument parsing for `--discover` and `--root` in `main()`, with incompatibility checks against all other flags. Print each path on its own line.

**Surface B — Shared core (`first-officer-shared-core.md`, Startup step 2)**

*Before (line 8):*
```
2. Discover the workflow directory. Prefer an explicit user-provided path. Otherwise search for `README.md` files whose YAML frontmatter contains `commissioned-by: spacedock@...`. Ignore `.git`, `.worktrees`, `node_modules`, `vendor`, `dist`, `build`, and `__pycache__`.
```

*After:*
```
2. Discover the workflow directory. Prefer an explicit user-provided path. Otherwise run `{spacedock_plugin_dir}/skills/commission/bin/status --discover` and use the result. If the output contains exactly one path, use it. If zero paths, report that no workflow was found. If multiple paths, present the list to the operator and ask which to manage (or, in single-entity mode, fail with an ambiguity error).
```

**Surface C — Codex runtime adapter (`codex-first-officer-runtime.md`, Workflow Target section)**

*Before (lines 13-14):*
```
- If not, discover candidate workflows from the current repository.
- If multiple candidates exist, ask the user which workflow to manage.
```

*After:*
```
- If not, run `status --discover` to find candidate workflows.
- If exactly one result, use it. If zero, report no workflow found. If multiple, ask the user which to manage.
```

**Surface D — Claude runtime adapter (`claude-first-officer-runtime.md`)**

No change needed. The Claude runtime defers to the shared core startup sequence and does not have its own discovery prose. The shared core update (Surface B) is sufficient.

**Scope decision on doc changes:** The prose edits to Surfaces B and C land in this task. They are small, tightly coupled to the `--discover` implementation, and leaving them for a follow-up would create a window where the tool exists but the docs still tell agents to use raw grep.

### 6. Back-Compat Check

Existing invocations and their behavior:

| Invocation | Behavior today | Behavior after | Changed? |
|---|---|---|---|
| `status --boot --workflow-dir X` | Boot report for directory X | Unchanged | No |
| `status X` (positional, treated as unknown arg) | Ignored (no positional args parsed) | Unchanged | No |
| `status --workflow-dir X` | Default table for directory X | Unchanged | No |
| `status --set slug field=value` | Update frontmatter | Unchanged | No |
| `status --next` | Dispatchable entities | Unchanged | No |
| `status --next-id` | Next sequential ID | Unchanged | No |
| `status --archived` | Include archive in table | Unchanged | No |

The `--discover` flag is additive. It is incompatible with all existing flags, so there is no combination that could alter existing behavior. The `--root` flag only takes effect when `--discover` is present.

**No behavioral change to any existing caller.**

### 7. Acceptance Criteria

1. `status --discover` with a `--root` pointing at a directory containing one workflow directory outputs exactly that directory's absolute path and exits 0.
   - *Test:* `test_discover_single_workflow` — create a tmpdir with one README.md containing `commissioned-by: spacedock@test`, run `status --discover --root {tmpdir}`, assert stdout is one line with the correct path, exit code 0.

2. `status --discover` with a root containing zero workflow directories outputs nothing and exits 0.
   - *Test:* `test_discover_no_workflows` — create an empty tmpdir, run `status --discover --root {tmpdir}`, assert stdout is empty, exit code 0.

3. `status --discover` with a root containing multiple workflow directories outputs all paths alphabetically, one per line, exit 0.
   - *Test:* `test_discover_multiple_workflows` — create a tmpdir with two subdirs each containing a matching README.md, assert two lines in alphabetical order.

4. `status --discover` skips directories in the ignore list (`.git`, `.worktrees`, `node_modules`, `vendor`, `dist`, `build`, `__pycache__`, `tests`).
   - *Test:* `test_discover_ignores_excluded_dirs` — create a tmpdir with a matching README.md inside a `tests/fixtures/` subdirectory and one in a valid location. Assert only the valid location appears.

5. `status --discover` skips README.md files whose `commissioned-by` field does not start with `spacedock@`.
   - *Test:* `test_discover_skips_non_spacedock_readme` — create a README.md with `commissioned-by: other@1.0`, assert it is not in the output.

6. `status --discover` is incompatible with `--boot`, `--next`, `--next-id`, `--archived`, `--where`, `--set`, `--archive`, `--fields`, `--all-fields`, `--workflow-dir`. Each combination prints an error to stderr and exits 1.
   - *Test:* `test_discover_incompatible_flags` — parameterized test over each incompatible flag.

7. `status --discover --root /nonexistent` prints an error to stderr and exits 1.
   - *Test:* `test_discover_bad_root` — assert stderr contains "Error" and exit code 1.

8. `status --discover` without `--root` defaults to git toplevel (or cwd if not in a git repo).
   - *Test:* `test_discover_default_root` — run in a tmpdir initialized as a git repo with a workflow subdir, assert the correct path is found.

9. Symlinked directories containing workflows are discovered, and duplicate physical paths are deduplicated.
   - *Test:* `test_discover_deduplicates_symlinks` — create a workflow dir and a symlink pointing to it, assert only one path in output.

10. Shared core step 2 references `status --discover` instead of raw grep prose.
    - *Test:* Static grep of `first-officer-shared-core.md` for `status --discover` and absence of "search for `README.md` files".

11. Codex runtime adapter Workflow Target section references `status --discover`.
    - *Test:* Static grep of `codex-first-officer-runtime.md` for `status --discover`.

### 8. Test Plan

| # | Test name | Harness | Asserts | Cost |
|---|---|---|---|---|
| 1 | `test_discover_single_workflow` | pytest (test_status_script.py) | stdout = one correct path, rc=0 | Low — tmpdir + subprocess |
| 2 | `test_discover_no_workflows` | pytest | stdout empty, rc=0 | Low |
| 3 | `test_discover_multiple_workflows` | pytest | stdout = two paths alphabetically, rc=0 | Low |
| 4 | `test_discover_ignores_excluded_dirs` | pytest | only valid path in output | Low |
| 5 | `test_discover_skips_non_spacedock_readme` | pytest | non-spacedock README excluded | Low |
| 6 | `test_discover_incompatible_flags` | pytest (parameterized) | stderr "Error", rc=1 for each combo | Low |
| 7 | `test_discover_bad_root` | pytest | stderr "Error", rc=1 | Low |
| 8 | `test_discover_default_root` | pytest | correct path found from git root | Medium — needs `git init` in tmpdir |
| 9 | `test_discover_deduplicates_symlinks` | pytest | one path despite symlink | Low |
| 10 | `test_discover_prose_shared_core` | pytest (static grep) | shared core mentions `status --discover` | Low — file read |
| 11 | `test_discover_prose_codex_runtime` | pytest (static grep) | codex runtime mentions `status --discover` | Low — file read |

**Live E2E not required.** All tests use the existing pytest + subprocess pattern from `test_status_script.py`, creating temporary directories with fixture README.md files. No live API calls, no agent dispatch, no external services. The existing `build_status_script()` / `run_status()` test helpers are sufficient.

### 9. Scope Boundary

**IN scope:**
- `--discover` and `--root` flag implementation in `skills/commission/bin/status`
- `discover_workflows()` function in the status script
- Argument parsing and incompatibility checks
- pytest tests in `tests/test_status_script.py`
- Prose update to `first-officer-shared-core.md` step 2
- Prose update to `codex-first-officer-runtime.md` Workflow Target section

**OUT of scope (deferred):**
- Changing the Claude runtime adapter prose — not needed because it already defers to the shared core.
- `--max-depth` flag — YAGNI until performance is a proven problem.
- JSON output mode for discovery — can be added when a consumer needs it.
- Removing any existing raw grep/rg usage from agent behavior — the agents will pick up the new prose on their next session; no code migration is needed.

### 10. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| **Test fixtures as false positives.** The `tests/fixtures/` directory contains README.md files with `commissioned-by: spacedock@test`. Without `tests` in the ignore list, `--discover` from the repo root would return fixture directories. | Medium — would confuse real workflow discovery | Include `tests` in the ignore list. Acceptance criterion #4 explicitly tests this. |
| **`.worktrees` containing stale copies of workflow README.md files.** The spacedock repo has many `.worktrees/*/docs/plans/README.md` files with the frontmatter marker. | High — would return dozens of false positives | `.worktrees` is already in the shared core ignore list and will be in the implementation. Test #4 covers this. |
| **Performance on large repos.** `os.walk` with frontmatter parsing could be slow in monorepos with deep trees. | Low — the ignore list prunes the most common heavy subtrees (`node_modules`, `dist`, `build`, `vendor`). Real-world workflow directories are typically 1-3 levels deep. | Acceptable for now. `--max-depth` is deferred but straightforward to add. |
| **Symlink cycles.** `os.walk(followlinks=True)` can infinite-loop on symlink cycles. | Low — rare in practice | Use `os.path.realpath` on visited directories and track seen real paths to break cycles. |

### Checklist

1. DONE — Problem statement restated
2. DONE — Current discovery call sites surveyed
3. DONE — Concrete `--discover` design proposed with CLI surface, output format, exit codes, and interaction with existing flags
4. DONE — Search semantics specified (root, ignore list, depth, symlinks, tie-break)
5. DONE — Before/after for all affected surfaces (status script, shared core, Codex runtime, Claude runtime)
6. DONE — Back-compat check confirms no behavioral change to existing callers
7. DONE — 11 numbered acceptance criteria with named tests
8. DONE — Test plan with harness, assertions, and cost for each test
9. DONE — Scope boundary with explicit in/out decisions
10. DONE — Risk register with 4 risks and mitigations

## Stage Report — implementation

### Deliverables

**Status script** (`skills/commission/bin/status`):
- Added `DISCOVER_IGNORE_DIRS` constant and `discover_workflows(root)` function with full docstring documenting the ignore list, matching rule (bare `spacedock@` accepted), and symlink return-path behavior.
- Added `--discover` flag handling in `main()` with `--root` optional argument, incompatibility checks against all other flags, git-toplevel default with cwd fallback, and one-path-per-line output.
- Symlinks followed with `followlinks=True`, deduplicated via `os.path.realpath`, cycle-safe via visited-set tracking. Canonical resolved path returned, not symlink path.

**Shared core** (`skills/first-officer/references/first-officer-shared-core.md`):
- Startup step 2 now reads: run `{spacedock_plugin_dir}/skills/commission/bin/status --discover` and use the result. Old "search for `README.md` files" prose removed.

**Codex runtime** (`skills/first-officer/references/codex-first-officer-runtime.md`):
- Workflow Target section now reads: run `status --discover` to find candidate workflows, with cardinality handling. Old "discover candidate workflows from the current repository" prose removed.

**Tests** (`tests/test_status_script.py`):
- 11 new tests in `TestDiscover` class covering all acceptance criteria.

### Staff-Review Notes Resolution

1. **`spacedock@` matching tolerance** — Bare `spacedock@` (no version suffix) matches. `discover_workflows()` docstring documents the rule. `test_discover_skips_non_spacedock_readme` includes a `spacedock@` bare-version case asserting it is discovered.
2. **Prose replacement, not supplementation** — `test_discover_prose_shared_core` asserts `status --discover` present AND `search for \`README.md\` files` absent. `test_discover_prose_codex_runtime` asserts `status --discover` present AND `discover candidate workflows from the current repository` absent.
3. **`discover_workflows()` docstring** — Documents the canonical ignore list, matching rule, and symlink behavior. Single source of truth; the ignore list is the `DISCOVER_IGNORE_DIRS` constant referenced by the function.
4. **`spacedock@` bare-version boundary case** — Covered in `test_discover_skips_non_spacedock_readme` with a `commissioned-by: spacedock@` README that is asserted to match.
5. **Symlink return path** — `test_discover_deduplicates_symlinks` asserts that when both a symlink and its target match, only one result is returned, and it is the canonical `os.path.realpath` path. Documented in the docstring.

### Test Output

```
tests/test_status_script.py::TestDiscover::test_discover_bad_root PASSED
tests/test_status_script.py::TestDiscover::test_discover_deduplicates_symlinks PASSED
tests/test_status_script.py::TestDiscover::test_discover_default_root PASSED
tests/test_status_script.py::TestDiscover::test_discover_ignores_excluded_dirs PASSED
tests/test_status_script.py::TestDiscover::test_discover_incompatible_flags PASSED
tests/test_status_script.py::TestDiscover::test_discover_multiple_workflows PASSED
tests/test_status_script.py::TestDiscover::test_discover_no_workflows PASSED
tests/test_status_script.py::TestDiscover::test_discover_prose_codex_runtime PASSED
tests/test_status_script.py::TestDiscover::test_discover_prose_shared_core PASSED
tests/test_status_script.py::TestDiscover::test_discover_single_workflow PASSED
tests/test_status_script.py::TestDiscover::test_discover_skips_non_spacedock_readme PASSED
11 passed, 10 subtests passed in 0.52s
```

`make test-static`: 207 passed, 10 subtests passed in 4.63s — no regressions.

### Checklist

1. DONE — `--discover` flag with optional `--root`, one absolute path per line, sorted, exit 0 for any cardinality, exit 1 for errors, incompatible with all other flags.
2. DONE — `discover_workflows(root)` function with staff-review docstring covering ignore list, matching rule, and symlink return-path.
3. DONE — Ignore list: `.git`, `.worktrees`, `node_modules`, `vendor`, `dist`, `build`, `__pycache__`, `tests`.
4. DONE — Default `--root` to `git rev-parse --show-toplevel` with cwd fallback; `--root <path>` overrides.
5. DONE — Symlinks followed, deduplicated via `os.path.realpath`, canonical resolved path returned.
6. DONE — `first-officer-shared-core.md` step 2 updated: old grep prose removed, `status --discover` invocation added.
7. DONE — `codex-first-officer-runtime.md` Workflow Target updated: old "discover candidate workflows" prose removed, `status --discover` invocation added.
8. DONE — 11 acceptance-criteria tests added to `tests/test_status_script.py`.
9. DONE — All 11 new tests pass locally (0.52s).
10. DONE — `make test-static` passes: 207 passed, 0 failed.
11. DONE — Committed on branch `spacedock-ensign/status-workflow-discovery` as `d928f0f`.

## Stage Report — validation

### AC Verification

**AC1 — Single workflow discovery:** Inspected `test_discover_single_workflow` (line 1940). Creates tmpdir with one README.md containing `commissioned-by: spacedock@1.0`, runs `--discover --root`, asserts single line of output matching `os.path.realpath(wf_dir)` and rc=0. The implementation (`discover_workflows` at line 919) walks the tree, calls `parse_frontmatter`, checks `startswith('spacedock@')`, returns sorted absolute resolved paths. PASS.

**AC2 — Zero workflows:** Inspected `test_discover_no_workflows` (line 1955). Empty tmpdir, asserts stdout empty, rc=0. Implementation returns empty list when no README.md matches, `main()` prints nothing and exits 0. PASS.

**AC3 — Multiple workflows alphabetically:** Inspected `test_discover_multiple_workflows` (line 1963). Creates `alpha-workflow` and `beta-workflow` subdirs, asserts 2 lines with alpha before beta. Implementation calls `sorted(results)` on line 971. PASS.

**AC4 — Ignore list:** Inspected `test_discover_ignores_excluded_dirs` (line 1980). Creates matching README.md inside each of `tests`, `node_modules`, `.worktrees`, `vendor`, `dist`, `build`, `__pycache__` subdirs, plus one in `valid/`. Asserts only `valid` appears. `DISCOVER_IGNORE_DIRS` on line 916 is the canonical constant; pruning on line 954 removes these from `dirnames` during walk. All 7 ignored dirs plus `.git` are covered. PASS.

**AC5 — Non-spacedock skip:** Inspected `test_discover_skips_non_spacedock_readme` (line 2004). Creates `other@1.0`, bare (no field), `spacedock@` (bare version), and `spacedock@2.0`. Asserts exactly 2 matches: `bare-version` and `valid`. This also validates staff-review item 4 (bare `spacedock@` matching). PASS.

**AC6 — Incompatible flags:** Inspected `test_discover_incompatible_flags` (line 2046). Parameterized over 10 flag combinations: `--boot`, `--next`, `--next-id`, `--archived`, `--where`, `--set`, `--archive`, `--fields`, `--all-fields`, `--workflow-dir`. Each asserts rc=1 and `Error` in stderr. Implementation checks at lines 978-988. PASS.

**AC7 — Bad root:** Inspected `test_discover_bad_root` (line 2071). Runs `--discover --root /nonexistent/path`, asserts rc=1 and `Error` in stderr. Implementation checks `os.path.isdir` at line 1016. PASS.

**AC8 — Default root:** Inspected `test_discover_default_root` (line 2079). Creates a git repo in tmpdir, adds a workflow subdir, runs `--discover` from a subdirectory without `--root`. Asserts correct path found via `git rev-parse --show-toplevel` fallback. PASS.

**AC9 — Symlink deduplication:** Inspected `test_discover_deduplicates_symlinks` (line 2113). Creates a real workflow dir and a symlink to it, asserts 1 result that equals `os.path.realpath(real_dir)`. Implementation tracks `seen_real` set (line 944) and resolves with `os.path.realpath` (line 967). Validates staff-review item 5 (canonical realpath assertion on line 2132). PASS.

**AC10 — Shared core prose:** Inspected `test_discover_prose_shared_core` (line 2134). Asserts `status --discover` is present AND `search for \`README.md\` files` is absent. Verified the actual file content at line 8 of `first-officer-shared-core.md` — the old grep prose is gone, replaced with `status --discover` invocation with cardinality handling. PASS.

**AC11 — Codex runtime prose:** Inspected `test_discover_prose_codex_runtime` (line 2141). Asserts `status --discover` is present AND `discover candidate workflows from the current repository` is absent. Verified the actual diff — old lines 14-15 replaced with `status --discover` invocation and cardinality handling. PASS.

### Test Runs

**pytest:** `unset CLAUDECODE && uv run --with pytest python -m pytest tests/test_status_script.py -q` → `104 passed, 10 subtests passed in 4.27s`. All 11 TestDiscover tests present and passing.

**make test-static:** `207 passed, 10 subtests passed in 4.98s`. No regressions.

### Manual Spot-Checks

**Spot-check 1:** `python3 skills/commission/bin/status --discover --root {worktree}` → stdout: `/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-status-workflow-discovery/docs/plans`, exit code 0. Sensible result — the worktree's own `docs/plans` is the only match; no test fixture directories leaked.

**Spot-check 2:** `python3 skills/commission/bin/status --discover --boot` → stderr: `Error: --discover is incompatible with --boot`, exit code 1.

**Spot-check 3:** `python3 skills/commission/bin/status --discover --root /nonexistent/path` → stderr: `Error: --root path does not exist: /nonexistent/path`, exit code 1.

### Staff-Review Item Verification

1. **`spacedock@` matching tolerance** — DONE. `discover_workflows()` docstring (lines 924-928) explicitly documents: "Both `spacedock@1.0` and bare `spacedock@` (no version suffix) are accepted."

2. **Prose replacement, not supplementation** — DONE. `test_discover_prose_shared_core` asserts `assertNotIn('search for \`README.md\` files', content)` (line 2139). `test_discover_prose_codex_runtime` asserts `assertNotIn('discover candidate workflows from the current repository', content)` (line 2146). Both assert old wording absent, not just new wording present.

3. **Single-sourced ignore list** — DONE. Searched the script: `DISCOVER_IGNORE_DIRS` appears on line 916 (definition) and line 954 (usage). No duplicated string literals of individual ignore entries elsewhere in the file. The docstring on line 931 documents the list but references the constant as "canonical source of truth."

4. **Bare `spacedock@` test case** — DONE. `test_discover_skips_non_spacedock_readme` (lines 2025-2029) creates a README with `commissioned-by: spacedock@` and asserts it is discovered (included in the 2-match result on lines 2041-2044).

5. **Symlink realpath assertion** — DONE. `test_discover_deduplicates_symlinks` line 2132: `self.assertEqual(lines[0], os.path.realpath(real_dir))` — explicitly asserts the canonical resolved path, not the symlink path. Docstring documents this behavior at lines 933-938.

### Prose Changes

- `first-officer-shared-core.md` step 2: Contains `status --discover`. Does NOT contain `search for \`README.md\` files`. Verified via diff and direct file read.
- `codex-first-officer-runtime.md` Workflow Target: Contains `status --discover`. Does NOT contain `discover candidate workflows from the current repository`. Verified via diff and direct file read.

### Scope Check

Files changed (from `git diff main..HEAD --name-only`):
1. `docs/plans/status-workflow-discovery.md` — entity file (always in scope)
2. `skills/commission/bin/status` — in scope per ideation section 9
3. `skills/first-officer/references/codex-first-officer-runtime.md` — in scope per ideation section 9
4. `skills/first-officer/references/first-officer-shared-core.md` — in scope per ideation section 9
5. `tests/test_status_script.py` — in scope per ideation section 9

No files outside declared scope.

### Back-Compat Check

Spot-checked:
- `status --boot --workflow-dir docs/plans` → normal boot output (MODS, NEXT_ID, ORPHANS, PR_STATE, DISPATCHABLE), exit 0. Unchanged.
- `status --workflow-dir docs/plans` (default table) → normal table output, exit 0. Unchanged.

The `--discover` flag is additive and incompatible with all existing flags, so no existing invocation can be affected.

### Checklist

1. DONE — Verified all 11 ACs with evidence (see AC Verification above).
2. DONE — pytest: 104 passed, 10 subtests passed in 4.27s. 11 TestDiscover tests present and passing.
3. DONE — make test-static: 207 passed, 10 subtests passed in 4.98s. No regressions.
4. DONE — Manual spot-check: `--discover --root {worktree}` outputs `docs/plans`, exit 0. No test fixtures in output.
5. DONE — Manual spot-check: `--discover --boot` exits 1 with `Error: --discover is incompatible with --boot` on stderr.
6. DONE — Manual spot-check: `--discover --root /nonexistent/path` exits 1 with `Error: --root path does not exist: /nonexistent/path` on stderr.
7. DONE — All 5 staff-review items verified in code and tests (see Staff-Review Item Verification above).
8. DONE — Prose changes verified in both files (see Prose Changes above).
9. DONE — Scope check: all 5 changed files within declared scope, no scope creep.
10. DONE — Back-compat spot-checked: `--boot --workflow-dir` and default table both work unchanged.
11. DONE — Recommendation: **PASSED**.
