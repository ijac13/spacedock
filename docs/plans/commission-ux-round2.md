---
title: Commission UX — Round 2 fixes from testflight observation
status: ideation
source: testflight sd5-test observation
started: 2026-03-24T01:00:00Z
completed:
verdict:
score: 0.90
worktree:
---

UX issues observed from a fresh commission run (sd5-test: product idea to simulated customer interview pipeline). Covers both the commission conversation flow and the quality of generated artifacts.

## Architecture issue: first-officer has pipeline-specific logic baked in

The first-officer template (~160 lines) hardcodes pipeline-specific behavior: approval gate stage names, conflict check referencing "implementation", worktree-for-all-stages, no concurrency limits. The README is supposed to be the single source of truth, but the first-officer duplicates and sometimes contradicts it.

Fix: make the first-officer a generic dispatcher that reads behavior from the README. Stage definitions in the README gain structured properties (worktree, approval), and the first-officer derives dispatch rules at runtime. No hardcoded stage names in the template.

This subsumes the ideation-on-main entity (stage properties in README schema).

## Commission conversation flow issues

1. **Command args ignored** — `/spacedock:commission product idea to simulated customer interview` provided the mission in args, but Q1 still asked for it. Args should be treated as the mission; skip to entity/stages if mission is already provided.

2. **Git repo auto-init** — Commission asked "Can I initialize a git repo?" instead of just doing it. This is friction for a new project.

3. **Seed entity lookup too heavyweight** — User said "spacedock - find the info in ~/git/spacedock" and commission spawned a full Agent to search. For seed descriptions, a quick read is sufficient.

4. **TaskCreate spam** — 8 TaskCreate calls during generation clutter the user's view. Internal bookkeeping should be invisible.

## Generated artifact issues

5. **Status script missing slug column** — Shows STATUS, TITLE, SCORE, SOURCE but no filename/slug. Users need the slug to know which file to open/edit.

6. **Conflict check references "implementation"** — Hardcoded stage name in first-officer doesn't match the pipeline's actual stages (research, interview-prep, etc.).

7. **`{entity-slug}` in git refs** — Branch names, worktree paths use `ensign-{entity-slug}`. Should be `{slug}` (neutral, no "entity" leak).

8. **No stage-aware dispatch** — All stages go through worktrees, including research-type stages that only modify entity markdown. Should respect per-stage worktree property.

9. **No concurrency limits** — Neither the generated README nor first-officer mention concurrency.

10. **README vs first-officer commit discipline contradiction** — README says "session end", first-officer says "dispatch boundaries".
