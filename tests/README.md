# Test Authoring Guidelines

This document covers the Spacedock test infrastructure, conventions, and how to write tests that integrate with the existing harness.

## Test Infrastructure Overview

Tests live in `tests/` and share two library modules under `scripts/`:

| Module | Purpose | Session type |
|--------|---------|-------------|
| `scripts/test_lib.py` | Non-interactive tests via `claude -p` or `codex exec` | Pipe mode (structured JSONL logs) |
| `scripts/test_lib_interactive.py` | Interactive multi-turn tests via PTY | Interactive TUI (raw terminal output) |

### `test_lib.py` — Non-Interactive Harness

Provides `TestRunner`, `LogParser`, `CodexLogParser`, and project setup helpers. Use this when:

- Testing FO behavior that runs to completion without human interaction (single-entity mode, guardrails, dispatch patterns)
- You need structured log parsing (tool calls, agent dispatches, text output)
- The test should support both `--runtime claude` and `--runtime codex`

Key classes and functions:

- **`TestRunner`** — Test framework with pass/fail counters, temp directory management, and results summary. Automatically cleans up temp dirs on success and preserves them on failure.
- **`LogParser`** — Parses `--output-format stream-json` JSONL logs from `claude -p`. Provides `tool_calls()`, `agent_calls()`, `fo_texts()`, `assistant_messages()`.
- **`CodexLogParser`** — Parses mixed JSON/text output from `codex exec --json`. Provides `full_text()`, `spawn_count()`, `completed_agent_messages()`.
- **`create_test_project(runner)`** — Creates a temp git repo with an initial empty commit.
- **`setup_fixture(runner, fixture_name, pipeline_dir)`** — Copies a fixture from `tests/fixtures/` into the test project.
- **`install_agents(runner, include_ensign=False)`** — Copies agent wrappers (`.claude/agents/`) into the test project.
- **`run_first_officer(runner, prompt, ...)`** — Runs `claude -p` with `--plugin-dir`, `--agent`, `--permission-mode bypassPermissions`, `--verbose`, `--output-format stream-json`. Returns exit code.
- **`run_codex_first_officer(runner, workflow_dir, ...)`** — Runs `codex exec` with skill home setup. Returns exit code.
- **`assembled_agent_content(runner, agent_name)`** — Reads the agent entry point and all referenced files, returning the full behavioral contract as a string. Useful for static content checks.
- **`git_add_commit(project_dir, message)`** — Stage all and commit.
- **`extract_stats(log_path, phase_name, output_dir)`** — Extract token usage, wallclock time, and model delegation from a JSONL log.

### `test_lib_interactive.py` — PTY Interactive Harness

Provides `InteractiveSession` for driving live Claude Code TUI sessions. Use this when:

- Testing multi-turn interactive behavior (skill invocations, team interactions, captain-agent communication)
- The behavior under test requires an interactive session (not reproducible via `-p`)
- You need to send multiple messages and check responses sequentially

Key class:

- **`InteractiveSession`** — Spawns `claude` in a PTY, waits for the prompt, sends messages, and checks output for patterns.
  - `start(ready_timeout)` — Start session and wait for the `❯` prompt.
  - `send(message)` — Type a message and press Enter.
  - `send_key(key_name)` — Send a special key sequence (e.g., `shift-down`, `ctrl-c`).
  - `wait_for(pattern, timeout, min_matches)` — Wait for a regex pattern in output after the last `send()`. Default `min_matches=2` to skip the input echo.
  - `stop()` — Send `/exit` and kill the process.
  - `get_clean_output()` — Return output with ANSI escapes stripped.
  - `get_subagent_logs(project_dir)` — Find subagent JSONL logs for the session.

**Trust dialog handling:** When `cwd` points to an untrusted directory, Claude Code shows a trust dialog that blocks the PTY. Use `start_with_trust_handling()` (see `test_single_entity_mode.py`) to detect and dismiss the dialog before waiting for the prompt.

## Standard CLI Flags

All E2E tests should accept these flags via `argparse`:

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--runtime` | `choices=["claude"]` or `choices=["claude", "codex"]` | `"claude"` | Which runtime to test. Use `["claude"]` for interactive-only tests. |
| `--agent` | `str` | `"spacedock:first-officer"` | Agent id to invoke |
| `--model` | `str` | `"haiku"` | Model for the test run |
| `--effort` | `str` | `"low"` | Effort level (non-interactive tests) |
| `--budget` | `float` | varies | Max budget in USD |

Tests should run by default without special flags. Do not gate tests behind a `--live` flag.

Use `parse_known_args()` to pass extra CLI args through to the claude/codex invocation:

```python
def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="My E2E test")
    parser.add_argument("--runtime", choices=["claude", "codex"], default="claude")
    parser.add_argument("--model", default="haiku")
    return parser.parse_known_args()
```

## When to Use Which Harness

### Static content checks (`assembled_agent_content`, `file_contains`)

Use for verifying that reference files, agent contracts, or assembled prompts contain required text patterns. These are fast, free, and should be the first line of defense.

Examples: `test_agent_content.py`, `test_codex_packaged_agent_ids.py`, static portions of `test_reuse_dispatch.py`.

### Non-interactive E2E (`test_lib.py` + `run_first_officer`)

Use for testing FO/ensign behavior that runs to completion in pipe mode. The test sets up a fixture, runs `claude -p` or `codex exec`, and parses the structured JSONL logs for tool calls, text output, and behavioral patterns.

Examples: `test_gate_guardrail.py`, `test_rejection_flow.py`, `test_single_entity_team_skip.py`.

### Codex FO Prompt Discipline

When a test exercises Codex first-officer behavior:

- Invoke only `$first-officer` / `spacedock:first-officer`.
- Keep the invocation prompt minimal: identify the workflow target, runtime, and entity scope only.
- Do not add behavioral coaching in the test prompt for reuse, wait semantics, shutdown, rejection routing, or other FO operating rules.
- If Codex FO behavior needs to change, encode that in the scaffolding under test: `SKILL.md` references, shared core, runtime adapter, or fixture/workflow structure.
- Prefer shared runtime-switchable tests such as `test_rejection_flow.py --runtime codex` for generic workflow behavior. Use Codex-only E2E tests only for truly Codex-specific deltas that cannot be covered by the shared path.

### Interactive PTY (`test_lib_interactive.py` + `InteractiveSession`)

Use only when the behavior under test requires an interactive session — multi-turn conversation, skill invocations, team member switching, or behavior that differs between interactive and pipe mode.

Examples: `test_interactive_poc.py`, `test_single_entity_mode.py`.

### Purely offline (no claude/codex)

Some tests validate infrastructure without needing a live session: `test_stats_extraction.py` (log parsing), `test_status_script.py` (status script behavior), `test_codex_packaged_agent_ids.py` (worker id resolution).

## Fixture Conventions

Fixtures live under `tests/fixtures/{fixture-name}/` and represent minimal self-contained workflows:

```
tests/fixtures/spike-no-gate/
  README.md        # Workflow README with frontmatter (stages, entity labels)
  status           # Executable status script (copied from the real one)
  test-entity.md   # Pre-seeded entity file with frontmatter
```

Each fixture directory contains:

- **`README.md`** — Workflow definition with `commissioned-by` frontmatter, stages, schema, and stage definitions.
- **`status`** — The status script (executable). Copied from `skills/commission/bin/status` or a test-specific variant.
- **Entity files** — One or more `.md` files with YAML frontmatter at appropriate starting stages.
- **Optional extras** — Source files, test directories, or `_mods/` for hook-specific tests.

Existing fixtures and their purposes:

| Fixture | Stages | Purpose |
|---------|--------|---------|
| `spike-no-gate` | backlog → work → done | Minimal no-gate pipeline for basic dispatch tests |
| `spike-gated` | backlog → work (gated) → done | Gate approval behavior |
| `gated-pipeline` | Similar to spike-gated | Gate guardrail testing |
| `multi-stage-pipeline` | Multiple stages | Multi-stage dispatch and reuse |
| `reuse-pipeline` | Stages with reuse conditions | Agent reuse vs fresh dispatch |
| `rejection-flow` | Includes validation with `feedback-to` | Rejection and feedback cycle testing |
| `rejection-flow-packaged-agent` | Same with `agent:` property | Packaged agent rejection flow |
| `merge-hook-pipeline` | Terminal stage with `_mods/` | Merge hook execution |
| `push-main-pipeline` | Terminal with PR mod | Push ordering and PR creation |
| `output-format-custom` / `output-format-default` | With/without `## Output Format` | Output format behavior |

## Running Tests

Tests use `uv run`. When running from inside a Claude Code session (including from dispatched team agents / ensigns), unset `CLAUDECODE` first — Claude Code refuses to launch as a subprocess when this variable is set. The `unset CLAUDECODE &&` prefix is the escape hatch:

```bash
unset CLAUDECODE && uv run tests/test_agent_content.py
```

This works from any context: your terminal, the FO session, a dispatched ensign's Bash tool call, or a CI runner. The spawned `claude -p` subprocess gets its own isolated home directory with the project's OAuth token, so authentication is handled automatically.

Stable repo-level entrypoints:

```bash
make test-static
make test-e2e TEST=tests/test_gate_guardrail.py RUNTIME=codex
```

- `make test-static` is the canonical offline repo suite. It runs `pytest tests/ --ignore=tests/fixtures` because `tests/fixtures/` contains runnable fixture payloads for harness tests, not repo-level suite modules.
- `make test-e2e` is the canonical live harness entrypoint. Override `TEST=...` to choose the E2E script and `RUNTIME=claude|codex` to select the runtime.
- Do not use bare repo-wide `pytest tests/` as the suite entrypoint unless you intentionally want pytest to recurse into `tests/fixtures/`.

Static tests (no live session needed):

```bash
make test-static
uv run tests/test_agent_content.py
uv run tests/test_codex_packaged_agent_ids.py
uv run tests/test_stats_extraction.py
uv run tests/test_status_script.py
```

E2E tests (require live claude, cost varies):

```bash
make test-e2e TEST=tests/test_gate_guardrail.py RUNTIME=claude
unset CLAUDECODE && uv run tests/test_gate_guardrail.py --model haiku
unset CLAUDECODE && uv run tests/test_single_entity_mode.py --model haiku
```

With Codex runtime:

```bash
make test-e2e TEST=tests/test_gate_guardrail.py RUNTIME=codex
uv run tests/test_gate_guardrail.py --runtime codex
```

Set `KEEP_TEST_DIR=1` to preserve temp directories after test runs for debugging.

## File Requirements

Every test file must:

1. Start with `#!/usr/bin/env -S uv run` and `# /// script` / `# ///` header for `uv run` compatibility
2. Have two `# ABOUTME:` comment lines explaining what the test does
3. Use `argparse` with standard CLI flags
4. Print `RESULT: PASS` or `RESULT: FAIL` and exit with appropriate code

Example header:

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: E2E test for feature X in the first-officer template.
# ABOUTME: Verifies behavior Y using fixture Z.
```
