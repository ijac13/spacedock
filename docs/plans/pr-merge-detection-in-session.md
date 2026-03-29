---
id: 071
title: Detect PR merges during long-running sessions
status: implementation
source: CL
started: 2026-03-29T05:28:00Z
completed:
verdict:
score: 0.80
worktree: .worktrees/ensign-071-pr-merge-detection
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

## Detailed Design

### 1. PR-pending check placement in the FO event loop

The seed description proposed a first-class PR-pending scan before every `status --next` call. On closer analysis, this collapses into the `idle` hook (section 2 below). The reasoning:

- The FO doesn't hardcode PR logic — it delegates to mod hooks (startup, merge). The in-session PR check should follow the same pattern: the pr-merge mod provides the behavior, the FO provides the lifecycle point.
- Checking on every event loop iteration is heavier than needed. If the FO has entities to dispatch, a merged PR frees a concurrency slot that won't be needed until the current batch finishes. Checking only when idle (nothing dispatchable) catches merges exactly when they matter — when the FO would otherwise be waiting.
- Without pr-merge installed, there's nothing to check. Making this a hook means no-op when no mods hook `idle`.

**Tradeoff:** A PR merged during a busy period won't be detected until the FO becomes idle. In practice this is a delay of minutes (one event loop cycle), which is acceptable — the entity was waiting for days for PR review, a few more minutes is noise.

**Placement:** The PR-pending check is the `idle` hook firing. The event loop paragraph (line 59 of `templates/first-officer.md`) gets the idle hook behavior. No separate "PR scan step" in the core loop.

### 2. The `idle` lifecycle hook point

**When `idle` fires:** After the FO processes an agent completion (including gate flow) and before running `status --next`, the FO checks if there are currently zero agents running. If so, the FO is "idle" — no active work, about to check for new work. At this point, fire `idle` hooks.

More precisely, `idle` fires at two points:
- **After processing a completion that leaves no agents running:** The agent just finished, gate flow resolved (or no gate), and no other agents are active. Before `status --next`, fire `idle` hooks.
- **When `status --next` returns nothing dispatchable:** The FO has checked for work and found none. Before reporting idle state to the captain, fire `idle` hooks. Then re-run `status --next` in case a hook advanced an entity.

The second point is the more important one — it catches the case where the FO's entire work queue is empty but a PR-pending entity exists. Without this, the FO would report "nothing to do" while a PR sits merged on GitHub.

**Simplification:** Combine both into a single rule. The FO fires `idle` hooks whenever `status --next` returns nothing dispatchable. The event loop becomes:

1. Process completion (existing)
2. Run `status --next`
3. If dispatchable entities exist: dispatch them (existing)
4. If nothing dispatchable: fire `idle` hooks, then re-run `status --next`
5. If still nothing dispatchable after idle hooks: report idle state to captain, wait for next event

This is simpler than checking "zero agents running" because it reuses the existing `status --next` result as the trigger. It also naturally handles the case where multiple completions arrive — the FO processes each completion, runs `status --next`, and only fires `idle` hooks when truly idle.

**What mods can do in `idle` hooks:** Check external state and advance entities. The pr-merge mod checks GitHub PR states. Other mods might poll CI status, check issue trackers, etc. The hook body is prose instructions, same as startup and merge hooks.

**Re-check after hooks:** After all `idle` hooks fire, the FO re-runs `status --next`. If a hook advanced an entity (e.g., PR merged, entity moved to done, freed a concurrency slot), the re-check picks up the newly dispatchable entity. If hooks didn't change anything, `status --next` returns nothing and the FO enters its idle wait.

### 3. pr-merge mod: `## Hook: idle` section

The pr-merge mod needs a `## Hook: idle` section. The core FO loop does NOT hardcode PR-checking logic — it delegates to mod hooks. The idle hook in pr-merge should contain the same logic as the startup hook (scan for PR-pending entities, check `gh pr view`, advance/report/no-op).

The wording can be nearly identical to the startup hook, since the behavior is the same. The only difference is context: startup fires once at session start, idle fires repeatedly during the session.

To avoid duplication, the idle hook can reference the startup hook:

```
## Hook: idle

Same scan as the startup hook: check all entities with non-empty `pr` and non-terminal status.
For each, run `gh pr view` and handle MERGED/CLOSED/OPEN as described in the startup hook.
```

This keeps the mod self-contained (both hooks are in the same file) and avoids duplicating the MERGED/CLOSED/OPEN logic.

### 4. FO template changes

Three sections of `templates/first-officer.md` need changes:

**A. Event loop paragraph (line 59)**

Current: "After each completion, run `status --next` again and dispatch any newly ready entities. This is the event loop — repeat until nothing is dispatchable."

Updated: "After each completion, run `status --next` again and dispatch any newly ready entities. If `status --next` returns nothing dispatchable, fire `idle` hooks (from `_mods/`), then re-run `status --next`. If still nothing dispatchable, report idle state to the captain and wait. This is the event loop."

**B. Mod Hook Convention section (lines 129-140)**

Add `idle` to the available lifecycle points list:

- **idle** — Fires when `status --next` returns nothing dispatchable. Use for polling external state that may unblock work (e.g., checking if a PR merged, polling CI status). After all idle hooks fire, the FO re-runs `status --next` to pick up any entities that hooks may have advanced.

Remove `idle` from the "Future lifecycle points" sentence (it's no longer future). The sentence becomes: "Future lifecycle points (not yet implemented): **dispatch** (before agent spawning) and **gate** (while waiting for captain approval)."

**C. No changes to Startup or Completion and Gates**

The startup flow is unchanged — startup hooks still fire once at session start. The gate-approval path (lines 84-87) is unchanged — it handles the post-gate PR creation flow, not PR merge detection.

## Acceptance Criteria

1. When `status --next` returns nothing dispatchable, the FO fires `idle` hooks before entering its idle wait
2. After `idle` hooks fire, the FO re-runs `status --next` and dispatches any newly ready entities
3. The pr-merge mod has a `## Hook: idle` section that checks PR-pending entities (same logic as startup hook)
4. Merged PRs detected during idle are advanced to done, archived, and worktree cleaned up (same as startup hook behavior)
5. `idle` is documented as an available mod lifecycle hook point in the FO template's Mod Hook Convention section
6. The startup hook still works unchanged (defense in depth — catches merges from between sessions)
7. The event loop paragraph in the FO template describes the idle hook firing and re-check behavior

## Stage Report: ideation

- [x] Problem statement grounded in the specific gap (startup-only PR detection)
  Entity file opens with the gap: "the pr-merge startup hook only fires once" — PR-pending entities go undetected until next session.
- [x] Exact placement of PR-pending check in the FO event loop (section, ordering)
  Detailed Design section 1: collapses into the idle hook rather than a separate first-class scan. Fires via the event loop paragraph (line 59 of template), after `status --next` returns nothing dispatchable, before idle wait. Tradeoff (delayed detection during busy periods) documented and accepted.
- [x] `idle` hook definition — when it fires, what it enables, re-check after hooks
  Detailed Design section 2: fires when `status --next` returns nothing dispatchable. 5-step event loop defined. Re-check `status --next` after hooks. Enables external state polling (PR merge, CI status, etc.).
- [x] Decision on whether pr-merge mod needs an idle hook or if core loop suffices
  Detailed Design section 3: pr-merge mod needs `## Hook: idle`. The FO is generic and delegates to mod hooks — no hardcoded PR logic in the core loop. Idle hook references startup hook logic to avoid duplication.
- [x] Acceptance criteria — testable conditions for "done"
  7 acceptance criteria, all testable. Covers idle hook firing, re-check, pr-merge mod hook, merge detection behavior, documentation, startup defense-in-depth, and event loop paragraph wording.

### Summary

The original two-part approach (first-class PR scan + idle hook) simplifies to one: the `idle` lifecycle hook point. The FO doesn't hardcode domain logic — PR checking belongs in the pr-merge mod's idle hook, not in the core event loop. The idle hook fires when `status --next` returns nothing dispatchable, mod hooks run, then `status --next` re-runs. Three sections of the FO template change: event loop paragraph, Mod Hook Convention (add idle), and the "future lifecycle points" sentence. The pr-merge mod gets a `## Hook: idle` section that references its startup hook logic. Acceptance criteria updated from the seed's 5 items to 7 refined items reflecting the consolidated design.
