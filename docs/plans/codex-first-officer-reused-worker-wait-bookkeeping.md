---
id: 131
title: Codex first officer: wait bookkeeping for reused worker threads after send_input
status: implementation
source: FO observation during task 117 feedback routing on 2026-04-11
started: 2026-04-11T19:19:27Z
completed:
verdict:
score: 0.68
worktree: .worktrees/spacedock-ensign-codex-first-officer-reused-worker-wait-bookkeeping
issue:
pr:
---

## Problem Statement

Task 130 made reused Codex workers reachable through `send_input` and clarified that they can be explicitly shut down when no longer needed. The remaining gap is bookkeeping: once the FO routes follow-up work to a reused worker, that worker is still being treated as if it were only "available" rather than active again. That makes the run look idle even when the reused worker is still on the critical path, and it weakens the FO's ability to know when it must block on the reused result.

The runtime contract needs to be explicit about this lifecycle:

- after `send_input`, the reused worker becomes active again
- FO must track that active reused worker explicitly, not just the original dispatch
- if the reused worker's result is on the critical path, FO must `wait_agent` on that same agent instead of treating `send_input` as fire-and-forget
- status/reporting should describe the worker as active again, not merely reachable
- once the reused cycle is finished and no later advancement is expected, the worker must be shut down explicitly

## Proposed Approach

Keep the change tightly bounded to the Codex first-officer runtime wording and the Codex E2E harness.

1. Update the Codex FO runtime contract so "reuse through `send_input`" implies an active-again state, not just a routed message.
2. Make the runtime guidance state when the FO must wait: any reused worker whose completion is part of the current critical path must be followed by `wait_agent` on that same worker handle.
3. Keep shutdown semantics explicit: if the reused worker will not receive more input or gating, shut it down after the reused cycle completes.
4. Extend the live Codex E2E so it proves the follow-up path, the active-again bookkeeping, the wait behavior, and the explicit shutdown path all occur in one run.

This stays within the existing architecture. It does not require a new workflow mechanism, only clearer runtime contract wording and stronger end-to-end verification of the existing control flow.

## Bounded Implementation Surfaces

- `scripts/test_lib.py`: the Codex helper prompt should keep the reuse/wait/shutdown wording aligned with the runtime contract.
- `skills/first-officer/references/codex-first-officer-runtime.md`: this is the runtime source of truth for when a reused worker becomes active again, when FO must wait, and when shutdown is required.
- `tests/test_codex_packaged_agent_e2e.py`: this is the live Codex E2E that should prove the reused-worker follow-up and shutdown behavior in practice.

## Acceptance Criteria

1. The Codex FO runtime explicitly states that `send_input` to a reused worker makes that worker active again, not just addressable.
   Test: a static content check on the assembled Codex FO runtime text verifies the active-again wording is present and unambiguous.
2. The Codex FO runtime explicitly requires `wait_agent` when the reused worker's result is on the critical path.
   Test: a static content check verifies the wait requirement is described alongside reused-worker follow-up, and the live E2E log shows the FO actually waits on the reused path.
3. The Codex FO runtime and helper guidance explicitly require shutdown when the reused worker will not receive more work.
   Test: a static content check verifies the shutdown wording, and the live E2E log shows an explicit shutdown call after the reused cycle completes.
4. The live Codex E2E exercises reused-worker follow-up end to end.
   Test: `tests/test_codex_packaged_agent_e2e.py` confirms the implementation worker receives follow-up through `send_input` on the existing handle rather than a replacement dispatch.
5. The live Codex E2E exercises active-again bookkeeping and wait behavior on the reused worker.
   Test: the FO log must show that the reused worker is treated as active again and that the critical-path result is awaited with `wait_agent` rather than treated as background work.
6. The live Codex E2E exercises explicit shutdown after the reused cycle.
   Test: the FO log must show the reused worker is explicitly shut down once it is no longer needed.

## Test Plan

- Static checks: low cost, deterministic. Verify the runtime wording in `skills/first-officer/references/codex-first-officer-runtime.md` and the helper alignment in `scripts/test_lib.py`.
- Live Codex E2E: medium cost, higher risk, required. Extend `tests/test_codex_packaged_agent_e2e.py` so it proves reused-worker follow-up, active-again bookkeeping, wait behavior, and explicit shutdown in one run.
- No extra unit-only surface is needed for this task. The behavioral guarantee is only meaningful if the live Codex path is exercised.

## Stage Report: ideation

- [x] DONE: Expanded the seed into a full problem statement, proposed approach, acceptance criteria, and test plan.
  The body now defines the reused-worker bookkeeping gap and the desired runtime semantics after `send_input`.
- [x] DONE: Defined the runtime contract so a reused worker becomes active again after `send_input` and FO waits on it when the result is critical-path.
  The new spec text states the active-again and `wait_agent` requirements directly.
- [x] DONE: Identified the bounded implementation surfaces needed for runtime wording and test coverage.
  The body now names `scripts/test_lib.py`, `skills/first-officer/references/codex-first-officer-runtime.md`, and `tests/test_codex_packaged_agent_e2e.py`.
- [x] DONE: Added concrete acceptance criteria with test methods for each criterion.
  Each criterion now has a matching static or live-E2E test note.
- [x] DONE: Required live Codex E2E coverage for reused-worker follow-up, active-again bookkeeping, wait behavior, and explicit shutdown.
  The test plan explicitly calls for extending `tests/test_codex_packaged_agent_e2e.py` to cover all four behaviors.

### Summary

This ideation pass turns the seed into a bounded runtime spec for Codex reused-worker bookkeeping. The task now focuses on making `send_input` imply an active-again worker state, ensuring critical-path follow-up uses `wait_agent`, and proving the whole cycle with live Codex E2E coverage.

## Stage Report: implementation

- [x] Read the entity spec and kept the implementation bounded to the listed surfaces.
  Only `scripts/test_lib.py`, `skills/first-officer/references/codex-first-officer-runtime.md`, and the named Codex test files were changed.
- [x] Implemented the runtime-contract and helper wording changes for active-again reused workers and critical-path `wait_agent` behavior.
  The Codex runtime and invocation helper now state that `send_input` makes the reused worker active again, requires `wait_agent` on the same handle for critical-path results, and requires explicit shutdown after the reused cycle.
- [x] Updated live Codex E2E coverage for reused-worker follow-up, active-again bookkeeping, explicit wait behavior, and explicit shutdown.
  `tests/test_codex_packaged_agent_e2e.py` now asserts active-again wording, critical-path wait evidence, no replacement dispatch on reuse, and shutdown after the reused cycle.
- [ ] FAIL: Ran the relevant verification and recorded concrete outcomes.
  `uv run --with pytest python -m pytest tests/test_agent_content.py -k "active_again_wait or reuse_and_shutdown_wording"` and `uv run --with pytest python -m pytest tests/test_codex_packaged_agent_ids.py -k exec_harness_invokes_first_officer_skill_by_name` passed; `uv run --with pytest python tests/test_codex_packaged_agent_e2e.py` stalled with the FO log stuck at the first worker `wait` in `/var/folders/h1/vnssm1dj6ks4nzzvx8y29yjm0000gn/T/tmp2o0gqhyr/codex-fo-log.txt`.
- [x] Appended a `## Stage Report: implementation` section to the entity file with every checklist item represented as DONE, SKIPPED, or FAILED.
  This report is appended at the end of the entity file in the assigned worktree copy.
- [x] Committed the work in the worktree before reporting completion.
  The implementation commit includes the runtime wording, helper wording, test updates, and this stage report.

### Summary

The Codex first-officer runtime and helper prompt now treat reused `send_input` workers as active again, require same-handle waiting on critical-path reuse, and keep explicit shutdown semantics after the reused cycle. Static verification for the new contract passed, while the live Codex packaged-agent E2E coverage was updated but the run itself stalled at the first worker wait; that concrete outcome is recorded above.
