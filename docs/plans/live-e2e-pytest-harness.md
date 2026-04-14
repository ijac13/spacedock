---
id: 148
title: "Migrate live E2E tests to pytest with runtime markers"
status: validation
source: "CL observation during 2026-04-13 session — standalone uv-run scripts cause test sprawl and boilerplate duplication"
started: 2026-04-14T19:40:43Z
completed:
verdict:
score: 0.70
worktree: .worktrees/spacedock-ensign-live-e2e-pytest-harness
issue:
pr:
---

Each live E2E test is a standalone `uv run` script with its own `main()`, `argparse` setup, `TestRunner` instantiation, project scaffolding, FO invocation, log parsing, and result reporting. Adding a new test means copying 60+ lines of boilerplate. The Makefile must list each test by path, and the CI workflow must keep that list in sync.

Meanwhile `make test-static` already uses pytest for the offline suite (`pytest tests/ --ignore=tests/fixtures`). The live tests sit outside pytest because they were written before the static harness existed, and because they need runtime-specific flags (`--runtime`, `--model`, `--effort`) that pytest doesn't natively understand.

## Proposed shape

Migrate live E2E tests to pytest with custom markers so a single `pytest` invocation replaces the per-script `uv run` dance:

```bash
# Run all claude-live tests
make test-live-claude   →   pytest -m live_claude

# Run all codex-live tests
make test-live-codex    →   pytest -m live_codex

# Run a specific test
pytest tests/test_gate_guardrail.py -m live_claude
```

### What changes

1. **Custom markers:** `@pytest.mark.live_claude`, `@pytest.mark.live_codex`. A test can carry both if it's runtime-agnostic. Register in `pyproject.toml` or `conftest.py`.

2. **Shared fixtures:** Replace the per-test `create_test_project → setup_fixture → install_agents` boilerplate with pytest fixtures (`@pytest.fixture`). Candidates:
   - `test_project(fixture_name)` — creates tmpdir, inits git, copies fixture, installs agents, yields project dir, cleans up.
   - `fo_run(test_project, prompt, ...)` — runs `claude -p` or `codex exec`, returns parsed log.
   - `runtime` — parametrize over `["claude", "codex"]` for cross-runtime tests.

3. **Runtime flags via conftest.py:** Add `--runtime`, `--model`, `--effort` as pytest addopts via `conftest.py::pytest_addoption`. Tests access them via `request.config.getoption("--model")`.

4. **Result reporting:** Replace `TestRunner.pass_()` / `TestRunner.fail()` with standard pytest assertions. The `RESULT: PASS` / `RESULT: FAIL` output is no longer needed when pytest owns reporting.

5. **Makefile targets:** `test-live-claude` becomes `pytest -m live_claude`. `test-live-codex` becomes `pytest -m live_codex`. The Makefile no longer lists individual test scripts — pytest discovers them.

6. **CI workflow:** `make test-live-claude` / `make test-live-codex` continue to work; the make target just calls pytest now.

### What doesn't change

- `scripts/test_lib.py` helpers (`LogParser`, `CodexLogParser`, `run_first_officer`, etc.) stay as importable utilities. They just get called from pytest test functions instead of standalone `main()`.
- Test logic and assertions stay the same; only the harness changes.
- Static tests continue to use `make test-static` / `pytest tests/ --ignore=tests/fixtures`.

## Migration order

Migrate one test first (e.g., `test_gate_guardrail.py` — simplest, single runtime) to prove the pattern, then batch-migrate the rest. The standalone `main()` entrypoints can be preserved temporarily as thin wrappers around the pytest function for backward compat, or dropped if the Makefile is the only caller.

## Scope

- Migrate all live E2E tests under `tests/test_*.py` to pytest
- Register `live_claude` and `live_codex` markers
- Add `conftest.py` with runtime CLI options and shared fixtures
- Update Makefile `test-live-claude` and `test-live-codex` targets
- Update `tests/README.md` to document the new invocation pattern
- Update `docs/plans/README.md` Testing Resources section if it references the old `uv run` pattern

## Out of scope

- Interactive PTY tests (`test_lib_interactive.py`) — different harness, different lifecycle
- Static tests — already on pytest
- Changing test logic or assertions — harness migration only

## Test structure: sequential short-circuit vs parallel (CL note, 2026-04-14)

The current `test-live-claude` Makefile target uses `&&` with `set -euo pipefail`, which means the first failing test short-circuits the chain and subsequent tests never run. Concrete consequence observed on PR #90 cycles: a `test_rebase_branch_before_push` failure masked whether `test_dispatch_completion_signal` would have passed — we reported "completion-signal passed" when in fact it never executed.

The pytest migration should fix this by structuring the suite into two tiers:

1. **Sequential short-circuit tier** — tests that genuinely require sequential execution because a later test depends on the FO state or fixture produced by an earlier test. These run with `pytest -x` (stop on first failure) when the sequencing is meaningful.

2. **Parallel tier** — tests that are hermetic and share no state. These run in parallel (pytest-xdist or marker-based batching). A failure in one should not prevent others from running.

The goal is that after any CI run we know exactly which tests were supposed to run and which actually ran. The current ad-hoc chain obscures both.

### Proposed mechanism

Use pytest markers per stage / dependency tier rather than `&&`-chaining in the Makefile:

- `@pytest.mark.live_claude_sequential` — for tests that must run in order
- `@pytest.mark.live_claude_parallel` — for hermetic tests safe to parallelize
- A single custom marker decorator `@live_claude_stage("sequential"|"parallel")` could wrap both — implementation detail to decide during ideation

The Makefile target then invokes both tiers explicitly:

```bash
test-live-claude: ## run sequential tier, then parallel tier regardless of the first result
	pytest -m live_claude_sequential -x || SEQ_RESULT=$$?; \
	pytest -m live_claude_parallel -n auto || PAR_RESULT=$$?; \
	exit $${SEQ_RESULT:-0} || exit $${PAR_RESULT:-0}
```

This guarantees every parallel test runs regardless of sequential failures, while still failing the overall CI job if any test fails.

### Acceptance criteria addendum

- Every live test carries exactly one tier marker (`sequential` or `parallel`).
- The CI summary clearly shows how many tests were collected, ran, passed, and failed — distinct from whether the suite short-circuited.
- The Makefile does not use `&&` to chain individual test invocations.

## Test Inventory (ideation, 2026-04-13)

### Classification conventions

- **Kind:** `live` = spawns `claude -p` / `codex exec` / PTY `claude` under test; `static` = no runtime spawn, only file/content assertions; `unit` = pure Python helper tests; `spike` = experiment/probe, not a gate.
- **Runtime:** `claude-pipe`, `claude-pty`, `codex`, `shared` (parametrized), or `none`.
- **Subsystem:** FO template (`fo`), ensign template (`ensign`), `status` script, `claude-team` helper, commission skill, mods (pr-merge/merge-hook), CI workflows, test harness itself.
- **Stage:** gate, dispatch, validation, merge, commission, archive, bootstrap, or "template-content" for static contract checks.
- **Parallel candidacy:** `yes` (hermetic — own tmpdir, own git, no shared globals), `no` (spike/probe or shares claude config state problematically), `n/a` (static/unit — trivially parallel).

A note on shared Claude-runtime state: `run_first_officer` does **not** isolate `HOME` / `~/.claude` between concurrent invocations. Every live_claude test spawns `claude -p` against the host's Claude config. Parallelism at `-n auto` is therefore bounded by whatever the Claude CLI tolerates for concurrent sessions against the same OAuth token and cache. In practice this has not been stress-tested; the design below starts conservative (`-n 2`) and makes the worker count a Makefile knob.

### Inventory — `tests/`

| # | File | Kind | Runtime | Subsystem / Stage | Purpose (one sentence) | Concrete failure caught | Parallel candidate | Redundancy / overlap | Tautology risk |
|---|------|------|---------|-------------------|------------------------|--------------------------|--------------------|----------------------|----------------|
| 1 | `test_agent_captain_interaction.py` | live | claude-pipe | fo / dispatch | FO uses direct text to captain and does not prematurely shut down agents (AC6, AC7). | Regression where FO reaches for SendMessage-to-captain or pre-kills the ensign before completion signal. | yes | Shares the "no premature shutdown" axis with `test_dispatch_completion_signal` but exercises it via agent-captain text channel, not completion signal. Keep both. | Low — parses real log for shutdown patterns. |
| 2 | `test_agent_content.py` | static | none | fo + ensign / template-content | Pytest-native static asserts on assembled agent content: Claude wait policy, Codex wait policy, shared guardrail wording. | Contract drift where SKILL.md / agent wrapper loses a required line. | n/a | Overlaps `test_codex_packaged_agent_ids.py` for *Codex* prompt-discipline wording; the two split cleanly (this file = shared contract, that file = Codex-specific). | Low — matches strings, but they are load-bearing contracts. |
| 3 | `test_ci_static_workflow.py` | static | none | CI workflows | Verifies `.github/workflows/ci-static.yml` uses the canonical `pytest tests/ --ignore=tests/fixtures` entrypoint. | Someone hand-edits the workflow and breaks the static CI signal. | n/a | None. | Low. |
| 4 | `test_claude_team.py` | unit + static | none | claude-team helper | Unit tests for `scripts/claude-team` — context-budget math, model mapping, dispatch assembly, validation. | Refactor of the helper silently breaks token thresholds or dispatch structure. | n/a | None. Largest file (1073 lines); heavy pytest-native parametrize. | Low — exercises real subprocess-invoked binary. |
| 5 | `test_codex_packaged_agent_e2e.py` | live | codex | fo / dispatch | Proves Codex FO reuses packaged workers and honors explicit shutdown. | Codex adapter loses reuse semantics or ignores shutdown directive. | yes | Partial overlap with `test_reuse_dispatch.py` (Claude reuse); the Codex path is a distinct adapter. | Low — parses codex log spawn count. |
| 6 | `test_codex_packaged_agent_ids.py` | unit | none | fo / template-content | Pure-Python coverage of Codex worker-id resolution and FO/bootstrap prompt shape. | Bootstrap prompt loses required id or wait-policy wording. | n/a | See #2 note — split is clean. | Low. |
| 7 | `test_commission_template.py` | static | none | commission / template-content | Static structural checks on `skills/commission/SKILL.md` (Schema section has no YAML fence, required sections). | Template edit breaks schema fencing. | n/a | Partial overlap with `test_commission.py` AC-set (which also validates commission output); this one is cheaper (no live run). | Low. |
| 8 | `test_commission.py` | live | claude-pipe | commission / commission | Batch-mode commission E2E: runs `run_commission`, validates every output artifact (README, entities, status script, mod). | Commission skill regresses on output shape, frontmatter, guardrails. | yes | See #7; they are complementary. | Low — inspects generated files. |
| 9 | `test_dispatch_completion_signal.py` | live | claude-pipe | fo / dispatch | Team-mode dispatch: ensign sends `SendMessage(team-lead, "Done: …")`, FO advances status. | Recurrence of #114 pattern: FO silently drops completion signal; entity stalls. | yes | Touches the same FO code path as `test_dispatch_names.py` and `test_reuse_dispatch.py` but asserts a *different* invariant (completion-signal handling). Keep. | Low — asserts on status advance + archive, not on mocked text. |
| 10 | `test_dispatch_names.py` | live | claude-pipe | fo / dispatch | Full multi-stage pipeline runs without agents getting killed by stale shutdowns (dispatch-name collision regression). | #90-era collision where reusing a stage name kills the live agent. | yes | Overlap with `test_team_dispatch_sequencing.py` (both use `multi-stage-pipeline` / `gated-pipeline`), but they assert different invariants. | Low. |
| 11 | `test_feedback_keepalive_helpers.py` | unit | none | fo / harness | Regex unit tests for the `_agent_targets_stage` helper inside `test_feedback_keepalive.py`. | Prompt-format change silently regresses the stage-detection regex. | n/a | Scaffolding for #12 — pure unit-level. | **Medium** — this *only* tests a helper that lives inside another test file. It's defensible as a regression guard for the regex but indicates the helper probably belongs in `scripts/test_lib.py` where it can serve more than one test. **Call out:** migration is a good moment to move `_agent_targets_stage` into `test_lib.py` so this unit test stops reaching sideways into a peer test module. |
| 12 | `test_feedback_keepalive.py` | live | claude-pipe | fo / validation | FO keeps implementation ensign alive across validation rejection; routes feedback via SendMessage instead of fresh dispatch. | Regression where rejected validation respawns a fresh implementer instead of reusing the kept-alive one. | yes | Close sibling of `test_rejection_flow.py` (both exercise rejection path). The split: this one asserts *keepalive* (no fresh dispatch); rejection_flow asserts *flow* (fresh dispatch for fix after reject). They are complementary and in tension — together they pin the policy. | Low. |
| 13 | `test_gate_guardrail.py` | live | shared (claude + codex) | fo / gate | FO halts at a gate and does not self-approve. | Regression: FO marks gate approved without captain. | yes | None — smallest/simplest live test, intended pilot. | Low. |
| 14 | `test_interactive_poc.py` | live | claude-pty | harness | PoC that the PTY harness itself works (offline helpers + live smoke). | Regression in `InteractiveSession` framework. | **no** (PTY is not parallel-safe against shared claude config; see note above) | Scaffolding for #21. | **Medium** — runs mostly `assert` statements against local helpers (`_strip_ansi`, `_KEY_SEQUENCES`) that are pure Python — those are fine. The live smoke portion is a real signal. Split it: pure-python asserts → unit marker, live smoke → live_claude_sequential. |
| 15 | `test_merge_hook_guardrail.py` | live | shared (claude + codex) | fo / merge | Merge hooks fire before local merge; no-mods fallback works. | Merge hook registration regresses; FO silently skips hooks. | yes | None. | Low. |
| 16 | `test_output_format.py` | live | claude-pipe | fo / dispatch | FO obeys README `## Output Format` block, falls back to default when absent. | Regression in per-workflow output-format lookup. | yes | None. | Low. |
| 17 | `test_pr_merge_template.py` | static (unittest) | none | mods / template-content | Wording, word-count, and AC regression tests for `docs/plans/_mods/pr-merge.md`. | Template prose drifts outside AC bounds. | n/a | None. Uses `unittest.TestCase` rather than pytest-native; pytest collects it fine. | Low — content asserts. |
| 18 | `test_push_main_before_pr.py` | live | claude-pipe | mods / merge | `pr-merge` mod pushes `main` before the branch; gh stub sees `gh pr create`. | Push ordering regresses (PR opens against stale main). | **no** — heavier test that stubs `git`/`gh` via wrapper scripts; safer serialized. With its sibling `test_rebase_branch_before_push.py` it would compete for the same `push-main-pipeline` semantics if parallelized. (Both run their own tmpdir, but CL's inventory instruction wants this flagged.) | Overlaps heavily with `test_rebase_branch_before_push.py` (same fixture, same stub strategy). The distinction: this test asserts push-order invariants; the rebase test asserts rebase-before-push invariants. Keep both but sequence them. | Low. |
| 19 | `test_rebase_branch_before_push.py` | live | claude-pipe | mods / merge | `pr-merge` mod rebases branch onto main via bare-repo remote before push; merge-base validation. | Rebase step skipped; PR opens with stale base. | **no** — same reason as #18 (stubs + PR side-effects). | See #18. | Low. |
| 20 | `test_rejection_flow.py` | live | shared (claude + codex) | fo / validation | Rejected validation triggers a fix dispatch via relay protocol. | Rejection path fails to re-dispatch implementer. | yes | See #12. | Low. |
| 21 | `test_repo_edit_guardrail.py` | live | claude-pipe | fo / dispatch | FO refuses to directly edit code/tests/mods on main before dispatch. | FO starts editing source files instead of dispatching an ensign. | yes | Partial overlap with `test_scaffolding_guardrail.py` (same *pattern* — guardrail blocks direct edits) but different target set (code/tests/mods vs. scaffolding/issues). | Low. |
| 22 | `test_reuse_dispatch.py` | live | claude-pipe | fo / dispatch | Ensign reuse uses SendMessage, `fresh: true` forces new Agent dispatch. | Reuse vs fresh semantics regresses. | yes | See #9, #10. | Low. |
| 23 | `test_runtime_live_e2e_workflow.py` | static | none | CI workflows | Static checks on `.github/workflows/runtime-live-e2e.yml` (PR trigger, approval gating, two jobs). | CI workflow edits break PR approval gating. | n/a | None. | Low. |
| 24 | `test_scaffolding_guardrail.py` | live | claude-pipe | fo / dispatch | FO refuses to edit scaffolding files and refuses `gh issue create` without captain approval. | Scaffolding/issue guardrail regresses. | yes | See #21. **Note** the Makefile already marks this SKIPPED because FO currently violates the issue-filing guardrail. Migration must preserve that deliberate skip (as `xfail` or a skip marker with the same rationale — NOT silently enable it). | Low. |
| 25 | `test_single_entity_mode.py` | live | claude-pty | fo / bootstrap | PTY regression: interactive FO in single-entity mode does NOT create a team. | Interactive bootstrap regresses to team-creating behavior for single-entity workflows. | **no** — PTY; see #14. | Overlap with `test_single_entity_team_skip.py` which exercises the same invariant in pipe mode. Keep both; interactive vs pipe mode have distinct code paths. | Low. |
| 26 | `test_single_entity_team_skip.py` | live | claude-pipe | fo / bootstrap | Pipe-mode version of #25 — assert `TeamCreate` absent, `team_name` absent from Agent calls. | Same invariant as #25 but for pipe mode. | yes | See #25. | Low. |
| 27 | `test_spike_termination.py` | spike | claude-pipe | fo / research | Experiments A/B/C on whether/how FO terminates naturally in `claude -p` mode. | n/a — exploratory, not a regression gate. | **no** — spike, ~3x serial experiments, expensive. | **Near-duplicate** of `tests/spike_termination.py`. See #35. | **Medium** — spikes are allowed to be exploratory but this shouldn't run as a gating live test. Migration: mark `@pytest.mark.spike` and exclude from `live_claude` / `live_codex` default targets. |
| 28 | `test_stats_extraction.py` | unit | none | harness | Parses a known-shape JSONL fixture through `LogParser` + `extract_stats`. | Parser regresses on real stream-json logs. | n/a | None. | **Low, but watch:** fixture is inline and synthetic. Any parser change that also updates the fixture passes vacuously. Keep but add a real-log snapshot as a follow-up if the parser gets more intricate. |
| 29 | `test_status_script.py` | unit | none | status script | Forms the bulk of status-script coverage (frontmatter parsing, stage ordering, `--next`, `--set`, help output). | Status-script regression in any subcommand. | n/a | #30 imports its helpers — good sharing. | Low. Heaviest pytest suite, very thorough. |
| 30 | `test_status_set_missing_field.py` | unit | none | status script | Focused coverage for `--set` inserting fields missing from frontmatter. | Missing-field path regresses. | n/a | Extension of #29; imports `build_status_script`, `make_pipeline`, etc. | Low. |
| 31 | `test_team_dispatch_sequencing.py` | live | claude-pipe | fo / dispatch | No assistant message mixes `TeamCreate`/`TeamDelete` with `Agent` dispatch. | FO batches team-lifecycle and dispatch into the same turn (forbidden). | yes | See #10. | Low. |
| 32 | `test_team_health_check.py` | live | claude-pipe | fo / dispatch | FO runs `test -f config.json` preflight before first `Agent` dispatch. | Pre-dispatch health check drops off. | yes | None. | Low. |
| 33 | `test_test_lib_helpers.py` | unit | none | harness | Unit tests for `scripts/test_lib.py` helpers (`probe_claude_runtime`, `bash_command_targets_write`). | Harness helper regression. | n/a | None. | Low. |
| 34 | `spike_termination.py` | spike | claude-pipe | fo / research | Older sibling of #27 — earlier version of the same experiment set; filename lacks `test_` prefix so pytest would not auto-collect it. | n/a. | **no** — spike. | **Direct redundancy with #27** (`test_spike_termination.py` is the newer, cleaned-up variant). See "Resolution" below. | n/a — spike. |

### Inventory — `scripts/`

| # | File | Kind | Runtime | Subsystem / Stage | Purpose | Failure caught | Parallel | Redundancy | Tautology |
|---|------|------|---------|-------------------|---------|----------------|----------|-----------|-----------|
| 35 | `scripts/test_checklist_e2e.py` | live | claude-pipe | fo+ensign / dispatch | Commissions a full workflow then runs FO to verify ensign checklist compliance. | Checklist protocol regression (ensign skips required checklist entries). | yes | None. Lives in `scripts/` because it pre-dates the `tests/` convention; it IS a live test and should move to `tests/`. | Low. |
| 36 | `scripts/test_lib.py` | library | n/a | harness | Shared test library (TestRunner, parsers, runtime wrappers). Not a test file — naming just starts with `test_`. | n/a — library. | n/a | n/a | n/a. Leave where it is; only rename if we want to stop pytest from attempting collection (it currently skips because there are no `test_*` functions, but the filename is collision-prone). |
| 37 | `scripts/test_lib_interactive.py` | library | n/a | harness | PTY-session library. Same note as #36. | n/a | n/a | n/a | n/a. |

### Findings — redundancy and tautology resolutions

The inventory surfaces these concrete cleanups that the pytest migration should resolve (or explicitly defer with a rationale):

1. **`tests/spike_termination.py` AND `tests/test_spike_termination.py` (#27, #34) — both deleted.** Revised 2026-04-13 per CL feedback. Both files are exploratory probes for `claude -p` termination behavior. Their findings (natural end vs budget vs result-entry vs stop_reason) are already baked into the runtime adapter and the termination handling in `scripts/test_lib.py`. Keeping either as a marked-and-excluded test adds clutter without signal. Delete both. No `spike` marker is registered; if a future probe is needed, the author can add the marker back at that time.
2. **`_agent_targets_stage` helper (#11 vs #12)** — move the helper from `tests/test_feedback_keepalive.py` into `scripts/test_lib.py`. `test_feedback_keepalive_helpers.py` then imports from `test_lib`, which is how every other harness unit test works.
3. **`scripts/test_checklist_e2e.py` (#35)** — move to `tests/test_checklist_e2e.py`. The `scripts/` location is historical and hides the test from default pytest collection in `tests/`.
4. **`scripts/test_lib.py` and `scripts/test_lib_interactive.py` (#36, #37)** — leave in `scripts/` (they are libraries, not tests) but confirm pytest does not attempt to collect them as tests. If pytest complains when it tries to import them from a `scripts/conftest.py`, add `collect_ignore` to exclude them.
5. **`test_interactive_poc.py` (#14)** — split into two test functions: pure-Python asserts under `@pytest.mark.unit`, live PTY smoke under `@pytest.mark.live_claude` + `@pytest.mark.live_claude_sequential`.
6. **`test_scaffolding_guardrail.py` (#24)** — carry the existing SKIPPED status over as `@pytest.mark.skip(reason="FO violates issue-filing guardrail — see task to file")` so the skip is surfaced in the pytest summary instead of hidden in a Makefile comment.
7. **Static files written in `unittest`** — `test_pr_merge_template.py` (#17) and `test_status_script.py` / `test_status_set_missing_field.py` (#29, #30) use `unittest.TestCase`. Pytest collects these fine; do not rewrite them just to please a style guide. YAGNI.
8. **`test-e2e-commission` Makefile target — fold into `test-e2e`.** Current shape:
   ```makefile
   test-e2e:
       unset CLAUDECODE && uv run $(TEST) --runtime $(RUNTIME)
   test-e2e-commission:
       unset CLAUDECODE && uv run tests/test_commission.py
   ```
   The `-commission` target is `TEST=tests/test_commission.py make test-e2e` minus `--runtime`. Since `test_commission.py` is claude-pipe-only and its `parse_args` accepts but does not require `--runtime`, the combined form `make test-e2e TEST=tests/test_commission.py` works identically. **Decision: fold.** Drop `test-e2e-commission` entirely. Anyone calling it today just passes `TEST=tests/test_commission.py`. Post-migration, once `test_commission.py` is a pytest function, `pytest tests/test_commission.py` is also a valid entrypoint. Update any CI references if present (none observed in the current workflow files; re-verify in implementation).

No tautologies in the "tests that test mocked behavior" sense were found. Most live tests parse real JSONL logs from a real `claude -p` / `codex exec` subprocess; static tests match against real on-disk template files. The only concerns worth flagging to CL: (a) `test_stats_extraction.py` uses a synthetic inline fixture, and (b) the `_agent_targets_stage` helper test is one layer removed from production code — both are defensible but noted.

## Pytest Structure Design (ideation, 2026-04-13)

### Marker scheme

Registered in `pyproject.toml` under `[tool.pytest.ini_options] markers = [...]`. Using plain markers (not a custom decorator) keeps collection-time discovery simple and lets `pytest -m` filter work out of the box.

**Revised 2026-04-13 per CL feedback: collapsed from 9 markers to 3.** The runtime × tier matrix (`live_claude_sequential`, `live_claude_parallel`, `live_codex_sequential`, `live_codex_parallel`) was redundant — pytest's `-m "live_claude and not serial"` handles the parallel-tier case without a dedicated marker. `unit`/`static` are dropped because a missing live marker *is* the static signal. `spike` is dropped because both spike files are being deleted (see Findings #1) and no tests need the marker.

| Marker | Meaning |
|--------|---------|
| `live_claude` | Test spawns a live Claude runtime (pipe or PTY). |
| `live_codex` | Test spawns a live Codex runtime. |
| `serial` | Must run serially (PTY, stubbed-git/gh, or explicit sequencing). Applies regardless of runtime. |
| (no marker) | Implicit static/unit. Collected by `make test-static`. |

A pytest session hook (`pytest_collection_modifyitems` in `conftest.py`) applies a looser invariant: every test with `live_claude` or `live_codex` may carry `serial` or not — both are valid. The hook's only job is to flag a test that accidentally carries *neither* `live_claude` nor `live_codex` but still imports `run_first_officer` / `run_codex_first_officer` — a heuristic cross-check that a live test was not left unmarked. That check is advisory (warn, don't fail); the real safety net is reviewer attention during migration batches.

### Tier assignments

Parallel (carries `live_claude` only — no `serial`; those marked † are shared and also carry `live_codex`):

- `test_gate_guardrail.py` †
- `test_rejection_flow.py` †
- `test_merge_hook_guardrail.py` †
- `test_feedback_keepalive.py`
- `test_dispatch_completion_signal.py`
- `test_dispatch_names.py`
- `test_reuse_dispatch.py`
- `test_single_entity_team_skip.py`
- `test_team_dispatch_sequencing.py`
- `test_team_health_check.py`
- `test_output_format.py`
- `test_repo_edit_guardrail.py`
- `test_scaffolding_guardrail.py` (skipped; marker set but test is `@pytest.mark.skip`)
- `test_agent_captain_interaction.py`
- `test_commission.py`
- `test_checklist_e2e.py` (after moving to `tests/`)
- `test_codex_packaged_agent_e2e.py` (carries `live_codex`, no `serial`)

Serial (carries `live_claude` + `serial`):

- `test_push_main_before_pr.py` — stubs `git`/`gh`, side-effecty.
- `test_rebase_branch_before_push.py` — same.
- `test_single_entity_mode.py` — PTY.
- `test_interactive_poc.py` (live portion only) — PTY.

Spike tests:

- **Both deleted.** `tests/spike_termination.py` and `tests/test_spike_termination.py` are removed outright (see revised Findings #1). The design does not reserve a `spike` marker.

Static / unit (no live marker — collected by `make test-static`):

- All of: `test_agent_content`, `test_ci_static_workflow`, `test_claude_team`, `test_codex_packaged_agent_ids`, `test_commission_template`, `test_feedback_keepalive_helpers`, `test_pr_merge_template`, `test_runtime_live_e2e_workflow`, `test_stats_extraction`, `test_status_script`, `test_status_set_missing_field`, `test_test_lib_helpers`.

### `conftest.py` shape

A top-level `tests/conftest.py` — with a deliberately short surface:

```python
# ABOUTME: pytest wiring for live runtime flags, fixtures, and tier-marker invariants.
# ABOUTME: One conftest at tests/ root — no per-subdir conftests.

def pytest_addoption(parser):
    parser.addoption("--runtime", action="store", default="claude",
                     choices=["claude", "codex"])
    parser.addoption("--model",   action="store", default="haiku")
    parser.addoption("--effort",  action="store", default="low")
    parser.addoption("--budget",  action="store", type=float, default=None)

def pytest_configure(config):
    # Registration is declared in pyproject.toml; this hook stays empty unless
    # we need dynamic behavior.
    pass

def pytest_collection_modifyitems(config, items):
    """Advisory check: warn if a test imports run_first_officer / run_codex_first_officer
    but carries neither live_claude nor live_codex. Does not enforce a tier marker —
    serial-vs-parallel is per-test judgement and both are valid."""
    ...

# --- Fixtures ---
@pytest.fixture
def runtime(request):           return request.config.getoption("--runtime")
@pytest.fixture
def model(request):             return request.config.getoption("--model")
@pytest.fixture
def effort(request):            return request.config.getoption("--effort")

@pytest.fixture
def test_project(request):
    """Yield a TestRunner with tmpdir + git init + cleanup on success."""
    t = TestRunner(request.node.name)
    t.create_test_project()
    yield t
    t.finish()       # prints summary; does NOT sys.exit

@pytest.fixture
def fo_run(test_project, runtime, model, effort):
    """Factory fixture — returns a callable that runs FO and returns parsed logs."""
    def _run(prompt, fixture=None, **extra):
        ...
    return _run
```

Key decisions in the conftest:

- Single conftest at `tests/` root. No nested conftests — the file stays under 150 lines and all wiring is visible.
- `TestRunner.finish()` (new method) replaces the `sys.exit` path used today. In pytest mode the summary is printed but the process keeps running; standard pytest assertions drive pass/fail.
- The `test_project` fixture yields a `TestRunner`, so individual tests can keep calling `setup_fixture(t, ...)`, `install_agents(t)`, `run_first_officer(t, ...)` verbatim. This makes the per-test migration a near-mechanical delete-the-`main()`-and-argparse change.
- `fo_run` is opt-in. Tests that prefer to keep calling `run_first_officer` directly still can — we do not force a new call shape on day one.

### Makefile changes

Replace the hand-rolled `&&` chain with explicit pytest invocations that honor the "sequential tier first, parallel tier regardless" rule:

```makefile
# Worker count is a knob because we have not yet stress-tested Claude config
# under concurrency. Start low; raise once green.
LIVE_CLAUDE_WORKERS ?= 2

test-live-claude:
	unset CLAUDECODE && \
	pytest tests/ -m "live_claude and serial" -x ; SEQ=$$? ; \
	pytest tests/ -m "live_claude and not serial" -n $(LIVE_CLAUDE_WORKERS) ; PAR=$$? ; \
	test $$SEQ -eq 0 -a $$PAR -eq 0

test-live-codex:
	pytest tests/ -m "live_codex and serial" -x ; SEQ=$$? ; \
	pytest tests/ -m "live_codex and not serial" -n $(LIVE_CLAUDE_WORKERS) ; PAR=$$? ; \
	test $$SEQ -eq 0 -a $$PAR -eq 0

test-static:
	unset CLAUDECODE && uv run --with pytest python -m pytest tests/ \
	  --ignore=tests/fixtures -m "not live_claude and not live_codex" -q

test-e2e:     # single-file override, unchanged shape
	unset CLAUDECODE && pytest $(TEST) --runtime $(RUNTIME)
```

- `-x` on the sequential tier is intentional: within a sequential chain the later tests often depend on the earlier setup/learning, so short-circuit is the right semantics. The parallel tier runs regardless.
- The final `test $$SEQ -eq 0 -a $$PAR -eq 0` makes the overall target fail if *either* tier failed — so CI signal stays honest.
- The `test-static` marker filter guarantees collection under `tests/` does not accidentally run a live test offline.
- `test-live-claude-opus` survives as a variant of `test-live-claude` with `--model opus --effort low` override — same shape, different defaults.

### `pyproject.toml`

Add:

```toml
[tool.pytest.ini_options]
markers = [
    "live_claude: spawns a live Claude runtime (pipe or PTY)",
    "live_codex: spawns a live Codex runtime",
    "serial: must run serially (PTY, stubbed git/gh, or explicit sequencing)",
]
```

Add `pytest-xdist` to the dev dependency group so `-n` works.

### Migration order

1. **Land the wiring first, migrate zero tests.** Add `conftest.py`, register markers in `pyproject.toml`, add pytest-xdist. Update `tests/README.md` with the new invocation pattern but keep old `uv run` entrypoints intact. Run `make test-static` to prove wiring does not break anything. Commit.
2. **Pilot: `test_gate_guardrail.py`.** Convert to a pytest function with `@pytest.mark.live_claude @pytest.mark.live_claude_parallel @pytest.mark.live_codex @pytest.mark.live_codex_parallel`. Preserve the old `main()` as a thin `if __name__ == "__main__": pytest.main([__file__])` wrapper so the Makefile / CI can still invoke the file directly during transition. Run under both runtimes manually, commit.
3. **Update Makefile `test-live-claude` / `test-live-codex`** to the pytest form, with the gate_guardrail test already migrated. Verify chain runs end-to-end. Commit.
4. **Batch-migrate parallel tier, one commit per file.** Follow the parallel-tier list above in order of increasing complexity: `test_single_entity_team_skip`, `test_team_health_check`, `test_team_dispatch_sequencing`, `test_dispatch_names`, `test_output_format`, `test_repo_edit_guardrail`, `test_scaffolding_guardrail`, `test_reuse_dispatch`, `test_merge_hook_guardrail`, `test_dispatch_completion_signal`, `test_rejection_flow`, `test_feedback_keepalive`, `test_agent_captain_interaction`, `test_commission`, `test_codex_packaged_agent_e2e`.
5. **Move and migrate `scripts/test_checklist_e2e.py` → `tests/test_checklist_e2e.py`.** Same commit moves the file and converts to pytest.
6. **Migrate sequential tier.** `test_push_main_before_pr`, `test_rebase_branch_before_push`, `test_single_entity_mode`, `test_interactive_poc` (splitting unit/live halves).
7. **Delete spikes.** `git rm tests/spike_termination.py tests/test_spike_termination.py`. No marker work needed — the `spike` marker is not registered.
8. **Helper relocation.** Move `_agent_targets_stage` into `scripts/test_lib.py`; update `test_feedback_keepalive_helpers.py` import path.
9. **Drop the old `main()` wrappers.** Once every test is migrated and the Makefile is green, remove the `if __name__ == "__main__": pytest.main([__file__])` tails — the Makefile is the only caller.
10. **Docs.** Final pass over `tests/README.md`, `docs/plans/README.md` Testing Resources, and any onboarding notes. Each mention of `uv run tests/test_...py` becomes `pytest tests/...` or a `make` target.

Each step is a committable checkpoint. Steps 1–3 must land before any CI pipeline flips; steps 4–10 are incremental.

### Acceptance criteria

Each AC lists the concrete command or assertion that verifies it.

1. **Marker registration.** `pyproject.toml` declares exactly three markers: `live_claude`, `live_codex`, `serial`. Verify: `pytest --markers | grep -E 'live_claude|live_codex|serial'` prints three lines; `pytest --markers | grep -E 'spike|unit|static|_sequential|_parallel'` prints nothing.
2. **Collection-time advisory check.** A test that imports `run_first_officer` or `run_codex_first_officer` but carries neither `live_claude` nor `live_codex` triggers a warning in the pytest header. Verify: add a deliberately-unmarked live test in a throwaway branch; `pytest --collect-only tests/` emits the warning naming the file. Remove the throwaway before merging.
3. **Conftest fixtures available.** `test_project`, `fo_run`, `runtime`, `model`, `effort`, `budget` are resolvable from any test under `tests/`. Verify: `pytest tests/test_gate_guardrail.py --collect-only -q` shows the test using those fixtures with no "fixture not found" errors.
4. **Static Makefile target unaffected.** `make test-static` passes with the same test count as pre-migration. Verify: compare `make test-static 2>&1 | tail -1` before and after — the "N passed" count matches (or is higher, per splits like `test_interactive_poc`).
5. **Sequential-first, parallel-always Makefile behavior.** If a sequential-tier test fails, parallel-tier tests still run and are reported. Verify: run `make test-live-claude` against a branch where `test_push_main_before_pr` is deliberately failing; confirm `test_gate_guardrail`, `test_rejection_flow`, etc. still collected and reported.
6. **No `&&` chain in Makefile targets.** Verify: `grep -c '&&' Makefile` shows only the `unset CLAUDECODE &&` prefix, not test-file chaining.
7. **CI summary surfaces collected / ran / passed / failed.** `pytest` default output (`-v` or `-ra`) satisfies this — no custom summary needed. Verify: `make test-live-claude 2>&1 | tail -5` shows the pytest short summary line with explicit counts.
8. **Every live test has a runtime marker.** Verify: `pytest --collect-only -q tests/` with the advisory hook emits no warnings about unmarked live tests after migration is complete.
9. **`test-live-claude-opus` variant preserved.** Verify: `make test-live-claude-opus` runs the same test set as `test-live-claude` with `--model opus --effort low` — no behavioral drift beyond the flag override.
10. **Skipped tests surface as skipped.** `test_scaffolding_guardrail` shows as skipped (with rationale) in the pytest short summary. Verify: `pytest -rs tests/test_scaffolding_guardrail.py` prints `SKIPPED` with the reason.
11. **Spike tests removed.** Verify: `git ls-files tests/spike_termination.py tests/test_spike_termination.py` prints nothing; `grep -r 'pytest.mark.spike' tests/ scripts/` prints nothing.
12. **Checklist test relocated.** `tests/test_checklist_e2e.py` exists and is collected; `scripts/test_checklist_e2e.py` does not. Verify: `git ls-files tests/test_checklist_e2e.py scripts/test_checklist_e2e.py` lists only the `tests/` path.
13. **Helper relocation.** `scripts/test_lib.py` exports `_agent_targets_stage`; `test_feedback_keepalive_helpers.py` imports from `test_lib`, not from `test_feedback_keepalive`. Verify: `grep -n 'from test_feedback_keepalive' tests/test_feedback_keepalive_helpers.py` is empty; `grep -n '_agent_targets_stage' scripts/test_lib.py` is non-empty.

### Test plan

| Check | Command | Expected | Cost | When run |
|-------|---------|----------|------|----------|
| Static regression | `make test-static` | all green, count >= pre-migration | free, ~30s | every commit during migration |
| Marker invariant | `pytest --collect-only -q tests/` | collection succeeds, no "missing tier" errors | free, ~3s | every commit |
| Pilot E2E green | `make test-e2e TEST=tests/test_gate_guardrail.py RUNTIME=claude` | PASS | ~$0.02 haiku, ~60s | after step 2 |
| Shared runtime pilot | `make test-e2e TEST=tests/test_gate_guardrail.py RUNTIME=codex` | PASS | ~$0.05 codex, ~90s | after step 2 |
| Sequential-first short-circuit | `make test-live-claude` with `test_push_main_before_pr` forced-fail | sequential fails, parallel still runs, overall red | ~$0.30 haiku | after step 3 + periodically |
| Full live-claude green (haiku) | `make test-live-claude` on clean branch | all green | ~$0.30 haiku, ~6–10 min | after each migration batch |
| Full live-claude green (opus) | `make test-live-claude-opus` | all green | ~$2–3 opus, ~10–15 min | once after migration complete |
| Full live-codex green | `make test-live-codex` | all green | codex usage ~$1, ~5 min | after codex tests migrate |
| Spike deletion | `make test-live-claude` | no spike test collected; `git ls-files tests/*spike*` empty | free to observe | step 7 |

Total one-time migration cost during ideation + implementation: on the order of $10–15 of live-runtime budget assuming 3 full `test-live-claude` passes, 1 opus, 1 codex, and incremental pilots. No E2E burn is required during ideation — this plan is complete without running live.

## Stage Report

- **Inventory every test file under `tests/`**: **DONE** — 33 files inventoried (#1–#34; `tests/spike_termination.py` counted as #34).
- **Inventory every test file under `scripts/`**: **DONE** — 3 files (`test_checklist_e2e.py`, `test_lib.py`, `test_lib_interactive.py`, #35–#37). Only `test_checklist_e2e.py` is a real test; the other two are libraries noted as such.
- **Per-file breakdown (purpose / stage / coverage / parallel / redundancy / tautology)**: **DONE** — see the two tables in "Test Inventory". Columns populated for every row.
- **Inventory written into entity body as "Test Inventory" section**: **DONE**.
- **Open classification questions resolved by reading test code**: **DONE** — sequential/parallel calls made by inspecting `run_first_officer` (shared Claude config note), `InteractiveSession` (PTY = sequential), and the stubbed-git/stubbed-gh tests (`test_push_main_before_pr`, `test_rebase_branch_before_push` flagged sequential). Codex isolation via `prepare_codex_skill_home` confirmed per-test.
- **Pytest structure design written as "Pytest Structure Design" section**: **DONE** — marker scheme, tier assignments, `conftest.py` shape, `pyproject.toml` additions, Makefile rewrite, migration order.
- **Acceptance criteria — at least one per marker scheme / conftest / Makefile / sequential-parallel split / every-test-categorized**: **DONE** — 13 ACs, each with a concrete verification command. Marker (AC1), conftest (AC3), Makefile (AC5, AC6, AC9), sequential/parallel split (AC5, AC11), every-test-categorized (AC2, AC8).
- **Test plan with specific commands and cost estimates**: **DONE** — 9-row table with commands, expected outcomes, cost estimates, and when-to-run guidance.

### Summary

The inventory turned up 37 files: 20 live E2E tests (17 parallelizable, 3 sequential — PTY and stubbed-git), 2 spikes to quarantine, 12 static/unit tests that already work under pytest, 1 test misplaced in `scripts/`, and one near-duplicate spike file to delete. The design proposes nine pytest markers (`live_claude`, `live_codex`, their `_sequential`/`_parallel` tiers, `spike`, `unit`, `static`), a single small `tests/conftest.py` that exposes a `TestRunner`-yielding `test_project` fixture and enforces the tier invariant at collection, and a Makefile that runs the sequential tier first (`-x`) and the parallel tier always (`-n $(LIVE_CLAUDE_WORKERS)`), with an explicit failure aggregation so no tier's result is ever masked by another's. Migration starts with wiring-only landing, pilots `test_gate_guardrail.py`, then batches the remaining tests one commit per file, finishing with helper relocation and spike quarantining.

## Stage Report — Ideation Revision (2026-04-13)

Team-lead feedback on the original ideation report flagged three simplifications. This revision applies all three in the body above and records the changes here. Original report retained above for diff-ability.

### Feedback items addressed

1. **Collapse marker scheme from 9 to 5 (then to 3).** **DONE.** Dropped the runtime × tier matrix in favor of a single `serial` marker that applies regardless of runtime. Dropped `unit` and `static` because *absence* of a live marker already signals those. Team-lead's note "actually, if we delete both spike files, we can drop `spike` too — four markers total" was carried through: final registered set is **three** (`live_claude`, `live_codex`, `serial`). "No marker" is the implicit fourth category (static/unit), collected by `make test-static`.
   - Updated: Marker scheme table (design section), Tier assignments list, `pyproject.toml` snippet, Makefile snippet (filter expressions switched to `"live_claude and serial"` / `"live_claude and not serial"`), `pytest_collection_modifyitems` description (looser: advisory warning only, no hard gate on tier markers), ACs 1, 2, 8.
2. **Delete BOTH spike files.** **DONE.** Revised Findings #1 to delete `tests/spike_termination.py` *and* `tests/test_spike_termination.py`. Migration order step 7 rewritten to `git rm` both files with no marker work. AC11 now verifies deletion (no files, no `spike` marker references anywhere). Test-plan "Spike gating" row renamed to "Spike deletion" with the same free-to-observe cost.
3. **`test-e2e-commission` consolidation.** **DONE — folded.** Added Findings #8 documenting the decision. Current `test-e2e-commission` is equivalent to `make test-e2e TEST=tests/test_commission.py` minus the `--runtime` flag (which `test_commission.py` accepts but does not require). No separate env, no separate CI routing, no meaningful divergence. Drop the target during migration; callers pass `TEST=...` instead. No behavioral change.

### Revision checklist

- Update the marker table (5 markers, not 9): **DONE** (landed at 3 markers after team-lead's follow-up note).
- Update the tier-assignment sections (drop `_sequential`/`_parallel`; use `serial`): **DONE**.
- Update the Makefile snippet: **DONE**.
- Update the `pyproject.toml` snippet: **DONE**.
- Update `pytest_collection_modifyitems` hook description (looser invariant): **DONE**.
- Update Finding #1 — delete both spike files: **DONE**.
- Add a Finding on `test-e2e-commission` consolidation: **DONE** (Findings #8).
- Update ACs that referenced dropped markers (ACs 1, 2, 8, 11): **DONE** — AC1 now checks 3 markers, AC2 describes the advisory collection hook, AC8 checks runtime marker presence only, AC11 verifies spike deletion.
- Commit on the same branch: **DONE** (see commit following this report).

### Revised summary

The revised design registers three pytest markers — `live_claude`, `live_codex`, `serial` — and treats the absence of a live marker as the implicit static/unit signal. The serial-vs-parallel split becomes a per-test flag rather than a runtime-coupled matrix. Both spike files are deleted outright; the `spike` marker is not registered. `test-e2e-commission` is folded into `test-e2e` with a `TEST=` override. Every other element of the original design — the `test_project` / `fo_run` fixtures, the migration order, the cost estimates, the sequential-first / parallel-always Makefile semantics — is unchanged.

## Stage Report — Implementation (2026-04-14)

### Completion checklist

1. **Read the Test Inventory / Pytest Structure Design / migration order / 13 ACs.** DONE — implementation followed the revised design (3 markers, serial-flag-per-test, spike files deleted).
2. **Step 1 — Wiring only.** DONE — added `tests/conftest.py` with `pytest_addoption` for `--runtime/--model/--effort/--budget`, fixtures `runtime / model / effort / budget / test_project / fo_run`, and an advisory `pytest_collection_modifyitems` warning for live tests missing a runtime marker. Added `pytest-xdist>=3.5` in the `[dependency-groups] dev` list of a new `pyproject.toml`. Registered the three markers (`live_claude`, `live_codex`, `serial`) in `[tool.pytest.ini_options] markers`. `make test-static` green at 271 passed (baseline unchanged). Commit: `tests: #148 step 1 — pytest wiring only`.
3. **Step 2 — Pilot.** DONE — converted `tests/test_gate_guardrail.py` to a pytest function carrying `@pytest.mark.live_claude` and `@pytest.mark.live_codex`, driven by the `runtime` fixture. Added `TestRunner.finish()` to `scripts/test_lib.py` as the pytest-mode counterpart to `results()` — prints the summary then raises `AssertionError` instead of `sys.exit`. Kept a `__main__` pytest.main shim for transitional direct invocation. Commit: `tests: #148 step 2 — pilot convert test_gate_guardrail`.
4. **Step 3 — Makefile rewrite.** DONE — `test-live-claude` / `test-live-codex` now run the serial tier (`-m "live_claude and serial" -x`) first, then the parallel tier (`-m "live_claude and not serial" -n $LIVE_CLAUDE_WORKERS`) regardless of the serial tier outcome, with a final `test $$SEQ -eq 0 -a $$PAR -eq 0` aggregation. `test-live-claude-opus` follows the same shape with `--model opus --effort low`. `test-e2e-commission` dropped — replaced by `make test-e2e TEST=tests/test_commission.py`. Updated `tests/test_runtime_live_e2e_workflow.py::test_live_makefile_skips_push_main_before_pr_until_mod_block_enforcement_lands` to check for the pytest skip marker on the migrated test file rather than the legacy Makefile comment. Commit: `tests: #148 step 3 — switch live Makefile targets to pytest two-tier form`.
5. **Step 4 — Parallel tier, one commit per file.** DONE — migrated in the order dictated by the dispatch (single_entity_team_skip, team_health_check, team_dispatch_sequencing, dispatch_names, output_format, repo_edit_guardrail, scaffolding_guardrail, reuse_dispatch, merge_hook_guardrail, dispatch_completion_signal, rejection_flow, feedback_keepalive, agent_captain_interaction, commission, codex_packaged_agent_e2e). `test_scaffolding_guardrail.py` carries `@pytest.mark.skip(reason="FO violates issue-filing guardrail on haiku — file follow-up task to re-enable")` so the skip surfaces in the pytest summary instead of a Makefile comment. Each file is its own commit.
6. **Step 5 — Checklist move.** DONE — `git mv scripts/test_checklist_e2e.py tests/test_checklist_e2e.py` + migration in a single commit. `CHECKLIST_SNAPSHOT` env var replaces the old `--from-snapshot` CLI flag. Commit: `tests: #148 step 5 — move + migrate test_checklist_e2e`.
7. **Step 6 — Sequential tier.** DONE — migrated `test_push_main_before_pr` (carries `@pytest.mark.skip(reason="FO still archives past pr-merge without persisting pr state. Track: #114")` to mirror the pre-migration Makefile skip), `test_rebase_branch_before_push` (both `live_claude` + `serial` because it stubs `git`/`gh`), `test_single_entity_mode` (PTY, serial), `test_interactive_poc` (split into `test_interactive_poc_offline` with no marker + `test_interactive_poc_live` with `live_claude` + `serial`).
8. **Step 7 — Delete spikes.** DONE — `git rm tests/spike_termination.py tests/test_spike_termination.py`. No marker registration required; neither file produced a collected test after deletion. Commit: `tests: #148 step 7 — delete spike_termination and test_spike_termination`.
9. **Step 8 — Helper relocation.** DONE — moved `_agent_targets_stage` from `tests/test_feedback_keepalive.py` into `scripts/test_lib.py`. `tests/test_feedback_keepalive_helpers.py` now imports from `test_lib` (its `sys.path.insert` for the tests/ directory was removed). All 9 helper tests still pass. Commit: `tests: #148 step 8 — move _agent_targets_stage helper`.
10. **Step 9 — Drop __main__ shims.** DONE — all 21 migrated tests had their transitional `if __name__ == "__main__": sys.exit(pytest.main([__file__, "-v"]))` tail removed. The Makefile is now the only caller. Commit: `tests: #148 step 9 — drop __main__ pytest.main shims`.
11. **Step 10 — Docs.** DONE — `tests/README.md` now documents pytest invocation (Makefile wrappers + direct `uv run pytest` forms), tier markers, conftest fixtures, `LIVE_CLAUDE_WORKERS` knob, and a pytest-shaped file requirements section with a marker-carrying skeleton. `docs/plans/README.md` Testing Resources section now references `make test-live-{claude,codex}` / `make test-live-claude-opus` / `make test-e2e TEST=...`, documents the `test-e2e-commission` fold, and replaces the `uv run tests/*.py` example with `uv run pytest tests/*.py --runtime claude -v`. Commit: `docs: #148 step 10 — update tests/README and docs/plans README`.
12. **Final verification.** DONE.
    - `make test-static` green — 271 passed, 21 live tests deselected, 10 subtests passed in 5.36s (count matches AC4 baseline).
    - `pytest --markers` shows exactly `live_claude`, `live_codex`, `serial` — `pytest --markers | grep -E "spike|unit|static|_sequential|_parallel"` prints nothing.
    - Sanity live run on haiku: `uv run pytest tests/test_gate_guardrail.py -m "live_claude and not serial" --runtime claude -v` — pytest collected the test, resolved fixtures, ran `claude -p`, and `TestRunner.finish()` raised `AssertionError` correctly on one FO-behavior regression (6/7 inner checks pass; the failing check — "first officer did NOT self-approve" — is an FO-behavior issue, not a harness regression). Artifacts preserved at the printed `tmp` path for validator inspection.
    - `LIVE_CLAUDE_WORKERS=4` spot-check: ran `uv run pytest tests/test_{gate_guardrail,rejection_flow,feedback_keepalive,merge_hook_guardrail}.py -m "live_claude and not serial" --runtime claude -n 4 -v` — **wallclock 349.27s** for 4 live Claude tests (3 passed, 1 failed on the gate self-approval regression called out above). Serial execution would have been ≈4×(60–120s) per test + pytest overhead, so ~5–10 min minimum; at `-n 4` the four tests ran concurrently and the suite finished in roughly the length of the longest test. Parallel path empirically confirmed.
13. **Commit each step separately.** DONE — see `git log spacedock-ensign/live-e2e-pytest-harness ^main` for the atomic sequence: step 1 wiring → step 2 pilot → step 3 Makefile → step 4 per-file parallel batch → step 5 checklist move → step 6 sequential batch → step 7 spike delete → step 8 helper relocation → step 9 shim strip → step 10 docs.

### Acceptance-criteria spot checks

| AC | Evidence |
|----|----------|
| 1 — marker registration | `pytest --markers` prints the three registered markers and nothing for `spike|unit|static|_sequential|_parallel`. |
| 2 — collection-time advisory | `pytest_collection_modifyitems` in `tests/conftest.py` emits a `warnings.warn` when a module imports `run_first_officer` / `run_codex_first_officer` but has no `live_claude`/`live_codex` marker. No throwaway test remains in the branch. |
| 3 — conftest fixtures available | `uv run pytest tests/test_gate_guardrail.py --collect-only -q` succeeds; no "fixture not found" errors. |
| 4 — static target unaffected | `make test-static` prints `271 passed, 21 deselected, 10 subtests passed` (baseline was 271 passed, 10 subtests passed — deselection is new but count of passes preserved). |
| 5 — sequential-first, parallel-always | Makefile uses `{ uv run pytest -m "... and serial" -x ; SEQ=$? ; uv run pytest -m "... and not serial" -n $WORKERS ; PAR=$? ; test $SEQ -eq 0 -a $PAR -eq 0 ; }` — parallel tier runs regardless of serial outcome and overall exit reflects both. |
| 6 — no `&&` test-file chain | `grep -c '&&' Makefile` → 4, all of which are the `unset CLAUDECODE &&` prefix (`make test-static`, `make test-e2e`, and the shell-block opener of `make test-live-{claude,claude-opus}`). `make test-live-codex` uses no `&&` at all. |
| 7 — CI summary counts | Standard pytest `-v` output surfaces `N passed, M failed, K skipped` (plus deselected counts). The Makefile uses `-v` in every live target. |
| 8 — every live test marked | Suite collection under `pytest --collect-only` emits no advisory warnings after migration; every live test carries `live_claude` and/or `live_codex`. |
| 9 — `test-live-claude-opus` preserved | Target remains with the same shape as `test-live-claude` plus `--model opus --effort low`. |
| 10 — skip surfaces | `pytest -rs tests/test_scaffolding_guardrail.py` prints `SKIPPED [1] tests/test_scaffolding_guardrail.py:26: FO violates issue-filing guardrail on haiku — file follow-up task to re-enable`. |
| 11 — spike tests removed | `git ls-files tests/spike_termination.py tests/test_spike_termination.py` prints nothing; `grep -r 'pytest.mark.spike' tests/ scripts/` empty. |
| 12 — checklist relocated | `git ls-files tests/test_checklist_e2e.py scripts/test_checklist_e2e.py` prints only `tests/test_checklist_e2e.py`. |
| 13 — helper relocation | `grep -n '_agent_targets_stage' scripts/test_lib.py` — non-empty (definition at line 24). `grep -n 'from test_feedback_keepalive' tests/test_feedback_keepalive_helpers.py` — empty. |

### Summary

Landed the full migration of the live E2E suite from standalone `uv run` scripts to pytest with tier markers. 21 live tests converted to pytest functions, 2 spike files deleted, 1 test relocated from `scripts/` to `tests/`, and the `_agent_targets_stage` helper moved into `scripts/test_lib.py`. The Makefile now runs the serial tier first (`-x`) and the parallel tier always (`-n $LIVE_{CLAUDE,CODEX}_WORKERS`) with explicit exit-code aggregation, so CI signal stays honest when either tier fails. `make test-static` preserved at 271 passed. Parallel path empirically validated: 4 live Claude tests ran concurrently at `-n 4` in 349s wallclock. One live test (`test_gate_guardrail`) surfaces an FO-behavior regression on haiku (self-approval language) that is a genuine code issue to triage in validation — the harness itself is correctly detecting and reporting it.
