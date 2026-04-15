---
id: 083
title: Stage skip logic — allow entities to bypass stages when preconditions are met
status: ideation
source: oh-my-codex analysis
started: 2026-04-15T05:18:01Z
completed:
verdict:
score: 0.40
worktree:
issue:
pr:
---

Every entity passes through every stage regardless of complexity. A single-line typo fix gets the same ideation → implementation → validation pipeline as a multi-file architectural change. There's no mechanism for an entity to skip a stage when its preconditions are already satisfied.

## Inspiration

oh-my-codex's pipeline stages have a `canSkip` callback — each stage can evaluate accumulated context and short-circuit when preconditions are met (e.g., skip planning if a plan already exists).

## Proposed Design

Add an optional `skip-when` property to stage definitions in README frontmatter. The first officer evaluates it before dispatch and advances the entity directly if the condition holds.

Possible conditions:
- Entity body already contains the stage's expected outputs (e.g., skip ideation if acceptance criteria already exist)
- Entity score below a threshold (e.g., skip ideation for low-complexity tasks)
- A frontmatter field is already populated

The first officer would log the skip in the entity's stage report for auditability.

## Open Questions

- Should skip be a per-entity override (frontmatter flag) or purely stage-level?
- Should the captain be notified on skip, or is a log entry sufficient?
- How does this interact with gated stages — can a gated stage be skipped?
