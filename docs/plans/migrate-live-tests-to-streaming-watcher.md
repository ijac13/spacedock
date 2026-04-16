---
id: 175
title: "Migrate remaining live E2E tests to streaming watcher"
status: backlog
source: "CL directive during 2026-04-16 session — #173 shipped FOStreamWatcher + two pilot migrations; extending to 4 high-value + 2 medium-value tests completes the cohort and unlocks fast-fail CI signals across the live suite."
started:
completed:
verdict:
score: 0.6
worktree:
issue:
pr:
---

## Problem Statement

PR #109 shipped `FOStreamWatcher` + `run_first_officer_streaming` and migrated two pilot tests (`test_standing_teammate_spawn.py`, `test_claude_per_stage_model.py`). The live smoke proved the feature: a 600s failure becomes a 75s failure. Six more tests under `tests/` still use the post-hoc `run_first_officer` + `LogParser` pattern — each a latent 10-minute wait-on-red-CI. The migration pattern is now template-stable; this task applies it across the remaining cohort.

## Migration targets

### High-value (4)

| Test | Markers | Milestone structure |
|---|---|---|
| `test_gate_guardrail.py` | `live_claude`, `live_codex`, `serial` | gate presentation → captain response emit → post-gate transition |
| `test_merge_hook_guardrail.py` | `live_claude`, `live_codex` | mod-block set → hook invocation → PR create → merge detection |
| `test_feedback_keepalive.py` | `live_claude` | reviewer reject → reuse fix-agent → re-review |
| `test_team_dispatch_sequencing.py` | `live_claude`, `teams_mode` | sequential `Agent()` calls — each call is a milestone |

### Medium-value (2)

| Test | Current state | Why migrate |
|---|---|---|
| `test_dispatch_names.py` | `xfail(strict=False)` pending #160 (haiku multi-dispatch compression) | Fast-fail while #160 is open speeds iteration |
| `test_rebase_branch_before_push.py` | `xfail(strict=False)` pending #158 (pr-merge hook haiku skips rebase) | Same — fast-fail while #158 is open |

### Explicitly out of scope

- `test_single_entity_team_skip.py` — `bare_mode`, simple flow. Marginal gain.
- Six `xfail` tests tracking #154 (`test_agent_captain_interaction`, `test_checklist_e2e`, `test_dispatch_completion_signal`, `test_output_format`, `test_repo_edit_guardrail`, `test_reuse_dispatch`) — target pre-#085 prose assertions. Un-xfail first.
- Three skipped tests (`test_rejection_flow`, `test_scaffolding_guardrail`, `test_push_main_before_pr`) — migrate after the skips are addressed.

## Migration pattern

Each test follows the same structural rewrite, modeled on `test_standing_teammate_spawn.py`'s migration:

1. Replace `run_first_officer(...)` with `with run_first_officer_streaming(...) as w:` context manager.
2. Replace post-hoc `LogParser`-driven assertions with `w.expect(predicate, timeout_s=..., label=...)` calls in milestone order.
3. Use `tool_use_matches` / `entry_contains_text` / `assistant_model_equals` predicate helpers from `scripts/test_lib.py`.
4. Capture matched entries when the test needs to assert on their content (e.g., prompt content, model stamp).
5. End with `w.expect_exit(timeout_s=...)` for clean termination.
6. Keep the final `LogParser` pass only for aggregate assertions that cannot be expressed as a single milestone (e.g., "at least N `Agent()` calls observed").
7. Preserve all existing `pytest.mark` decorators, including `xfail` markers and their `reason`/`strict` arguments.

## Per-milestone timeout guidelines

- Short milestones (initial tool call, simple dispatch): `timeout_s=60-120`
- Team-mode spawn + first `Agent()` call: `timeout_s=120-180`
- Stage transitions / multi-step sequences: `timeout_s=180-240` per step
- `expect_exit` at end: `timeout_s=120-240` depending on expected post-milestone work

Start conservative and tighten once green.

## Acceptance criteria

1. Each of the six tests is migrated to use `run_first_officer_streaming` + `expect()` calls.
2. All existing `pytest.mark` decorators preserved verbatim, including `xfail` reasons and `strict` arguments.
3. `make test-static` remains green (425+ pass count from the offline suite, unchanged — these are live tests).
4. A live smoke of one migrated test at its typical target model confirms the watcher integration works end-to-end (most relevant: `test_gate_guardrail.py` or `test_merge_hook_guardrail.py`).
5. Each migration commit scopes to a single test file plus any incidental predicate-helper additions. Commit message names the test and the milestone set added.
6. Entity stage report lists each migration commit, the per-migration milestone count, and any cases where the test's existing assertion shape resisted clean conversion (e.g., needed a post-hoc `LogParser` pass alongside the streaming watcher).

## Test plan

Offline unit tests: no new tests required — all new behavior is exercised by the existing `tests/test_fo_stream_watcher.py` suite shipped in #173. Each migration is structurally identical to the pilot migrations.

Live smoke: one test, one run. The goal is confirming the watcher integration still works after the six migrations land — not measuring per-test wallclock gains, which are known in principle from the #173 smoke.

## Out of Scope

- Migrating the nine deferred tests listed above.
- Changes to `FOStreamWatcher`, `run_first_officer_streaming`, or predicate helpers.
- Changes to CI workflow or Makefile.
- Codex-runtime streaming watcher equivalent (Codex tests have their own `CodexLogParser`; a matching watcher is follow-up after this cohort).
