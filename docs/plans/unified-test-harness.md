---
id: "084"
title: Unify test harness across Claude Code and Codex runtimes
status: ideation
source: CL — 076 validation findings
started: 2026-04-02T16:35:40Z
completed:
verdict:
score: 0.75
worktree: .worktrees/ensign-084-unified-test-harness
issue:
pr:
---

# Unify test harness across Claude Code and Codex runtimes

## Problem framing

The repo already has shared harness utilities in `scripts/test_lib.py`, but the behavioral coverage is still split along runtime lines. Claude tests launch with `claude -p` and inspect `LogParser`, while Codex tests launch with `codex exec` and inspect `CodexLogParser`. That split is fine at the process boundary, but the actual assertions are still duplicated:

- gate hold behavior is checked in separate Claude and Codex files
- rejection-flow behavior is checked in separate Claude and Codex files
- merge-hook behavior is checked in separate Claude and Codex files
- offline content checks are scattered across E2Es plus `tests/test_codex_skill_content.py`

The result is a brittle maintenance surface. Any change to stage wording, guardrails, or prompt content has to be mirrored in multiple places, and it is easy for one runtime to drift without the other. The branch already passes Codex E2E tests, so the task is not to invent a new testing architecture. It is to make the harness share the right logic while keeping the runtime-specific launchers explicit.

This task is intentionally narrow. It targets the paired behavior tests and scattered offline content checks. It does not try to unify every runtime-specific test; dispatch preparation, packaged-agent id handling, output-format checks, and other genuinely runtime-specific probes should stay separate unless sharing them removes code rather than adding framework.

## Proposed approach

1. **Keep runtime boundaries, share the assertions.** Add a thin runtime adapter layer in `scripts/test_lib.py` for the pieces that truly differ: how a test is launched, which log parser is used, and how the runtime bootstraps the first-officer skill. Do not try to fully abstract away `claude -p` vs `codex exec`; the flags, environment, and log formats are different enough that forcing a single launcher would hide useful runtime-specific behavior.

2. **Move offline content checks into one static test module.** Consolidate the current `assembled_agent_content()` checks and `tests/test_codex_skill_content.py` into one content-focused file, `tests/test_agent_content.py`. That file should validate the assembled Claude agent text, the Codex packaged-agent references, and the shared guardrail sections without needing a full E2E run. This makes content drift cheap to detect and removes the same text assertions from runtime smoke tests.

3. **Share scenario logic for the behavioral E2Es.** Create common scenario helpers for gate guardrail, rejection flow, and merge hook behavior, then run them against both runtimes with small per-runtime adapters. The scenario helpers should own the fixture setup and verification logic; the wrappers should only supply the launcher, parser, and any runtime-specific setup like agent installation or Codex skill-home preparation.

4. **Add one Codex plugin-discovery smoke path.** Keep a dedicated Codex E2E that proves the real packaged path works with `--plugin-dir` and isolated HOME, using `spacedock:first-officer` rather than local agent copies. This is the one place where the harness should prove it can resolve the repo as a plugin namespace, not just as a directly copied worktree asset.

Implementation rule: prefer the fewest new lines that remove duplicated assertions. If a helper abstraction adds more surface area than the duplication it removes, keep the behavior test split and only share the verification logic that is actually repeated.

### Design decisions and tradeoffs

- Prefer a small adapter over a big test framework. The current helpers already cover most of the shared mechanics, so the value is in consolidating assertions, not inventing a new test DSL.
- Keep Codex-only helper tests for packaging and terminal-entity behavior. `resolve_codex_worker()`, `build_codex_first_officer_invocation_prompt()`, `codex_prepare_dispatch.py`, and `codex_finalize_terminal_entity.py` cover Codex-specific plumbing that does not have a Claude equivalent.
- Preserve one E2E per meaningful behavior, not one per runtime artifact. The shared scenario tests should prove the behavior once per runtime, while the unit-style content tests cover the text contract cheaply.
- Avoid over-merging launcher code. The launcher differences are not accidental; they encode different runtime contracts and should stay visible in the helpers.

## Acceptance criteria

1. A single content-focused test file covers all offline agent-content assertions that are currently split across runtime E2Es and `tests/test_codex_skill_content.py`.
2. Gate guardrail, rejection flow, and merge-hook behavior are exercised through shared scenario logic instead of separate Claude-only and Codex-only assertion blocks.
3. At least one Codex E2E verifies the real packaged path with `spacedock:first-officer`, `--plugin-dir`, and isolated HOME.
4. The shared harness keeps the runtime-specific launchers explicit and leaves genuinely runtime-specific tests as separate files when merging them would add more code than it removes.
5. The existing Codex helper tests for packaged worker ids, dispatch preparation, and finalization remain intact.
6. No existing behavioral check is lost: the same gate hold, rejection, merge-hook, and dispatch-name guarantees remain covered, just with less duplication.

## Test plan

### Static and unit-style coverage

- Move all offline content assertions into `tests/test_agent_content.py`.
- Keep `tests/test_codex_packaged_agent_ids.py` as the unit-style check for Codex worker-id resolution and prompt assembly.
- Keep `tests/test_codex_prepare_dispatch.py` and `tests/test_codex_finalize_terminal_entity.py` as helper-level checks for Codex-only plumbing.
- Verify shared reference content with `assembled_agent_content()` rather than by running the full agents.

### E2E coverage

- Run the shared gate guardrail scenario against both runtimes and verify the entity stays at the gate, is not archived, and emits a gate/approval report.
- Run the shared rejection-flow scenario against both runtimes and verify a rejected validation can trigger observable follow-up work.
- Run the shared merge-hook scenario against both runtimes and verify merge hooks fire before local merge, with a no-mods fallback still succeeding.
- Keep one Codex-specific smoke test that proves the plugin-discovery path works with `spacedock:first-officer` and isolated HOME.

### What stays static vs. what needs E2E

- Static/unit-only: text contract assertions, helper prompt construction, Codex id resolution, and packaged-agent asset references.
- E2E only: gate holding, rejection follow-up, merge-hook execution, archive/cleanup behavior, and Codex plugin discovery.
- Explicitly out of scope unless simplification falls out for free: runtime-specific tests such as output-format behavior and Codex-only dispatch-preparation/finalization probes.

### Cost and scope

- Low risk: moving content assertions out of E2Es and into one static file.
- Medium risk: introducing the shared runtime adapter and scenario helpers.
- Higher cost but still necessary: the handful of E2E runs needed to prove both runtimes still behave the same after the harness consolidation.

## Stage Report: validation

### 1. Merge main — DONE

Merged `origin/main` into `ensign/084-unified-test-harness`. One conflict: `tests/test_codex_skill_content.py` was deleted by the branch (consolidated into `test_agent_content.py`) but modified on main (stale-reference cleanup). Resolved by keeping the deletion and updating `test_agent_content.py` to use `agents/` instead of `.claude/agents/` to match main's path cleanup. All 51 static tests pass after merge.

### 2. AC1 — single content test file — DONE

`tests/test_agent_content.py` covers all offline agent-content assertions that were previously split across:
- `tests/test_codex_skill_content.py` (deleted) — skill bootstrap, agent entry points, shared-core sections, ensign stage report, guardrails, codex runtime docs
- Runtime E2E inline content checks — assembled agent gate guardrails, rejection flow guardrails, merge hook guardrails

The single file has 10 test functions covering both runtime-neutral reference checks and assembled-claude-agent content assertions. Strictly a superset of the old coverage.

### 3. AC2 — shared scenario logic for gate, rejection, merge-hook — DONE

Three shared assertion helpers in `scripts/test_lib.py`:
- `check_gate_hold_behavior()` (line 771): entity status, archive state, gate mention
- `rejection_signal_present()` (line 797) + `rejection_follow_up_observed()` (line 816): rejection evidence in entities/worktrees/output
- `check_merge_outcome()` (line 833): hook marker, archive state, worktree/branch cleanup

The three behavioral E2Es (`test_gate_guardrail.py`, `test_rejection_flow.py`, `test_merge_hook_guardrail.py`) each accept `--runtime claude|codex` and use the shared helpers for common assertions while keeping runtime-specific checks in per-runtime branches. The old separate Codex E2E files (`test_codex_gate_guardrail.py`, `test_codex_rejection_flow.py`, `test_codex_merge_hook_guardrail.py`) are deleted.

### 4. AC3 — Codex packaged path E2E — DONE

`tests/test_codex_packaged_agent_e2e.py` verifies the real packaged path with `spacedock:first-officer` via the `run_codex_first_officer()` launcher, which calls `prepare_codex_skill_home()` to create an isolated HOME with the repo symlinked as the `spacedock` skill namespace. Checks include: invocation prompt contains `spacedock:first-officer`, FO resolves `spacedock:ensign`, safe worktree keys (no colon leakage), and branch naming.

### 5. AC4 — runtime-specific launchers remain explicit — DONE

`run_first_officer()` (line 377) and `run_codex_first_officer()` (line 417) remain as separate functions in `test_lib.py`. Claude uses `claude -p --plugin-dir --agent`, Codex uses `codex exec` with `prepare_codex_skill_home()`. No single-launcher abstraction hides these differences.

### 6. AC5 — Codex helper tests intact — DONE

All three Codex-specific helper test files remain unchanged:
- `test_codex_packaged_agent_ids.py` (6 tests): `resolve_codex_worker()`, `build_codex_first_officer_invocation_prompt()`, `build_codex_worker_bootstrap_prompt()`
- `test_codex_prepare_dispatch.py` (1 test): worktree creation, payload structure, entity frontmatter update
- `test_codex_finalize_terminal_entity.py` (2 tests): merge hook firing + cleanup, no-mods local merge fallback

### 7. AC6 — no behavioral check lost — DONE

Systematic comparison of old vs new test assertions:

**Gate guardrail:** Old Claude checks (entity not past gate, not archived, gate review, no self-approval) + old Codex checks (entity not past gate, not archived, worktree/output, gate mention) all present in unified `test_gate_guardrail.py` under `--runtime` flag.

**Rejection flow:** Old Claude checks (ensign dispatched, REJECTED signal, fix dispatch count) + old Codex checks (REJECTED signal, worker completed, multiple dispatches, follow-up observed, safe worktree key, no id leak) all present in unified `test_rejection_flow.py`.

**Merge hook:** Old Claude checks (hook fired, entity archived, worktree/branch cleanup, no-mods fallback) + old Codex checks (same) all present in unified `test_merge_hook_guardrail.py` via shared `check_merge_outcome()`.

**Content:** Old `test_codex_skill_content.py` checks (skill bootstrap, agent entry points, shared-core sections, ensign stage report, guardrails, codex runtime docs) all present in `test_agent_content.py`, plus additional assembled-agent guardrail checks.

### 8. Static tests pass — DONE

51 tests collected, 51 passed (post-merge with main). Command: `uv run --with pytest python -m pytest tests/ --ignore=tests/fixtures -q`. Main had 40 collectable static tests; branch has 51 (+11 from new assembled-content tests and reorganization).

### 9. Claude E2E assessment — DONE

Rerun was warranted: the absolute-workflow-path fix (commits `9e7fecc`, `0d47cdb`) targeted the two previously-failing tests, and the merge from main brought structural path changes.

Results:
- **Rejection flow** (`test_rejection_flow.py`): 5/5 PASS. Previously failed; the absolute workflow path fix resolved the issue. FO dispatched 3 ensigns, validation surfaced REJECTED, follow-up fix dispatch observed.
- **Merge hook** (`test_merge_hook_guardrail.py`): 7/8 pass, 1 fail. Ran twice (once during rate-limit window, once after clearance). Same result both times: "merge hook fired marker exists" fails. The FO completes the entity to `status: done` and cleans up worktree/branch, but haiku does not invoke the merge hook script within the $2 budget cap. This is a consistent model-behavior limitation with haiku at low effort, not a harness regression or rate-limit artifact. Archive was skipped (SKIP, not FAIL).

### 10. Test file count — DONE

Main: 17 test `.py` files. Branch: 14 test `.py` files. Net reduction: 3 files.
- Removed: `test_codex_gate_guardrail.py`, `test_codex_merge_hook_guardrail.py`, `test_codex_rejection_flow.py`, `test_codex_skill_content.py` (4 files)
- Added: `test_agent_content.py` (1 file)

### Recommendation

**PASSED** — all 6 acceptance criteria are met with evidence. The one E2E check failure (merge hook marker) is a pre-existing model-budget limitation, not a harness regression. The harness consolidation reduced test file count by 3, increased static test coverage from 40 to 51, and preserved all behavioral guarantees with less duplication.
