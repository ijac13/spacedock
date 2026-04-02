---
id: "084"
title: Unify test harness across Claude Code and Codex runtimes
status: ideation
source: CL — 076 validation findings
started: 2026-04-02T16:35:40Z
completed:
verdict:
score: 0.75
worktree:
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
