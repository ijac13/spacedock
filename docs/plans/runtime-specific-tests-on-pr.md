---
id: 134
title: "Runtime-specific tests on PR when necessary"
status: validation
source: "CL direction during 2026-04-11 session — need a way to run live/E2E tests on PRs that change FO behavior, without burning API time on every PR"
score: 0.75
worktree: .worktrees/spacedock-ensign-runtime-specific-tests-on-pr
started: 2026-04-13T18:01:05Z
completed:
verdict:
issue:
pr:
---

## Problem Statement

Live E2E coverage for first-officer/runtime behavior still depends on somebody remembering to run expensive `claude -p` or `codex exec` scripts by hand. That is already letting regressions sit on `main`: the seed recorded live failures in `test_scaffolding_guardrail.py`, `test_rejection_flow.py`, `test_feedback_keepalive.py`, and `test_dispatch_completion_signal.py`; fresh Codex runs on 2026-04-13 added that `test_gate_guardrail.py --runtime codex` passed, `test_rejection_flow.py --runtime codex` passed with a bounded timeout warning, `test_merge_hook_guardrail.py --runtime codex` failed, and `tests/test_codex_packaged_agent_e2e.py` failed.

Task 134 should not respond by running every live test on every PR. The captain wants one secret-bearing GitHub workflow that a maintainer manually triggers only after PR approval. The v1 design therefore needs to stay deliberately simple: manual invocation is the trust decision, the workflow result must make that trust/provenance obvious, and the live suite must be split only by runtime rather than by path classifier or fine-grained shard logic. Per captain clarification on 2026-04-13, this implementation cycle ships that manual CI infrastructure first; current Claude-side and Codex-side live failures remain follow-up suite work that the workflow should expose honestly rather than hide.

## Recommended Approach

Add one manual GitHub Actions workflow, `.github/workflows/runtime-live-e2e.yml`, triggered by `workflow_dispatch`. A maintainer runs it after the PR has been approved and the always-on static workflow from task 133 is already green.

The workflow takes `pr_number` as its required input and runs exactly two live jobs:

1. `claude-live`
2. `codex-live`

Each job begins with one lightweight provenance step that queries the PR metadata with `GITHUB_TOKEN` and writes a visible summary block to the job summary and final workflow result. That provenance block must include at least:

- PR number
- tested workflow SHA
- current PR head SHA at run time
- whether the PR branch is same-repo or fork
- approval context used to justify the manual run, including reviewer login(s) or an explicit `none recorded` result

This is intentionally operator-visible rather than policy-heavy. The goal is not to build a large custom approval gate; the goal is that anyone looking at the workflow result can immediately tell which PR and SHA were tested and what approval context existed when the maintainer chose to spend secrets.

The documented invocation should be either the Actions UI on the PR branch or `gh workflow run runtime-live-e2e.yml --ref <pr-branch> -f pr_number=<N>`.

## Trigger Options Considered

### Recommended: `workflow_dispatch` after approval

- Manual and explicit, which matches the captain's requirement.
- Standard GitHub check/run UI, plus easy CLI reruns via `gh workflow run`.
- Secrets stay out of automatic `pull_request` jobs.
- Provenance can be surfaced in the workflow result without inventing another approval mechanism.

### Alternative 1: `pull_request_review` on `approved`

- Rejected for this task.
- It is automatic, not manual.
- Approval-state churn makes reruns awkward.
- It would spend secrets as a side effect of review state rather than as an explicit maintainer action.

### Alternative 2: label or slash-command trigger

- Plausible follow-up if PR-local ergonomics become important.
- Still manual, but adds more state and parsing machinery than this task needs.
- If the repo later wants `/run-live-e2e`, it should dispatch the same workflow rather than replace it.

## Secrets and Approval Model

The captain must configure GitHub repository secrets for the runtime keys used by CI:

- `ANTHROPIC_API_KEY` for Claude `claude -p` jobs.
- `OPENAI_API_KEY` for Codex `codex exec` jobs.

`claude-live` gets only `ANTHROPIC_API_KEY`. `codex-live` gets only `OPENAI_API_KEY`. `GITHUB_TOKEN` with read access to `contents` and `pull-requests` is sufficient for PR metadata lookup and provenance reporting.

Budget enforcement should be runtime-specific:

- Claude jobs should keep using the existing per-test `--max-budget-usd` caps already present in the live scripts, plus job-level `timeout-minutes`.
- Codex jobs should use job-level `timeout-minutes`. The current local `codex exec --help` surface does not expose a repo-standard dollar-budget flag analogous to Claude's `--max-budget-usd`, so this task should not invent one.

Fork handling does not need special v1 policy beyond visible provenance. The workflow summary should say whether the PR branch was same-repo or fork so the trust decision is inspectable after the fact.

## Live Suite Scope

Phase 1 should keep the suite simple: one Claude live job and one Codex live job. The maintainer decides when the whole workflow is worth running; the workflow does not auto-select subsets based on changed files.

### `claude-live` job

Run the in-scope Claude live tests:

- `unset CLAUDECODE && uv run tests/test_gate_guardrail.py --runtime claude`
- `unset CLAUDECODE && uv run tests/test_rejection_flow.py --runtime claude`
- `unset CLAUDECODE && uv run tests/test_scaffolding_guardrail.py`
- `unset CLAUDECODE && uv run tests/test_feedback_keepalive.py`
- `unset CLAUDECODE && uv run tests/test_dispatch_completion_signal.py`
- `unset CLAUDECODE && uv run tests/test_merge_hook_guardrail.py --runtime claude`
- `unset CLAUDECODE && uv run tests/test_push_main_before_pr.py`
- `unset CLAUDECODE && uv run tests/test_rebase_branch_before_push.py`

### `codex-live` job

Run the in-scope Codex live tests:

- `uv run tests/test_gate_guardrail.py --runtime codex`
- `uv run tests/test_rejection_flow.py --runtime codex`
- `uv run tests/test_merge_hook_guardrail.py --runtime codex`

## Current Live Suite Status Follow-Up

These failures remain important current-suite signals, but they are not implementation blockers for shipping the manual `workflow_dispatch` infrastructure in this cycle. Once the workflow is in place, they should surface as honest red `claude-live` or `codex-live` jobs until follow-up work fixes them.

1. **`test_scaffolding_guardrail.py` false positive**. Tighten the write-detection heuristic so read-only `Bash` probes such as `ls`, `cat`, `head`, `tail`, `grep`, `find`, `file`, `stat`, and `wc` do not count as scaffolding writes, while `Write`, `Edit`, `NotebookEdit`, and shell writes still do.

2. **`test_rejection_flow.py` timeout ambiguity**. The test must stop treating a timeout as a soft warning that still prints `PASS`. The implementation can raise the timeout, shrink the fixture, or adjust runtime/model defaults, but the terminal outcome must be an actual pass or fail in both runtimes.

3. **`test_feedback_keepalive.py` stale reference path**. Update the reference lookup to the post-task-076 location under `skills/first-officer/references/`, and fix the matching stale references in `scripts/test-harness.md` in the same implementation pass if those files remain coupled.

4. **`test_merge_hook_guardrail.py --runtime codex` current red state**. Fresh 2026-04-13 Codex runs showed this test failing while `gate_guardrail` and `rejection_flow` already reached bounded outcomes. This remains follow-up suite work after the manual PR check infrastructure lands.

5. **`test_dispatch_completion_signal.py` Claude regression**. Keep this in the manual suite because the seed's current failure is on the Claude team-mode completion-signal contract. A runtime preflight `SKIP` is acceptable only when the test's own Claude-availability probe fires before FO dispatch.

## Out of Scope

- Static/offline CI. Task 133 already owns the always-on `pull_request` check.
- `tests/test_codex_packaged_agent_e2e.py`. Today's failure is real evidence that the Codex packaged-agent path needs work, but it belongs to the Codex packaged-agent pipeline, not this shared FO/runtime PR gate.
- Runtime-impact classifiers, path-based sharding, or a separate `merge-and-pr-mods` lane. The maintainer decides when to run the workflow; the workflow does not auto-triage which suite to run.
- Elaborate trust-policy automation, `pull_request_target`, or a custom slash-command bot. The v1 trust decision is the human-triggered run plus the visible provenance block.

## Acceptance Criteria

1. A manual workflow exists at `.github/workflows/runtime-live-e2e.yml` and is invoked via `workflow_dispatch` after PR approval, not automatically on every `pull_request`.
   - Test: inspect the workflow trigger block and `tests/README.md`; confirm the documented run path is manual and approval-gated.
2. The workflow runs exactly two live jobs, `claude-live` and `codex-live`, with no path classifier and no extra shard selection logic.
   - Test: inspect the workflow job list and command steps; confirm there are only the two runtime jobs plus any lightweight setup/provenance steps they need.
3. The workflow result makes run provenance obvious by surfacing PR number, tested workflow SHA, current PR head SHA, same-repo vs fork status, and approval/reviewer context in the job summary or check summary.
   - Test: manually run the workflow on an approved PR and inspect the summary text for those fields.
4. CI secrets are explicit and minimal: `ANTHROPIC_API_KEY` is used only by `claude-live`, `OPENAI_API_KEY` only by `codex-live`, and each job fails clearly if its required secret is absent.
   - Test: inspect workflow `env` / step wiring and confirm missing-secret handling is explicit.
5. The command inventory matches this spec's two runtime suites: the Claude job runs the eight listed Claude tests, and the Codex job runs the three listed Codex tests.
   - Test: inspect the workflow commands and compare them to the lists in `Live Suite Scope`.
6. The workflow reports current live-suite failures honestly: if a Claude or Codex live test fails, the corresponding runtime job/check goes red with no soft-warning-pass path. Making the suites green is follow-up work after this infrastructure lands, not an implementation blocker for this cycle.
   - Test: inspect the workflow shell steps and docs; confirm the jobs run with `set -euo pipefail`, there is no warning-only wrapper or `continue-on-error`, and the docs/report describe current suite failures as follow-up status.
7. `tests/README.md` documents the manual approval/run procedure, the two-job suite structure, the required repo secret names, and the provenance fields operators should expect in the workflow result.
   - Test: inspect the README text and confirm it matches the workflow inputs and visible summary fields.

## Test Plan

- **Workflow structure review**: inspect the YAML and confirm `workflow_dispatch`, `pr_number` input, exactly two live jobs, and provenance-summary steps in both jobs. Cost/complexity: low. No E2E required.
- **Manual positive smoke**: run `Runtime Live E2E` on one approved PR and verify the workflow result shows the PR number, tested SHA, current PR head SHA, same-repo/fork status, and approval/reviewer context before or alongside the live test results. Cost/complexity: medium. E2E required: yes, one GitHub Actions run.
- **Negative cases worth keeping in v1**:
  - Missing secret handling: verify by inspection that each runtime job checks for its required secret and fails clearly if it is not configured. Cost/complexity: low. No extra E2E required.
  - Red-suite behavior: when a live test fails, the corresponding runtime job/check must go red rather than reporting a soft warning pass. Cost/complexity: medium. E2E required: yes, covered by the live regression runs below.
- **Live suite status after the infrastructure lands**:
  - `claude-live`: medium-high cost, real Anthropic spend, useful for measuring the current Claude suite once the manual workflow is available.
  - `codex-live`: medium cost, real OpenAI spend, useful for measuring the current Codex suite once the manual workflow is available.
  E2E required: yes for follow-up suite-status and greening work, but not as a blocker on shipping the manual workflow/docs/provenance/secrets wiring in this implementation cycle.

## Captain Clarification (2026-04-13)

Task 134 implementation completes when the manual `workflow_dispatch` infrastructure ships with exactly two runtime jobs, runtime-scoped secrets, and visible provenance in the workflow result. Current Claude-side and Codex-side live test failures remain known follow-up work and current suite status. The workflow must surface those failures honestly as red jobs/checks; it does not need to make the suites green in this cycle.

## Related

- **Task 133** (`ci-static-tests-and-known-failures`, shipped as PR #79) owns always-on static CI; this task layers the manual live gate on top of it.
- **Task 117** (`fo-idle-guardrail-flake-on-haiku`) remains related because `test_dispatch_completion_signal.py` and `test_rejection_flow.py` both exposed Claude-runtime timing sensitivity, but this task owns the PR-gating policy and the remaining bounded-outcome requirement.
- **Task 076** (`plugin-shipped-agents`) is the source of the moved reference path that broke `test_feedback_keepalive.py`.

## Stage Report: ideation

- [x] Expand the entity body into a clear problem statement and scope that reflects the captain's manual-trigger-on-approval requirement.
  Added Problem Statement, Recommended Approach, Live Suite Scope, and Out of Scope sections centered on a manual `workflow_dispatch` check after PR approval.
- [x] Evaluate concrete trigger/approval options and recommend one, including how GitHub checks/workflows would be invoked and how repo secrets should be managed for CI API keys.
  Compared `workflow_dispatch`, `pull_request_review`, and label/comment flows; recommended `workflow_dispatch` plus preflight with `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`.
- [x] Refine acceptance criteria so each is testable and aligned with the chosen manual-trigger mechanism and secrets setup.
  Replaced the seed acceptance criteria with seven criteria, each paired with an explicit inspection or smoke-test method.
- [x] Write a proportional test plan covering workflow behavior, secrets/config expectations, and live-test execution boundaries.
  Added low/medium/high cost guidance, manual positive and negative smoke runs, and shard-specific E2E expectations.
- [x] Keep scope tight: static tests stay out of scope; be explicit about which live suites/runtimes are in scope and why.
  Scoped phase 1 to `claude-core`, `codex-core`, and `merge-and-pr-mods`, and explicitly excluded static CI, fork PR secrets, and `tests/test_codex_packaged_agent_e2e.py`.
- [x] Append an ideation stage report at the end of the entity file with DONE/SKIPPED/FAILED coverage for every checklist item.
  This appended section covers all seven dispatch checklist items with status and evidence lines.
- [x] Commit the ideation work on the current branch before sending your completion message.
  The entity update was prepared with the required stage report and committed on the current branch after review.

### Summary

The task now recommends a manual `workflow_dispatch` live-E2E check that runs only after PR approval and only for runtime-impacting changes. It names the required repo secrets, narrows the live suite to three explicit shards, and records the remaining known failures that must be cleared before the manual check is trusted.

## Stage Report: ideation (cycle 2)

- [x] Revise the recommendation to keep one manual `workflow_dispatch` workflow run after PR approval.
  Rewrote the top-level approach so the captain's manual-after-approval trigger is the core design, not a path-triggered classifier flow.
- [x] Remove the runtime-impact classifier and extra shard design from the spec.
  Deleted the runtime-impact path map and replaced the shard model with exactly two runtime jobs: `claude-live` and `codex-live`.
- [x] Make trust/provenance visible in the workflow result without adding heavy policy machinery.
  The spec now requires each runtime job to surface PR number, tested SHA, current PR head SHA, same-repo/fork status, and approval/reviewer context in the run summary.
- [x] Keep the secrets model simple and tied to the two runtime jobs only.
  `ANTHROPIC_API_KEY` is scoped to `claude-live`; `OPENAI_API_KEY` is scoped to `codex-live`; no separate classifier job is described.
- [x] Rework acceptance criteria to match the simplified two-job design.
  Replaced classifier/shard criteria with criteria for `workflow_dispatch`, two jobs only, visible provenance, runtime-scoped secrets, and fixed test inventories.
- [x] Rework the test plan so it matches the simplified design and keeps only the negative cases that still matter.
  Dropped docs-only/path-classifier smoke cases and kept positive smoke, missing-secret handling, and red-suite behavior as the relevant negative coverage.
- [x] Append a new ideation stage report for this rejection/revision cycle at the end of the entity file.
  This `cycle 2` section is appended after the prior ideation report rather than replacing it.
- [x] Commit the revised ideation work before reporting completion.
  The revised entity was verified and committed on the current branch after this cycle's updates.

### Summary

The revised ideation spec now matches the captain's simpler trust model: a maintainer manually runs one live-E2E workflow after approval, and the workflow result itself shows enough provenance to justify the secret-bearing run. The suite design is reduced to two runtime jobs, and the acceptance criteria/test plan were rewritten to remove the discarded classifier and sharding logic.

## Stage Report: implementation

Captain clarification (2026-04-13): this implementation cycle ships the manual `workflow_dispatch` infrastructure first. Current Claude-side and Codex-side live-suite failures remain follow-up work and current suite status. The workflow is expected to surface those failures honestly as red jobs; fully green live suites are not required for implementation completion here.

- DONE: Implement `.github/workflows/runtime-live-e2e.yml` with manual `workflow_dispatch` and exactly the two runtime jobs/checks described above.
  Added `claude-live` and `codex-live` only, with the command inventories defined in `Live Suite Scope` and no path classifier or extra shard lane.
- DONE: Make provenance visible in the workflow/job summaries without adding unnecessary extra lanes/checks.
  Both jobs write PR number, tested workflow SHA, current PR head SHA, branch source, and approval context to the job summary via `actions/github-script`.
- DONE: Scope secrets to the right jobs and make missing-secret failure clear.
  `ANTHROPIC_API_KEY` is wired only into `claude-live`; `OPENAI_API_KEY` only into `codex-live`; each job fails immediately if its required secret is absent.
- DONE: Update `tests/README.md` to document the manual run procedure, secret names, two-job structure, provenance expectations, and honest-red suite-status behavior.
  Added a `Manual PR Runtime Live E2E` section with the `gh workflow run` example and explicit operator expectations for provenance plus red job behavior.
- SKIPPED: Fix the known live blockers that are in scope for this task.
  Captain clarification moved both Claude-side and Codex-side live failures out of the implementation blocker set for task 134. Clearing those failures is follow-up suite work after the workflow ships.
- DONE: Run proportional verification using the repo's documented entrypoints and focused checks; record concrete evidence.
  Verified the workflow/docs wiring with `unset CLAUDECODE && uv run --with pytest python -m pytest tests/test_ci_static_workflow.py tests/test_test_lib_helpers.py tests/test_runtime_live_e2e_workflow.py -q` and kept the implementation focused on infrastructure rather than requiring live-suite greening.
- DONE: Append an implementation stage report at the end of the entity file with DONE/SKIPPED/FAILED coverage for every checklist item.
  This section records the delivered infrastructure, the captain clarification, and the deferred follow-up scope.
- DONE: Commit the implementation work in the assigned worktree before replying.
  Committed on the assigned worktree branch after the final workflow/docs verification pass for this changeset.
