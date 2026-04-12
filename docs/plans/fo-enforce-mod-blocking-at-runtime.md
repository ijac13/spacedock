---
title: First officer must enforce mod-declared blocking actions at runtime
id: 114
status: backlog
source: CL observation during entity 110 closeout
started: 2026-04-09T22:56:43Z
completed:
verdict:
score: 0.80
worktree:
issue:
pr:
---

First officer currently relies too heavily on remembering mod instructions from prose. That is brittle. A mod can require a stop, approval, or external wait, but the runtime does not yet enforce those requirements mechanically.

## Problem Statement

The `pr-merge` mod correctly says gate approval does not imply PR approval, but first officer can still drift unless it re-reads and obeys the mod at the exact transition point. This is a general workflow safety problem, not just a PR problem.

## Desired Outcome

Add a generic runtime mechanism so active mods can force first officer to pause for captain approval or another blocking condition, and a resumed session cannot silently skip that pending requirement.

## Follow-up Observation From Task 139

Task 139 exposed the concrete failure mode this task needs to prevent. After validation passed, the first officer advanced the entity straight through terminalization and archival without running the `pr-merge` mod first. The problem was not lack of prose coverage; the shared core already says merge hooks run before any local merge, archival, or terminal status advancement. The failure was that the stop lived only in instructions, not in an enforced runtime checkpoint.

That confirms the main design direction here:

1. **Runtime enforcement remains the primary fix.** The first officer/runtime must track pending mod-controlled blocking actions at the transition boundary itself. A terminal or merge-sensitive transition should not complete until the mod has either handled it or explicitly yielded back to the default path.
2. **`status --set` is a useful supporting guardrail, not the source of truth.** In practice, first officer uses `status --set` to advance entities, so that command is a natural place to add friction for dangerous direct transitions. When a caller tries to set a mod-sensitive status (for example, a terminal state that would normally run merge hooks), `status --set` should warn or refuse by default and reserve `--force` for cases where the captain explicitly approved bypassing the normal hook/block flow.
3. **Pending mod blocks should survive session drift and resume.** If a mod requires approval, an external wait, or a PR-creation step, the resumed runtime should see that requirement as active state rather than recomputing it from memory or hoping the operator remembers the prose.

This means the likely implementation shape is layered:

- first-officer/runtime owns correctness and blocking semantics
- `status --set` provides last-mile friction against operator error on direct transitions
- `--force` exists only as an explicit override for captain-approved direct advancement
