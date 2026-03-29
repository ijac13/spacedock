---
id: 078
title: Modular test harness — shared commission snapshot, reusable E2E phases
status: ideation
source: CL — test duplication observed during model variation runs
started: 2026-03-29T20:30:00Z
completed:
verdict:
score: 0.70
worktree:
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

## Test Plan

- **Unit-level**: validate `test-lib.sh` functions in isolation with a small shell test script that sources it and exercises pass/fail/check/test_results
- **Integration**: run each of the 7 refactored scripts and verify they still pass
- **Snapshot round-trip**: commission with `--snapshot-dir`, then E2E with `--from-snapshot`, verify the full flow works
- **Cost**: the refactoring is shell-only, no API calls needed for the refactoring itself. Validation requires running the same tests that already exist (~$2-5 per full suite run)
- **E2E test needed?**: No new E2E test — this is infrastructure refactoring; the existing E2E tests serve as the validation suite

## Stage Report: ideation

- [x] All test scripts inventoried with shared/duplicated code identified
  See "Inventory of Test Scripts" and "Duplicated Code Analysis" sections above
- [x] Modular design proposed (test-lib, snapshot mechanism, from-snapshot)
  See "Proposed Modular Design" sections 1-3
- [x] Stats extraction built into design (messages, model delegation, wallclock)
  See section 3: wallclock, message count, model delegation, token usage — auto-extracted from stream-json
- [x] Acceptance criteria with test plan
  7 acceptance criteria with specific test commands, plus test plan section

### Summary

Inventoried all 7 test scripts (2 in `scripts/`, 5 in `tests/`). Found ~500+ lines of duplicated boilerplate across them: pass/fail counters, cleanup traps, results summaries, git init setup, first-officer sed substitution, and python3 log extraction. The commission duplication is limited to 2 scripts (`test-commission.sh` and `test-checklist-e2e.sh`); the other 5 use static fixtures. Proposed `test-lib.sh` with shared helpers, snapshot mechanism for commission reuse, and automatic stats extraction from stream-json logs. The fixture-based tests in `tests/` also benefit from shared `setup_fixture` and `generate_first_officer` helpers to eliminate the repeated 11-flag sed pattern.
