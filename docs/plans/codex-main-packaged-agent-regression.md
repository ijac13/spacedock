---
title: Codex main packaged-agent regression after merged runtime-loading changes
id: 110
status: validation
source: CL observation after merge to main
started: 2026-04-09T21:36:48Z
completed:
verdict:
score: 0.88
worktree: .worktrees/ensign-codex-main-packaged-agent-regression
issue:
pr:
---

The Codex packaged-agent regression is now narrower than the earlier runtime-loading bug. The worker boots and finishes, but the Codex path still sometimes names the worktree and branch from the bare worker stem instead of the safe packaged key.

## Problem Statement

`tests/test_codex_packaged_agent_e2e.py` still fails on `main` because the packaged logical id `spacedock:ensign` is not consistently threaded into the safe `worker_key` used for filesystem and branch naming.

Observed failure shape:

- first officer boots and dispatches a worker successfully
- the worker completes and returns a result
- the test still fails on safe-naming assertions
- live output shows `.worktrees/ensign-buggy-add-task` and `ensign/buggy-add-task` where `spacedock-ensign-*` is expected

This is a naming regression, not a worker-loading regression. The earlier runtime-loading fix should stay intact.

## Root-Cause Hypothesis

The Codex path is likely resolving the packaged worker correctly, but one later step still falls back to the raw agent stem when constructing stateful names. The most likely fault line is the dispatch helper that bridges:

- logical dispatch id: `spacedock:ensign`
- safe worker key: `spacedock-ensign`

The bug probably lives where the Codex launcher updates entity state, creates the worktree, or derives the temporary branch name after resolution. If that code uses `dispatch_agent_id` or the bare `ensign` stem instead of `worker_key`, the runtime contract diverges exactly the way the live evidence shows.

## Likely Code Surfaces

- `scripts/test_lib.py`
  - `resolve_codex_worker()`
  - `build_codex_worker_bootstrap_prompt()`
  - `run_codex_first_officer()`
- `skills/first-officer/references/codex-first-officer-runtime.md`
- `skills/first-officer/references/claude-first-officer-runtime.md`
- `skills/first-officer/references/first-officer-shared-core.md`
- `tests/test_codex_packaged_agent_ids.py`
- `tests/test_codex_packaged_agent_e2e.py`

The shared references already describe the correct split. The remaining work is to make the Codex implementation consistently honor it on the packaged path.

## Proposed Approach

### Option 1: Minimal Codex dispatch fix

Patch the Codex dispatch helper so every branch/worktree/status name is derived from `worker_key` after resolution. Keep `dispatch_agent_id` unchanged for reporting and skill lookup. This is the smallest change and the best fit if the bug is just one stale fallback to `ensign`.

### Option 2: Tighten the shared contract

Update the Codex runtime references and helper tests together so the naming split is asserted in one place and reused by both the launcher and the live E2E. This is slightly broader, but it reduces the chance of reintroducing the same fallback in a second helper.

### Option 3: Relax the test expectation

Allow bare `ensign` in the packaged-agent E2E. This would hide the bug rather than fix it, so it should not be chosen.

Recommendation: Option 1, with Option 2-style test reinforcement if the fix touches a shared helper.

## Acceptance Criteria

1. `dispatch_agent_id` stays `spacedock:ensign` for the packaged Codex worker path.
   - Test: `tests/test_codex_packaged_agent_ids.py` still asserts the resolved payload keeps the logical id unchanged.
2. `worker_key` becomes `spacedock-ensign` and is the only value used for worktree and branch naming.
   - Test: `tests/test_codex_packaged_agent_ids.py` and `tests/test_codex_packaged_agent_e2e.py` both assert the safe key appears in the derived names.
3. The Codex run still loads and executes the packaged worker contract correctly.
   - Test: `tests/test_codex_packaged_agent_e2e.py` still sees a spawned worker and a completed worker message.
4. The live worktree path contains `spacedock-ensign` and does not contain `spacedock:ensign`.
   - Test: `tests/test_codex_packaged_agent_e2e.py` reads the entity file and checks the `worktree:` frontmatter value.
5. The branch list contains `spacedock-ensign/` and does not contain `spacedock:ensign`.
   - Test: `tests/test_codex_packaged_agent_e2e.py` checks `git branch --list` output.
6. The fix does not reopen the earlier runtime-loading regression.
   - Test: rerun the Codex packaged-agent E2E after the change and confirm the worker still boots, completes, and reports the right logical id.

## Test Plan

- Fast static/unit coverage:
  - `tests/test_codex_packaged_agent_ids.py`
  - cost: low
  - complexity: low
  - purpose: prove the resolver still splits `dispatch_agent_id` from `worker_key` correctly
- Live Codex E2E:
  - `tests/test_codex_packaged_agent_e2e.py`
  - cost: medium to high
  - complexity: medium
  - purpose: prove the real Codex path writes the safe packaged key into worktree and branch state
- No separate browser/UI E2E is needed.
  - The failure is fully observable through the Codex log, the entity file, and git state.

## Stage Report: ideation

- DONE: Clarified the problem as a naming regression on the Codex packaged-agent path, not a repeat of the runtime-loading failure.
- DONE: Identified the likely fault line as the helper or runtime path that turns a resolved packaged worker into stateful names.
- DONE: Listed the most relevant code surfaces, centered on `scripts/test_lib.py`, the first-officer runtime references, and the packaged-agent tests.
- DONE: Proposed three approaches and recommended the minimal Codex dispatch fix with test reinforcement.
- DONE: Wrote concrete acceptance criteria, each with an explicit verification method.
- DONE: Wrote a proportional test plan covering cheap unit coverage and one live Codex E2E; no browser E2E is needed.

## Stage Report: implementation

- DONE: Kept `dispatch_agent_id` logical for the packaged Codex path while making the safe `worker_key` explicit for namespaced packaged workers.
  Evidence: `scripts/test_lib.py`, `scripts/run_codex_first_officer.sh`, and `skills/first-officer/references/codex-first-officer-runtime.md` now say `dispatch_agent_id: spacedock:ensign`, `worker_key: spacedock-ensign`, and `role_asset_name: ensign`.
- DONE: Made worktree and branch naming consistently use the safe key instead of the bare stem.
  Evidence: the runtime prompt and shell launcher now specify `.worktrees/{worker_key}-{slug}` for worktrees and `{worker_key}/{slug}` for branches; live E2E created `.worktrees/spacedock-ensign-buggy-add-task` and `spacedock-ensign/buggy-add-task`.
- DONE: Preserved packaged worker-contract loading and execution.
  Evidence: `tests/test_codex_packaged_agent_e2e.py` completed successfully with `13 passed, 0 failed`; the live log shows the worker completed and returned `Verdict: REJECTED` with the logical id `spacedock:ensign`.
- DONE: Added or adjusted targeted tests to lock the naming behavior.
  Evidence: `tests/test_codex_packaged_agent_ids.py` and `tests/test_agent_content.py` now assert the safe key, asset stem, and `{worker_key}/{slug}` branch template.
- DONE: Ran focused verification for touched helpers/tests.
  Evidence: `uv run --with pytest python tests/test_codex_packaged_agent_ids.py -q`, `uv run --with pytest python tests/test_agent_content.py -q`, and `bash -n scripts/run_codex_first_officer.sh` all passed.
- DONE: Ran the live Codex packaged-agent E2E from this worktree.
  Evidence: `uv run tests/test_codex_packaged_agent_e2e.py` passed with `13 passed, 0 failed`; the live branch list contained `spacedock-ensign/buggy-add-task` and did not contain `spacedock:ensign`.
- DONE: Ran the broader live Codex runtime tests and they passed.
  Evidence: `uv run tests/test_gate_guardrail.py --runtime codex` passed with `6 passed, 0 failed`; `uv run tests/test_rejection_flow.py --runtime codex` passed with `10 passed, 0 failed`; `uv run tests/test_merge_hook_guardrail.py --runtime codex` passed with `13 passed, 0 failed`.
