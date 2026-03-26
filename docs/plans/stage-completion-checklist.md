---
id: 043
title: Stage completion checklist for ensign reporting
status: ideation
source: CL
started: 2026-03-26T00:00:00Z
completed:
verdict:
score: 0.80
worktree:
---

Ensigns currently report completion as free-form text. This lets them rationalize skipping steps without the first officer noticing until it's too late (e.g., skipping the test harness and burying the rationale in a paragraph).

Add a structured checklist that ensigns must fill out when completing a stage. Items come from two sources:

1. **Stage-level requirements** — defined in the README stage definition (e.g., "run tests from Testing Resources section"). These apply to every entity passing through that stage.
2. **Entity-level acceptance criteria** — from the entity body. These are task-specific.

Each item gets a status: done, skipped (with rationale), or failed. The ensign reports the filled checklist to the first officer. The first officer's job is to review the checklist and push back on invalid skip rationales — separating execution from judgment.

Motivated by: a validation ensign skipping the commission test harness and self-approving the skip as reasonable.
