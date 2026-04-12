---
id: 140
title: Codex interactive-mode completion and gate ergonomics
status: ideation
source: FO observation during task 136 completion handling on 2026-04-12
score: 0.64
started: 2026-04-12T18:25:22Z
completed:
verdict:
worktree: .worktrees/spacedock-ensign-interactive-mode-completion-gate-ergonomics
issue:
pr:
---

The current Codex first-officer runtime guidance is clear about what to do when a worker completes, but it is not ergonomic enough about how interactive Codex sessions should react to asynchronous completion notifications. In practice, a worker can complete in the background, notify the first officer, and still leave the entity sitting unprocessed while the conversation continues on unrelated topics. That happened with task 136: the ideation worker completed and wrote a valid stage report, but the gate was not foregrounded until the captain explicitly pushed for it.

Single-entity mode already captures part of the desired behavior because it is outcome-driven and stops on the entity's meaningful result. Interactive Codex mode needs an equivalent event-handling rule: a worker completion notification for a gated or critical-path stage should immediately become the first officer's next required action. The first officer should process the stage report, present the gate if needed, and only then return to unrelated orchestration.

This task should improve the Codex runtime guidance for interactive sessions so worker completions foreground the next operator action instead of becoming easy-to-ignore background chatter. Changes to the shared first-officer contract are out of scope unless the Codex-specific rule proves it needs to be generalized later.
