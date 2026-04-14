---
id: 150
title: "Add claude-live-opus job to runtime-live-e2e workflow"
status: backlog
source: "CL direction during 2026-04-14 session — separate opus signal needed alongside haiku for #114 cycle issues"
started: 
completed:
verdict:
score: 0.55
worktree: 
issue:
pr:
---

The current `.github/workflows/runtime-live-e2e.yml` runs `make test-live-claude` (haiku) and `make test-live-codex` on every PR with manual environment approval. We have a `make test-live-claude-opus` Makefile target that runs the full live-claude suite against opus with `--effort low`, but no CI job invokes it.

CL has created a `CI-E2E-OPUS` GitHub environment so the opus job can be approved independently from the haiku job — useful when a haiku run flakes in a way that may be model-specific, or when extra signal is wanted before merging a dispatch-prose change.

## Scope

Add a `claude-live-opus` job to `.github/workflows/runtime-live-e2e.yml` mirroring the existing `claude-live` job structure:

- `runs-on: ubuntu-latest`
- `environment: CI-E2E-OPUS` (the env CL just created)
- Same provenance-loading step as `claude-live` (PR number resolution, summary write)
- Same git-identity and tooling setup as `claude-live`
- Run command: `make test-live-claude-opus`
- Upload artifacts to `runtime-live-e2e-claude-live-opus`
- Same `ANTHROPIC_API_KEY` secret (no new secret needed since the env-scoped secrets are inherited from the env config CL set up)

The job stays pending until a maintainer approves the `CI-E2E-OPUS` deployment, exactly the same flow as `claude-live` waiting on `CI-E2E`.

## Acceptance criteria

1. `.github/workflows/runtime-live-e2e.yml` declares a `claude-live-opus` job referencing `environment: CI-E2E-OPUS`.
2. The job runs `make test-live-claude-opus` (not `make test-live-claude`).
3. Artifact upload uses a distinct name (e.g. `runtime-live-e2e-claude-live-opus`) so it doesn't collide with the haiku run's artifact.
4. The provenance-summary step shows trigger source, PR number, head SHA, and the same metadata `claude-live` shows (so it's clear which job we're looking at).
5. Static workflow test (`tests/test_runtime_live_e2e_workflow.py`) extended to assert the new job exists and references the correct environment.
6. `tests/README.md` "Live E2E CI" section updated to mention the new job alongside `claude-live` and `codex-live`.

## Test plan

- Static: extend `tests/test_runtime_live_e2e_workflow.py` to assert the third job's presence, environment name, and the `make test-live-claude-opus` run command. Cost: free, ~3s.
- Live E2E: open this PR; observe that GitHub shows three pending live jobs (`claude-live`, `claude-live-opus`, `codex-live`), each with its own approval gate. Cost: at PR time, approving the opus environment costs ~$2-3 of opus runtime.

## Out of scope

- New live tests. The opus job runs the existing suite via the existing Makefile target.
- Changing the Makefile target itself.
- Changing the haiku or codex jobs.
- Branch protection or required-checks configuration.
