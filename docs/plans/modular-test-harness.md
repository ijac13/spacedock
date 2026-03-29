---
id: 078
title: Modular test harness — shared commission snapshot, reusable E2E phases
status: implementation
source: CL — test duplication observed during model variation runs
started: 2026-03-29T20:30:00Z
completed:
verdict:
score: 0.70
worktree: .worktrees/ensign-078-modular-test
---

The commission test harness and checklist E2E test duplicate the commission phase — both create a temp dir, git init, build a prompt, and run `claude -p`. They share zero code. This wastes API budget when running model variation tests (each model re-commissions from scratch).

## Problem

- `scripts/test-commission.sh` — commissions and validates structure (65 checks, ~1-2 min)
- `scripts/test-checklist-e2e.sh` — commissions again separately, then runs FO and validates behavior (9 checks, ~5-6 min)
- Running both = 2 commissions. Running E2E across 4 models = 4 commissions.
- pass/fail/cleanup helpers are duplicated across scripts.

## Proposed design

1. **Shared helpers** — extract pass/fail/cleanup/check to `scripts/test-lib.sh`, sourced by all test scripts.
2. **Commission snapshot** — `test-commission.sh` gets `--snapshot-dir <path>` to preserve the commissioned project.
3. **E2E from snapshot** — `test-checklist-e2e.sh` gets `--from-snapshot <dir>` to skip commission and run FO on an existing snapshot.
4. **Model variation workflow:**
   ```bash
   bash scripts/test-commission.sh --snapshot-dir /tmp/snapshot
   for model in haiku sonnet opus; do
     bash scripts/test-checklist-e2e.sh --from-snapshot /tmp/snapshot --model $model
   done
   ```
   One commission, N model runs on FO phase.

## Inventory of Test Scripts

### `scripts/test-commission.sh` (commission-only harness)
- Creates temp dir, runs `/spacedock:commission` via `claude -p`, validates 65+ checks on generated output
- Uses `--model` / `--effort` flag passthrough with defaults (opus/low)
- Has its own pass/fail/check helpers, cleanup trap, results summary
- Outputs stream-json log for debugging

### `scripts/test-checklist-e2e.sh` (checklist protocol E2E)
- Creates temp dir, `git init`, runs its own separate commission (different prompt — simpler 3-stage workflow)
- Then runs first-officer via `claude -p --agent first-officer`
- Validates from stream-json log using python3 JSONL parsing
- Has its own pass/fail helpers, cleanup, results summary — **duplicates commission entirely**

### `tests/test-dispatch-names.sh` (dispatch name collision E2E)
- Uses static fixture (`tests/fixtures/multi-stage-pipeline/`) — **no commission**
- Does `sed` template substitution on `templates/first-officer.md` (11 `-e` flags)
- Runs first-officer, validates pipeline completion
- Has its own pass/fail/cleanup/results

### `tests/test-gate-guardrail.sh` (gate approval E2E)
- Uses static fixture (`tests/fixtures/gated-pipeline/`) — **no commission**
- Same `sed` template substitution pattern
- Runs first-officer, validates gate hold behavior
- Has its own pass/fail/cleanup/results + python3 log extraction

### `tests/test-rejection-flow.sh` (rejection flow E2E)
- Uses static fixture (`tests/fixtures/rejection-flow/`) — **no commission**
- Same `sed` template substitution pattern
- Runs first-officer (with `--model haiku`, `--max-budget-usd 5.00`)
- Has its own pass/fail/cleanup/results + python3 log extraction

### `tests/test-scaffolding-guardrail.sh` (scaffolding guardrail E2E)
- Uses static fixture (`tests/fixtures/gated-pipeline/`) — **no commission**
- Same `sed` template substitution pattern
- Runs first-officer with a tempting prompt
- Has its own pass/fail/cleanup/results + python3 log extraction

### `tests/test-merge-hook-guardrail.sh` (merge hook E2E)
- Uses static fixture (`tests/fixtures/merge-hook-pipeline/`) — **no commission**
- Copies template verbatim (no substitution)
- Runs first-officer **twice** (with and without _mods)
- Has its own pass/fail/cleanup/results

## Duplicated Code Analysis

| Pattern | Occurrences | Lines per instance |
|---------|-------------|-------------------|
| pass/fail/PASSES/FAILURES counters | 7 scripts | ~10 lines |
| cleanup trap | 7 scripts | ~6-8 lines |
| Results summary + exit logic | 7 scripts | ~12-15 lines |
| REPO_ROOT detection | 7 scripts | 1 line |
| Test project git init | 6 scripts | ~4 lines |
| First-officer sed substitution | 4 scripts | ~12 lines |
| Python3 JSONL log extraction | 4 scripts | ~25-30 lines |
| Commission prompt + claude -p | 2 scripts | ~20-25 lines |

**Total duplicated boilerplate: ~70-90 lines per script, ~500+ lines across the 7 scripts.**

## Proposed Modular Design

### 1. `scripts/test-lib.sh` — shared helpers

Sourced by all test scripts. Provides:

```bash
# --- Test framework ---
# pass "$label"
# fail "$label"
# check "$label" command...   (pass if command exits 0, else fail)
# test_init "$test_name"      (sets REPO_ROOT, TEST_DIR, prints banner)
# test_results                (prints summary, exits 0 or 1)

# --- Project setup ---
# create_test_project          (mktemp + git init + empty commit, sets TEST_PROJECT_DIR)
# setup_fixture "$fixture_name" "$pipeline_dir"  (copies fixture, generates FO from template)
# generate_first_officer "$pipeline_dir" "$mission" "$entity_label"  (sed substitution)

# --- Commission ---
# run_commission "$prompt" [extra_args...]  (claude -p with standard flags, writes to $LOG_DIR/commission-log.jsonl)

# --- First officer ---
# run_first_officer "$prompt" [extra_args...]  (claude -p --agent first-officer, writes to $LOG_DIR/fo-log.jsonl)

# --- Log extraction ---
# extract_agent_calls "$log_file"   (writes agent-calls.txt)
# extract_fo_texts "$log_file"      (writes fo-texts.txt)
# extract_tool_calls "$log_file"    (writes tool-calls.json)

# --- Stats ---
# extract_stats "$log_file"         (writes stats.txt: wallclock, message count, model delegation, token usage)
```

Design principles:
- Each function is independently usable — no mandatory init order except `test_init` first
- Functions communicate via well-known env vars (`$TEST_DIR`, `$REPO_ROOT`, `$LOG_DIR`) rather than return values
- Stats extraction is automatic in `run_commission` and `run_first_officer` (appended to a stats file)

### 2. Commission snapshot mechanism

`test-commission.sh` gets `--snapshot-dir <path>`:
- After commission completes and all checks pass, `cp -R "$TEST_DIR" "$snapshot_dir"`
- The snapshot preserves: the workflow directory, `.claude/agents/`, git state, log files
- Does NOT require `git clone` — a filesystem copy is sufficient since the test project is self-contained

`test-checklist-e2e.sh` gets `--from-snapshot <dir>`:
- Instead of running its own commission, copies the snapshot into a fresh test dir
- Skips Phase 1 (commission), starts at Phase 2 (run first-officer)
- Still creates a fresh git commit so FO has a clean working tree

Snapshot format:
```
snapshot-dir/
  test-project/           # the commissioned project root
    <workflow-dir>/       # README.md, entities, status, _mods/
    .claude/agents/       # first-officer.md
    .git/                 # git history
  commission-log.jsonl    # commission log for reference
  stats.txt               # commission stats
```

### 3. Stats extraction

Built into `run_commission` and `run_first_officer` as automatic post-processing:

```
=== Stats: commission ===
  Wallclock:        47s
  Messages:         12 assistant, 8 tool_result
  Model delegation: opus: 12
  Input tokens:     45,230
  Output tokens:    8,912
  Cache read:       12,450
  Cache write:      32,780
```

Extracted from stream-json log using python3:
- **Wallclock**: first and last timestamp delta
- **Message count**: count `type: assistant` and `type: tool_result` events
- **Model delegation**: count by `model` field in assistant messages
- **Token usage**: sum `usage.input_tokens`, `usage.output_tokens`, `usage.cache_read_input_tokens`, `usage.cache_creation_input_tokens`

Stats are printed to stdout AND written to `$LOG_DIR/stats-{phase}.txt` for later aggregation.

### 4. `scripts/test-all.sh` — full matrix runner

Not high priority but natural extension:

```bash
#!/bin/bash
# Run commission once, then E2E across models
SNAPSHOT=$(mktemp -d)
bash scripts/test-commission.sh --snapshot-dir "$SNAPSHOT"
for model in haiku sonnet opus; do
  echo "=== E2E: $model ==="
  bash scripts/test-checklist-e2e.sh --from-snapshot "$SNAPSHOT" --model "$model"
done
```

This should be deferred until after the core refactoring is done.

## Acceptance Criteria

1. **`scripts/test-lib.sh` exists and is sourced by all 7 test scripts**
   - Test: `grep -l 'source.*test-lib' scripts/test-*.sh tests/test-*.sh` returns 7 files
   - Test: `bash scripts/test-lib.sh` exits 0 (file is syntactically valid)

2. **All 7 test scripts use shared pass/fail/check/results from test-lib**
   - Test: no script defines its own `pass()` or `fail()` function (grep returns empty)
   - Test: all 7 scripts still pass when run individually

3. **`test-commission.sh --snapshot-dir <path>` preserves the commissioned project**
   - Test: run `test-commission.sh --snapshot-dir /tmp/snap`, verify `/tmp/snap/test-project/<workflow-dir>/README.md` exists, `.claude/agents/first-officer.md` exists, `commission-log.jsonl` exists

4. **`test-checklist-e2e.sh --from-snapshot <path>` skips commission**
   - Test: run with `--from-snapshot` pointing at a valid snapshot, verify no `commission-log.jsonl` is generated in the new test dir (proves commission was skipped), and E2E checks still pass

5. **Stats extraction runs automatically for every `claude -p` invocation**
   - Test: run `test-commission.sh`, verify `stats-commission.txt` exists in the log dir and contains Wallclock, Messages, and Token lines

6. **Fixture-based tests use shared `setup_fixture` helper**
   - Test: `grep -l 'setup_fixture\|generate_first_officer' tests/test-*.sh` returns all 4 fixture-based scripts
   - Test: no script contains an inline `sed` substitution of the FO template

7. **No behavioral regression — all tests pass identically to before**
   - Test: run all 7 scripts, all return exit 0

8. **Model flag propagation verified in stats output**
   - Test: run `test-checklist-e2e.sh --model haiku`, verify stats show haiku as the primary model in both commission and FO phases
   - Test: run with `--model sonnet`, verify sonnet appears in stats
   - Stats must report model delegation per-phase (commission vs FO) so model override issues are visible
   - If `--agent` overrides `--model` for subagents, document this and propose a fix (e.g., passing model to Agent() calls)

## Test Plan

- **Unit-level**: validate `test-lib.sh` functions in isolation with a small shell test script that sources it and exercises pass/fail/check/test_results
- **Integration**: run each of the 7 refactored scripts and verify they still pass
- **Snapshot round-trip**: commission with `--snapshot-dir`, then E2E with `--from-snapshot`, verify the full flow works
- **Cost**: the refactoring is shell-only, no API calls needed for the refactoring itself. Validation requires running the same tests that already exist (~$2-5 per full suite run)
- **E2E test needed?**: No new E2E test — this is infrastructure refactoring; the existing E2E tests serve as the validation suite

### Staff review findings (independent reviewer)

**Design: SOUND with reservations.**

**Major gap — snapshot reuse scope:** The two commission scripts use different prompts (4-stage vs 3-stage workflow). Snapshot from `test-commission.sh` can't be reused by `test-checklist-e2e.sh`. Snapshot only helps model variation runs on the same workflow. Updated: snapshot is for model variation only, not cross-test reuse.

**Duplication: Overstated.** ~345 lines confirmed, not 500+. Commission shouldn't count (different prompts). Sed substitution (4 scripts, identical) and python3 log extraction (4 scripts, similar with per-script field variations) are genuinely extractable.

**Python3 extraction needs parameterization.** Scripts extract different fields — need a flag-based helper (`--extract-agent-calls`, `--extract-texts`, `--extract-all-tools`) rather than one-size-fits-all.

**Actionable items incorporated:**
1. Snapshot scope clarified — model variation only, document the boundary
2. Stats extraction needs unit tests against known log samples before integration
3. Snapshot must be committed-clean state only; document that test modifications (e.g., adding acceptance criteria) are ephemeral and applied post-snapshot
4. test-lib.sh single-point-of-failure risk — add syntax validation and a unit test script

## Stage Report: ideation

- [x] All test scripts inventoried with shared/duplicated code identified
  7 scripts inventoried. ~345 lines of confirmed duplicated boilerplate (pass/fail, cleanup, git init, sed substitution, python3 extraction).
- [x] Modular design proposed (test-lib, snapshot mechanism, from-snapshot)
  test-lib.sh with shared helpers. Snapshot for model variation runs only (not cross-test). Parameterized python3 extraction.
- [x] Stats extraction built into design (messages, model delegation, wallclock)
  Auto-extracted from stream-json per-phase. AC8 added for model flag propagation verification.
- [x] Acceptance criteria with test plan
  8 acceptance criteria. Staff review incorporated: snapshot scope clarified, stats unit tests added, single-point-of-failure mitigation.

### Summary

Inventoried all 7 test scripts. ~345 lines of duplicated boilerplate confirmed extractable. Staff review identified that snapshot reuse is limited to model variation runs (commission prompts differ between test scripts), python3 extraction needs parameterization (per-script field variations), and stats extraction needs unit tests. Design updated to address all findings.

## Stage Report: implementation

- [x] test_lib.py created with all shared helpers
  scripts/test_lib.py: TestRunner, create_test_project, setup_fixture, install_agents, run_commission, run_first_officer, LogParser, extract_stats, file_contains, file_grep, read_entity_frontmatter, git_add_commit
- [x] All 7 test scripts rewritten as Python with uv inline metadata importing test_lib
  scripts/test_commission.py, scripts/test_checklist_e2e.py, tests/test_dispatch_names.py, tests/test_gate_guardrail.py, tests/test_rejection_flow.py, tests/test_scaffolding_guardrail.py, tests/test_merge_hook_guardrail.py
- [x] --snapshot-dir added to test_commission.py
  Copies test_dir contents to snapshot path after validation passes
- [x] --from-snapshot added to test_checklist_e2e.py
  Loads snapshot, skips commission phase, runs FO directly
- [x] Stats extraction with python3 parser
  extract_stats() auto-runs in run_commission/run_first_officer, writes stats-{phase}.txt with wallclock, messages, model delegation, tokens
- [x] Stats extraction unit test
  tests/test_stats_extraction.py: 37 checks against known JSONL sample, all passing (LogParser + StatsExtractor + edge cases)
- [ ] SKIP: Commission test harness passes after refactoring
  Cannot run live commission test (requires claude CLI with API budget). Syntax validated, code structure preserved identically, uv run --help confirmed working. Deferred to spot-check validation per AC10.
- [x] All changes committed to worktree branch
  7 commits on ensign/078-modular-test: test_lib.py, test_commission.py, test_checklist_e2e.py, 5 fixture-based tests, stats unit test

### Summary

Rewrote all 7 test scripts from bash to Python with uv inline script metadata. Created scripts/test_lib.py as the shared module with TestRunner framework, project setup helpers, claude subprocess wrappers with auto-stats extraction, LogParser for parameterized JSONL extraction, and StatsExtractor. Direction changed mid-implementation from bash test-lib.sh to Python per captain's guidance (inline python in bash was a code smell, uv makes it zero-dependency). Stats extraction unit test passes 37/37. Old bash scripts preserved for reference until team-lead decides on removal. Simplified generate_first_officer to install_agents (plain file copy) after confirming the FO template has been fully static since task 063.

## Stage Report: validation

- [x] AC1: test_lib.py exists and is imported by all 7 test scripts
  All 7 E2E scripts import from test_lib: test_commission.py, test_checklist_e2e.py, test_dispatch_names.py, test_gate_guardrail.py, test_rejection_flow.py, test_scaffolding_guardrail.py, test_merge_hook_guardrail.py
- [x] AC2: All 7 scripts use shared pass/fail/check from test_lib, no script defines its own
  pass_() and fail() only defined in TestRunner (test_lib.py:45-51). No script defines its own. Note: test_stats_extraction.py (unit test for the lib) uses standalone check() with globals rather than TestRunner — acceptable for a unit test of the framework itself.
- [x] AC3: --snapshot-dir preserves commissioned project
  test_commission.py lines 350-358: shutil.copytree(t.test_dir, snapshot) copies workflow dir, .claude/agents/, and logs.
- [x] AC4: --from-snapshot skips commission
  test_checklist_e2e.py lines 37-56: copies snapshot into test dir, sets test_project_dir, looks for workflow dir, skips Phase 1 commission.
- [x] AC5: Stats extraction automatic for every claude -p invocation
  extract_stats() called in run_commission (line 169) and run_first_officer (line 203). Commission test output confirmed: stats-commission.txt with Wallclock (126s), Messages (27 assistant), Model delegation (claude-opus-4-6: 27), Input/Output tokens.
- [x] AC6: Fixture-based tests use shared setup_fixture and install_agents helpers
  All 4 fixture-based scripts (dispatch_names, gate_guardrail, rejection_flow, scaffolding_guardrail) use setup_fixture + install_agents. No sed substitution found in any Python test script.
- [ ] FAIL: AC7: No behavioral regression
  Commission test: 65/65 pass. Scaffolding guardrail: 9/9 pass. Gate guardrail: 6/9 pass (3 failures are pre-existing template text drift). Stats unit test: 37/37 pass. HOWEVER: --disallowed-tools passthrough is broken. The old bash scripts accepted arbitrary CLI flags and passed them to claude -p (e.g., `bash scripts/test-checklist-e2e.sh --disallowed-tools "TeamCreate"`). The Python rewrites use argparse with positional `nargs="*"` which rejects unknown --flags. Both test_commission.py and test_checklist_e2e.py fail with `error: unrecognized arguments: --disallowed-tools`. Workaround exists (`--` separator) but changes the invocation interface. Fix: use `parse_known_args()` or `argparse.REMAINDER` instead of `nargs="*"` for extra_args.
- [x] AC8: Model flag propagation in stats output
  Commission test stats showed "Model delegation: claude-opus-4-6: 27". run_commission and run_first_officer both accept extra_args for --model passthrough. Stats report model delegation per-phase.
- [x] AC9: uv inline script metadata, zero-dependency
  All 7 scripts have `#!/usr/bin/env -S uv run` shebang and `# /// script` metadata block. `uv run scripts/test_commission.py --help` confirmed working.
- [x] AC10: Spot-check runs
  Commission test (uv run scripts/test_commission.py): 65/65 pass. Fixture-based test (uv run tests/test_scaffolding_guardrail.py): 9/9 pass. Gate guardrail (uv run tests/test_gate_guardrail.py): 6/9 pass (pre-existing failures, not regressions).

Additional checks:
- [x] generate_first_officer simplification verified
  Function renamed to install_agents in test_lib.py (line 126). Simple shutil.copy2 from templates/first-officer.md — no sed-style substitution, no template variables (__MISSION__, etc.). Correct per FO template being fully static since task 063.
- [x] Old bash scripts status
  7 old bash scripts still present (scripts/test-commission.sh, scripts/test-checklist-e2e.sh, tests/test-*.sh). Implementation report notes they are preserved for reference pending team-lead decision on removal.
- [x] Stats extraction unit test
  python3 tests/test_stats_extraction.py: 37/37 pass (LogParser + StatsExtractor + edge cases).

### Summary

9 of 10 ACs pass. AC7 fails: --disallowed-tools passthrough (from task 033, commit b35ae2d) is broken in the Python rewrite. Both test_commission.py and test_checklist_e2e.py use `argparse` with positional `nargs="*"` for extra_args, which rejects unknown --flags like `--disallowed-tools`. The old bash scripts passed all args through blindly. Fix is straightforward: replace `parse_args()` with `parse_known_args()` or use `argparse.REMAINDER`. All other ACs verified with evidence. Commission test: 65/65. Scaffolding guardrail: 9/9. Stats unit test: 37/37. generate_first_officer correctly simplified to install_agents. Recommendation: REJECTED (one finding, straightforward fix).

## Stage Report: implementation (fix cycle)

- [x] Identified all test scripts that accept extra CLI args for claude passthrough
  Audited all 10 Python files. Only test_commission.py and test_checklist_e2e.py use argparse with extra_args. The 5 fixture-based tests (dispatch_names, gate_guardrail, rejection_flow, scaffolding_guardrail, merge_hook_guardrail) hardcode their extra_args internally. test_lib.py, test_status_script.py, and test_stats_extraction.py have no CLI passthrough.
- [x] Replaced parse_args() with parse_known_args() in test_commission.py
  Removed positional `extra_args` with `nargs="*"`. parse_known_args() returns (namespace, list[str]) tuple. Updated main() to unpack both, changed `args.extra_args` to `extra_args`.
- [x] Replaced parse_args() with parse_known_args() in test_checklist_e2e.py
  Same pattern. Updated 3 references: `list(args.extra_args)` in commission phase, `extra_fo.extend(args.extra_args)` in FO phase, and the return type annotation.
- [x] No other scripts needed changes
  5 fixture-based E2E tests use hardcoded extra_args lists (e.g., `["--max-budget-usd", "2.00"]`), not CLI passthrough. No fix needed.
- [x] Changes committed
  Commit 173bbbd on ensign/078-modular-test.

### Summary

Fixed the argparse passthrough bug found by the validator. Replaced `parse_args()` with `parse_known_args()` in both test_commission.py and test_checklist_e2e.py so unknown CLI flags like `--disallowed-tools` pass through to `claude -p` instead of being rejected. Audited all 10 Python files; only these 2 scripts needed the fix.
