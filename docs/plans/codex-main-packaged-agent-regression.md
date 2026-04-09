---
title: Codex main packaged-agent regression after merged runtime-loading changes
id: 110
status: ideation
source: CL observation after merge to main
started: 2026-04-09T21:36:48Z
completed:
verdict:
score: 0.88
worktree:
issue:
pr:
---

The Codex packaged-agent live test still fails on `main` after the runtime-loading work landed.

## Problem

`tests/test_codex_packaged_agent_e2e.py` no longer times out in the original way, but it still fails its packaged safe-naming assertions on `main`.

Observed failure shape:

- first officer boots and dispatches a worker
- worker completes and returns a result
- test still fails because the packaged logical id `spacedock:ensign` is not consistently converted into the safe worker key `spacedock-ensign`
- resulting worktree/branch names use `ensign` instead of `spacedock-ensign`

## Why this matters

The Codex runtime contract requires a split between:

- `dispatch_agent_id` — logical packaged id, e.g. `spacedock:ensign`
- `worker_key` — filesystem-safe name, e.g. `spacedock-ensign`

If the FO collapses the worker key to bare `ensign`, the packaged-agent path still does not preserve namespace-safe naming in worktree and branch state.

## Evidence

- `tests/test_codex_packaged_agent_e2e.py` fails on `main`
- failure assertions are:
  - FO keeps packaged logical id while dispatch stays on shared safe naming
  - safe packaged worker key appears in worktree path
  - safe packaged worker key appears in branch names
- live logs showed worktree/branch values like:
  - `.worktrees/ensign-buggy-add-task`
  - `ensign/buggy-add-task`
  instead of `spacedock-ensign-*`

## Expected outcome

Fix the Codex packaged dispatch path so:

1. `dispatch_agent_id` stays `spacedock:ensign`
2. `worker_key` becomes `spacedock-ensign`
3. state updates, worktree creation, branch naming, and reporting all use the safe worker key consistently
4. `tests/test_codex_packaged_agent_e2e.py` passes on `main`
