---
id: 102
title: "Spike: multi-turn team test harness"
status: implementation
source: "099 testing gap — no infra for interactive team behavior tests"
started: 2026-04-08T18:49:36Z
completed:
verdict:
score: 0.8
worktree: .worktrees/spacedock-ensign-multi-turn-test-harness
issue:
pr:
---

We can't test team interaction behavior (idle handling, captain-to-ensign communication, agent routing) because all tests use `claude -p` (single prompt, single response). This spike investigates what's feasible and builds a minimum viable multi-turn test harness.

## Spike questions

1. Can `claude` be driven interactively via PTY (`pexpect` or `pty` module)?
2. Where do agent JSONL logs live in team sessions — one per agent, or merged into the FO's log?
3. If ensign JSONL is captured separately, can we verify ensign behavior (direct text vs SendMessage) purely from log analysis without interactive input?
4. Can the captain switch to talking directly to an ensign mid-session, and how does that appear in logs?
5. What's the minimum code needed to: start a session, wait for agent spawn, inject a user message, collect logs, shut down?

## Success criteria

- Answer all 5 spike questions with evidence (actual test runs, not speculation)
- If PTY driving works: produce a working `test_lib.InteractiveSession` class (~80-100 lines) that can start claude, send messages, wait for JSONL patterns, and collect logs
- If PTY driving doesn't work: document why and propose alternatives
- If JSONL-only analysis suffices for the 099 test cases: document the approach and show it working on a sample log
