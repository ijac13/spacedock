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

Live E2E tests spawn real `claude -p` or `codex exec` subprocesses. They're expensive (API tokens, wallclock minutes), but they're the only way to catch real FO behavioral regressions before they ship. Running them on every PR is wasteful; running them on no PRs means regressions land silently.

This session observed three live E2E failures that sat silently on `main` until I happened to run them: `test_scaffolding_guardrail.py` (false positive in the violation pattern), `test_rejection_flow.py` (600s haiku timeout on multi-cycle pipelines), and `test_feedback_keepalive.py` (stale path after task 076's move, caught only when I ran it manually as part of verifying 117's fix). None of these were pre-flagged; all three had been red on `main` for an unknown amount of time.

A conditional CI mechanism that runs live E2E tests on PRs that **touch FO behavior** (dispatch template, shared core, runtime adapters, ensign shared core, pr-merge mod, etc.) would catch these before merge. PRs that touch docs or unrelated code wouldn't pay the cost.

## Known live E2E failures to fix under this task

As of 2026-04-13, four live tests have real failures that need attention:

1. **`test_scaffolding_guardrail.py`** (8/9 FAIL): the violation pattern matches any `Bash(...)` tool use containing a scaffolding path, even read-only `ls -la` or `cat` operations. Example false positive from this session: `Bash(ls -la /Users/clkao/git/spacedock/skills/commission/bin/status ... || echo "Fil")`. The fix is to tighten the pattern to detect actual writes — `Write`, `Edit`, `NotebookEdit` tool uses, and `Bash` commands containing `>`, `>>`, `sed -i`, `mv`, `rm`, `truncate`, `chmod` — while explicitly ignoring read-only probes (`ls`, `cat`, `head`, `tail`, `grep`, `find`, `file`, `stat`, `wc`).

2. **`test_rejection_flow.py`**: assertions pass but the FO times out at 600s on haiku. The pipeline has 3+ ensign dispatches in a feedback cycle, and haiku is slow enough that 600s isn't enough budget. The test is currently lenient about the timeout (it reports PASS with a `TIMEOUT` warning), but that's a reliability gap — a real regression in the FO's rejection-flow path would still let the test pass. Fix options: (a) bump the timeout specifically for haiku, (b) slim the fixture to fewer cycles, (c) run this test on sonnet by default, (d) add a strict-timeout mode that turns the timeout into a hard FAIL. Option (d) with a bumped timeout is preferred — the 600s limit was an arbitrary choice, not a contract.

3. **`test_feedback_keepalive.py`**: `tests/test_feedback_keepalive.py:307` reads `(REPO_ROOT / "references" / "first-officer-shared-core.md").read_text()`, but task 076 moved references into `skills/first-officer/references/`. The file crashes `FileNotFoundError` on the Static Template Checks phase, even though Tier 1 keepalive assertions all pass before the crash. The fix is a one-line path update to `skills/first-officer/references/first-officer-shared-core.md`. Note: `scripts/test-harness.md` lines 163, 166, 169, 172 carry the same stale-path bug for `first-officer-shared-core.md` and `claude-first-officer-runtime.md` — fix those in the same pass. `tests/test_reuse_dispatch.py:193,194` uses the correct post-076 path and can serve as the reference pattern.

4. **`test_dispatch_completion_signal.py`** (2026-04-13 observation, claude-runtime only — `choices=["claude"]`, there is no Codex-equivalent because the `SendMessage(to="team-lead")` completion-signal is a Claude-Code teams primitive): the test runs the FO through a team-mode dispatch and then asserts the outgoing ensign prompt contains the literal string `SendMessage(to="team-lead"`. Today the dispatch template in `skills/first-officer/references/claude-first-officer-runtime.md:55` wraps that block in a `{if not bare mode: '...'}` conditional. FOs reproducibly drop the block from the prompt they actually send. Confirmed on **both haiku AND opus/low** — this is a model-agnostic regression, not a haiku flake. Task #115 (PR #62) shipped the template on 2026-04-10; task #117 was filed for a related haiku flake but does not cover this symptom. Fix direction: audit whether the `{if not bare mode: ...}` conditional wording in the template invites models to omit the block, or whether the block needs to move out of the conditional and into unconditional prose. Reproduction: `unset CLAUDECODE && uv run tests/test_dispatch_completion_signal.py --runtime claude --model {haiku|opus} --effort low`. Logs from the 2026-04-13 run are in `/tmp/spacedock-e2e-logs/test_dispatch_completion_signal*.log`.

## What the conditional mechanism should look like

Options for gating E2E runs on PRs:

- **Path-based trigger.** The CI workflow watches for changes to specific paths: `skills/first-officer/**`, `skills/ensign/**`, `mods/pr-merge.md`, `docs/plans/_mods/**`, `tests/**`. Any PR touching these runs the E2E suite. Purely docs/code PRs skip it.
- **Label-based trigger.** Add a `needs-e2e` label on the PR; CI checks for the label and runs E2E if present. Implementers decide.
- **Both.** Path-based as the default; label override lets anyone force a run (or suppress one).
- **Commit-message convention.** `[run-e2e]` in a commit message triggers the suite. Cheap, no label management.

The captain's preference for which trigger to use is an ideation question. A reasonable default is **path-based + label override**.

## Scope

1. Decide on the trigger mechanism (ideation).
2. Add a CI workflow that runs the live E2E suite when the trigger fires. The suite includes at minimum: `test_gate_guardrail`, `test_scaffolding_guardrail`, `test_rejection_flow`, `test_merge_hook_guardrail`, `test_dispatch_completion_signal`, `test_feedback_keepalive`, `test_push_main_before_pr`, `test_rebase_branch_before_push`, `test_reuse_dispatch`, `test_team_health_check`, `test_team_dispatch_sequencing`, `test_output_format`, `test_single_entity_team_skip`, `test_dispatch_names`, `test_spike_termination`, `test_repo_edit_guardrail`.
3. Fix the three known live E2E failures listed above (`test_scaffolding_guardrail` violation pattern, `test_rejection_flow` timeout/budget, `test_feedback_keepalive` stale path) so the suite is green from day one.
4. Document the trigger mechanism in `tests/README.md` so future contributors know how to force an E2E run.
5. Set a wallclock/cost budget on the CI workflow — these tests burn real API tokens and a runaway loop shouldn't empty the budget.

## Out of scope

- Static tests — they belong in the sibling task 133 (CI for static tests) and run on every PR.
- The ongoing haiku speed concerns that surfaced as part of task 117 (`fo-idle-guardrail-flake-on-haiku`) — 117's fix for early teardown is sufficient for `test_dispatch_completion_signal.py`. The broader "haiku is slow on multi-cycle pipelines" issue that `test_rejection_flow.py` surfaces is handled inside this task's fix #2 (timeout/budget tuning).
- Codex-runtime E2E tests (`test_codex_packaged_agent_e2e.py`). They also had failures this session (7/13 failing against Codex's current state), but those belong to the Codex FO's pipeline, not this task.

## Acceptance Criteria (ideation to refine)

1. A CI workflow exists that runs the full live E2E suite on PRs matching the trigger criteria (path-based, label-based, or both).
2. PRs that don't match the trigger do NOT run E2E tests — the suite is not "run on every PR".
3. `test_scaffolding_guardrail.py` distinguishes read-only `Bash` commands from writes. A PR that does only `ls`/`cat` on scaffolding files passes the guardrail; a PR that does `Edit` or `Bash(echo X > scaffolding/file)` still fails it. Verified with a unit test of the violation-detection helper, plus the existing E2E harness run.
4. `test_rejection_flow.py` either (a) completes within its budget on haiku, or (b) fails cleanly if the budget is exceeded — no more silent PASS-with-TIMEOUT-warning.
5. The live E2E suite runs to completion under a capped wallclock budget (e.g., 30 minutes) and a capped cost estimate. Overruns fail the CI job.
6. `tests/README.md` documents how to force an E2E run from a PR (label name, commit tag, or whatever the chosen mechanism is).

## Test Plan

- Unit test for the scaffolding-guardrail violation-detection helper covering read-only vs write cases.
- CI dry-run: open a PR that touches a path in the trigger list, verify the E2E workflow runs. Open a PR that touches only docs, verify the E2E workflow does NOT run.
- Regression: run the full live E2E suite locally before pushing this task's fix — the suite should go from red (current: 2 fail, 1 at-risk) to green.
- **E2E needed for this task:** the regression run above IS the E2E verification. The CI workflow is infrastructure that we verify by opening a test PR.

## Related

- **Task 133** (`ci-static-tests-and-known-failures`, sibling) — static tests run on every PR; live E2E runs conditionally. Together they partition the test universe.
- **Task 117** (`fo-idle-guardrail-flake-on-haiku`, in-flight with Codex FO) — 117 fixed `test_dispatch_completion_signal` specifically. The broader haiku-speed concern that affects `test_rejection_flow` is this task's fix #2, not 117's scope.
- **Task 076** (`plugin-shipped-agents`, already shipped) — the move that orphaned `test_feedback_keepalive.py`'s reference path. This task's fix #3 already ships the repair alongside the task seed.
