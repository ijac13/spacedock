---
id: 132
title: Codex first officer: derive reusable context/agent visibility from ~/.codex runtime state
status: backlog
source: FO observation during tasks 130/131/117 on 2026-04-11
started:
completed:
verdict:
score: 0.62
worktree:
issue:
pr:
---

Claude-team gives first officer an explicit `context-budget` check with a `reuse_ok`-style signal. Codex does not currently expose an equivalent supported interface, but the runtime appears to persist agent/session state under `~/.codex/` (for example `sessions/*.jsonl`, `state_*.sqlite`, and `logs_*.sqlite`).

This task should investigate whether Codex first officer can derive a practical visibility layer for:

- whether a reused worker is still active or merely reachable
- whether a reused thread is a good candidate for further work
- whether agent/thread pressure or context degradation is likely to make reuse unsafe
- how to inspect Codex runtime state without depending on brittle undocumented assumptions where avoidable

The goal is not to promise exact parity with `claude-team context-budget`, but to establish whether Codex can provide a stable enough signal for reuse decisions and operator reporting, and what runtime/test surfaces would need to change if Spacedock wants to rely on it.
