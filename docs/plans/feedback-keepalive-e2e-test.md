---
id: 106
title: E2E test for feedback-to keepalive — FO must not kill implementation agent during validation
status: implementation
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
