---
id: 112
title: Multi-player claim semantics for entity ownership
status: backlog
source: CL — design discussion during 111 ideation, 2026-04-09
started:
completed:
verdict:
score:
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
