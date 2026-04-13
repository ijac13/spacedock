---
id: 145
title: "PR-triggered runtime live E2E with environment approval gate"
status: validation
source: "CL direction during 2026-04-13 session — show runtime live checks on PRs and gate same-repo runs with a GitHub environment review"
score: 0.73
started: 2026-04-13T22:58:00Z
completed:
verdict:
worktree: .worktrees/spacedock-ensign-runtime-live-e2e-pr-trigger-and-environment-gate
issue:
pr:
---

## Problem Statement

Task 134 shipped `Runtime Live E2E` as a manual `workflow_dispatch` workflow. That made the workflow runnable, but it does not surface a visible pending runtime check on ordinary PRs. The captain wants the live runtime checks to appear alongside Static CI on PRs, with GitHub itself blocking execution until a maintainer approves the environment-backed run.

The follow-up should therefore shift the workflow from "manual launch after approval" to "automatic PR trigger with explicit environment approval before expensive jobs run." The environment to use is `CI-E2E`.

## Recommended Approach

Update `.github/workflows/runtime-live-e2e.yml` so it supports `pull_request` events and references the `CI-E2E` environment on both live jobs:

1. `claude-live`
2. `codex-live`

Each job should declare `environment: CI-E2E`. GitHub should then hold the job in a review-pending state until an authorized reviewer approves the environment deployment.

Keep `workflow_dispatch` support unless implementation proves it conflicts with the PR-triggered path. It remains useful for explicit reruns and targeted debugging, but the primary operator experience should become PR-native.

Because the workflow now needs to support both event shapes, the provenance/preflight logic must derive the active PR number from either:

- `github.event.pull_request.number` on `pull_request`
- `inputs.pr_number` on `workflow_dispatch`

The summary output should continue to show:

- PR number
- tested workflow SHA
- current PR head SHA
- branch source (same-repo or fork)
- approval/reviewer context
- trigger source (`pull_request` or `workflow_dispatch`)

## Scope Notes

- This task is about trigger and approval behavior for the live runtime workflow.
- It does **not** make the Claude or Codex live suites green.
- It does **not** require branch protection or ruleset changes.
- It should document how `CI-E2E` interacts with the job approvals and secret access.

## Acceptance Criteria

1. `Runtime Live E2E` triggers on `pull_request` and still supports `workflow_dispatch` unless implementation finds a concrete incompatibility.
   - Test: inspect `.github/workflows/runtime-live-e2e.yml` trigger block and confirm both paths are wired, or that any removed path is explicitly justified in the task/report.
2. Both `claude-live` and `codex-live` reference `environment: CI-E2E`.
   - Test: inspect the workflow job definitions and confirm the environment field is present on both jobs.
3. The provenance/preflight step works for both trigger paths and resolves the correct PR number without requiring `workflow_dispatch` inputs on a PR-triggered run.
   - Test: inspect the workflow logic and focused static tests for event-specific PR-number resolution.
4. The docs explain the new operator flow: PR opens -> runtime jobs appear -> GitHub blocks them pending `CI-E2E` review -> approved reviewer releases the jobs.
   - Test: inspect `tests/README.md` and confirm the described flow matches the workflow.
5. Existing static workflow checks for `runtime-live-e2e.yml` are updated so the repo has offline coverage for the trigger/environment logic.
   - Test: run the targeted offline tests covering workflow structure and helper logic.

## Test Plan

- Workflow-structure inspection: verify trigger block, environment fields, and provenance logic for both event types. Cost/complexity: low. No E2E required.
- Focused offline tests: update/add static tests for the PR-trigger and `CI-E2E` environment wiring. Cost/complexity: low-medium. No E2E required.
- Optional GitHub smoke after merge: open or reuse a PR and confirm the runtime workflow appears on the PR and waits for `CI-E2E` approval before the live jobs run. Cost/complexity: medium. E2E required: yes, but not required to finish implementation in this cycle.
