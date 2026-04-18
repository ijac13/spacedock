---
id: 112
title: Multi-player claim semantics for entity ownership
status: ideation
source: CL — design discussion during 111 ideation, 2026-04-09
started: 2026-04-15T05:18:01Z
completed:
verdict:
score: 0.45
worktree:
issue:
pr:
---

The `worktree` field currently serves three roles: claim/lock (someone is working on this), local filesystem path (the checkout location), and implicit branch reference. In a multi-player scenario (multiple people or agents working from clones of the same repo), these conflate:

- The local path is per-machine — meaningless to other clones
- The branch is the shareable coordination point (exists on remote)
- The claim/lock intent ("I'm actively working on this") has no explicit representation

Design opportunities:
- Split into explicit fields: `branch` (shared, committed), `claimed-by` / `claimed-at` (identity + staleness), `worktree` (local-only or ephemeral)
- Use remote branch existence as source of truth for work-in-progress
- Staleness detection: claim without recent commits → flag as stale
- PR as the natural multi-player handoff mechanism (already partially implemented via pr-merge mod)

Key question: what's the target multi-player scenario — simultaneous FO sessions against the same repo, or async handoffs across sessions/people?

## Agent-stamp extension (added 2026-04-18, surfaced by team zombie sweep)

Single-session FO scope hit a related ergonomics gap: agent-lifecycle state lives only in the team config (`~/.claude/teams/{team}/config.json`), separate from the workflow's source of truth (entity frontmatter on main). This makes it impossible to:

- Sweep zombie agents at boot (FO can't tell which alive team members correspond to entities that have advanced/merged)
- Resume agent shutdown after a context-loss restart
- Detect when a stamped agent + a current entity-state mismatch (e.g., entity at `validation`, but team has agent stamped at `implementation`)

**Proposed addition to the claim-semantics design:** stamp the dispatched worker's name on the entity at dispatch time. Field shape: `agent: {worker_name}` (or `claimed-by` if folded into the broader claim concept above). Cleared on shutdown sweep / merge / archive.

This composes cleanly with the multi-player concept: in multi-player mode the stamp identifies WHO claimed (machine + agent name); in single-player mode it identifies WHICH local agent. Both modes benefit from a stable, durable, cross-session-readable agent identifier.

Concrete affordance unlocked: a `claude-team` health subcommand can compare the team config's alive members against the entity frontmatter's stamps and surface discrepancies (zombie agent, stale claim, missing-but-expected). See task on team-health command (filed 2026-04-18).
