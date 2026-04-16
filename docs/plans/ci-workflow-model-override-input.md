---
id: 176
title: "CI workflow `model_override` input — parameterize Claude model for bisection and mitigation"
status: validation
source: "CL directive during 2026-04-16 session — 2.1.111 bisection confirmed the regression is Claude Code's default-alias flip from claude-opus-4-6 to claude-opus-4-7. Mitigation via dated-model pin needs workflow parameterization; #174 shipped claude_version but not model_override."
started: 2026-04-16T22:57:26Z
completed:
verdict:
score: 0.55
worktree: .worktrees/spacedock-ensign-ci-workflow-model-override-input
issue:
pr:
mod-block: merge:pr-merge
---

## Problem Statement

#174 added `claude_version`, `test_selector`, and `effort_override` inputs to `runtime-live-e2e.yml`. The model name is still hardcoded per job: `--model opus` for the opus job, default (haiku) for the others. This is the last remaining variable that bisection and mitigation work cannot parameterize from the dispatch form.

The 2026-04-16 bisection narrowed the opus regression to a one-version window (2.1.110 → 2.1.111). Evidence from the `fo-log.jsonl` artifacts shows the regression is specifically that `--model opus` changed resolution: 2.1.107 and 2.1.110 resolve it to `claude-opus-4-6`; 2.1.111 resolves it to `claude-opus-4-7`. Confirming this hypothesis — and mitigating it — requires passing `--model claude-opus-4-6` explicitly. Today that requires editing the workflow file and pushing a PR per experiment, which defeats the fast-bisection purpose of #174.

## Proposed design

Add a fourth optional `workflow_dispatch` input to `runtime-live-e2e.yml`:

- `model_override` — string, optional, default empty. When set, each job's test-run step substitutes `$MODEL_OVERRIDE` for the job's default `--model` value.

Per-job threading:

- `claude-live` (haiku default): today has no explicit `--model` flag. When `model_override` is set, pass `--model $MODEL_OVERRIDE`.
- `claude-live-bare` (haiku default): same shape as `claude-live`.
- `claude-live-opus` (opus default): today passes `--model opus`. When `model_override` is set, substitute `--model $MODEL_OVERRIDE`.
- `codex-live`: does not use `--model` in the same sense (Codex runtime has its own model-selection mechanism); this input is a no-op on the `codex-live` job. Document that explicitly.

Captain invocation for the immediate bisection need:

```
gh workflow run runtime-live-e2e.yml --ref main \
  -f pr_number=<N> \
  -f claude_version=2.1.111 \
  -f test_selector=tests/test_standing_teammate_spawn.py::test_standing_teammate_spawns_and_roundtrips \
  -f effort_override=low \
  -f model_override=claude-opus-4-6
```

Expected outcome if the hypothesis holds: `claude-live-opus` passes in ~2-3 minutes on 2.1.111 with the dated-model pin, matching 2.1.107/2.1.110 behavior.

## Acceptance criteria

1. Fourth optional input `model_override` added to `workflow_dispatch.inputs` in `runtime-live-e2e.yml`. Default empty string, `required: false`, `type: string`. Existing `pr_number`, `claude_version`, `test_selector`, `effort_override` inputs preserved verbatim.
2. Per-job threading: each of `claude-live`, `claude-live-bare`, `claude-live-opus` honors `$MODEL_OVERRIDE` when set by substituting it into the `--model` flag of the pytest invocation. When unset, default behavior is preserved line-for-line.
3. `codex-live` documents the no-op behavior in the job's prose or in `tests/README.md` — do not silently drop the input.
4. `GITHUB_STEP_SUMMARY` records the effective model used for each Claude job, in addition to the existing `claude --version` and `uv --version` lines shipped in #174.
5. YAML lint passes (`yaml.safe_load`). Bash conditional branches are `bash -n`-verified under both set and unset paths.
6. Default-unset path preserves current behavior exactly — the `pytest` invocation lines match the pre-change form for every job when `model_override` is empty.

## Test plan

Per-AC verification is static: YAML parse, diff review, `bash -n`. No new CI runs are required from this task — the captain verifies the new input end-to-end by dispatching one bisection run with `model_override=claude-opus-4-6` against Claude Code 2.1.111 and confirming the `claude-live-opus` job passes in the expected 2-3 minute window.

Offline tests: none required. The change is additive YAML and shell.

Live validation: one manual `gh workflow run` after merge, same pattern as #108's post-merge validation. Fast-track past a separate validation stage per #174's precedent.

## Out of Scope

- Per-test model overrides (making different tests run on different models in the same CI run). A single global `model_override` is sufficient for bisection and mitigation today.
- Validating specific model strings — the input is opaque, passed as-is to pytest. If the model name is invalid, Claude Code returns an error at runtime.
- Makefile target changes. `make test-live-claude-opus` continues to hardcode `--model opus --effort low` as the developer-local default. `model_override` affects only CI dispatches.
- Codex runtime model parameterization. Codex has its own model-selection path; out of scope for this Claude-focused input.
- Documentation in `tests/README.md` beyond what the no-op bullet requires. A fuller `tests/README.md` refresh covering all four `workflow_dispatch` inputs is a separate task.
