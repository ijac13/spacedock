---
id: 175
title: "Migrate remaining live E2E tests to streaming watcher"
status: validation
source: "CL directive during 2026-04-16 session — #173 shipped FOStreamWatcher + two pilot migrations; extending to 4 high-value + 2 medium-value tests completes the cohort and unlocks fast-fail CI signals across the live suite."
started: 2026-04-16T22:53:47Z
completed:
verdict:
score: 0.6
worktree: .worktrees/spacedock-ensign-migrate-live-tests-to-streaming-watcher
issue:
pr:
mod-block: merge:pr-merge
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

## Stage Report (implementation)

| # | Commit | Test | Milestones | Post-hoc LogParser retained? |
|---|---|---|---|---|
| 1 | `0e855813` | `test_gate_guardrail.py` | 2 (gate review presented; at-gate report) + `expect_exit` — claude path only | Yes — scrubbed self-approval aggregate scan |
| 2 | `6790dde0` | `test_merge_hook_guardrail.py` | With-hook: 2 (ensign dispatch; `_merge-hook-fired.txt` Bash write) + `expect_exit`. No-mods: 1 (ensign dispatch) + `expect_exit`. Claude paths only via new `_run_claude_merge_case`; codex routed through `_run_merge_case` unchanged. | Yes — `check_merge_outcome` filesystem checks (hook file, archive, worktree cleanup) |
| 3 | `6350c3dd` | `test_feedback_keepalive.py` | 2 (implementation ensign dispatch; validation ensign dispatch = keepalive crossed transition) + `expect_exit` | Yes — `_scan_keepalive_events` cross-entry shutdown scan and Tier 2 feedback-routing classification |
| 4 | `86d61dd3` | `test_team_dispatch_sequencing.py` | 2 (first Agent(); second Agent()) + `expect_exit` | Yes — whole-log sequencing invariant (no assistant message mixes TeamCreate/TeamDelete with Agent) |
| 5 | `d39c4eba` | `test_dispatch_names.py` | 2 (first Agent(); second Agent() — fails fast under #160 xfail condition) + `expect_exit` | Yes — entity state + `dispatch_count >= 2` + completed-timestamp checks, relevant on the xpass branch |
| 6 | `47c4c4e9` | `test_rebase_branch_before_push.py` | 3 (Bash `push origin main`; Bash `push origin <branch>`; Bash `gh pr create`) + `expect_exit` | Yes — git-wrapper push-log ordering, bare-remote rebase verification, gh-stub PR check, entity frontmatter |

### Per-migration notes on assertion shape

- `test_gate_guardrail`: the self-approval check strips guardrail-citation phrasings like "cannot self-approve" before searching — a regex scrub-and-search that operates on the *concatenated* FO text. Does not reduce to a single milestone predicate, so it stayed as a post-hoc `LogParser.fo_texts()` pass.
- `test_merge_hook_guardrail`: `check_merge_outcome` verifies filesystem state (hook file contents, archive presence, worktree cleanup) — inherently post-execution filesystem inspection.
- `test_feedback_keepalive`: `_scan_keepalive_events` correlates impl-dispatch → impl-completion → validation-dispatch ordering to detect premature shutdown messages *in that specific window*. The Tier 2 classifier also distinguishes `SendMessage`-to-impl-agent (keepalive worked) from fresh `Agent()` impl dispatch (keepalive failed) — requires cross-entry state, not a single predicate.
- `test_team_dispatch_sequencing`: the AC5 invariant is a *whole-log* property — "no assistant message anywhere mixes TeamCreate/TeamDelete with Agent in its tool_use set." Post-hoc aggregation is the natural fit.
- `test_dispatch_names`: xfail hits at the second milestone's `StepTimeout` under #160's 1-Agent()-instead-of-2 symptom. Post-hoc entity state checks remain for the xpass branch when #160 is fixed.
- `test_rebase_branch_before_push`: the *ordering* of pushes (main before branch) plus remote-branch rebase verification against the bare repo require git commands against the post-run repo state, not stream-json entries.

### `make test-static` results

```
426 passed, 22 deselected, 10 subtests passed in 19.92s
```

Baseline AC: `425+ pass count`. Achieved 426 (up one from the 425 baseline cited in the entity body, likely reflecting an unrelated test that landed between the #173 snapshot and this dispatch). No regressions.

### Spot-check collection

`uv run pytest --collect-only` across all six migrated tests returns `6 tests collected` with no import errors.

### Recommendation for validation

Per dispatch note #12: **offline + single live smoke**. Offline (`make test-static`) is green. For the live smoke, `test_gate_guardrail.py` at `opus` is the most direct confirmation — the gate-presentation milestone is quick (~120s target) and the `expect_exit` at 180s lets us confirm the watcher correctly closes down a budget-capped run. Alternatively `test_merge_hook_guardrail.py` at `opus` / `medium` effort exercises a more complex two-phase flow but costs more wallclock.

All six migrations follow the pilot template from #173 verbatim; structural risk is low. The real test is that the per-step timeouts are tuned correctly — the smoke will surface any that are too tight.
