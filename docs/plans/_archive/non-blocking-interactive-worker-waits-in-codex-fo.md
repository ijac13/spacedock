---
id: 138
title: Non-blocking interactive worker waits in Codex first officer
status: done
source: FO observation during task 136 dispatch on 2026-04-12
score: 0.66
started: 2026-04-12T18:17:59Z
completed: 2026-04-14T14:42:15Z
verdict: PASSED
worktree: 
issue:
pr: #87
---

The current Codex first-officer runtime guidance encourages `spawn_agent(...); wait_agent(...)` as the normal dispatch pattern. That works for bounded or single-entity runs, but in an interactive captain conversation it blocks the foreground while a worker is running. During task 136 dispatch, that meant the captain had to interrupt the session just to continue discussing another workflow improvement while the ideation worker was still in flight.

This task should refine the Codex first-officer runtime so interactive sessions keep workers in the background by default. The first officer should foreground `wait_agent` only when the next orchestration step is truly blocked on that worker result. Bounded or single-entity runs remain a separate case where immediate waiting is still appropriate because completion is the point of the turn. Post-completion foregrounding and gate ergonomics are handled separately by task 140 and are out of scope here.

## Problem Statement

Codex interactive sessions are conversational, not strictly transactional. The first officer can spawn a worker and still have useful work to do in the same turn, such as discussing scope, clarifying requirements, or advancing a different entity. If the runtime foregrounds `wait_agent` immediately after dispatch, the conversation loses that flexibility and the captain has to interrupt the turn to keep working.

The observed failure from task 136 was not that waiting exists, but that the default waiting behavior was applied in the wrong mode. Interactive FO sessions should treat worker execution as background activity unless the next orchestration step depends on the result. This task is Codex-specific runtime guidance focused on in-flight behavior only; it should not generalize the behavior into a shared contract for all platforms, and it should not absorb the post-completion ergonomics already covered by task 140.

## Proposed Approach

Define two waiting modes in the Codex first-officer runtime guidance:

1. **Interactive mode.** After `spawn_agent`, keep the worker in the background and continue the turn. Foreground a `wait_agent` only when:
   - the next step is blocked on that worker result,
   - or the worker result is needed before any other orchestration can proceed.
2. **Bounded or single-entity mode.** Keep the current blocking behavior when the session is focused on one entity or one immediate outcome. In that case, waiting right away is still the correct default because the session is already scoped around a single completion.

The implementation should identify interactive vs bounded mode from existing Codex runtime context rather than introducing a new shared abstraction. The goal is a local guidance change: same worker APIs, different waiting policy depending on the session shape. The branch should rely on shared `--runtime codex` live E2E where possible for blocked and bounded behavior, use static contract checks for the interactive wording that the repo can actually prove today, and leave explicit captain-driven wait requests to a future task if a real Codex interactive harness is needed.

## Acceptance Criteria

1. The Codex runtime contract states that interactive sessions keep dispatched workers in the background by default until the next orchestration step is blocked on the result.
   - Test: static content checks verify the Codex runtime wording and assembled first-officer contract describe background-by-default interactive behavior without claiming a live PTY proof.
2. The shared `--runtime codex` path still foregrounds `wait_agent` when the next orchestration step is blocked on the worker result.
   - Test: `tests/test_rejection_flow.py --runtime codex` shows the single-entity validation path waiting on the validation worker before gate handling.
3. Bounded or single-entity Codex runs can still wait immediately after dispatch.
   - Test: the same shared `--runtime codex` rejection-flow run preserves the bounded immediate-wait behavior in its live log.
4. Codex FO test prompts stay minimal and do not encode wait-policy coaching.
   - Test: `tests/test_codex_packaged_agent_ids.py` verifies the Codex invocation prompt identifies workflow target/scope only and omits behavioral coaching.
5. The behavior stays Codex-specific and does not require a shared-contract change.
   - Test: review the touched runtime guidance and confirm the change is limited to Codex-first-officer behavior, not shared workflow semantics.

## Test Plan

Use the existing shared Codex harness where it can prove real behavior, and keep the remaining checks honest about their scope:

- static content checks for the Codex runtime wording that describes background-by-default interactive behavior,
- shared live `--runtime codex` E2E for blocked and bounded wait behavior via `tests/test_rejection_flow.py`,
- and prompt-discipline checks that keep Codex invocation prompts minimal per `tests/README.md`.

Do not claim live interactive Codex PTY coverage in this task. If explicit captain-requested waiting or true interactive timing proof becomes necessary, that should be a separate follow-up that introduces a real Codex interactive harness instead of overloading this entity.

## Stage Report: ideation

- [x] Problem statement expanded
  Explained why interactive Codex FO sessions should not foreground `wait_agent` by default and called out the task 136 failure mode.
- [x] Bounded design proposed
  Distinguished interactive mode from bounded/single-entity mode and kept the change Codex-specific instead of turning it into a shared contract.
- [x] Acceptance criteria defined with test mapping
  Listed five concrete criteria and attached a test approach to each one.
- [x] Test plan made proportional
  Identified static/runtime harness checks as the primary validation path and reserved E2E only if the existing harness cannot cover the behavior deterministically.

### Summary

The task is now scoped as a Codex-only runtime guidance change: interactive sessions should prefer background worker execution, while bounded or single-entity runs may keep immediate waiting. The revised body includes concrete acceptance criteria and a proportional test plan so implementation can be validated without over-scoping the work. This update stays inside the assigned worktree and leaves workflow scaffolding untouched.

## Stage Report: implementation

- [x] DONE: Implement the Codex-specific runtime guidance and minimal supporting tests.
  Updated `skills/first-officer/references/codex-first-officer-runtime.md`, `scripts/test_lib.py`, `tests/test_agent_content.py`, and `tests/test_codex_packaged_agent_ids.py` to make interactive waits background by default while preserving bounded behavior.
- [x] DONE: Preserve the blocked-next-step and explicit-captain-wait paths.
  The Codex runtime now says to wait when the next orchestration step is blocked on the worker result or when the captain explicitly asks to wait; the generated invocation prompt mirrors that rule.
- [x] DONE: Preserve bounded or single-entity immediate waiting.
  Both the runtime doc and the invocation prompt still allow immediate waiting when the run is scoped to a single completion.
- [x] DONE: Keep the change Codex-specific.
  Only the Codex runtime guidance and Codex harness prompt/tests changed; the shared first-officer contract was left untouched.
- [x] DONE: Run targeted verification and record concrete evidence.
  `python3 -m py_compile scripts/test_lib.py` passed; `uv run --with pytest python tests/test_codex_packaged_agent_ids.py` passed (6/6); `uv run --with pytest python tests/test_agent_content.py` passed (28/28).
- [x] DONE: Commit the implementation work in the assigned worktree.
  Code changes were committed as `d5fd50b` (`implement: codex interactive wait policy`).

### Summary

Interactive Codex first-officer guidance now keeps spawned workers in the background by default and only foregrounds `wait_agent` when the next step is blocked or the captain explicitly requests waiting. The bounded and single-entity paths still permit immediate waiting, and the new tests pin both the runtime wording and the generated invocation prompt to that split.

## Stage Report: validation

- [x] DONE: Re-ran the currently available targeted tests.
  `uv run --with pytest python tests/test_agent_content.py -q` passed (28/28), and `uv run --with pytest python tests/test_codex_packaged_agent_ids.py -q` passed (6/6).
- [x] DONE: Verified the Codex-specific scope remained local.
  The touched runtime guidance is still confined to `skills/first-officer/references/codex-first-officer-runtime.md` and Codex harness helpers/tests; the shared first-officer contract was not expanded.
- [x] FAILED: Verify each acceptance criterion with evidence.
  The implementation does not provide a test that drives an actual Codex interactive dispatch and proves `spawn_agent` stays in the background until a dependency block or explicit wait request occurs. The bounded/single-entity immediate-wait behavior is also not exercised directly. Current coverage is limited to static content checks and prompt-shape assertions.
- [x] FAILED: Assess interactive-mode policy coverage intent.
  The added tests document wording and naming conventions, but they do not clearly test the runtime policy split between interactive and bounded sessions. No test here demonstrates the next orchestration step blocking on worker output or the captain explicitly requesting a wait.
- [x] SKIPPED: Add or update interactive behavioral regression coverage.
  This validation pass does not produce implementation changes; the missing interactive/bounded wait regression needs to be added by implementation if the policy claims are meant to be validated.

### Summary

The available tests pass, but they only prove text-level contract and ID-resolution behavior. They do not prove the acceptance criteria that depend on actual interactive dispatch timing, dependency-blocked waiting, explicit-wait handling, or bounded immediate waiting. Because the requested behavior is not yet covered by a deterministic behavioral test, the validation outcome is `REJECTED`.

Recommendation: REJECTED

## Stage Report: implementation (cycle 4)

- [x] DONE: Re-scope the entity to pre-completion wait behavior after task 140 merged.
  Updated the intro, problem statement, approach, acceptance criteria, and test plan so task 138 owns only in-flight wait semantics and explicitly leaves post-completion gate ergonomics to task 140.
- [x] DONE: Remove the explicit-captain-wait proof requirement from this entity.
  The narrowed acceptance criteria now cover interactive contract wording, blocked/bounded shared Codex evidence, prompt discipline, and Codex-only scope; true explicit-wait interactive proof is left to future harness work instead of being overclaimed here.
- [x] DONE: Confirm the existing branch code already matches the narrowed scope.
  No additional runtime/helper code changes were required after the rebase because cycle 3 had already fixed the prompt-discipline issue and restored the shared Codex rejection-flow path.
- [x] DONE: Re-run proportional verification against the narrowed scope.
  `python3 -m py_compile scripts/test_lib.py tests/test_rejection_flow.py tests/test_codex_packaged_agent_ids.py tests/test_agent_content.py` passed; `uv run --with pytest python tests/test_codex_packaged_agent_ids.py -q` passed (9/9); `uv run --with pytest python tests/test_agent_content.py -q` passed (36/36); `KEEP_TEST_DIR=1 uv run tests/test_rejection_flow.py --runtime codex` passed (16/16) with preserved evidence under `/var/folders/h1/vnssm1dj6ks4nzzvx8y29yjm0000gn/T/tmp0vftdfqu/`.
- [x] DONE: Keep the worktree-only ownership rule intact while applying the captain feedback.
  The scope rewrite and this cycle report were applied only in the worktree copy of the entity; `main` retained only the separate workflow-fix commit outside this task entity.
- [ ] SKIP: Add a new interactive Codex PTY harness in this cycle.
  The narrowed task no longer depends on that infra, and any future explicit captain-wait proof should land as a separate harness-oriented task.

### Summary

Cycle 4 turns task 138 into the narrow pre-completion wait-policy task we agreed on after task 140 merged. The existing branch code already satisfies that narrowed scope, and the refreshed verification now lines up with what the repo can actually prove: contract wording for interactive backgrounding, shared live Codex evidence for blocked and bounded waiting, and minimal-prompt discipline.

## Stage Report: implementation (cycle 3)

- [x] DONE: Reproduce the broken shared Codex path and identify the real `stop_checker` mismatch.
  `KEEP_TEST_DIR=1 uv run tests/test_rejection_flow.py --runtime codex` failed immediately with `TypeError: run_codex_first_officer() got an unexpected keyword argument 'stop_checker'`; `git show 20ba861 -- scripts/test_lib.py` showed that cycle 1/2 had dropped the earlier `stop_checker` support while re-expanding the Codex invocation prompt.
- [x] DONE: Remove prompt coaching from the Codex FO invocation helper and stop treating prompt wording as wait-policy proof.
  `scripts/test_lib.py` now emits only a minimal Codex invocation prompt (workflow target plus optional run goal), and `tests/test_codex_packaged_agent_ids.py` now checks prompt discipline by asserting the old coaching text is absent.
- [x] DONE: Repair the shared Codex bounded/blocked harness path without changing the shared contract.
  Restored optional streaming `stop_checker` support in `run_codex_first_officer()`, fixed the rejection-flow milestone parser to recognize fresh implementation bounce-after-rejection as follow-up, and stopped counting never-completed `todo_list` items as active work so the bounded stop condition can terminate the Codex run.
- [x] DONE: Preserve bounded safe-naming behavior and keep the change Codex-specific.
  The Codex runtime docs remain the only source of wait-policy behavior, the shared first-officer contract was not widened, and the preserved shared Codex rejection-flow logs still show `validation_dispatch`, `validation_wait`, `implementation_dispatch`, `implementation_wait`, and safe `spacedock-ensign` worktree naming.
- [x] DONE: Re-run proportional verification and record the exact evidence.
  `python3 -m py_compile scripts/test_lib.py tests/test_rejection_flow.py tests/test_codex_packaged_agent_ids.py tests/test_agent_content.py` passed; `uv run --with pytest python tests/test_codex_packaged_agent_ids.py` passed (6/6); `uv run --with pytest python tests/test_agent_content.py` passed (31/31); `python3 - <<'PY' ... codex_rejection_flow_stop_ready(...) ... PY` returned `stop_ready=True` with all rejection-flow milestones true for `/var/folders/h1/vnssm1dj6ks4nzzvx8y29yjm0000gn/T/tmp0tsfugxm/codex-fo-log.txt` and `/var/folders/h1/vnssm1dj6ks4nzzvx8y29yjm0000gn/T/tmpa5x8bv06/codex-fo-log.txt`.
- [x] DONE: Append the required cycle-3 implementation report in the assigned worktree copy.
  This report is appended in `/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-non-blocking-interactive-worker-waits-in-codex-fo/docs/plans/non-blocking-interactive-worker-waits-in-codex-fo.md` and leaves main-orchestrator state ownership untouched.
- [ ] SKIP: Prove AC1 and AC3 with a real Codex interactive PTY harness.
  No Codex interactive PTY test exists under `tests/`, so interactive background-by-default waiting and explicit captain wait requests remain unproven rather than being overclaimed by prompt-shape tests.

### Summary

Cycle 3 removes the prompt-coached Codex test shape, restores the shared Codex rejection-flow harness path, and moves the bounded/blocked proof back onto shared live Codex logs instead of invocation wording. AC2 and AC4 now have shared Codex live-log evidence through `test_rejection_flow` milestones, AC5 remains local to Codex surfaces, and AC1/AC3 are still explicitly unproven until a real interactive Codex harness exists.

## Stage Report: implementation (cycle 2)

- [x] DONE: Tighten the wait-policy claim to match the actual harness guarantee.
  The Codex wait-policy checks are now labeled as contract/prompt-assembly coverage instead of implying live interactive timing proof.
- [x] DONE: Make each added test's purpose and coverage intention explicit.
  Added module-level notes and test docstrings in `tests/test_agent_content.py` and `tests/test_codex_packaged_agent_ids.py` describing the checks as contract-level, not live interactive session coverage.
- [x] DONE: Preserve the bounded and explicit-wait policy wording.
  The Codex runtime text and prompt assembly still describe interactive background behavior, explicit captain wait requests, and bounded single-entity immediate waiting.
- [x] DONE: Re-run targeted verification.
  `python3 -m py_compile scripts/test_lib.py tests/test_agent_content.py tests/test_codex_packaged_agent_ids.py` passed; `uv run --with pytest python tests/test_codex_packaged_agent_ids.py` passed (6/6); `uv run --with pytest python tests/test_agent_content.py` passed (29/29).
- [x] DONE: Commit the feedback-cycle update in the assigned worktree.
  This cycle's code and report updates were committed in the worktree after verification.
- [ ] SKIP: Prove actual live interactive wait timing in Codex.
  The current harness can validate prompt-level contract text and ID resolution, but it does not expose a deterministic live interactive Codex session that can observe internal wait scheduling.

### Summary

This feedback cycle corrects the overclaim: the implementation now says exactly what the current harness proves, namely Codex runtime guidance and prompt assembly for interactive, blocked, explicit-wait, and bounded paths. The tests now state their coverage intent plainly so the report no longer overstates live interactive behavioral proof.

## Stage Report: validation (cycle 2)

- [x] DONE: Read the current entity body and validate against the current acceptance criteria.
  Compared the cycle-2 implementation claims with the unchanged AC1-AC5 in this worktree before judging evidence.
- [x] DONE: Identify the substantive deliverable under review.
  The behavior under review lives in `skills/first-officer/references/codex-first-officer-runtime.md`, `scripts/test_lib.py`, `tests/test_agent_content.py`, and `tests/test_codex_packaged_agent_ids.py`.
- [x] DONE: Run proportional verification commands and record results.
  `python3 -m py_compile scripts/test_lib.py tests/test_agent_content.py tests/test_codex_packaged_agent_ids.py` passed; `uv run --with pytest python tests/test_codex_packaged_agent_ids.py -q` passed (6/6); `uv run --with pytest python tests/test_agent_content.py -q` passed (31/31); `uv run tests/test_gate_guardrail.py --runtime codex` passed (6/6).
- [ ] FAILED: Verify AC1 interactive dispatch stays background by default.
  No Codex interactive PTY test exists in `tests/`, so this branch still has only runtime-doc and prompt-shape checks for AC1 rather than a live interactive Codex proof.
- [ ] FAILED: Verify AC2 foreground waiting happens only when the next orchestration step is blocked on the worker result.
  A preserved bounded Codex spot-check shows a blocked path does wait (`/var/folders/h1/vnssm1dj6ks4nzzvx8y29yjm0000gn/T/tmps411n4mp/codex-fo-log.txt` lines 34-38), but the generic shared Codex proof path is broken: `KEEP_TEST_DIR=1 uv run tests/test_rejection_flow.py --runtime codex` fails immediately with `TypeError: run_codex_first_officer() got an unexpected keyword argument 'stop_checker'`.
- [ ] FAILED: Verify AC3 explicit captain wait requests trigger foreground waiting.
  No test or live harness run in this worktree drives a Codex interactive session with an explicit captain "wait" request, so AC3 remains unproven.
- [x] DONE: Verify AC4 bounded or single-entity runs can still wait immediately after dispatch.
  The preserved packaged-agent Codex log shows bounded single-entity behavior explicitly: line 34 states the FO will wait because the run is bounded, `spawn_agent` completes at line 36, and `wait` on the same handle completes at line 38.
- [x] DONE: Verify AC5 the change stays Codex-specific.
  The changed wait-policy text is confined to Codex runtime guidance and Codex-specific helpers/tests; the shared first-officer core was not expanded for this policy.
- [ ] FAILED: Evaluate the prompt-discipline concern and route the fix request.
  `tests/README.md` requires minimal Codex FO invocation prompts and forbids behavioral coaching, but `scripts/test_lib.py` still encodes wait/reuse/shutdown rules into `build_codex_first_officer_invocation_prompt()` and `tests/test_codex_packaged_agent_ids.py` asserts on that wording. Route this back to implementation: remove behavioral coaching from the invocation prompt helper, stop treating prompt wording as proof of FO policy, repair shared `--runtime codex` live coverage for generic blocked/bounded behavior starting with `tests/test_rejection_flow.py`, and leave AC1/AC3 unproven until a real Codex interactive harness exists or the criteria are narrowed.

Counts: 5 done, 0 skipped, 4 failed

### Summary

Cycle 2 correctly narrows the written claim to contract-level coverage, but the current acceptance criteria still ask for behavioral proof the branch does not yet provide. AC4 now has live bounded evidence and AC5 passes, but AC1 and AC3 remain unproven, AC2 lacks a compliant shared Codex behavioral test, and the current prompt-shape tests conflict with `tests/README` prompt-discipline guidance.

Recommendation: REJECTED

## Stage Report: validation (cycle 3)

- [x] DONE: Read the current entity body and inspect the reviewed implementation surfaces.
  Validated cycle-3 claims against AC1-AC5 after reading this entity plus `scripts/test_lib.py`, `tests/test_rejection_flow.py`, `tests/test_codex_packaged_agent_ids.py`, `tests/test_agent_content.py`, `tests/README.md`, and `skills/first-officer/references/codex-first-officer-runtime.md`.
- [x] DONE: Re-run the proportional static checks.
  `python3 -m py_compile scripts/test_lib.py tests/test_rejection_flow.py tests/test_codex_packaged_agent_ids.py tests/test_agent_content.py` passed; `uv run --with pytest python tests/test_codex_packaged_agent_ids.py -q` passed (6/6); `uv run --with pytest python tests/test_agent_content.py -q` passed (31/31).
- [x] DONE: Verify the `tests/README.md` prompt-discipline violation is fixed.
  `tests/README.md` lines 95-103 require a minimal Codex FO prompt; `scripts/test_lib.py` lines 91-100 now emit only skill + workflow target + optional run goal, `tests/test_codex_packaged_agent_ids.py` lines 49-73 assert the old coaching text is absent, and the live rerun preserved `/var/folders/h1/vnssm1dj6ks4nzzvx8y29yjm0000gn/T/tmp7n5o4mbt/codex-fo-invocation.txt` with only the workflow path plus `Process only the entity \`buggy-add-task\`.`.
- [x] DONE: Verify bounded/blocked waiting still works on the shared `--runtime codex` path.
  `KEEP_TEST_DIR=1 uv run tests/test_rejection_flow.py --runtime codex` no longer fails with the old `stop_checker` `TypeError`; the preserved live log at `/var/folders/h1/vnssm1dj6ks4nzzvx8y29yjm0000gn/T/tmp7n5o4mbt/codex-fo-log.txt` shows the FO saying the single-entity run is blocked on the validation verdict (line 32), then issuing `wait` on the validation worker (lines 35-36). I treated that preserved log as the evidence source instead of overclaiming the coarse milestone helper.
- [x] DONE: Verify AC5 remains Codex-specific.
  The wait-policy text remains local to `skills/first-officer/references/codex-first-officer-runtime.md` lines 133-134, and no shared-contract file was changed for this behavior.
- [ ] FAILED: Verify AC1 interactive Codex dispatch stays background by default.
  No Codex interactive PTY harness exists under `tests/`; `tests/README.md` lines 105-109 describe only the Claude `InteractiveSession` path, and `tests/test_agent_content.py` lines 7-8 and 129-138 explicitly describe contract-wording checks rather than a live interactive Codex session.
- [ ] FAILED: Verify AC3 explicit captain wait requests trigger foreground waiting.
  No current test or preserved live run drives a Codex interactive session where the captain explicitly asks to wait, so AC3 remains unproven in this branch.

Counts: 5 done, 0 skipped, 2 failed

### Summary

Cycle 3 fixes the prior prompt-coaching problem and restores fresh shared Codex evidence for bounded blocked waiting: the live rerun now reaches the validation wait path and the invocation prompt is compliant with `tests/README.md`. The branch still does not satisfy the unchanged interactive acceptance criteria, though, because there is still no interactive Codex harness for AC1 or AC3, so the recommendation remains `REJECTED`.

Recommendation: REJECTED

## Stage Report: validation (cycle 4)

- [x] DONE: Verify the Codex runtime contract describes background-by-default interactive waiting.
  `skills/first-officer/references/codex-first-officer-runtime.md` says interactive sessions keep workers in the background unless the next step is blocked, while bounded single-entity runs may wait immediately; `uv run --with pytest python tests/test_agent_content.py -q` passed (36/36) with the Codex contract wording checks included.
- [x] DONE: Verify the shared `--runtime codex` path still foregrounds `wait_agent` when the next step is blocked.
  `KEEP_TEST_DIR=1 uv run tests/test_rejection_flow.py --runtime codex` passed (16/16); the preserved live log at `/var/folders/h1/vnssm1dj6ks4nzzvx8y29yjm0000gn/T/tmp0vftdfqu/codex-fo-log.txt` shows the FO saying it will wait because the verdict is on the critical path, then completing the validation `wait` before routing the rejection follow-up.
- [x] DONE: Verify bounded or single-entity Codex runs can still wait immediately after dispatch.
  The preserved invocation prompt at `/var/folders/h1/vnssm1dj6ks4nzzvx8y29yjm0000gn/T/tmp0vftdfqu/codex-fo-invocation.txt` scopes the run to `Process only the entity \`buggy-add-task\`.`, and the same shared live Codex run dispatches validation and waits on that handle before any unrelated orchestration.
- [x] DONE: Verify Codex FO prompts stay minimal and do not encode wait-policy coaching.
  `tests/README.md` requires minimal Codex FO prompts; `uv run --with pytest python tests/test_codex_packaged_agent_ids.py -q` passed (9/9) while checking that the invocation prompt omits behavioral coaching text.
- [x] DONE: Verify the behavior stays Codex-specific and does not require a shared-contract change.
  The touched wait-policy behavior remains confined to `skills/first-officer/references/codex-first-officer-runtime.md`, `scripts/test_lib.py`, `tests/test_agent_content.py`, and `tests/test_codex_packaged_agent_ids.py`; no shared first-officer contract file was widened for this policy.

### Summary

The narrowed task is satisfied. The repo now proves the Codex-local pre-completion wait policy with contract wording, shared live `--runtime codex` blocked-wait evidence, bounded single-entity immediate-wait evidence, and prompt-discipline checks aligned with `tests/README.md`. Recommendation: PASSED
