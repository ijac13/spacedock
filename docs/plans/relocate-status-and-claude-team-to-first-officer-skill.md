---
id: 167
title: "Relocate `status` and `claude-team` scripts from commission skill to first-officer skill"
status: backlog
source: "CL observation during 2026-04-16 boot session — both scripts are runtime tooling the first officer uses every loop iteration; keeping them under `skills/commission/bin/` is a historical artifact of where they were first authored, not where they belong."
started:
completed:
verdict:
score:
worktree:
issue:
pr:
---

## Problem Statement

The status viewer (`skills/commission/bin/status`) and dispatch-prompt builder (`skills/commission/bin/claude-team`) both live under the `commission` skill's `bin/` directory. Neither is used by the commission flow itself — commission is a one-shot workflow-scaffolding skill. Both scripts are runtime tooling consumed by the first officer on every loop iteration:

- `status --boot` / `--next` / `--where` / `--set` / `--next-id` / `--archive` — called from the FO event loop and the dispatch/merge lifecycle
- `claude-team build` / `spawn-standing` / `context-budget` — called from the FO dispatch adapter and standing-teammate spawn pass

The current layout forces every runtime reference in `skills/first-officer/references/*.md` to path-reach into a sibling skill (`{spacedock_plugin_dir}/skills/commission/bin/status`). The cross-skill dependency is load-bearing but invisible: a captain who reads `first-officer/` alone can't tell which scripts the FO actually executes without grepping the references.

## Context

This gap surfaced during the 2026-04-16 boot when CL asked why session-diagnostic commands were hitting `commission/bin/` — the directory name suggests one-shot setup tooling, but the FO runs them as its primary interface to workflow state. The mental model and the filesystem are out of sync.

## Observable asymmetries

- Every first-officer runtime adapter (Claude, Codex) references `commission/bin/` paths verbatim.
- The commission skill itself never invokes `status` or `claude-team` as part of its scaffolding flow — those scripts only run at FO runtime.
- Tests in `tests/` that exercise FO runtime behavior must shell out to `commission/bin/` paths.
- The `claude-team build` helper's prompt-assembly logic encodes FO-specific dispatch knowledge (checklist shape, feedback-reflow routing, bare-mode switching). That lives far from the first-officer skill that depends on it.

## Approach (for ideation)

Surface-level: move both scripts to `skills/first-officer/bin/` and update every reference.

Open questions ideation should resolve:

- Where does the `status --discover` boot probe belong? It scans for workflow directories regardless of first-officer context — is it truly FO-owned, or does some shared utility location fit better?
- Are there any external callers (tests, other skills, documentation) that assume the commission path? What breaks and how is it migrated?
- Do we keep compatibility shims under `commission/bin/` during migration, or cut over in one PR?
- Does the `commission` skill retain *any* runtime bin tooling, or does `bin/` empty out entirely?
- Is there an even better home — e.g., a plugin-level `skills/shared/bin/` — for tooling that both the first-officer runtime and a future debrief skill might share?

## Out of Scope

- Renaming or restructuring the scripts themselves (they keep their current CLI shape).
- Changing commission-skill behavior beyond the file relocation.
- Codex runtime equivalents if any — Codex has its own dispatch path; same migration pattern applies but is a separate rollout decision.
