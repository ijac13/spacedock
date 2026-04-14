---
id: 146
title: "Release-branch runtime live E2E matrix parameterization"
status: backlog
source: "CL direction during 2026-04-13 session — keep PR live CI on fixed defaults, but allow manual/release full-matrix runtime runs"
score: 0.61
started:
completed:
verdict:
worktree:
issue: #89
pr:
---

## Problem Statement

Task 145 moved the runtime live suite onto PRs with environment-backed approvals and split Claude/Codex environments. That gives operators a good default CI path, but it is intentionally fixed: the PR-triggered workflow runs the default jobs only, and the environment approval UI cannot collect `workflow_dispatch` inputs such as model overrides or matrix selection.

We still need an operator-friendly way to run broader live validation for release branches and targeted manual checks without weakening the default PR path. That follow-up should add dispatch-time parameterization for manual runs while keeping ordinary PR CI simple and stable.

## Recommended Approach

Keep the `pull_request` path opinionated and fixed. Extend `workflow_dispatch` so manual/API-triggered runs can request a broader runtime matrix for release validation.

The likely control surface is:

1. target PR/ref selection
2. default vs full-matrix mode
3. optional Claude model override
4. optional Codex model override
5. any additional release-only axes the live suite needs

Those values should be provided when the workflow is dispatched. Environment approval remains a separate release gate for the already-configured jobs and should not be treated as an input form.

## Scope Notes

- This task is about dispatch-time parameterization for manual and release-branch live runs.
- It should not change the default PR-triggered job set for ordinary pull requests.
- It should document the operator flow clearly: dispatch with inputs, approve the relevant environments, then inspect per-job artifacts and results.
- It may require plumbing model inputs through the current Codex and Claude live test entrypoints so overrides actually reach the invoked runtime.

## Acceptance Criteria

1. Ordinary PR-triggered runs keep the current default runtime jobs and do not require new inputs.
   - Test: inspect `.github/workflows/runtime-live-e2e.yml` and confirm the `pull_request` path still runs the default jobs with no extra operator input required.
2. `workflow_dispatch` supports explicit inputs for manual/release live runs, including matrix selection and optional runtime/model overrides.
   - Test: inspect the workflow input block and confirm the dispatched jobs derive their runtime configuration from those inputs.
3. The workflow documentation explains that `workflow_dispatch` inputs are supplied at run creation time, not at environment approval time.
   - Test: inspect `tests/README.md` and confirm the operator caveat is documented.
4. The live test entrypoints actually honor any new manual/runtime override inputs that the workflow exposes.
   - Test: inspect the relevant test scripts/helpers and run targeted offline checks to confirm the workflow wiring matches the harness CLI surface.
5. The repo keeps offline coverage for the workflow structure and dispatch-time parameter logic.
   - Test: run the targeted workflow/helper tests covering the added input surface.

## Test Plan

- Workflow-structure inspection: verify the fixed `pull_request` path remains unchanged while `workflow_dispatch` gains the intended parameter surface. Cost/complexity: low. No E2E required.
- Focused offline tests: update workflow/helper tests for the new input block and any runtime-argument plumbing. Cost/complexity: medium. No E2E required.
- Manual release-path smoke: dispatch the workflow with a non-default matrix/model configuration and confirm the resulting jobs reflect the requested inputs before approval. Cost/complexity: medium. E2E required: yes, but only for final validation.
