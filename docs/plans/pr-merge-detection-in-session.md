---
id: 071
title: Detect PR merges during long-running sessions
status: ideation
source: CL
started: 2026-03-29T05:28:00Z
completed:
verdict:
score: 0.80
worktree:
issue:
pr:
---

In a long-running FO session, merged PRs go undetected until the next startup — the pr-merge startup hook only fires once. An entity sitting at `validation` with `pr` set will stay there indefinitely even after the PR merges.

## Approach

Two changes, agreed with CL:

### 1. PR-pending check in the event loop (first-class)

After each agent completion, the FO already runs `status --next`. Add a step before that: scan for entities with non-empty `pr` and non-terminal status, check `gh pr view` for each, and advance any that have merged. Same logic as the startup hook, but running on every event loop iteration.

This is lightweight (one `gh` call per pending PR) and catches merges within minutes.

### 2. `idle` mod hook lifecycle point

Add `idle` as a new lifecycle hook point that fires when `status --next` returns nothing dispatchable. The pr-merge mod can hook `idle` to check PR states, but the core PR check is already handled by #1. The idle hook is for future extensibility — other mods might want to act when the FO has no work (e.g., cleanup, notifications, polling external systems).

After idle hooks run, the FO should re-run `status --next` in case a hook advanced an entity and unblocked new work.

## What changes

- **FO template event loop**: Add PR-pending entity scan before `status --next` on each iteration
- **FO template mod hook convention**: Document `idle` as an available lifecycle point
- **pr-merge mod**: Optionally add `## Hook: idle` (may not be needed if the core loop handles it)

## Acceptance Criteria

1. After each agent completion, the FO checks all PR-pending entities before running `status --next`
2. Merged PRs are advanced to done, archived, and worktree cleaned up (same as startup hook behavior)
3. `idle` is documented as a mod lifecycle hook point in the FO template
4. After idle hooks fire, the FO re-checks `status --next` for newly dispatchable entities
5. The startup hook still works unchanged (defense in depth)
