---
id: 134
title: "Runtime-specific tests on PR when necessary"
status: ideation
source: "CL direction during 2026-04-11 session — need a way to run live/E2E tests on PRs that change FO behavior, without burning API time on every PR"
score: 0.75
worktree:
started: 2026-04-13T18:01:05Z
completed:
verdict:
issue:
pr:
---

## Problem Statement

Live E2E coverage for first-officer/runtime behavior still depends on somebody remembering to run expensive `claude -p` or `codex exec` scripts by hand. That is already letting regressions sit on `main`: the seed recorded live failures in `test_scaffolding_guardrail.py`, `test_rejection_flow.py`, `test_feedback_keepalive.py`, and `test_dispatch_completion_signal.py`; fresh Codex runs on 2026-04-13 added that `test_gate_guardrail.py --runtime codex` passed, `test_rejection_flow.py --runtime codex` passed with a bounded timeout warning, `test_merge_hook_guardrail.py --runtime codex` failed, and `tests/test_codex_packaged_agent_e2e.py` failed.

Task 134 should not respond by running every live test on every PR. The captain wants a GitHub check that is manually triggered after PR approval. That means the design needs to preserve two constraints at once: reviewers must be able to decide when a PR is worth real model spend, and the resulting check must still be reproducible, documented, and narrow enough that CI secrets are only exposed when a maintainer explicitly opts in.

## Recommended Approach

Add one manual GitHub Actions workflow, `.github/workflows/runtime-live-e2e.yml`, triggered by `workflow_dispatch`. A maintainer runs it only after the PR has at least one GitHub review in the `APPROVED` state and the always-on static workflow from task 133 is already green.

The workflow takes `pr_number` as its required input and uses the GitHub API to resolve the PR head SHA, approval state, and changed-file list before any model job starts. The preflight job uses only the built-in `GITHUB_TOKEN` and enforces these gates:

1. PR targets `main`.
2. PR head branch lives in this repository, not a fork.
3. PR has at least one current approval from someone other than the PR author.
4. Changed files intersect the runtime-impact path map declared by this task.

If any preflight check fails, the workflow exits with a clear summary and does not expose model secrets. If preflight passes, the workflow runs only the live shard(s) selected by the changed files. The documented invocation should be either the Actions UI on the PR branch or `gh workflow run runtime-live-e2e.yml --ref <pr-branch> -f pr_number=<N>`.

## Trigger Options Considered

### Recommended: `workflow_dispatch` after approval

- Manual and explicit, which matches the captain's requirement.
- Standard GitHub check/run UI, plus easy CLI reruns via `gh workflow run`.
- Secrets stay out of automatic `pull_request` jobs.
- The workflow can self-verify approval and path impact before spending tokens.

### Alternative 1: `pull_request_review` on `approved`

- Rejected for this task.
- It is automatic, not manual.
- Approval-state churn makes reruns awkward.
- It would expose model secrets whenever someone approves a matching PR, even if they only meant "looks good" and not "spend live-test budget now."

### Alternative 2: label or slash-command trigger

- Plausible follow-up if PR-local ergonomics become important.
- Still manual, but adds state management (`needs-live-e2e`, comment parsing, actor permission checks, rerun semantics).
- Larger surface area than needed for the first version.
- If we later want `/run-live-e2e` from the PR thread, it should dispatch the same `workflow_dispatch`-style workflow rather than replace the preflight logic.

## Secrets and Approval Model

The captain must configure GitHub repository secrets for the runtime keys used by CI:

- `ANTHROPIC_API_KEY` for Claude `claude -p` jobs.
- `OPENAI_API_KEY` for Codex `codex exec` jobs.

The preflight/classifier job must not receive either secret. Claude jobs get only `ANTHROPIC_API_KEY`; Codex jobs get only `OPENAI_API_KEY`. `GITHUB_TOKEN` with read access to `contents` and `pull-requests` is sufficient for PR metadata lookup and should remain the only token available before shard selection.

Budget enforcement should be runtime-specific:

- Claude jobs should keep using the existing per-test `--max-budget-usd` caps already present in the live scripts, plus job-level `timeout-minutes`.
- Codex jobs should use job-level `timeout-minutes` and a fixed, small shard list. The current local `codex exec --help` surface does not expose a repo-standard dollar-budget flag analogous to Claude's `--max-budget-usd`, so this task should not invent one.

Initial scope stays same-repo PRs only. Fork PR support is out of scope for the first version because the whole point of the manual gate is to avoid automatic secret exposure on untrusted branches.

## Live Suite Scope

Phase 1 of this manual check should cover only the live tests that directly exercise shared FO/runtime behavior or the PR-merge path already implicated by the seed and today's evidence.

### `claude-core` shard

Run when the PR touches shared FO/ensign behavior, Claude runtime wording, or the fixture/test files that own these behaviors:

- `unset CLAUDECODE && uv run tests/test_gate_guardrail.py --runtime claude`
- `unset CLAUDECODE && uv run tests/test_rejection_flow.py --runtime claude`
- `unset CLAUDECODE && uv run tests/test_scaffolding_guardrail.py`
- `unset CLAUDECODE && uv run tests/test_feedback_keepalive.py`
- `unset CLAUDECODE && uv run tests/test_dispatch_completion_signal.py`

### `codex-core` shard

Run when the same PR touches shared FO/ensign behavior or Codex runtime wording:

- `uv run tests/test_gate_guardrail.py --runtime codex`
- `uv run tests/test_rejection_flow.py --runtime codex`

### `merge-and-pr-mods` shard

Run only when the PR touches `mods/pr-merge.md`, `docs/plans/_mods/**`, merge-hook behavior, or the test/fixture files that cover those paths:

- `unset CLAUDECODE && uv run tests/test_merge_hook_guardrail.py --runtime claude`
- `uv run tests/test_merge_hook_guardrail.py --runtime codex`
- `unset CLAUDECODE && uv run tests/test_push_main_before_pr.py`
- `unset CLAUDECODE && uv run tests/test_rebase_branch_before_push.py`

### Runtime-impact path map

Use a checked-in allow-list rather than ad hoc globbing in the workflow body. Phase 1 should treat these path groups as runtime-impacting:

- Shared FO/runtime code: `skills/first-officer/**`, `skills/ensign/**`, `scripts/test_lib.py`
- PR-merge behavior: `mods/pr-merge.md`, `docs/plans/_mods/**`
- In-scope live test files and their fixtures under `tests/test_*` and `tests/fixtures/**` for the shards above

The workflow should skip cleanly when a PR changes only docs, static-only tests, or unrelated repository files.

## Known Live Failures This Task Must Clear

1. **`test_scaffolding_guardrail.py` false positive**. Tighten the write-detection heuristic so read-only `Bash` probes such as `ls`, `cat`, `head`, `tail`, `grep`, `find`, `file`, `stat`, and `wc` do not count as scaffolding writes, while `Write`, `Edit`, `NotebookEdit`, and shell writes still do.

2. **`test_rejection_flow.py` timeout ambiguity**. The test must stop treating a timeout as a soft warning that still prints `PASS`. The implementation can raise the timeout, shrink the fixture, or adjust runtime/model defaults, but the terminal outcome must be an actual pass or fail in both runtimes.

3. **`test_feedback_keepalive.py` stale reference path**. Update the reference lookup to the post-task-076 location under `skills/first-officer/references/`, and fix the matching stale references in `scripts/test-harness.md` in the same implementation pass if those files remain coupled.

4. **`test_merge_hook_guardrail.py --runtime codex` current red state**. Fresh 2026-04-13 Codex runs showed this test failing while `gate_guardrail` and `rejection_flow` already reached bounded outcomes. The manual PR check is not ready until the Codex merge-hook path is green.

5. **`test_dispatch_completion_signal.py` Claude regression**. Keep this in the manual suite because the seed's current failure is on the Claude team-mode completion-signal contract. A runtime preflight `SKIP` is acceptable only when the test's own Claude-availability probe fires before FO dispatch.

## Out of Scope

- Static/offline CI. Task 133 already owns the always-on `pull_request` check.
- `tests/test_codex_packaged_agent_e2e.py`. Today's failure is real evidence that the Codex packaged-agent path needs work, but it belongs to the Codex packaged-agent pipeline, not this shared FO/runtime PR gate.
- Adding every existing live E2E script to CI. This task should stay focused on the shards above, not become a blanket "all E2E on demand" launcher.
- Fork PR secret handling, `pull_request_target`, or a custom slash-command bot. Those can be follow-ups if the first manual workflow proves insufficient.

## Acceptance Criteria

1. A manual workflow exists at `.github/workflows/runtime-live-e2e.yml` and is invoked via `workflow_dispatch` after PR approval, not automatically on every `pull_request`.
   - Test: inspect the workflow trigger block and `tests/README.md`; confirm the documented run path is manual and approval-gated.
2. The workflow performs a secret-free preflight that refuses to start live jobs unless the PR targets `main`, has at least one non-author approval, comes from the same repository, and changes at least one runtime-impact path.
   - Test: inspect the workflow/script logic and manually dry-run it on one approved runtime PR plus one unapproved or docs-only PR.
3. The workflow selects only the declared live shards for the changed paths, and the command list matches this spec's exact test inventory.
   - Test: inspect the shard matrix/command script and exercise representative changed-file sets for `claude-core`, `codex-core`, `merge-and-pr-mods`, and a no-match skip case.
4. CI secrets are explicit and minimal: `ANTHROPIC_API_KEY` is used only by Claude jobs, `OPENAI_API_KEY` only by Codex jobs, and the preflight job uses neither.
   - Test: inspect workflow `env` / step wiring and confirm a selected shard fails early with a clear missing-secret message if its required key is absent.
5. The current live blockers covered by this task are CI-actionable: `test_scaffolding_guardrail.py`, `test_rejection_flow.py`, `test_feedback_keepalive.py`, `test_merge_hook_guardrail.py --runtime codex`, and `test_dispatch_completion_signal.py` all produce bounded pass/fail/explicit-preflight-skip outcomes consistent with this spec.
   - Test: run the relevant local scripts or CI shards and confirm there is no PASS-with-timeout warning path.
6. `tests/README.md` documents the manual approval/run procedure, the required repo secret names, the in-scope shards, and the same-repo-only boundary.
   - Test: inspect the README text and confirm it matches the workflow inputs and shard map.
7. The task remains narrow: static CI stays in task 133, `tests/test_codex_packaged_agent_e2e.py` remains out of scope, and unmatched PRs do not spend live-test tokens.
   - Test: inspect the workflow inputs, command list, and scope notes; confirm docs-only PRs skip before any runtime job starts.

## Test Plan

- **Workflow preflight / classifier checks**: add small deterministic coverage around the PR metadata + path-classification helper (or equivalent shell/script logic). Cost/complexity: low. No E2E required.
- **Manual positive smoke**: open or reuse an approved same-repo PR that touches `skills/first-officer/**` and run `Runtime Live E2E` against that PR. Verify the check lands on the PR head commit, preflight passes, and the expected core shard(s) start. Cost/complexity: medium. E2E required: yes, one GitHub Actions run.
- **Manual negative smoke**: use an approved docs-only PR and run the same workflow. Verify preflight reports "no runtime-impact paths" and exits before model jobs or secrets are used. Cost/complexity: low to medium. E2E required: yes, but negligible model spend because the run should stop before live steps.
- **Live regression verification before enabling the check as a required maintainer tool**:
  - `claude-core` shard: medium-high cost, real Anthropic spend, needed to prove scaffolding/feedback/completion fixes and Claude gate/rejection behavior.
  - `codex-core` shard: medium cost, real OpenAI spend, needed to prove Codex gate/rejection behavior and eliminate the timeout-warning ambiguity.
  - `merge-and-pr-mods` shard: medium cost, real model spend, needed when `pr-merge` or merge-hook paths change.
  E2E required: yes for all three shards; these are the actual behavioral proofs this task exists to provide.
- **Secrets/config verification**: static review of workflow env wiring plus one successful manual run with both repo secrets configured. Do not require destructive secret-removal testing in the main repo; clear missing-secret failure handling in the workflow is enough. Cost/complexity: low to medium. No additional E2E beyond the smoke run above.

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
