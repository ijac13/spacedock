---
id: 133
title: "CI for static tests + track known static failures"
status: backlog
source: "CL direction during 2026-04-11 session — session discovered static test regression that slipped through PR #74 merge because no CI ran test_agent_content.py"
score: 0.80
worktree:
started:
completed:
verdict:
issue:
pr:
---

Static tests currently run only when a human or a dispatched ensign remembers to invoke `uv run tests/X.py`. This session discovered a concrete regression: PR #74 (task 129) shipped a change to `docs/plans/_mods/pr-merge.md` that removed the literal string `"Workflow entity: {entity title}"`, but `tests/test_agent_content.py:138` still asserts that string is present. The 129 pipeline ran its own new `test_pr_merge_template.py` (which asserts the string is GONE) and its regression suite `test_status_script.py`, but nobody ran `test_agent_content.py`. The contradiction between two test files sat green in the 129 PR and red on main, with no CI to catch it. Task 117 (`fo-idle-guardrail-flake-on-haiku`) has already folded the specific `test_agent_content.py` repair into its scope via commit `6bc5a90`, so the fix will land when 117 merges — but the underlying gap (no automated verification that static tests stay green) remains. This task closes that gap.

## What CI should run on every PR

All tests that do not require spawning a live `claude -p` subprocess. As of 2026-04-11 these are:

| Test file | Tests | Harness | Notes |
|---|---|---|---|
| `tests/test_pr_merge_template.py` | 27 | unittest | Shipped by task 129, asserts the new tightened template rules. |
| `tests/test_status_script.py` | 90 | unittest | Task 123's status tool coverage. |
| `tests/test_stats_extraction.py` | 37 | script | Log parser / stats extraction. |
| `tests/test_status_set_missing_field.py` | 5 | unittest | Task 122's silent-noop fix coverage. |
| `tests/test_codex_packaged_agent_ids.py` | 6 | pytest | Codex worker-id resolution, static. |
| `tests/test_claude_team.py` | 20 | pytest | claude-team helper unit tests (includes task 131's fix). |
| `tests/test_agent_content.py` | 25 | pytest | 125's shared-core / dispatch template assertions. **Currently red on main** (see "known failures" below). |

**Not in scope for this task:** anything that uses `run_first_officer`, `run_codex_first_officer`, or `InteractiveSession`. Those are live/E2E tests that belong to the sibling task on runtime-specific PR tests.

## Prerequisite

Task 117 lands the current known static failure in `tests/test_agent_content.py` (the stale 129 assertion at lines 138, 141, 148). This task depends on 117 shipping first so the static suite is green before CI is enabled. If 117 slips, implementation should wait rather than ship a broken CI that flags every PR.

## Scope

1. Add a CI workflow (GitHub Actions, `.github/workflows/ci-static.yml` or equivalent) that runs on every PR against `main`.
2. The workflow runs all 7 static test files listed above and fails the PR check if any fail.
3. The workflow handles the mixed invocation styles — some tests are unittest-style (`uv run tests/X.py`), some are pytest-style (`uv run --with pytest python -m pytest tests/X.py -q`). Either standardize one invocation per test or document both in the workflow.
4. Verify the full static suite is green locally before enabling the CI gate. Expect ~210 passing tests.
5. Smoke-verify the CI check by introducing a deliberate stale assertion in a draft PR and confirming the workflow catches it.

## Out of scope

- Live E2E tests that spawn `claude -p` or `codex exec` subprocesses. Those belong to sibling task 134 (runtime-specific PR tests).
- Fixing the 060s tools — these are all stable static tests, no overhauls needed.
- Adding new tests beyond the 129 regression fix.

## Acceptance Criteria (ideation to refine)

1. A CI workflow exists that runs all static tests on every PR against `main`. Failures block the PR merge.
2. All 7 static test files listed in "What CI should run" are green in a single CI run.
3. The workflow handles both unittest-style and pytest-style invocations — document the split or standardize.
4. A trivial test edit that removes an assertion causes the CI check to fail (smoke-verified manually once by the implementer).
5. The static suite green baseline is captured in the task's stage report as the implementer's reference (expected ~210 passing tests against post-117 main).

## Test Plan

- Manually run all 7 static tests locally before pushing the CI workflow.
- Run the CI workflow on the fix-branch PR and verify it catches the 129 regression before the fix is applied, then passes after.
- No new live E2E tests needed — this task is CI plumbing + one stale assertion fix.
- E2E not needed — CI is a meta-infrastructure change with purely observable outputs.

## Related

- **Task 129** (`pr-mod-tighten-body-template`, already shipped as PR #74) — its merge created the `test_agent_content.py` regression because its validation pipeline didn't run `test_agent_content.py`. This task closes that gap structurally.
- **Task 134** (`runtime-specific-tests-on-pr`, sibling) — live E2E tests that belong in a conditional PR check, not every-PR. The two tasks partition the test universe between them.
- **Task 125** (`entity-body-accumulation-anti-pattern`, already shipped) — introduced `test_agent_content.py` with its original set of assertions. This task's stale-assertion fix is a direct follow-up on 125's contract enforcement pattern.
