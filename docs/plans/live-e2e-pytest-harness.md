---
id: 148
title: "Migrate live E2E tests to pytest with runtime markers"
status: ideation
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
