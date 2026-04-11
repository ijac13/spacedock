---
id: 133
title: "CI for static tests + track known static failures"
status: validation
source: "CL direction during 2026-04-11 session — session discovered static test regression that slipped through PR #74 merge because no CI ran test_agent_content.py"
score: 0.80
worktree:
started: 2026-04-11T20:57:12Z
completed:
verdict:
issue:
pr: #79
---

## Problem Statement

Static tests in this repo only run when a human or a dispatched ensign remembers to invoke them. That gap already caused a real regression: task 129 changed `docs/plans/_mods/pr-merge.md` so the literal string `"Workflow entity: {entity title}"` was removed, but `tests/test_agent_content.py` still asserted that string existed. The 129 PR ran its own new template test and its status-script regression suite, while `test_agent_content.py` was never included, so the contradiction landed on main without any PR-level signal.

Task 117 (`fo-idle-guardrail-flake-on-haiku`) already absorbed the specific `test_agent_content.py` repair into its scope, with commit `6bc5a90` noted as the landing point. This task should not duplicate that fix. Its job is to close the structural gap so always-on static CI catches this class of mismatch after the 117 baseline is green.

## Proposed Approach

### Recommended approach

Add one GitHub Actions workflow, `.github/workflows/ci-static.yml`, that runs on every PR targeting `main` and executes the repo's documented offline static suite entry point in one job: `uv run --with pytest python -m pytest tests/ --ignore=tests/fixtures -q`. Keep the job boring: check out the repo, install Python and `uv`, run that single stable command, and fail the PR if it returns non-zero. This is the smallest change that gives a reliable PR gate without redesigning the broader test harness or hard-coding a fragile file list in CI.

### Alternative 1

Split the workflow into two jobs: one for the faster unittest-style files and one for the pytest-style files. This gives more granular logs, but it adds orchestration complexity without changing the actual coverage.

### Alternative 2

Create a more general test matrix that mixes static and runtime tests. That would solve more of the workflow space, but it is the wrong size for this task and would blur the boundary with the sibling runtime-specific PR test work.

## Static Test Scope

The always-on PR check should cover only tests that do not require live `claude -p`, `codex exec`, or `InteractiveSession` subprocesses. The stable repo-level entry point for that scope is the offline suite documented in `scripts/test-harness.md`:

```bash
uv run --with pytest python -m pytest tests/ --ignore=tests/fixtures -q
```

This task should rely on that documented entry point rather than freezing today's set of collected files into workflow YAML. Validation can still spot-check representative offline coverage such as `tests/test_pr_merge_template.py`, `tests/test_status_script.py`, `tests/test_stats_extraction.py`, `tests/test_status_set_missing_field.py`, `tests/test_codex_packaged_agent_ids.py`, `tests/test_claude_team.py`, and `tests/test_agent_content.py`, but the CI contract should stay at the repo-entry-point level.

## Scope Boundaries

- In scope: the PR workflow for always-on static tests, the exact invocation commands for the seven static files, and the dependency on task 117 landing first.
- In scope: a small, explicit note in the task body that known static failures must be cleared before the workflow becomes a required gate.
- Out of scope: runtime/live E2E coverage, any `claude -p` or `codex exec` subprocess tests, and any broader redesign of the test harness or dispatch system.
- Out of scope: adding a permanent skip list or flaky-test suppression mechanism. This task assumes the static suite should be green before CI is enabled.

## Known Failure Handling

"Known failures" are rollout policy only for this task, not an allowlist or suppression mechanism. The stale `test_agent_content.py` assertion discussed in ideation was already absorbed by task 117 and landed with merge commit `bbc3b1e` (PR #78), after scope note `6bc5a90` folded that repair into 117. The rollout order is therefore:

1. Confirm the 117 baseline is on the branch and the offline static suite is green locally.
2. Enable the PR workflow with the documented offline suite command.
3. Treat any future offline-suite failure as a blocking CI failure until fixed.

If the 117 baseline were absent on a target branch, the correct action would be to delay rollout rather than add a permanent exception.

## Acceptance Criteria

1. A GitHub Actions workflow exists at `.github/workflows/ci-static.yml` or an equivalent path and triggers on pull requests targeting `main`.
   - Test: inspect the workflow trigger block and confirm `pull_request` includes `main`.
2. The workflow runs the documented repo-level offline suite entry point `uv run --with pytest python -m pytest tests/ --ignore=tests/fixtures -q` and does not invoke live runtime test paths.
   - Test: inspect the workflow command and confirm it does not mention `run_first_officer`, `run_codex_first_officer`, or `InteractiveSession`.
3. The workflow is blocking: if the offline suite returns non-zero, the PR job fails.
   - Test: inspect the workflow and confirm there is no `continue-on-error` or non-blocking exception mechanism around the offline suite step.
4. The task 117 baseline is treated as a prerequisite rollout condition, not as a permanent exception.
   - Test: confirm the spec and implementation notes state that CI enablement depends on the 117 baseline being present and the static suite being green first.
5. The implementation keeps scope narrow and does not add runtime/live test orchestration, a file allowlist, or a broader test-infra redesign.
   - Test: inspect the workflow diff and confirm the only new behavior is the static PR gate and its associated command.

## Test Plan

- Local static verification: run `uv run --with pytest python -m pytest tests/ --ignore=tests/fixtures -q` on the implementation branch and confirm the offline suite is green.
- Focused red/green verification: add an offline test that fails when `.github/workflows/ci-static.yml` is missing or wired to the wrong command, then rerun it after the workflow exists.
- Workflow syntax and trigger check: inspect the YAML for the PR trigger, job name, and command. This is a cheap static review, not an E2E test.
- Manual smoke path: optional follow-up on a draft PR by temporarily breaking an offline test and confirming the CI job turns red, then restoring it.
- No E2E tests are required for this task. The deliverable is CI plumbing plus the policy that static regressions must block merge.

## Related

- **Task 117** (`fo-idle-guardrail-flake-on-haiku`) is the prerequisite baseline because it carries the current `test_agent_content.py` fix.
- **Task 129** (`pr-mod-tighten-body-template`, already shipped as PR #74) exposed the gap by changing the template without having `test_agent_content.py` in the validation set.
- **Task 134** (`runtime-specific-tests-on-pr`, sibling) should own the runtime/live PR test path; this task should stay limited to always-on static coverage.

## Stage Report: ideation

- [x] Expand the task body into a proper ideation spec for static-test CI and known-failure handling.
  Rewritten with Problem Statement, Proposed Approach, Known Failure Handling, Acceptance Criteria, and Test Plan sections.
- [x] Clarify scope boundaries between always-on static CI and sibling runtime/live test coverage.
  Added explicit in-scope and out-of-scope bullets and excluded live subprocess tests.
- [x] Refine acceptance criteria so they are concrete, testable, and reflect dependency on task 117 landing first.
  Acceptance criteria now name the workflow path, the seven files, the fail condition, and the 117 prerequisite.
- [x] Produce a proportional test plan for the CI workflow itself, including one manual smoke verification path.
  Test plan covers local static runs, YAML inspection, and a deliberate stale-assertion smoke test.
- [x] Keep the task narrowly focused on static CI and known static failures, not broader test infrastructure redesign.
  Proposed approach explicitly rejects broader matrix/runtime redesign and avoids a skip-list design.
- [x] Append a complete `## Stage Report` for ideation at the end of the entity file, with every checklist item marked DONE, SKIPPED, or FAILED.
  This section is appended at the end of the entity body and uses only `[x]` checklist items.
- [x] Commit the ideation work before reporting completion.
  Committed as `b04101d` after the document update.

### Summary

The task body now describes a narrow always-on static CI gate for PRs to `main`, with the current `test_agent_content.py` fix explicitly delegated to task 117 first. The spec stays out of runtime/live test redesign and defines a concrete smoke test for the workflow itself. No runtime tests were run in ideation; the deliverable here is the reviewed spec text.

## Stage Report: implementation

- DONE: Implement the narrow CI change for static/offline tests in the assigned worktree.
  Added `.github/workflows/ci-static.yml` to run on `pull_request` to `main` and execute the documented offline suite command in one blocking job.
- DONE: Align the entity body/report with the captain-approved interpretation above so validation has the right target.
  Rewrote the implementation target around the stable repo-level offline suite entry point, removed the stale seven-file CI framing, and clarified that "known failures" are rollout policy only.
- DONE: Use the stable offline-suite entry point if it is the correct repo-level command; if you discover a better stable entry point, justify it in the report.
  Used `uv run --with pytest python -m pytest tests/ --ignore=tests/fixtures -q` exactly as documented in `scripts/test-harness.md`. I did not find a better repo-level entry point.
- DONE: Keep scope narrow: no live runtime tests, no allowlist/suppression system, no unrelated refactors.
  The workflow runs one offline command only. The only supporting code changes were to make the documented offline suite itself green: refresh the stale PR-template assertion in `tests/test_agent_content.py` and stop pytest from auto-collecting the live PTY proof-of-concept path in `tests/test_interactive_poc.py`.
- DONE: Run the relevant local verification for the implementation and report concrete results.
  Red phase: `unset CLAUDECODE && uv run --with pytest python -m pytest tests/test_ci_static_workflow.py -q` failed with 3 failures because `.github/workflows/ci-static.yml` did not exist.
  Green phase: the same focused command passed with `3 passed in 0.01s`.
  Focused regression rerun: `unset CLAUDECODE && uv run --with pytest python -m pytest tests/test_agent_content.py tests/test_interactive_poc.py tests/test_ci_static_workflow.py -q` passed with `31 passed, 1 warning in 0.05s`.
  Full offline suite: `unset CLAUDECODE && uv run --with pytest python -m pytest tests/ --ignore=tests/fixtures -q` passed with `179 passed, 19 warnings in 3.87s`.
- DONE: Append a `## Stage Report: implementation` section to the entity file with every checklist item represented as DONE, SKIPPED, or FAILED.
  This section is appended at the end of the entity file.
- DONE: Commit your work in the worktree before reporting completion.
  Worktree changes were committed before the completion message for this stage.

## Stage Report: validation

- [x] Read the entity body, including acceptance criteria and implementation report.
  Reviewed this entity's Problem Statement, Acceptance Criteria, Test Plan, and implementation report in the assigned worktree before validating.
- [x] Inspect the actual implementation diff and confirm scope stayed narrow.
  `git show --stat a42ac0f` and diff inspection showed the implementation commit touches only `.github/workflows/ci-static.yml`, `tests/test_ci_static_workflow.py`, `tests/test_agent_content.py`, `tests/test_interactive_poc.py`, and this entity file; no runtime/live orchestration was added.
- [x] Run the applicable validation commands for this task and record concrete outcomes.
  Spot-check: `unset CLAUDECODE && uv run --with pytest python -m pytest tests/test_ci_static_workflow.py -q` -> `3 passed in 0.01s`; focused support checks: `... pytest tests/test_agent_content.py tests/test_interactive_poc.py tests/test_ci_static_workflow.py -q` -> `31 passed, 1 warning in 0.04s`; full offline suite: `... pytest tests/ --ignore=tests/fixtures -q` -> `179 passed, 19 warnings in 3.79s`.
- [x] Verify each acceptance criterion with evidence and give a PASSED or REJECTED recommendation.
  AC1-3 pass because `.github/workflows/ci-static.yml` triggers on `pull_request` to `main`, runs `uv run --with pytest python -m pytest tests/ --ignore=tests/fixtures -q`, and contains no `continue-on-error`; AC4 passes because the entity body treats task 117 / merge `bbc3b1e` as a prerequisite baseline and `git merge-base --is-ancestor bbc3b1e HEAD` returned `yes`; AC5 passes because the workflow adds only the static PR gate and the two supporting test-file changes are limited to making the offline suite green. Recommendation: PASSED.
- [x] Append a `## Stage Report: validation` section to the entity file with every checklist item represented as DONE, SKIPPED, or FAILED.
  This validation section is appended at the end of the entity body in the assigned worktree.
- [x] Commit the validation report in the worktree before reporting completion.
  The validation report commit follows this file update in the assigned worktree.

### Summary

Validation was performed against the assigned worktree only. The implementation satisfies the documented acceptance criteria, the scope stayed limited to a blocking offline static PR gate plus minimal offline-suite fixes, and the relevant offline test commands all passed locally. Verdict: PASSED.
