---
id: 133
title: "CI for static tests + track known static failures"
status: implementation
source: "CL direction during 2026-04-11 session — session discovered static test regression that slipped through PR #74 merge because no CI ran test_agent_content.py"
score: 0.80
worktree: .worktrees/spacedock-ensign-ci-static-tests-and-known-failures
started: 2026-04-11T20:57:12Z
completed:
verdict:
issue:
pr:
---

## Problem Statement

Static tests in this repo only run when a human or a dispatched ensign remembers to invoke them. That gap already caused a real regression: task 129 changed `docs/plans/_mods/pr-merge.md` so the literal string `"Workflow entity: {entity title}"` was removed, but `tests/test_agent_content.py` still asserted that string existed. The 129 PR ran its own new template test and its status-script regression suite, while `test_agent_content.py` was never included, so the contradiction landed on main without any PR-level signal.

Task 117 (`fo-idle-guardrail-flake-on-haiku`) already absorbed the specific `test_agent_content.py` repair into its scope, with commit `6bc5a90` noted as the landing point. This task should not duplicate that fix. Its job is to close the structural gap so always-on static CI catches this class of mismatch after the 117 baseline is green.

## Proposed Approach

### Recommended approach

Add one GitHub Actions workflow, `.github/workflows/ci-static.yml`, that runs on every PR targeting `main` and executes the complete static test set in one job. Keep the job boring: check out the repo, install dependencies once, run the seven static test files in a fixed order, and fail fast if any command fails. This is the smallest change that gives a reliable PR gate without redesigning the broader test harness.

### Alternative 1

Split the workflow into two jobs: one for the faster unittest-style files and one for the pytest-style files. This gives more granular logs, but it adds orchestration complexity without changing the actual coverage.

### Alternative 2

Create a more general test matrix that mixes static and runtime tests. That would solve more of the workflow space, but it is the wrong size for this task and would blur the boundary with the sibling runtime-specific PR test work.

## Static Test Scope

The always-on PR check should cover only tests that do not require live `claude -p`, `codex exec`, or `InteractiveSession` subprocesses:

| Test file | Invocation | Notes |
|---|---|---|
| `tests/test_pr_merge_template.py` | `uv run tests/test_pr_merge_template.py` | Template assertions from task 129. |
| `tests/test_status_script.py` | `uv run tests/test_status_script.py` | Status tool coverage from task 123. |
| `tests/test_stats_extraction.py` | `uv run tests/test_stats_extraction.py` | Static parser coverage. |
| `tests/test_status_set_missing_field.py` | `uv run tests/test_status_set_missing_field.py` | Silent-noop fix coverage from task 122. |
| `tests/test_codex_packaged_agent_ids.py` | `unset CLAUDECODE && uv run --with pytest python -m pytest tests/test_codex_packaged_agent_ids.py -q` | Codex worker-id resolution. |
| `tests/test_claude_team.py` | `unset CLAUDECODE && uv run --with pytest python -m pytest tests/test_claude_team.py -q` | Claude-team helper coverage. |
| `tests/test_agent_content.py` | `unset CLAUDECODE && uv run --with pytest python -m pytest tests/test_agent_content.py -q` | Shared-core / dispatch template assertions. This must be green after task 117 lands. |

## Scope Boundaries

- In scope: the PR workflow for always-on static tests, the exact invocation commands for the seven static files, and the dependency on task 117 landing first.
- In scope: a small, explicit note in the task body that known static failures must be cleared before the workflow becomes a required gate.
- Out of scope: runtime/live E2E coverage, any `claude -p` or `codex exec` subprocess tests, and any broader redesign of the test harness or dispatch system.
- Out of scope: adding a permanent skip list or flaky-test suppression mechanism. This task assumes the static suite should be green before CI is enabled.

## Known Failure Handling

The only known static failure in the current discussion is the stale `test_agent_content.py` assertion that task 117 is already set up to repair. The rollout order is therefore:

1. Let task 117 land and restore a green static baseline.
2. Verify the seven static files pass locally against that baseline.
3. Enable the PR workflow so future regressions fail before merge.

If task 117 has not landed, implementation of this task should pause rather than introduce a required CI check that immediately fails on every PR.

## Acceptance Criteria

1. A GitHub Actions workflow exists at `.github/workflows/ci-static.yml` or an equivalent path and triggers on pull requests targeting `main`.
   - Test: inspect the workflow trigger block and confirm `pull_request` includes `main`.
2. The workflow runs exactly the seven static test files listed in this spec and does not invoke the live runtime test paths.
   - Test: inspect the job steps and command list; confirm the commands match the table above and do not mention `run_first_officer`, `run_codex_first_officer`, or `InteractiveSession`.
3. The workflow fails the PR check if any one of the seven static files fails.
   - Test: manual smoke verification by introducing a deliberate stale assertion or temporary failure in one static file on a draft branch and confirming the CI check turns red.
4. The task 117 baseline is treated as a prerequisite, not as a permanent exception.
   - Test: confirm the spec and implementation notes state that CI enablement waits for task 117 to land and for the static suite to be green first.
5. The implementation keeps the scope narrow and does not add runtime/live test orchestration or a broader test-infra redesign.
   - Test: inspect the workflow diff and confirm the only new behavior is the static PR gate and its associated commands.

## Test Plan

- Local static verification after task 117 lands: run all seven static files using the exact commands listed above. Expected cost is low: one short `uv run` pass plus three short pytest invocations, roughly a few minutes total.
- Workflow syntax and trigger check: inspect the YAML for the PR trigger, job name, and command order. This is a cheap static review, not an E2E test.
- Manual smoke path: on a draft PR, temporarily remove or invert one assertion in a static test file, rerun the workflow, and verify the check fails. Then restore the assertion and verify the check passes again.
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
