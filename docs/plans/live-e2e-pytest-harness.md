---
id: 148
title: "Migrate live E2E tests to pytest with runtime markers"
status: backlog
source: "CL observation during 2026-04-13 session — standalone uv-run scripts cause test sprawl and boilerplate duplication"
started:
completed:
verdict:
score: 0.70
worktree:
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
