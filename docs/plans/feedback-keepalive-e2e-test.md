---
id: 106
title: E2E test for feedback-to keepalive — FO must not kill implementation agent during validation
status: validation
source: CL — observed FO prematurely shutting down implementation ensign when entering validation (feedback-to stage)
started: 2026-04-09T15:24:00Z
completed:
verdict:
score: 0.85
worktree: .worktrees/spacedock-ensign-feedback-keepalive-e2e-test
issue:
pr:
---

The FO's shared core says: when the next stage has `feedback-to` pointing at the completed stage, keep the completed agent alive. The FO violated this rule by shutting down the implementation ensign when advancing to validation (which has `feedback-to: implementation`).

The static content test in `test_reuse_dispatch.py` (line 207) checks that the keepalive rule *exists in the contract text*, but no E2E test verifies the FO actually follows it at runtime.

## What to build

A PTY-based E2E test using `scripts/test_lib_interactive.py` (`InteractiveSession`) that:

1. Sets up a workflow fixture with at least: implementation (worktree) → validation (worktree, fresh, feedback-to: implementation) → done (terminal)
2. Seeds an entity ready for implementation dispatch
3. Starts an interactive claude session with the spacedock first-officer
4. Lets the FO dispatch the implementation ensign
5. Waits for the implementation ensign to complete
6. Observes the FO advancing to validation — at this point, the FO should dispatch a fresh validation agent BUT keep the implementation agent alive
7. Asserts: the implementation agent was NOT sent a shutdown request before or during validation dispatch
8. Clean up

## How to verify keepalive

After the FO dispatches validation, inspect the session logs (via `InteractiveSession.get_subagent_logs()` or raw JSONL) for:
- The implementation agent should still be in the team members list (read `~/.claude/teams/{team}/config.json`)
- No `shutdown_request` message should appear in the FO's output targeting the implementation agent between the implementation completion and validation dispatch
- Alternatively: scan the FO's output stream for `shutdown_request` — it should NOT appear for the implementation agent name

## Test fixture

Use or adapt `tests/fixtures/rejection-flow/` as the base — it already has a feedback-to stage. The fixture needs:
- A simple 3-stage pipeline: implementation → validation (feedback-to: implementation) → done
- A seed entity with enough content that the ensign can complete quickly (minimal real work)

## Acceptance criteria

1. Test file exists at `tests/test_feedback_keepalive.py`
2. Test uses `InteractiveSession` from `scripts/test_lib_interactive.py`
3. Test sets up a workflow with a `feedback-to` stage
4. Test verifies the FO does NOT shut down the implementation agent when dispatching validation
5. Test passes when the FO follows the keepalive rule
6. Test fails when the FO prematurely shuts down the implementation agent

## Stage Report: ideation

### 1. Review PTY test harness capabilities and existing E2E test patterns — DONE

Reviewed `scripts/test_lib_interactive.py` (InteractiveSession class) and `scripts/test_lib.py` (TestRunner, LogParser, setup helpers). Key findings:

- **InteractiveSession** provides PTY-driven multi-turn interaction: `start()`, `send()`, `wait_for(pattern, timeout, min_matches)`, `send_key()`, `get_subagent_logs(project_dir)`, `stop()`. It launches `claude --model ... --permission-mode bypassPermissions` via `pty.fork()`.
- **test_lib.py** provides the non-interactive path: `run_first_officer()` runs `claude -p` with `--output-format stream-json`, producing JSONL logs parsed by `LogParser`. LogParser extracts `agent_calls()`, `tool_calls()`, `fo_texts()`.

### 2. Review existing test fixtures — DONE

Reviewed fixtures at `tests/fixtures/`:
- **rejection-flow**: Has `backlog → implementation (worktree) → validation (worktree, fresh, feedback-to: implementation, gate) → done`. Entity starts at `status: implementation` with a pre-written stage report (already completed). Includes buggy `math_ops.py` and tests to trigger rejection. The `test_rejection_flow.py` test counts Agent dispatches but does NOT assert keepalive — it would pass whether the FO kept the agent alive or killed it and re-dispatched.
- **reuse-pipeline**: `backlog → analysis → implementation → validation (fresh, feedback-to: implementation) → done` — non-worktree stages for analysis/implementation.
- **spike-no-gate**: Simple `backlog → work → done` used by agent-captain-interaction test.

### 3. Design the test fixture — DONE

**Approach:** Create a new fixture at `tests/fixtures/keepalive-pipeline/` that uses a deliberately-buggy implementation to force a validation REJECTION, then verifies the FO routes feedback to the kept-alive implementation agent.

**README.md** (workflow definition):
```yaml
stages:
  defaults:
    worktree: false
    concurrency: 2
  states:
    - name: backlog
      initial: true
    - name: implementation
      worktree: true
    - name: validation
      worktree: true
      fresh: true
      feedback-to: implementation
      gate: true
    - name: done
      terminal: true
```

**Why a buggy implementation matters:** The keepalive rule (shared-core line 106) says keep the implementation agent alive when dispatching validation because `feedback-to: implementation`. But keepalive only MATTERS if the validator REJECTS — that's when the FO routes feedback to the kept-alive implementation agent via SendMessage. If validation passes, the implementation agent gets shut down at cleanup time and we never verify keepalive actually worked. A buggy implementation forces the rejection path, letting us assert that the FO uses SendMessage (not a fresh Agent dispatch) to route feedback to the existing implementation agent.

**Seed entity** (`keepalive-test-task.md`):
```yaml
---
id: "001"
title: Write a function that adds two numbers
status: backlog
score: 0.90
source: test
started:
completed:
verdict:
worktree:
---

Write a Python function `add(a, b)` in `math_ops.py` that returns the sum of two numbers.

## Acceptance Criteria

1. `add(2, 3)` returns `5`
2. `add(-1, 1)` returns `0`
3. `add(0, 0)` returns `0`
```

**Buggy implementation** (`math_ops.py`) — pre-seeded into the repo:
```python
def add(a, b):
    return a - b  # deliberate bug
```

**Test file** (`tests/test_add.py`):
```python
from math_ops import add

def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
```

This mirrors the rejection-flow fixture pattern. The implementation ensign will complete (it may or may not fix the bug — doesn't matter, the pre-seeded buggy code ensures the test will fail). The validator runs the tests, finds failures, and recommends REJECTED.

### 4. Design the test flow — DONE

**Key insight from CL's feedback:** The shared-core (line 112) says "if the stage is a feedback gate that recommends `REJECTED`, auto-bounce directly into the feedback rejection flow instead of waiting on manual review." This auto-bounce fires universally — not just in single-entity mode. So the non-interactive `-p` approach CAN exercise the full rejection + keepalive + feedback routing cycle without captain interaction.

The auto-bounce preempts captain review for REJECTED recommendations (line 112). Even with InteractiveSession, the captain wouldn't get to reject — the FO auto-bounces. The only scenario requiring PTY is captain rejection of a PASSED recommendation, which is a different test.

**Phase 1: Setup**
1. `create_test_project(t)` — temp git repo
2. `setup_fixture(t, "keepalive-pipeline", "keepalive-pipeline")` — copy fixture
3. Copy buggy `math_ops.py` and `tests/test_add.py` into the project (same as rejection-flow test)
4. `install_agents(t, include_ensign=True)` — install FO + ensign agents
5. `git_add_commit()` — initial commit
6. Run `status --next` to verify entity is dispatchable

**Phase 2: Run FO**
- `run_first_officer(t, prompt, ...)` with single-entity mode prompt targeting `keepalive-test-task`
- Model: haiku, effort: low, budget: $5.00
- Prompt: "Process the entity `keepalive-test-task` through the workflow. When you encounter a gate review where the reviewer recommends REJECTED, confirm the rejection so the feedback flow routes fixes back to implementation."

**Phase 3: Validation** — two tiers of assertions:

**Tier 1 — Keepalive at transition (shared-core line 106):**
No shutdown of implementation agent between implementation completion and validation dispatch.

**Tier 2 — Keepalive exercised via rejection feedback routing (shared-core lines 112, 120-124):**
After validation REJECTS, the FO routes feedback to the implementation agent via SendMessage (to the existing agent) rather than dispatching a fresh Agent. This proves the keepalive actually worked — the agent was alive to receive the feedback.

### 5. Design how to detect premature shutdown — DONE

**Detection strategy: temporal log scanning with two assertion tiers**

Walk FO JSONL log entries in order, tracking these events:

1. **Implementation dispatch**: Agent() call with "implementation" in the name
2. **Implementation completion**: completion_pattern in tool_result/FO text, or result/success entry
3. **Validation dispatch**: Agent() call with "validation" in the name
4. **Rejection signal**: FO text or tool_result containing REJECTED/rejection
5. **Feedback routing**: SendMessage or Agent() call targeting implementation agent after rejection

**Tier 1 assertion (keepalive at transition):**
Between events 2 and 3, scan for any SendMessage targeting the implementation agent name that contains shutdown language (`SHUTDOWN_PATTERN` from `test_agent_captain_interaction.py`) OR is a protocol `{"type": "shutdown_request"}` dict. Unlike that test (which excludes protocol dicts as "normal teardown"), we INCLUDE them — the keepalive rule says no shutdown at all during this transition.

**Tier 2 assertion (feedback routing proves keepalive worked):**
After event 4 (rejection), check whether feedback was routed via:
- **SendMessage** to the implementation agent name → keepalive worked (PASS)
- **Fresh Agent() dispatch** for implementation → keepalive failed, FO had to re-dispatch (FAIL)
- **Neither** → pipeline didn't progress far enough (SKIP)

**Secondary checks:**
- FO dispatched Agent() for both implementation and validation stages
- Entity status reached at least validation
- Static: shared-core still contains the keepalive rule text

### 6. Define acceptance criteria with test plan — DONE

**Acceptance criteria (revised):**

| # | Criterion | Test method |
|---|-----------|-------------|
| AC1 | Test file exists at `tests/test_feedback_keepalive.py` | File presence |
| AC2 | Test uses `test_lib.py` (TestRunner, LogParser, run_first_officer) for structured JSONL log analysis. See rationale below. | Code inspection |
| AC3 | Test fixture at `tests/fixtures/keepalive-pipeline/` with `feedback-to: implementation` on validation and a buggy implementation to force rejection | Fixture file inspection |
| AC4 | Tier 1: no shutdown SendMessage targets implementation agent between completion and validation dispatch | Log scanning assertion |
| AC5 | Tier 2: after rejection, feedback routed via SendMessage to existing implementation agent (not fresh Agent dispatch) | Log scanning assertion |
| AC6 | Test passes when FO follows keepalive rule, fails when FO prematurely shuts down | E2E test run |

**Rationale for test_lib.py over InteractiveSession (AC2):**
The shared-core line 112 auto-bounces REJECTED recommendations into the feedback rejection flow WITHOUT waiting for captain review — this fires universally, not just in single-entity mode. So even with InteractiveSession, the captain wouldn't get to reject at the gate. The non-interactive `-p` approach exercises the same code path and gives structured JSONL logs (via LogParser) that are far more reliable for detecting shutdown messages than parsing raw terminal output. The only scenario requiring PTY would be captain rejection of a PASSED recommendation, which is a different bug and a different test.

**Test plan:**
- Estimated cost: ~$2-5 per run (haiku model, low effort, buggy implementation + rejection cycle)
- Complexity: Medium — reuses established test patterns (rejection-flow structure), main novelty is temporal shutdown window detection + feedback routing assertion
- E2E test required: Yes — verifying FO runtime behavior, not static contract text
- Risk: FO may not complete the full rejection cycle within budget; mitigate with generous budget cap ($5.00) and simple task

### Checklist

1. Review PTY test harness capabilities and existing E2E test patterns — DONE
2. Review existing test fixtures (especially rejection-flow) — DONE
3. Design the test fixture (workflow README + seed entity) — DONE
4. Design the test flow (what to send, what to assert) — DONE
5. Define how to detect premature shutdown (log inspection, team config, output scanning) — DONE
6. Define acceptance criteria with test plan — DONE

## Stage Report: implementation

### 1. Create test fixture at tests/fixtures/keepalive-pipeline/ — DONE

Created `tests/fixtures/keepalive-pipeline/` with:
- `README.md` — workflow definition with `backlog → implementation (worktree) → validation (worktree, fresh, feedback-to: implementation, gate) → done (terminal)`
- `keepalive-test-task.md` — seed entity at `status: backlog` with acceptance criteria for an `add(a, b)` function
- `math_ops.py` — deliberately buggy implementation (`return a - b`) to force validation rejection
- `tests/test_add.py` — test suite that will fail against the buggy implementation

### 2. Write E2E test at tests/test_feedback_keepalive.py with Tier 1 and Tier 2 assertions — DONE

Created `tests/test_feedback_keepalive.py` with:
- **Tier 1 assertion:** Temporal log scanning between implementation completion and validation dispatch — verifies no shutdown SendMessage targets the implementation agent during this window
- **Tier 2 assertion:** After REJECTED signal, verifies feedback routed via SendMessage to the kept-alive implementation agent (not via fresh Agent() dispatch)
- `scan_keepalive_events()` function walks JSONL log entries in order, tracking implementation dispatch, completion, validation dispatch, shutdown messages, rejection signals, and feedback routing method
- Falls back gracefully (SKIP) when pipeline doesn't progress far enough within budget

### 3. Test follows existing patterns (test_lib.py, LogParser, run_first_officer) — DONE

Uses `TestRunner`, `LogParser`, `create_test_project`, `setup_fixture`, `install_agents`, `run_first_officer`, `git_add_commit`, and `rejection_signal_present` from `scripts/test_lib.py`. Follows the same Phase 1/2/3 structure as `test_rejection_flow.py` and `test_reuse_dispatch.py`. Includes static template checks against `first-officer-shared-core.md`.

### 4. Test is runnable with standard invocation — DONE

Runnable via `unset CLAUDECODE && uv run tests/test_feedback_keepalive.py`. File is executable with `#!/usr/bin/env -S uv run` shebang. Supports `--model`, `--effort`, `--agent` flags consistent with other tests.

### 5. All changes committed on branch — DONE

All files committed on branch `spacedock-ensign/feedback-keepalive-e2e-test`.

## Stage Report: validation

### 1. Verify AC1: test file exists — DONE

`tests/test_feedback_keepalive.py` exists (14,356 bytes, executable). Confirmed via filesystem inspection.

### 2. Verify AC2: test uses test_lib.py infrastructure — DONE

Lines 18-22 import `LogParser`, `TestRunner`, `create_test_project`, `setup_fixture`, `install_agents`, `run_first_officer`, `git_add_commit`, and `rejection_signal_present` from `scripts/test_lib.py`. All imports verified working. Follows the same Phase 1/2/3 structure as `test_rejection_flow.py`.

### 3. Verify AC3: fixture exists with correct stage definitions — DONE

`tests/fixtures/keepalive-pipeline/` exists with:
- `README.md` — YAML frontmatter defines `validation` stage with `feedback-to: implementation`, `fresh: true`, `gate: true`, `worktree: true`. Pipeline is `backlog → implementation (worktree) → validation (worktree, fresh, feedback-to: implementation, gate) → done (terminal)`.
- `keepalive-test-task.md` — seed entity at `status: backlog` with acceptance criteria for `add(a, b)`.
- `math_ops.py` — deliberately buggy (`return a - b`), will force validation rejection.
- `tests/test_add.py` — test suite that fails against the buggy implementation. Syntactically valid.

### 4. Verify AC4: Tier 1 shutdown detection assertion present — DONE

`scan_keepalive_events()` (lines 42-156) walks JSONL entries in temporal order, tracking the window between `impl_completion_seen` and `validation_dispatch_seen`. During this window, any SendMessage whose `message` field matches `SHUTDOWN_PATTERN` (line 27-30: `shut\s*down|terminat|kill|stop|cancel.*agent`) is captured in `shutdown_before_validation`. Lines 268-275 assert `len(events["shutdown_before_validation"]) == 0` — failing the test if any shutdown messages are detected in the keepalive window.

### 5. Verify AC5: Tier 2 feedback routing assertion present — DONE

After `rejection_seen` is set (lines 85-86, 103-104), the scanner checks two things:
- `feedback_via_send_message` (lines 140-145): SendMessage to the implementation agent containing rejection/fix/feedback keywords → proves keepalive worked (PASS at line 300).
- `feedback_via_fresh_agent` (lines 120-122): fresh Agent() dispatch for implementation after rejection → proves keepalive failed (FAIL at line 302).
- Fallback at lines 304-315: if neither is detected, checks for any SendMessage to implementation agent; if none found, fails with "no feedback routing observed."

### 6. Verify AC6: test logic would catch premature shutdown — DONE

Two complementary detection paths:

**Path A (Tier 1):** If FO sends a shutdown SendMessage to the impl agent between completion and validation dispatch, `SHUTDOWN_PATTERN` catches it and the assertion at line 270 fails.

**Path B (Tier 2):** If the impl agent was killed (by any mechanism), the FO must dispatch a fresh Agent() for implementation after rejection. This is caught by `feedback_via_fresh_agent` (line 122) and reported as FAIL at line 302 ("keepalive failed — agent was killed and re-dispatched").

The tiers are complementary: Tier 1 catches explicit shutdown messages; Tier 2 catches the consequence of any shutdown (even non-message-based) by detecting whether feedback routing used SendMessage (agent alive) or fresh Agent dispatch (agent dead). If neither detection fires, the test still fails at line 315 ("no feedback routing observed"), so there is no silent pass.

**Minor note:** Tier 1's shutdown detection at line 134 does not filter by `to` field — it catches shutdown-like messages to ANY agent during the window, not just the implementation agent. In this simple 3-stage pipeline this is unlikely to cause false positives, since only the implementation agent exists during that window. Not a blocker.

### 7. Verify test is syntactically valid and runnable — DONE

- `python3 -c "import py_compile; py_compile.compile('tests/test_feedback_keepalive.py', doraise=True)"` — SYNTAX OK
- All imports resolve successfully (`test_lib` symbols verified)
- `python3 tests/test_feedback_keepalive.py --help` — runs, shows expected flags (`--runtime`, `--agent`, `--model`, `--effort`)
- Static checks against `first-officer-shared-core.md` verified: all three regex patterns (`keepalive rule`, `auto-bounce rule`, `feedback rejection flow`) match current shared-core content

### 8. Live E2E test execution (run 1, entity at backlog) — DONE

Ran `unset CLAUDECODE && uv run tests/test_feedback_keepalive.py` with entity starting at `status: backlog`:

- **Wallclock:** 230s, 112 assistant messages (claude-haiku-4-5-20251001), ~4.2M tokens
- **Phase 1 (setup):** PASS — status script runs, entity detected as dispatchable
- **Phase 2 (FO run):** FO dispatched 3 ensigns total: 2 implementation, 1 validation
- **Tier 1 (keepalive at transition):** PASS — no shutdown SendMessage detected between implementation completion and validation dispatch
- **Tier 2 (feedback routing):** SKIP — rejection not observed within budget
- **Static template checks:** 3/3 PASS

**Result: 8 passed, 0 failed (out of 8 checks) — PASS**

### 9. Live E2E test execution (run 2, entity pre-staged at implementation) — DONE

After fixture update (commit `73669c1`) pre-staged entity at `status: implementation` with completed stage report to skip the slow implementation phase and reach Tier 2.

Ran `unset CLAUDECODE && uv run tests/test_feedback_keepalive.py`:

- **Wallclock:** 184s, 67 assistant messages (claude-haiku-4-5-20251001)
- **Phase 1 (setup):** PASS — status script runs, entity detected as dispatchable
- **Phase 2 (FO run):** FO dispatched 2 ensigns: 0 implementation, 2 validation
- **Tier 1:** SKIP — no implementation agent was dispatched (FO correctly recognized implementation was already complete)
- **Tier 2:** FAIL — rejection detected, but no feedback routing observed (neither SendMessage nor fresh Agent dispatch)

**Result: 7 passed, 2 failed (out of 9 checks) — FAIL**

**Root cause analysis:**

The pre-staging optimization broke the test's core assumptions:

1. **FAIL: "FO dispatched Agent() for implementation stage"** (line 246) — The FO never dispatched an implementation agent because the entity's implementation stage was already complete. The test unconditionally requires `len(impl_dispatches) >= 1`.

2. **FAIL: "no feedback routing observed after rejection"** (line 316) — The keepalive scenario requires an implementation agent to exist so it can be kept alive and receive feedback. Since no implementation agent was dispatched, there's nothing to keep alive and no target for feedback routing. The FO detected REJECTED but had no implementation agent to SendMessage to.

**The fundamental problem:** The keepalive rule says "when dispatching validation with `feedback-to: implementation`, keep the implementation agent alive." Pre-staging at implementation-complete means no implementation agent is ever created. The test needs the full pipeline: implementation dispatch -> completion -> validation dispatch (keepalive window) -> rejection -> feedback routing to kept-alive agent.

**Needed fixes (for implementation agent):**

- Option A: Revert entity to `status: backlog` so the FO dispatches implementation first, then use a higher budget or smarter prompt to ensure the full rejection cycle completes.
- Option B: Have the test prompt explicitly instruct the FO to dispatch an implementation agent first (even for already-complete work), but this fights the FO's natural behavior.
- Option C: Start entity at `status: backlog` but use a minimal implementation task that completes fast, giving more budget for the rejection cycle.

### 10. Live E2E test execution (run 3, backlog with trivial task) — DONE

After fixture revert (commit `bb54762`), entity starts from backlog with trivial task.

Ran `unset CLAUDECODE && uv run tests/test_feedback_keepalive.py`:

- **Wallclock:** 228s, 132 assistant messages (claude-haiku-4-5-20251001)
- **Phase 1 (setup):** PASS — status script runs, entity detected as dispatchable
- **Phase 2 (FO run):** FO dispatched 3 ensigns: 2 implementation, 1 validation
- **Tier 1:** PASS — no shutdown detected between implementation completion and validation dispatch
- **Tier 2:** FAIL — 1 failure: "no feedback routing observed after rejection"

**Result: 9 passed, 1 failed (out of 10 checks) — FAIL**

**Root cause analysis — two issues:**

**Issue 1: Implementation ensign fixed the bug.** The FO's log shows: "The implementation agent created `greeting.txt` with the correct content and fixed the add function so tests pass." The implementation ensign proactively fixed `math_ops.py` (changing `a - b` to `a + b`), so validation found no issues and recommended PASSED. No rejection occurred, so the feedback routing path was never exercised.

**Issue 2: False positive rejection detection.** Despite no actual rejection, `scan_keepalive_events()` set `rejection_seen: True` because the FO's final summary narrative contained the hypothetical text: "If validation had recommended **REJECTED**, the first officer would have..." The regex `r"REJECTED|recommend reject"` matched this hypothetical narrative, causing the test to enter the Tier 2 assertion path instead of the SKIP path. This turned a harmless SKIP into a FAIL.

**Needed fixes:**

1. **Fixture bug must survive implementation.** The buggy `math_ops.py` is too easily fixed by the ensign. Options:
   - Make the bug less obvious (e.g., off-by-one in a complex function rather than `a - b` vs `a + b`)
   - Separate the buggy code from the implementation task so the ensign doesn't touch it
   - Pre-commit the buggy file and instruct the entity NOT to modify `math_ops.py` (only create `greeting.txt`)

2. **Rejection detection needs tighter matching.** The `rejection_pattern` in `scan_keepalive_events()` should avoid matching hypothetical/narrative text. Options:
   - Only count rejection from `tool_result` entries (actual agent results), not from FO narrative text
   - Require rejection pattern to appear at sentence/line start, not embedded in hypothetical clauses
   - Use `rejection_signal_present()` from test_lib.py as the authoritative rejection check and skip Tier 2 assertions when `scan_keepalive_events()` doesn't independently confirm rejection from structured log data

### 11. Recommendation: REJECTED

The test fails 1/10 checks on live execution (run 3). Two root causes: (1) the implementation ensign proactively fixes the buggy code, preventing the rejection that Tier 2 needs; (2) the rejection detection regex produces a false positive from the FO's hypothetical narrative, converting a harmless SKIP into a FAIL.

### Checklist

1. Verify AC1: test file exists — DONE
2. Verify AC2: test uses test_lib.py infrastructure — DONE
3. Verify AC3: fixture exists with correct stage definitions — DONE
4. Verify AC4: Tier 1 shutdown detection assertion present — DONE
5. Verify AC5: Tier 2 feedback routing assertion present — DONE
6. Verify AC6: test logic would catch premature shutdown — DONE
7. Verify test is syntactically valid and runnable — DONE
8. Live E2E test execution (run 1, backlog start) — DONE (8/8 passed, Tier 2 SKIPped)
9. Live E2E test execution (run 2, pre-staged) — FAILED (7/9 passed, 2 failed — no impl agent dispatched)
10. Live E2E test execution (run 3, backlog with trivial task) — FAILED (9/10 passed, 1 failed — false positive rejection + ensign fixed bug)
11. REJECTED — fixture bug doesn't survive implementation; rejection detection has false positive
