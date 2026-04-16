---
id: 173
title: "Streaming FO watcher with per-step timeouts and progressive assertions"
status: ideation
source: "CL observation during 2026-04-16 session — PR #107 CI (claude-live-opus) took 24m38s to surface a test failure that could have failed in ~120s with per-step timeouts. Post-hoc log parsing hides where in the sequence things stalled."
started: 2026-04-16T21:55:52Z
completed:
verdict:
score: 0.75
worktree:
issue:
pr:
---

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

- Rewriting all live E2E tests to use the watcher. This task ships the watcher plus two pilot migrations (`test_standing_teammate_spawn.py`, `test_per_stage_model.py`). Other tests migrate later on their own cadence.
- Removing `LogParser`. The post-hoc parser remains useful for final-state assertions after exit.
- Changes to the `claude -p` invocation shape. The watcher reads the existing `--output-format stream-json` output.
- Codex runtime equivalents. Codex tests have their own `LogParser`; a matching watcher is follow-up.
