---
id: 174
title: "CI workflow bisection inputs — pin Claude Code version, run specific tests"
status: backlog
source: "CL directive during 2026-04-16 session — PR #105 introduced a test failure that correlates with the claude-opus-4-6 → claude-opus-4-7 cutover. Bisecting the Claude Code version against a specific test is currently impossible without code commits."
started:
completed:
verdict:
score: 0.7
worktree:
issue:
pr:
---

## Problem Statement

The `runtime-live-e2e.yml` workflow always installs the latest Claude Code with `curl -fsSL https://claude.ai/install.sh` and runs the full live suite. This produces reproducibility problems when debugging model or runtime regressions:

- **No version pinning.** When a test starts failing and the timing correlates with a Claude Code release (e.g., PR #105's failure aligned with the `claude-opus-4-6` → `claude-opus-4-7` default cutover), we cannot rerun the old CI workflow against the old Claude Code version to confirm. We can only push new commits and hope the cutover reverses on its own.

- **No selective test execution.** Debugging one failing test requires waiting for the full `make test-live-claude` / `make test-live-claude-opus` suite to finish, even though only one test matters. On opus that is 25 minutes per run; bisection across three or four Claude Code versions is 100+ minutes of CI time for a single-variable hypothesis test.

- **No programmatic effort override.** `make test-live-claude-opus` hardcodes `--effort low`. Checking whether a failure is effort-sensitive — common with `claude-opus-4-7`'s stricter effort calibration, per its migration guide — requires editing the Makefile and pushing.

## Observed impact (2026-04-16 session)

PR #105 (prose tightening) and PR #107 (lazy-spawn) both saw `claude-live-opus` failures that appear correlated with the model cutover. PR #100 passed on `claude-opus-4-6`. The fault domain — prose change, helper logic, model version, or Claude Code runtime version — remains ambiguous because variables cannot be isolated without pushing commits. A bisectable workflow would isolate the fault in a single afternoon.

## Proposed design

Extend `runtime-live-e2e.yml` with three new `workflow_dispatch` `inputs`, optional, preserving current defaults when omitted:

- `claude_version` — pin the installed Claude Code version (default: latest). Install step branches on this input: empty → `curl | sh`, set → `curl | sh --version {claude_version}` or equivalent pinning path the installer exposes.
- `test_selector` — pass a pytest `nodeid` or path to narrow the run (default: current full-suite shape). Example: `tests/test_standing_teammate_spawn.py::test_standing_teammate_spawns_and_roundtrips`.
- `effort_override` — override the `--effort` flag passed to `run_first_officer` in tests that honor it (default: respect the Makefile's hardcoded value). Example: `high` or `xhigh`.

Tests are invoked through a modified step that reads these inputs:

```yaml
- name: Run live suite
  run: |
    if [ -n "${{ inputs.test_selector }}" ]; then
      uv run pytest "${{ inputs.test_selector }}" \
        --runtime claude \
        ${{ inputs.effort_override && format('--effort {0}', inputs.effort_override) || '' }} \
        -v
    else
      make test-live-claude
    fi
```

Captain invocation via `gh workflow run` for a bisection step:

```
gh workflow run runtime-live-e2e.yml --ref main \
  -f claude_version=2.1.107 \
  -f test_selector=tests/test_standing_teammate_spawn.py::test_standing_teammate_spawns_and_roundtrips \
  -f effort_override=low
```

This produces a one-job run that isolates a single variable (Claude Code version) against a single test at a fixed effort, then reports pass/fail in ~5-10 minutes instead of 25.

## Open questions for ideation

- Does the `claude.ai/install.sh` installer support version pinning? If not, what is the mechanism — download a specific release artifact from GitHub, pin an npm version, or raise upstream? The answer affects complexity.
- Does `test_selector` apply to all four jobs (`CI-E2E`, `CI-E2E-OPUS`, `CI-E2E-CODEX`, bare) or only a subset? Which jobs accept the selector and which ignore it?
- Should `effort_override` propagate to tests that do not currently take `--effort` (e.g., bare-mode tests), or stay strictly additive for tests that already honor it?
- Is a fourth input `model_override` (sonnet/opus/haiku) worth adding so one job can run with a model different from its Makefile default? Low cost, expands bisection reach.
- Should each job report the installed `claude --version` explicitly in its output for audit trail, independent of whether it was pinned?
- Do the current environment-approval gates (`CI-E2E`, `CI-E2E-OPUS`, `CI-E2E-CODEX`) still gate manual dispatch, or does `workflow_dispatch` bypass them? If they still gate, the captain must approve each bisection run — that is probably fine but should be documented.

## Relationship to other tasks

- **#171** (Agent model override teams-mode) — this workflow would let us bisect Claude Code versions to pinpoint when `Agent(model=haiku)` stopped propagating.
- **#173** (streaming FO watcher) — a streaming watcher plus this bisection infrastructure is the minimal setup for reliably debugging live-runtime regressions. They compose well but ship independently.

## Out of Scope

- Regression tracking, history, or dashboards for bisection runs.
- Rewriting the existing Makefile targets. Current `make test-live-*` targets stay; this task adds manual-dispatch inputs that compose with them.
- Codex-runtime version pinning, if the Codex CLI distribution model is materially different from Claude Code's. Scope to Claude Code for v1.
