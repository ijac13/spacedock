---
id: 169
title: "Experiment workflow direction — autoresearch optimization loop alongside the ship pipeline"
status: backlog
source: "CL + Claude discussion during 2026-04-16 session — exploring how prompt optimization, contract trimming, and behavioral measurement fit alongside the existing ship-oriented workflow"
started:
completed:
verdict:
score:
worktree:
issue:
pr:
---

## Problem Statement

Spacedock's `docs/plans/` workflow is ship-oriented: `backlog → ideation → implementation → validation → done`, with unit-test-grade validation and pr-merge hooks. This works well for construction tasks (#166, #167, #168) but underserves a growing class of work: prompt optimization, contract trimming, behavioral measurement, and performance regression detection. These tasks share the development lifecycle — they produce code and prose changes that ship — but differ in validation cost model: they need multi-session behavioral evidence, not just `make test-static`.

CL currently runs an external experiment-focused workflow using spacedock as a submodule, with the workflow directory outside the repo. This works but creates a handoff gap: experiment conclusions must be manually translated into `docs/plans/` tasks to ship. The question is whether to formalize this relationship, absorb the experiment workflow into the repo, or hold the boundary as-is.

## Context

This direction surfaced during the 2026-04-16 session. CL proposed an autoresearch-style optimization loop — hypothesize, test, adopt on success — pinned to release branches. The loop would run against a frozen subject (release commit) to avoid signal contamination from concurrent main-branch changes, then produce recommendations that ship through the normal `docs/plans/` pipeline.

Specific measurement targets already identified:

- First-run wallclock, turns, and token consumption across project archetypes (empty repo, scaffold project, messy-boot with orphans)
- Contract-trim impact on boot cost and FO correctness
- Operating-contract compression vs behavioral fidelity

## Placement options

**(a) Second workflow directory in this repo.** `docs/experiments/` alongside `docs/plans/`, each with its own `README.md` defining stage semantics appropriate to its concerns. `status --discover` already handles multiple workflow dirs. Shared mods (comm-officer, pr-merge) cost nothing to reuse. Experiment stages might look like `hypothesis → design → pilot → scaled → interpret → adopt-or-reject`. Subject pinning is a worktree-management detail: experiment worktrees pin to `release/0.9.6@{sha}` instead of branching off main.

**(b) One workflow, richer entity types.** Keep `docs/plans/` as the single workflow; let entities declare themselves experiment-shaped via a `kind:` field or convention. Problem: spacedock currently defines stages at workflow level, not per-entity. Per-entity stage sequences require a nontrivial schema change.

**(c) Formalize the external handoff.** Keep the experiment workflow outside with spacedock-as-submodule. Add a lightweight convention: experiment-produced recommendations land as tasks in `docs/plans/` with `source:` citing the experiment run. Near-zero cost, but commits to the external shape long-term.

## Open design questions for ideation

- Which placement option — (a), (b), (c), or a hybrid?
- Termination condition per experiment: confidence threshold after N sessions? K consecutive passing trials? Budget exhausted, return best candidate?
- Dispatched-session budget: how does the experiment workflow cap the cost of multi-session measurement?
- Gate-adopt vs auto-adopt: should the experiment decide "hypothesis passed" and the captain decide "file the ship task" (gate), or should the loop auto-file on success? CL's existing gate discipline (FO never self-approves) suggests gate.
- Subject rotation: when a new release cuts, does the experiment workflow auto-retarget or hold at the old subject? Implicit rotation makes cross-release comparisons noisy.
- Concurrent experiments against the same release: read-only access to the subject, or can experiments mutate the pinned worktree? Read-only is safer but constrains what the experiment can probe.

## Out of Scope

- Commissioning the experiment workflow itself — this task captures the direction and open questions, not the scaffolding.
- Changes to the existing `docs/plans/` stage semantics.
- Building the measurement harness (see #170).
