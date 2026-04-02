---
id: "084"
title: Unify test harness across Claude Code and Codex runtimes
status: backlog
source: CL — 076 validation findings
started:
completed:
verdict:
score: 0.75
worktree:
issue:
pr:
---

# Unify test harness across Claude Code and Codex runtimes

## Problem

E2E tests for the same behavioral properties (gate guardrail, rejection flow, merge hook) are duplicated across Claude Code and Codex — separate files, separate launchers, same fixture and validation logic. Offline content checks are scattered across 5 E2E test files instead of being centralized.

## Proposed approach

1. **Unified offline content test** — Extract all `assembled_agent_content` checks from E2E files + merge with `test_codex_skill_content.py` into one `test_agent_content.py`. Remove Phase 1 from each E2E file.

2. **RuntimeAdapter abstraction** — Create `ClaudeAdapter` and `CodexAdapter` in test_lib that share a common interface for launch + log parsing. Pytest parametrize runs each test against both runtimes.

3. **Plugin discovery adapter** — Add a third variant that uses `--agent spacedock:first-officer --plugin-dir` with no local agent copies and isolated HOME. Tests the real plugin path.

## Acceptance criteria

1. All offline content checks in a single test file, covering both Claude and Codex agent content
2. Gate guardrail, rejection flow, and merge hook tests share validation logic across runtimes
3. Plugin discovery path (`spacedock:first-officer` via `--plugin-dir`) tested in at least one E2E
4. No increase in total test file count (6 paired files → 3 shared + 1 content)
5. All existing behavioral checks preserved
