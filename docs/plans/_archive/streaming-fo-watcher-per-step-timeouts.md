---
id: 173
title: "Streaming FO watcher with per-step timeouts and progressive assertions"
status: done
source: "CL observation during 2026-04-16 session — PR #107 CI (claude-live-opus) took 24m38s to surface a test failure that could have failed in ~120s with per-step timeouts. Post-hoc log parsing hides where in the sequence things stalled."
started: 2026-04-16T21:55:52Z
completed: 2026-04-16T22:44:34Z
verdict: PASSED
score: 0.75
worktree: 
issue:
pr: #109
mod-block: 
archived: 2026-04-16T22:44:40Z
---

### Feedback Cycles

**Cycle 1 (2026-04-16, captain rejection post-smoke)**

Validation reported ACCEPTED. Captain overrode based on live-smoke evidence from `test_standing_teammate_spawn.py::test_standing_teammate_spawns_and_roundtrips` at opus-low (local, worktree-HEAD):

- `StepTimeout` fired correctly at milestone 4 (`SendMessage to echo-agent observed`) with the right label.
- Test result: FAILED (correct assertion).
- FO subprocess exited with SIGTERM (exit 143) — context manager did kill it.
- **But wallclock was 600.16s**, not the ~180s promised by the feature. FO log `Wallclock: 160s` ended at ~T+160 when the FO went idle; pytest total hit the 600s hard cap.

**Root cause:** `run_first_officer_streaming.__exit__` uses `proc.wait(timeout=max(remaining, 1))` where `remaining = hard_cap_s - elapsed` regardless of whether exit is normal or exception-driven. On exception exit (StepTimeout / StepFailure / any test-body exception), the proc is typically hung (e.g., claude-p idle after FO work completes). Waiting `hard_cap - elapsed` for it to exit naturally wastes the rest of the budget. The terminate+kill escalation only fires after that wait expires.

**Fix requested:** on exception-driven exit, use a short fixed grace period (5-10s) before escalating to terminate → kill. Distinguish the two paths in `__exit__`:

```python
def __exit__(self, exc_type, exc, tb):
    if exc is not None:
        grace_s = 5  # abnormal exit — decisions already made, kill fast
    else:
        grace_s = max(hard_cap_s - elapsed, 1)  # normal exit path
    # existing wait/terminate/kill escalation using grace_s
```

**Test coverage required:** extend AC-6/7 (currently cover cleanup of lingering proc on normal with-exit and hard-cap) with a new AC: "context manager terminates within ~10s when an exception propagates through the `with` block." Offline unit test — use `sh -c 'sleep 60'` with `hard_cap_s=600`, raise an exception inside the with, assert total wallclock `< 15s`.

**Reject-to target:** implementation. Routing fix instructions to the live implementation ensign.

## Problem Statement

Today's live E2E harness runs `claude -p --output-format stream-json --verbose` as a subprocess, writes all stream events to `fo-log.jsonl`, waits up to 600s for the process to exit, then parses the full log post-hoc with `LogParser`. This has three concrete costs:

- **Slow failure signal.** A test that fails because the FO never reached milestone N still burns the full 600s timeout before pytest gets the assertion. On `claude-live-opus` in PR #107, the `test_standing_teammate_spawns_and_roundtrips` failure took 24m38s of CI time to surface what is a ~120s failure mode (ensign never sent the `SendMessage`).

- **No sequencing in assertions.** Post-hoc `LogParser` asserts "this tool call appears somewhere in the log", not "this tool call appeared before that tool call within K seconds". Tests cannot distinguish "hung before step 3" from "completed all 5 steps but one was wrong", so diagnostic work is log-archaeology.

- **Timing is tangled.** The 600s timeout is fixed regardless of model. `claude-opus-4-7` is slower per turn than haiku; a budget that fits haiku work comfortably may be too tight for opus. Worse, there is no way to distinguish "opus is slow but progressing" from "opus is stuck" until the timer trips.

## Observed impact (2026-04-16 session)

PR #107 CI surfaced the `test_standing_teammate_spawns_and_roundtrips` failure on `claude-live-opus` after 24m38s. The actual failure was observable within ~120s: the ensign never emitted a `SendMessage` to `echo-agent`. A streaming watcher with per-step timeouts would have failed fast, named the exact milestone missed, and freed CI minutes for other jobs.

## Proposed design

Add an `FOStreamWatcher` class to `scripts/test_lib.py` that tails the stream-json log while the FO subprocess runs. Each expected milestone carries its own timeout budget:

```python
class FOStreamWatcher:
    def __init__(self, log_path, proc): ...
    def expect(self, predicate, timeout_s, label) -> dict:
        """Tail log_path until predicate(entry) returns True or timeout.
        Raises StepTimeout on timeout, StepFailure if proc exits first."""
    def expect_exit(self, timeout_s) -> int:
        """Wait for the FO subprocess to exit within timeout_s."""
```

Usage rewrites `test_standing_teammate_spawns_and_roundtrips` from post-hoc `LogParser` assertions into a sequence of `expect()` calls:

```python
w.expect(lambda e: tool_use_matches(e, "Bash", command_contains="spawn-standing"),
         timeout_s=30, label="spawn-standing invoked")
w.expect(lambda e: tool_use_matches(e, "Agent", input_name="echo-agent"),
         timeout_s=60, label="echo-agent spawned")
w.expect(lambda e: tool_use_matches(e, "SendMessage", input_to="echo-agent"),
         timeout_s=120, label="ensign routed to echo-agent")
w.expect(lambda e: entry_contains_text(e, r"ECHO:\s*ping"),
         timeout_s=180, label="ECHO reply received")
w.expect_exit(timeout_s=60)
```

Failure semantics become actionable:

- Low-effort opus → fails at milestone 3 in ~120s ("ensign never `SendMessage`'d echo-agent")
- High-effort opus → passes 1-3, fails at milestone 4 in ~180s ("`SendMessage` fired but no ECHO reply")
- Hung FO → fails at whichever milestone is stuck, total wait 30-180s not 600s

## Open questions for ideation

- Where does the watcher live? `scripts/test_lib.py` (alongside `LogParser`) or a new module?
- Should `expect()` return the matched entry for follow-up assertions (e.g., extract model name from the matched `Agent()` call), or just return boolean?
- Polling interval: 0.2s is cheap but adds up across ~10 milestones per test. Is inotify/watchdog worth the dependency?
- How are `expect()`-based tests marked in pytest? A new fixture `fo_watcher` that wraps `run_first_officer` and returns a watcher handle?
- Is `LogParser` kept for the final assertion phase (run after `expect_exit`), or do all assertions move into streaming form?
- Migration scope: rewrite `test_standing_teammate_spawn.py` and `test_per_stage_model.py` first, leave other tests on post-hoc parsing? Full-cohort migration is out of scope.
- Is there value in a "weak" mode where `expect()` does not fail on timeout but logs — useful for bisecting which milestone flakes under different conditions without aborting the whole test?

## Out of Scope

- Rewriting all live E2E tests to use the watcher. This task ships the watcher plus two pilot migrations (`test_standing_teammate_spawn.py`, `test_claude_per_stage_model.py`). Other tests migrate later on their own cadence.
- Removing `LogParser`. The post-hoc parser remains useful for final-state assertions after exit.
- Changes to the `claude -p` invocation shape. The watcher reads the existing `--output-format stream-json` output.
- Codex runtime equivalents. Codex tests have their own `CodexLogParser`; a matching watcher is follow-up. The watcher targets the Claude stream-json format only.
- Replacing the 600s overall budget. The per-step timeouts are additive safety; `expect_exit(timeout_s=...)` still backstops the total run.

## Decision

Per-open-question resolutions (each open question from the original design section, answered concretely):

1. **Where does the watcher live?** Add to `scripts/test_lib.py` alongside `LogParser`. It is small (~150 lines), shares no state with `LogParser` beyond the log format contract, and every live E2E already imports from `test_lib`. A new module would force every migrated test to add a second import for marginal gain.

2. **`expect()` return shape.** Return the matched entry (full stream-json dict) on success; raise `StepTimeout` on timeout; raise `StepFailure` on early subprocess exit before match. Returning the entry lets callers extract data (e.g. `model = entry["message"]["model"]`) without a second pass. Boolean-only would force a post-hoc `LogParser` re-scan that defeats the point of streaming.

3. **Polling mechanism.** Sleep-poll at 0.2s. No watchdog/inotify dependency. Rationale: (a) `fo-log.jsonl` is appended ~1-10 lines/second during active FO work, not thousands — polling overhead is negligible; (b) watchdog adds a cross-platform dependency for microseconds of latency we do not need; (c) the watcher must also poll `proc.poll()` for early-exit detection, so we are already in a poll loop.

4. **Pytest fixture shape.** New fixture `fo_watcher` in `tests/conftest.py` that yields a builder callable. The callable takes the same arguments as `run_first_officer` but returns `(watcher, completion_handle)` instead of `int`. The watcher runs in the test body; `completion_handle.wait()` or `watcher.expect_exit()` finalizes the run. The existing `run_first_officer` stays put for non-migrated tests.

5. **Relationship to `LogParser`.** Composable. `LogParser(fo_log)` still works on the same log file after `expect_exit()` for final-state assertions (stats extraction, archive checks, multi-entry aggregation). The watcher does not re-implement `assistant_messages()` or `agent_calls()`; it iterates raw entries and delegates matching to caller predicates.

6. **Weak mode.** Not in v1. YAGNI — no caller has asked for it, and bisection can be done by temporarily swapping `expect()` for a try/except log-and-continue in a debug branch. Defer until a real use case appears.

## API

The watcher and helpers live in `scripts/test_lib.py`. New public surface:

```python
class StepTimeout(AssertionError):
    """Expected log entry did not appear within the per-step budget."""

class StepFailure(AssertionError):
    """FO subprocess exited before the expected log entry appeared."""


class FOStreamWatcher:
    """Tails an FO stream-json log and asserts per-step progress.

    The watcher owns a read offset into `log_path` plus a handle to the
    live `proc`. `expect()` polls for new entries at 0.2s intervals,
    invokes the caller-supplied predicate on each, and returns the first
    matching entry. On per-step timeout it raises StepTimeout with a
    label; on early subprocess exit it raises StepFailure with exit code
    and a tail of the log.
    """

    POLL_INTERVAL_S = 0.2

    def __init__(self, log_path: Path, proc: subprocess.Popen):
        self.log_path = Path(log_path)
        self.proc = proc
        self._fh = None            # opened lazily on first expect()
        self._buffer = ""          # carry-over for partial trailing line

    def expect(
        self,
        predicate: Callable[[dict], bool],
        timeout_s: float,
        label: str,
    ) -> dict:
        """Return the first log entry where predicate(entry) is True.

        Raises StepTimeout after timeout_s wallclock.
        Raises StepFailure if proc.poll() returns non-None before match.
        """

    def expect_exit(self, timeout_s: float) -> int:
        """Wait up to timeout_s for the FO subprocess to exit. Returns exit code.

        Drains remaining stream-json output into the log file before returning.
        Raises StepTimeout on timeout (after terminating the process).
        """


# Predicate helpers — small, composable, do not hide the predicate shape.

def tool_use_matches(
    entry: dict,
    tool_name: str,
    **input_contains: str,
) -> bool:
    """True when entry is an assistant tool_use for tool_name whose input
    contains all `key=substring` pairs as substrings of input[key]."""

def entry_contains_text(entry: dict, pattern: str) -> bool:
    """True when entry is an assistant text block or a user tool_result
    whose text matches the regex pattern."""

def assistant_model_equals(entry: dict, prefix: str) -> bool:
    """True when entry is an assistant message whose message.model starts with prefix."""
```

Predicate helpers ship with the watcher because every migrated test will reach for them; duplicating the tool-use shape check across five tests is the kind of repetition Rule-#1 calls out. Helpers accept a single entry (no list walks) so they compose cleanly inside `lambda e: tool_use_matches(e, "Bash", command="spawn-standing")`.

## Subprocess lifecycle

This is the load-bearing integration decision. Today `run_first_officer` does:

```python
result = subprocess.run(cmd, stdout=log_file, stderr=STDOUT, timeout=600, ...)
return result.returncode
```

That blocks until exit. A streaming watcher must observe the log while the process still runs. Options considered:

- **A: Split into `run_first_officer_async` returning `(proc, log_path)` and let the test drive a watcher manually.** Clean but leaks subprocess plumbing (env selection, cwd, stats extraction) into every test.
- **B: Make `run_first_officer` launch via `Popen` unconditionally, accept an optional `watcher` callable that gets `(proc, log_path)` and returns when done.** Keeps one entry point but couples the watcher closure to the runner.
- **C (chosen): Add `run_first_officer_streaming` sibling that yields a context manager.** Existing `run_first_officer` is untouched. The sibling does the Popen dance, yields a live `FOStreamWatcher`, and on exit drains output + extracts stats + enforces the 600s hard cap.

Chosen flow (option C):

```python
@contextmanager
def run_first_officer_streaming(
    runner: TestRunner,
    prompt: str,
    agent_id: str = "spacedock:first-officer",
    extra_args: list[str] | None = None,
    log_name: str = "fo-log.jsonl",
    hard_cap_s: int = 600,
) -> Iterator[FOStreamWatcher]:
    """Launch the FO as a live subprocess and yield a watcher.

    The context manager guarantees:
    - log_path exists and is opened for writing before yield
    - proc is Popen'd with stdout -> log_path, stderr -> STDOUT
    - on normal exit: wait for proc (up to hard_cap_s), extract_stats
    - on exception inside `with`: terminate proc, drain log, reraise
    - on caller forgetting to call expect_exit: enforce hard_cap_s wait
      at context exit, terminate+kill if exceeded
    """
```

Implementation sketch:

```python
with open(log_path, "w") as log_file:
    proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=runner.test_project_dir,
        env=env,
    )
    watcher = FOStreamWatcher(log_path, proc)
    try:
        yield watcher
    finally:
        if proc.poll() is None:
            remaining = hard_cap_s - (time.monotonic() - start)
            try:
                proc.wait(timeout=max(remaining, 1))
            except subprocess.TimeoutExpired:
                proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        extract_stats(log_path, "fo", runner.log_dir)
```

The watcher opens `log_path` for reading independently of the write handle (POSIX allows this — same file, separate fds). Reads use `tell()`/`seek()` to track offset across calls. Windows would need `O_SHARE_DELETE` semantics, but Spacedock live E2E is POSIX-only, matching the existing `select` usage in `run_codex_first_officer`.

Early-exit detection: inside `expect()`, each poll iteration checks `self.proc.poll() is not None` **after** draining available log lines. Order matters — the process may have just exited and written the expected entry in its final flush. If poll is non-None and predicate still unmatched, raise `StepFailure` with exit code and last 50 lines of log.

`expect_exit()` stops polling for matches, calls `proc.wait(timeout_s)`, drains any final log lines, and returns the exit code. On timeout it terminates the process before re-raising.

## Pilot migrations

Line-by-line before/after sketches for both pilot tests. Each migration removes post-hoc `LogParser` assertions in favor of progressive `expect()` calls, keeping the final aggregate assertion (e.g. "at least one ensign dispatched") as a post-exit `LogParser` pass.

### `test_standing_teammate_spawns_and_roundtrips`

Before (current, lines 50-117): single `run_first_officer` call, then `LogParser`-driven assertions on the completed log. Fails only after the full 600s timeout when a milestone is missed.

After:

```python
def test_standing_teammate_spawns_and_roundtrips(test_project, effort):
    t = test_project
    setup_fixture(t, "standing-teammate", "standing-teammate")
    install_agents(t, include_ensign=True)
    git_add_commit(t.test_project_dir, "setup: standing-teammate fixture")

    abs_workflow = t.test_project_dir / "standing-teammate"
    prompt = (
        f"Process the workflow at {abs_workflow}/ to terminal completion. "
        "During startup, spawn every standing teammate ... [unchanged]"
    )

    with run_first_officer_streaming(
        t, prompt,
        extra_args=["--model", "opus", "--effort", effort, "--max-budget-usd", "2.00"],
    ) as w:
        w.expect(
            lambda e: tool_use_matches(e, "Bash", command="spawn-standing"),
            timeout_s=60, label="claude-team spawn-standing invoked",
        )
        w.expect(
            lambda e: tool_use_matches(e, "Agent", name="echo-agent"),
            timeout_s=90, label="echo-agent Agent() dispatched",
        )
        ensign_dispatch = w.expect(
            lambda e: tool_use_matches(e, "Agent") and
                      "ensign" in (e.get("message", {}).get("content", [{}])[0].get("input", {}).get("name", "")),
            timeout_s=180, label="ensign Agent() dispatched",
        )
        # AC-14: standing-teammates section is visible IN the ensign prompt
        # at dispatch time. Assert on the matched entry, no second scan.
        ensign_prompt = _agent_prompt_from_entry(ensign_dispatch)
        assert "### Standing teammates available in your team" in ensign_prompt
        assert "echo-agent" in ensign_prompt

        w.expect(
            lambda e: tool_use_matches(e, "SendMessage", to="echo-agent"),
            timeout_s=180, label="SendMessage to echo-agent observed",
        )
        w.expect(
            lambda e: entry_contains_text(e, r"ECHO:\s*ping"),
            timeout_s=180, label="ECHO: ping reply received",
        )
        exit_code = w.expect_exit(timeout_s=120)

    assert exit_code == 0
    # Final aggregate: post-hoc parser still available for stats/counts.
    log = LogParser(t.log_dir / "fo-log.jsonl")
    assert any(c.get("name") == "echo-agent" for c in log.agent_calls())
```

Failure map: low-effort opus fails at milestone 4 (SendMessage) in ~180s, labeled "SendMessage to echo-agent observed". Today's 24m38s CI failure becomes a ~90-180s failure with the exact missed step in the message.

### `test_per_stage_model_haiku_propagates`

Before (current, lines 52-109): `run_first_officer` returns, then `_assistant_models()` scans the full log for haiku model stamps. Passes/fails at the 600s mark or whenever the FO exits.

After:

```python
def test_per_stage_model_haiku_propagates(test_project, effort):
    t = test_project
    setup_fixture(t, "per-stage-model", "per-stage-model")
    install_agents(t, include_ensign=True)
    git_add_commit(t.test_project_dir, "setup: per-stage-model fixture")

    abs_workflow = t.test_project_dir / "per-stage-model"
    prompt = (
        f"Process all tasks through the workflow at {abs_workflow}/ to terminal "
        "completion. ... [unchanged]"
    )

    with run_first_officer_streaming(
        t, prompt,
        extra_args=["--model", "opus", "--effort", effort, "--max-budget-usd", "2.00"],
    ) as w:
        w.expect(
            lambda e: tool_use_matches(e, "Agent") and
                      "ensign" in _agent_name_from_entry(e).lower(),
            timeout_s=120, label="ensign Agent() dispatched",
        )
        # The hypothesis under test: the dispatched ensign stamps haiku on
        # its assistant messages. Fail fast if no haiku message arrives in
        # the next 120s after dispatch, even if opus messages keep coming.
        w.expect(
            lambda e: assistant_model_equals(e, "claude-haiku-"),
            timeout_s=120, label="haiku assistant message observed",
        )
        w.expect_exit(timeout_s=300)

    # Keep xfail marker until #171 is fixed.
```

Failure map: today the xfail surfaces after the full run. With per-step timeouts, the xfail becomes observable in ~240s (dispatch + haiku-wait), not 600s. When #171 lands, the assertion converts from xfail to expected-pass immediately.

## Acceptance Criteria

Each AC lists test strategy (offline unit vs live E2E) and rationale.

1. **`FOStreamWatcher.expect()` returns the matched entry dict on success.** Test strategy: offline unit test in `tests/test_fo_stream_watcher.py` that writes a JSONL log out-of-band, constructs the watcher with a fake `proc` (stub with `.poll()` returning None), and asserts the returned entry. No E2E needed — pure logic.

2. **`expect()` raises `StepTimeout` with the label when the predicate never matches.** Test strategy: offline unit test with a log containing only non-matching entries; assert the raised exception's `label` attribute and message include the step label.

3. **`expect()` raises `StepFailure` when the subprocess exits before a match.** Test strategy: offline unit test with a fake proc whose `.poll()` transitions from None to 1 mid-test; assert exit code and log-tail appear in the failure message.

4. **Polling handles partial trailing lines (line written but newline not yet flushed).** Test strategy: offline unit test that writes the first half of a line, polls once (should not match), writes the second half + newline, polls again (should match). Guards against a real-world stream-json flush pattern.

5. **`run_first_officer_streaming` context manager drains the log and runs `extract_stats` on exit.** Test strategy: offline unit test using a trivial shell subprocess (`sh -c "echo '{}'; sleep 0.1"`) as a stand-in for the claude CLI. Asserts the stats file appears under `runner.log_dir`. No real claude call needed.

6. **`run_first_officer_streaming` terminates the subprocess if the test exits the `with` block without calling `expect_exit`.** Test strategy: offline unit test — launch `sh -c "sleep 30"`, exit the `with` block after 1s, assert the process is no longer alive.

7. **`run_first_officer_streaming` enforces the 600s hard cap.** Test strategy: offline unit test with `hard_cap_s=1` against `sh -c "sleep 10"`; assert the context manager kills the process and raises (or returns) within ~2s.

8. **`tool_use_matches` helper correctly identifies Bash/Agent/SendMessage entries with input substring matches.** Test strategy: offline unit test with synthetic stream-json entries covering each tool type.

9. **Pilot migration: `test_standing_teammate_spawns_and_roundtrips` uses the watcher and still covers AC-12/AC-14 assertions from #162.** Test strategy: LIVE E2E — this test is already in the `live_claude` + `teams_mode` matrix. Run it against opus-4-7 low-effort and confirm (a) it still passes when the FO behaves, (b) it fails in under 180s when the FO skips the SendMessage step (verify by temporarily patching the fixture to disable the ensign instruction).

10. **Pilot migration: `test_per_stage_model_haiku_propagates` uses the watcher and keeps the xfail marker.** Test strategy: LIVE E2E — confirm xfail still surfaces on opus-4-7 low-effort, in ≤300s wallclock instead of 600s. When #171 is fixed, the test flips to xpass.

11. **Non-migrated live E2E tests continue to pass unchanged.** Test strategy: offline — confirm the diff to `test_lib.py` adds surface area without modifying `run_first_officer`, `LogParser`, or any other shared function. `make test-static` green; spot-check one unmigrated live test collects.

12. **Watcher failure messages include a log tail (last ~20 lines) and the step label.** Test strategy: offline unit test that asserts error message content. This is the user-facing payoff of the whole task — a bad failure message defeats the purpose of per-step timeouts.

13. **Context manager terminates within ~10s when an exception propagates through the `with` block** (added cycle 1). On exception-driven exit — `StepTimeout`, `StepFailure`, or any test-body assertion — the subprocess must be killed via a short fixed grace period (5s) before terminate+kill escalation, not by waiting out the remainder of `hard_cap_s`. Test strategy: offline unit test — launch `sh -c 'sleep 60'` with `hard_cap_s=600`, raise an exception inside the `with`, assert total wallclock `< 15s`. Reuses the `_REAL_POPEN` monkeypatch pattern already in `tests/test_fo_stream_watcher.py`.

## Test Plan

Offline unit tests (cheap, always run in CI):
- New file `tests/test_fo_stream_watcher.py`. Covers ACs 1-8, 11, 12, 13. Uses `subprocess.Popen` against `sh -c` for subprocess plumbing tests; no claude calls. Runs in ~12 seconds total (AC-13's 5s grace + ~7s from the other tests).

Live E2E tests (expensive, gated by `live_claude` marker):
- Covers ACs 9-10. Two tests, both already in the live-claude matrix. Net wallclock impact on a green CI run: unchanged (tests pass in ~3-5 min whether watcher-instrumented or not). Net wallclock impact on a red CI run: 24m+ saved per failure (the actual motivation).
- To validate "fails fast" behavior (AC-9), the reviewer or pilot temporarily patches the standing-teammate fixture's task body to drop the ensign SendMessage instruction, runs the test, and confirms StepTimeout fires at milestone 4 within 180s. Revert the patch after the one-shot validation. This is a manual verification step, not a committed test.

Risk-proportional rigor:
- The subprocess lifecycle is the highest-risk piece (zombie processes, hung fds, log-file descriptor races). AC-5/6/7 are offline tests with real subprocesses that exercise the failure modes.
- The `_fh`/offset/partial-line logic is the second-highest risk (data loss would cause false timeouts). AC-4 specifically targets partial-line handling.
- Predicate helpers are lowest risk but most called — AC-8 covers them unit-level.

E2E needed: yes, but only for the two pilots (ACs 9-10). Everything else is offline-testable.

## Stage Report

1. Read the full entity body — DONE. Problem statement, observed impact, proposed design, open questions, and out-of-scope list reviewed.
2. Read `scripts/test_lib.py` — DONE. Traced `run_first_officer` (blocking `subprocess.run` with 600s timeout, writes stream-json to `fo-log.jsonl`, extracts stats on return), `LogParser` (lazy JSONL parse + `assistant_messages`/`agent_calls`/`tool_calls`/`fo_texts` accessors over the completed log), and the `_isolated_claude_env`/`_clean_env` plumbing each subprocess needs. Noted `run_codex_first_officer`'s non-blocking `Popen` + `select` loop as prior art in the same file.
3. Read `tests/test_standing_teammate_spawn.py` and `tests/test_claude_per_stage_model.py` — DONE. Identified convertible assertions: standing-teammate's five milestones (Bash spawn-standing, Agent echo-agent, SendMessage to echo-agent, ECHO ping reply, final ensign dispatch with standing-teammates section) all fit `expect()` calls; per-stage-model's single haiku-stamp assertion converts to one `expect()` after the ensign dispatch. The AC-14 prompt-section assertion stays on the matched entry (no second scan needed). Final `LogParser` aggregate assertions stay post-exit.
4. Design the `FOStreamWatcher` API — DONE. All seven open questions (location, return shape, polling, fixture shape, LogParser relationship, migration scope, weak mode) resolved under `## Decision`. Full signatures + predicate helpers captured under `## API`.
5. Specify the subprocess-lifecycle integration — DONE. Chose option C: a new `run_first_officer_streaming` context manager that does `Popen` + yields a watcher. `run_first_officer` stays untouched. End-to-end flow, early-exit detection order (drain log before checking `proc.poll()`), and hard-cap enforcement at context exit documented under `## Subprocess lifecycle`. POSIX-only design noted (matches existing `run_codex_first_officer`).
6. Specify the pilot-migration diffs — DONE. Before/after sketches for both tests captured under `## Pilot migrations` with concrete `expect()` labels, timeouts, and the failure-map showing how today's 24m38s failure becomes ~90-180s.
7. Produce acceptance criteria with test strategy per item — DONE. 12 ACs under `## Acceptance Criteria` — ACs 1-8, 11, 12 are offline unit tests; ACs 9-10 are live E2E on the existing two tests. Risk-proportional test plan under `## Test Plan` identifies subprocess lifecycle and partial-line handling as the two highest-risk pieces and maps ACs to them.
8. Update the entity body with ideation outputs — DONE. Added `## Decision`, `## API`, `## Subprocess lifecycle`, `## Pilot migrations`, `## Acceptance Criteria`, `## Test Plan` sections. Original `## Problem Statement`, `## Observed impact`, `## Proposed design`, `## Open questions for ideation`, and `## Out of Scope` sections left intact (decision section explicitly resolves the open questions rather than deleting them).
9. Append `## Stage Report` — DONE (this section).

Recommendation for ideation gate review: **advance to implementation**. The design addresses a real CI pain point (24m38s → ~180s failure signal, measured on PR #107). Subprocess lifecycle is scoped to a new context-manager entry point that does not touch existing working code. 10 of 12 ACs are offline-testable, keeping rigor without a live-budget explosion. The two live ACs reuse tests already in the matrix. The only caveat I'd flag for staff review: AC-9's "fails fast" verification relies on a manual fixture patch (not a committed test) — if the reviewer wants that automated, it becomes a 13th AC covering a fixture-variant live test and adds ~3 minutes of CI per run. My recommendation is to keep the manual verification in v1 and only automate if a regression ships.

## Stage Report (implementation)

1. Read the ideation outputs (Decision, API, Subprocess lifecycle, Pilot migrations, ACs 1-12, Test Plan) — DONE. Treated ACs 1-12 as the implementation spec.
2. Implement `FOStreamWatcher` + `StepTimeout`/`StepFailure` + predicate helpers — DONE. `scripts/test_lib.py` additions: class with `POLL_INTERVAL_S=0.2`, `_buffer` attribute for partial-line carry-over, `_drain_entries()` + `_log_tail()` helpers, `expect()` with drain-before-poll ordering, `expect_exit()` with terminate-then-kill escalation; exception classes carry `.label` (and `.exit_code` on `StepFailure`); helpers `tool_use_matches`, `entry_contains_text`, `assistant_model_equals`. Commit `8438068b`.
3. Implement `run_first_officer_streaming` context manager — DONE. `@contextlib.contextmanager` sibling of `run_first_officer`. Opens log file, `subprocess.Popen` with stdout→log, yields watcher, enforces `hard_cap_s` with terminate+kill escalation on context exit, runs `extract_stats` in `finally`. `run_first_officer` untouched. Commit `df2a7f67`.
4. Write offline unit tests in `tests/test_fo_stream_watcher.py` — DONE. 12 tests covering ACs 1-8, 11, 12. Docstrings cite the AC number. Plumbing tests use `_REAL_POPEN` + `sh -c` to avoid monkeypatch recursion. Runs in 7.31s (under the 10s budget). Commit `8fa841e0`.
5. Migrate `test_standing_teammate_spawns_and_roundtrips` — DONE. Five `expect()` calls (spawn-standing 60s, echo-agent dispatch 120s, ensign dispatch 240s + AC-14 prompt-section check on matched entry, SendMessage 240s, ECHO reply 240s) then `expect_exit(240)`, then final `LogParser` aggregate check for the echo-agent call count. Markers preserved. Commit `fc426716`.
6. Migrate `test_per_stage_model_haiku_propagates` — DONE. Two `expect()` calls (ensign dispatch 180s, haiku assistant message 240s) then `expect_exit(300)`. `xfail(strict=False)` + `live_claude` markers preserved. Commit `362ba4f4`.
7. Run `make test-static` — DONE. **425 passed, 22 deselected (live gated), 10 subtests passed in 17.05s.** New offline tests picked up automatically via `tests/` glob.
8. Verify non-migrated default path — DONE. `python3 -c 'from test_lib import run_first_officer, LogParser, FOStreamWatcher, run_first_officer_streaming'` succeeds; `tests/test_gate_guardrail.py` still collects (1 test) without modification. AC-11 satisfied: `run_first_officer` + `LogParser` are untouched, only additive surface.
9. Focused commits — DONE. Six commits on `spacedock-ensign/streaming-fo-watcher-per-step-timeouts`: (i) `8438068b` watcher+helpers+exceptions, (ii) `df2a7f67` streaming context manager, (iii) `8fa841e0` offline unit tests, (iv) `fc426716` standing-teammate migration, (v) `362ba4f4` per-stage-model migration, (vi) this stage report.
10. Stage Report — DONE (this section).

AC-9's fails-fast live verification is a **manual** step per the ideation agreement: reviewer temporarily patches the standing-teammate fixture to drop the ensign SendMessage instruction, runs the live test under `make test-live-claude-opus`, and confirms `StepTimeout` fires at the `"SendMessage to echo-agent observed"` label in <4 minutes. Not committed as an automated test.

### Summary

Shipped `FOStreamWatcher` + `run_first_officer_streaming` + three predicate helpers + two `StepTimeout`/`StepFailure` exception classes in `scripts/test_lib.py` with 12 offline unit tests (all green in 7.31s). Migrated both pilot tests to progressive `expect()` sequences with per-step timeouts (60-240s each) replacing the 600s post-hoc wait. `make test-static` green (425/425). `run_first_officer` and `LogParser` untouched — all non-migrated live tests continue to work unchanged. Recommendation: advance to **validation**.

## Stage Report (validation)

### Inputs verified

1. Read the full entity (problem statement, decision, API, subprocess lifecycle, pilot migrations, ACs 1-12, test plan, implementation stage report) — DONE.
2. Inspected the six commits on `spacedock-ensign/streaming-fo-watcher-per-step-timeouts`: `8438068b` watcher+helpers+exceptions (`scripts/test_lib.py` only), `df2a7f67` streaming context manager (`scripts/test_lib.py` only), `8fa841e0` offline unit tests (`tests/test_fo_stream_watcher.py` only), `fc426716` standing-teammate migration (`tests/test_standing_teammate_spawn.py` only), `362ba4f4` per-stage-model migration (`tests/test_claude_per_stage_model.py` only), `f932f609` implementation Stage Report (entity file only). **No out-of-scope edits.** DONE.
3. `git diff main...HEAD -- scripts/test_lib.py` shows +317/-1 where the single deletion is the `Callable` import line (replaced by `Callable, Iterator`). `run_first_officer` and `LogParser` public surface are untouched — confirmed by full-file read at `scripts/test_lib.py:1-240` and `scripts/test_lib.py:735-812`.

### `make test-static`

- Ran from the worktree root.
- Result: **`425 passed, 22 deselected, 10 subtests passed in 17.74s`**. Matches the implementation-report count (425). PASS.
- New offline suite `tests/test_fo_stream_watcher.py` ran verbosely in isolation: **12 passed in 7.30s**.

### Per-AC verdicts

1. **AC-1 (`expect()` returns matched entry dict)** — PASSED. `scripts/test_lib.py:1145` and `:1153` both `return entry`. Test `test_expect_returns_matched_entry` (`tests/test_fo_stream_watcher.py:77-93`) asserts `result["message"]["content"][0]["input"]["command"] == "spawn-standing now"` — PASS.
2. **AC-2 (`StepTimeout` raised with `.label` attribute)** — PASSED. `StepTimeout.__init__` stores `self.label = label` (`scripts/test_lib.py:966-968`); `expect()` raises with `label=label` at `:1164-1168`. Test `test_expect_raises_step_timeout_with_label` asserts `excinfo.value.label == "echo-agent dispatched"` — PASS.
3. **AC-3 (`StepFailure` on early proc exit, drain-before-poll)** — PASSED. Poll loop in `expect()` drains entries first (`:1142-1147`), then checks `self.proc.poll()` (`:1149`), and on non-None exit **drains again** (`:1150-1155`) to catch the final-flush entry before raising `StepFailure` with `exit_code=self.proc.returncode` (`:1156-1161`). Both `test_expect_raises_step_failure_when_proc_exits` (asserts `exit_code == 1`, `"code=1" in str(...)`, label carried) and `test_expect_matches_final_flush_before_exit` (entry written + `proc.set_exited(0)` before `expect()` — matches on final drain) PASS.
4. **AC-4 (partial-line handling)** — PASSED. `_drain_entries()` appends the raw `read()` chunk to `self._buffer`, splits on `\n`, keeps any incomplete trailing fragment in `_buffer` for the next poll (`:1092-1117`). Test `test_partial_line_then_newline` writes half a line (expect times out), writes the rest + `\n`, and the next `expect()` matches exactly once — PASS.
5. **AC-5 (context manager drains + runs `extract_stats` on exit)** — PASSED. `finally` block at `scripts/test_lib.py:789-812` calls `watcher.close()`, closes the log file, and invokes `extract_stats(log_path, "fo", runner.log_dir)` on the normal-exit path. Test `test_context_manager_extracts_stats_on_normal_exit` monkeypatches `extract_stats`, uses `sh -c printf`, and asserts `calls["args"][1] == "fo"` and `calls["args"][0].name == "fo-log.jsonl"` — PASS.
6. **AC-6 (terminate on with-exit when caller skips `expect_exit`)** — PASSED. If `proc.poll() is None` at `finally`, the context manager waits up to `hard_cap_s`, then escalates `proc.terminate()` → `proc.wait(timeout=5)` → `proc.kill()` → `proc.wait()` (`:791-802`). Test `test_context_manager_terminates_lingering_proc` spawns `sh -c 'sleep 30'`, exits after 0.2s with `hard_cap_s=1`, asserts `proc.poll() is not None` and total elapsed `< 4.0s` — PASS.
7. **AC-7 (600s hard cap enforcement)** — PASSED. Same `finally` escalation as AC-6, gated by `remaining = hard_cap_s - elapsed`. Test `test_context_manager_enforces_hard_cap` uses `hard_cap_s=1` against `sh -c 'sleep 10'`, sleeps 3s inside the `with`, and confirms the subprocess is dead within `< 6.0s` — PASS.
8. **AC-8 (predicate helpers)** — PASSED. `tool_use_matches`, `entry_contains_text`, `assistant_model_equals` each accept a single entry (no list walks) and return bool (`scripts/test_lib.py:993-1065`). `tool_use_matches` checks all `key=substring` pairs via `needle in input[key]`. Tests `test_tool_use_matches_covers_all_tool_shapes` and `test_entry_contains_text_and_assistant_model_equals` PASS (covering Bash/Agent/SendMessage shapes, non-tool-use return-False, regex in assistant text and user tool_result, haiku/opus model prefix).
9. **AC-9 pilot: standing-teammate migration** — PASSED (static verification; live fails-fast verification is explicitly a deferred manual captain step per ideation agreement). `tests/test_standing_teammate_spawn.py` imports `run_first_officer_streaming`, `tool_use_matches`, `entry_contains_text`; uses five `expect()` calls (spawn-standing 60s, echo-agent 120s, ensign dispatch 240s, SendMessage 240s, ECHO: ping 240s) + `expect_exit(240)`; preserves `@pytest.mark.live_claude` + `@pytest.mark.teams_mode` (lines 32-33); final aggregate still uses `LogParser` after exit (lines 126-133).
10. **AC-10 pilot: per-stage-model migration** — PASSED (static). `tests/test_claude_per_stage_model.py` imports the same streaming surface; two `expect()` calls (ensign dispatch 180s, haiku model 240s) + `expect_exit(300)`; preserves `@pytest.mark.live_claude` + `@pytest.mark.xfail(strict=False)` (lines 30-36, reason cites #171).
11. **AC-11 (non-migrated tests unchanged)** — PASSED. `uv run pytest --collect-only tests/test_gate_guardrail.py` collects 1 test. `git diff main...HEAD -- scripts/test_lib.py` shows only +1 deletion (the `Callable`→`Callable, Iterator` import refactor); no modifications to `run_first_officer`, `LogParser`, or any other existing callable. Test `test_non_migrated_public_surface_intact` imports `{FOStreamWatcher, LogParser, run_first_officer, run_first_officer_streaming}` cleanly — PASS.
12. **AC-12 (failure messages include log tail + label)** — PASSED. Both `StepTimeout` and `StepFailure` messages embed `f"Log tail:\n{self._log_tail()}"` (`scripts/test_lib.py:1156-1161, 1164-1168, 1186-1190`). `_log_tail` reads up to `_LOG_TAIL_LINES=20` tail lines. Test `test_failure_messages_include_log_tail_and_label` writes 5 noise lines and asserts both `"echo-agent dispatched"`/`"after-exit step"` labels **and** `"Log tail:"` + `"noise line 4"` appear in each error message — PASS.

### AC-14 (prompt-section on matched entry, from #162)

AC-14 is explicitly called out in the dispatch. The ensign-dispatch `expect()` at `tests/test_standing_teammate_spawn.py:88-93` captures the matched entry into `ensign_dispatch`, then the prompt-section assertions at lines 94-102 operate on `_agent_input(ensign_dispatch).get("prompt", "")` — single-entry, no second scan of the log. PASSED.

### AC-9 live fails-fast verification

NOT RUN as part of validation — this is a deferred manual captain step per the ideation agreement (see entity `## Test Plan` line 380 and implementation Stage Report line 416). The manual procedure: temporarily patch the standing-teammate fixture to drop the ensign SendMessage instruction, run the live test, confirm `StepTimeout` fires at the `"SendMessage to echo-agent observed"` label in <4 min. Noted as SKIPPED (manual) here; no validation action required.

### Overall recommendation

**ACCEPTED — advance to merge.**

Evidence: 12/12 ACs verified (ACs 9-10 on static-only grounds per the dispatch brief; AC-14 prompt-section matched-entry pattern verified); `make test-static` green (425/425 + 10 subtests, 17.74s); six focused commits with no out-of-scope edits; `run_first_officer` / `LogParser` public surface untouched. Two follow-up items for the captain (not blocking this validation):
- Manual AC-9 fails-fast verification (temporarily patch fixture, run live, confirm <180s StepTimeout at milestone 4).
- Live-run the migrated pilots on `claude-live-opus` to confirm the wall-clock improvement (~180s vs. 24m38s) in practice — this is the feature's real payoff and should be measured once post-merge.

## Stage Report (implementation — cycle 2)

1. Read `### Feedback Cycles` section — DONE. Cycle 1 rejection summary: StepTimeout fired correctly at the SendMessage milestone, but `run_first_officer_streaming.__exit__` waited the remainder of `hard_cap_s` for the hung FO subprocess, pushing pytest wallclock to 600.16s vs. the promised ~180s.
2. Locate the finally block in `run_first_officer_streaming` — DONE. `scripts/test_lib.py:787-812` (original). The finally called `proc.wait(timeout=max(hard_cap_s - elapsed, 1))` regardless of exit path.
3. Implement exception-vs-normal grace-period split — DONE. Added `exception_exit` flag via a bare `except BaseException: exception_exit = True; raise` wrapping the `yield`. Finally now picks `grace_s = 5` on exception exit or `max(hard_cap_s - elapsed, 1)` on normal exit, then falls through to the same terminate+kill escalation. `scripts/test_lib.py:786-822`. Commit `be946306`.
4. Add AC-13 offline unit test — DONE. `tests/test_fo_stream_watcher.py::test_context_manager_terminates_fast_on_exception_exit` launches `sh -c 'sleep 60'` with `hard_cap_s=600`, raises `_Boom` inside the `with`, asserts subprocess dead and total wallclock `< 15s`. Docstring cites AC-13. Commit `eb01f949`.
5. Update `## Acceptance Criteria` with AC-13 — DONE. New numbered entry added after AC-12 describing the exception-exit fast-terminate requirement, the 5s grace contract, and the `sh -c 'sleep 60'` / `hard_cap_s=600` / `<15s` test strategy.
6. Update `## Test Plan` to reference AC-13 — DONE. Offline-unit-tests paragraph now lists ACs 1-8, 11, 12, 13 and notes the ~12s total runtime (AC-13 adds the 5s grace wait).
7. Run `make test-static` — DONE. **426 passed (+1 from cycle 1), 22 deselected, 10 subtests passed in 19.63s.** New AC-13 test picked up automatically; no regressions.
8. Append `## Stage Report (implementation — cycle 2)` — DONE (this section). Cycle 1 report at line 433 is preserved verbatim.
9. Focused commits on the existing branch — DONE. Three commits on `spacedock-ensign/streaming-fo-watcher-per-step-timeouts`: (i) `61283845` cherry-picked the main-branch reject commit to surface `### Feedback Cycles` in the worktree, (ii) `be946306` fast-terminate fix in `run_first_officer_streaming.__exit__`, (iii) `eb01f949` AC-13 regression test. This stage-report commit will be the fourth.
10. Send completion SendMessage — pending (next tool call).

### Summary

Fixed the cycle-1 defect: `run_first_officer_streaming` now terminates the claude subprocess within ~5s on any exception-driven exit (StepTimeout / StepFailure / test-body AssertionError) instead of waiting out the remainder of `hard_cap_s`. The normal `expect_exit`-path keeps its existing hard-cap behavior. Added AC-13 + regression test; all 426 offline tests green. Pilot tests, `LogParser`, and `run_first_officer` untouched. Recommend re-entry to **validation**.

## Stage Report (validation — cycle 2)

### Inputs verified

1. Read `### Feedback Cycles` (cycle 1), `## Stage Report (implementation — cycle 2)`, and the updated `## Acceptance Criteria` (AC-13). DONE.
2. Inspected the three cycle-2 commits for scope discipline:
   - `be946306` — fix to `run_first_officer_streaming.__exit__`. Touches `scripts/test_lib.py` only (+14/-3). No edits to `run_first_officer`, `LogParser`, or any other existing function.
   - `eb01f949` — AC-13 offline regression test. Touches `tests/test_fo_stream_watcher.py` only (+39/0).
   - `b460e849` — cycle-2 implementation stage report. Touches the entity file only.
   No out-of-scope edits. DONE.
3. `git diff 44acc983..HEAD --stat` confirms three files changed across cycle 2: entity file, `scripts/test_lib.py`, `tests/test_fo_stream_watcher.py` — total +101/-4. No pilot-file churn (`tests/test_standing_teammate_spawn.py`, `tests/test_claude_per_stage_model.py` untouched since `fc426716`/`362ba4f4` in cycle 1). DONE.

### `make test-static`

- Ran from the worktree root.
- Result: **`426 passed, 22 deselected, 10 subtests passed in 20.06s`**. Matches the cycle-2 implementation report's 426 count (+1 from cycle 1's 425, the new AC-13 test). PASS.

### AC-13 (exception-exit fast-terminate)

- **Fix inspection** (`scripts/test_lib.py:786-813`): the yield is now wrapped in `try: yield watcher / except BaseException: exception_exit = True; raise`. In `finally`, the wait timeout splits on `exception_exit`: 5s fixed grace on abnormal exit, `max(hard_cap_s - elapsed, 1)` on normal exit. Both paths fall through to the same `terminate → wait(5) → kill` escalation. Using `except BaseException` (not `Exception`) covers `StepTimeout`/`StepFailure` (both subclass `AssertionError`) and any test-body assertion/KeyboardInterrupt. PASSED.
- **Test inspection** (`tests/test_fo_stream_watcher.py:300-336`): uses `sh -c 'sleep 60'` via `_REAL_POPEN` (pattern reused from cycle 1), `hard_cap_s=600`, raises `_Boom` inside the `with`, asserts subprocess dead (`proc.poll() is not None`) and total wallclock `< 15s`. Matches the AC-13 spec verbatim. PASSED.
- **Direct run**: `uv run pytest tests/test_fo_stream_watcher.py::test_context_manager_terminates_fast_on_exception_exit -v --durations=0` → **1 passed in 5.02s; call duration 5.01s**. The 5.01s matches the 5s grace period (subprocess survives the wait, then is terminated+killed). Well under the 15s budget and proves the fix terminates within the grace, not after `hard_cap_s=600`. PASSED.

### AC-13 commentary on test semantics

The 5.01s call duration is expected and correct: `sh -c 'sleep 60'` does not respond to the 5s `proc.wait()` (still sleeping), so `wait` raises `TimeoutExpired`, then `terminate()` delivers SIGTERM, `sh` exits within sub-second on the second `wait(5)`. Total: ~5s + epsilon. If the fix were absent, the same test would take `~600s` (the full `hard_cap_s`) and FAIL the 15s budget. The test is a correct regression guard.

### Regression check for ACs 1-12

- Direct run of full `tests/test_fo_stream_watcher.py`: **13 passed in 12.29s**. Every test from cycle 1 (ACs 1-8, 11, 12 → 12 tests) plus the new AC-13 test. No regressions.
- The public surfaces touched in cycle 2 are strictly additive to `__exit__` semantics; the `expect()` / `expect_exit()` / predicate-helper paths are unchanged.

### Public-surface invariants (AC-11 reaffirmed)

- `git diff main...HEAD -- scripts/test_lib.py` covers lines added by the streaming surface only; `run_first_officer` and `LogParser` ranges at `scripts/test_lib.py:1-240` and `:735-812` show no modifications to their function bodies or signatures (the only touches in the `:735-812` range are inside `run_first_officer_streaming`'s finally block).
- Pilot migrations (`tests/test_standing_teammate_spawn.py`, `tests/test_claude_per_stage_model.py`) unchanged since cycle 1 commits `fc426716` and `362ba4f4`. `git log 44acc983..HEAD -- tests/test_standing_teammate_spawn.py tests/test_claude_per_stage_model.py` returns no commits. PASSED.

### Per-AC verdicts (cycle 2)

1. **AC-1** — PASSED (unchanged from cycle 1; test still green in the suite run).
2. **AC-2** — PASSED (unchanged).
3. **AC-3** — PASSED (unchanged).
4. **AC-4** — PASSED (unchanged).
5. **AC-5** — PASSED (unchanged; normal-exit path through the refactored finally still invokes `extract_stats`).
6. **AC-6** — PASSED (unchanged; lingering-proc normal-exit path still uses `hard_cap_s - elapsed` grace).
7. **AC-7** — PASSED (unchanged; hard-cap enforcement preserved on normal exit).
8. **AC-8** — PASSED (unchanged).
9. **AC-9 pilot (standing-teammate)** — PASSED (static; unchanged in cycle 2). Live fails-fast verification remains a deferred manual captain step.
10. **AC-10 pilot (per-stage-model)** — PASSED (static; unchanged in cycle 2).
11. **AC-11 (non-migrated tests unchanged)** — PASSED. Cycle-2 fix is confined to `run_first_officer_streaming.__exit__`; `run_first_officer`, `LogParser`, and all other public surface remain untouched.
12. **AC-12** — PASSED (unchanged).
13. **AC-13 (exception-exit fast-terminate)** — PASSED. Fix (`be946306`) correctly distinguishes exception-vs-normal exit with 5s grace. Regression test (`eb01f949`) runs in 5.02s wallclock against `hard_cap_s=600`, well under the 15s budget. Without the fix this would take ~600s.

### Manual post-merge items (unchanged from cycle 1)

- **Manual AC-9 fails-fast verification** — captain patches the standing-teammate fixture to drop the ensign SendMessage instruction, runs the live test, confirms `StepTimeout` fires at `"SendMessage to echo-agent observed"` in <4 min. Deferred manual step per ideation agreement.
- **Live-smoke re-run at opus-low** — with the cycle-2 fix, the 600.16s wallclock reported in the cycle-1 smoke should drop to ~180s + 5s grace = ~185s total. This is the payoff the rejection was predicated on; captain should re-run the same smoke to confirm the wallclock number before final merge.

### Overall recommendation

**ACCEPTED — advance to merge.**

Evidence: cycle-1 defect addressed at the root (exception-driven `__exit__` no longer waits out `hard_cap_s`); three cycle-2 commits with strictly scoped diffs (fix, regression test, stage report); `make test-static` green at 426/426 + 10 subtests in 20.06s; AC-13 test directly proves fast-terminate in 5.02s wallclock against a 600s hard cap; ACs 1-12 unaffected; pilots untouched; `run_first_officer` / `LogParser` untouched. Captain's manual live-smoke re-run at opus-low will provide the end-to-end payoff measurement (expected ~185s vs. cycle-1's 600.16s).
