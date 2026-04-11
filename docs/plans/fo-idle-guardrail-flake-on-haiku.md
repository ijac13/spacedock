---
id: 117
title: FO DISPATCH IDLE GUARDRAIL flake on haiku — premature ensign shutdown in nested test
status: validation
source: Validator observation during 115 validation (run 1 of test_dispatch_completion_signal.py)
started: 2026-04-11T04:45:04Z
completed:
verdict:
score: 0.70
worktree: .worktrees/spacedock-ensign-fo-idle-guardrail-flake-on-haiku
issue:
pr:
---

During validation of task 115, the validator ensign observed a flake in `tests/test_dispatch_completion_signal.py` on the haiku model: run 1 failed, run 2 passed cleanly. The failure is independent of task 115's completion-signal template fix. Task 115 ensured the dispatched worker was instructed to send a completion message; task 117 is about the FO deciding to stop waiting before that message arrives.

## Problem Statement

The first officer sometimes tears down a dispatched team too early on haiku, even when the worker prompt already contains the completion-signal instruction and the runtime guardrail says to ignore idle notifications. In the failing run, the FO entered a wait posture, executed a few Bash/Read cycles, and then shut the team down before the ensign's `SendMessage(to="team-lead", ...)` completion signal arrived.

That makes this a FO-side behavioral reliability issue, not a worker-template issue. The symptom only shows up in the nested haiku harness; the same workflow passed on a later retry without code changes, which points to model behavior or instruction robustness rather than a deterministic logic bug.

## Root Cause Framing

The current `DISPATCH IDLE GUARDRAIL` in `skills/first-officer/references/claude-first-officer-runtime.md` is directionally correct, but haiku appears to treat repeated idle cycles as a cue to clean up instead of continuing to wait. The likely failure path is:

1. FO dispatches an ensign and enters "Standing by."
2. Idle or routine tool cycles continue while the ensign is still working.
3. Haiku loses the "wait for explicit completion" invariant and treats the team as done or abandoned.
4. FO tears down the team before the completion message arrives.

The important distinction is that the fix surface is the FO's wait/teardown behavior, not the worker's completion instruction. This should not be broadened into a telemetry project or a general watchdog redesign unless the narrower instruction fix still flakes.

## Plausible Fix Surfaces

1. Tighten the FO guardrail wording in the runtime reference, especially around dispatch-time waiting and teardown preconditions.
   - This is the smallest and most likely fix surface.
   - It should explicitly say that idle is normal, that the FO must wait for `SendMessage` completion, and that repeated idle cycles are not evidence of failure.

2. Reinforce the rule closer to the dispatch path, not only in the standalone guardrail section.
   - If the instruction is only in one long guardrail paragraph, haiku may underweight it after several turns.
   - A short, repeated "wait until completion message" reminder near the dispatch adapter may be more robust.

3. Add a narrow runtime check before teardown.
   - This would make the wait decision less dependent on model memory.
   - It is a stronger behavioral change and should be treated as a fallback if wording alone is still flaky.

4. Build broader telemetry or a watchdog around agent liveness.
   - This could help diagnose the flake, but it is out of scope for task 117.
   - It would add complexity without proving the minimal fix first.

## Recommended Scope

Use the smallest fix that directly addresses premature teardown:

- Strengthen the FO runtime wording around dispatch-time waiting and teardown conditions.
- If needed, repeat the same rule near the dispatch adapter so the model sees it at the point of action.
- Keep the implementation bounded to the FO runtime reference and the regression test that proves the haiku flake no longer tears down early.

Do not expand this task into:

- completion-signal template work for the worker side, which is task 115
- telemetry/watchdog instrumentation
- generalized model-reliability research
- upstream Claude Code bug tracking

## Acceptance Criteria

1. The FO runtime text explicitly states that, after dispatching an agent, the FO must keep waiting until an explicit completion message arrives.
   - Test: static content check against `skills/first-officer/references/claude-first-officer-runtime.md` or the assembled FO agent content.

2. The FO runtime text explicitly says idle notifications are normal between-turn state and are not a reason to tear down the team.
   - Test: static content check for the idle-is-normal / do-not-shut-down language.

3. A haiku regression run no longer reproduces the premature shutdown seen in run 1.
   - Test: `tests/test_dispatch_completion_signal.py` or a task-117-specific regression test passes consistently across multiple runs, including the original failing scenario.

4. The fix does not change task 115's worker completion-signal template or widen scope into telemetry/watchdog work.
   - Test: diff review confirms the touched files stay limited to the FO runtime reference and the task-117 regression test.

5. Existing related suites still pass.
   - Test: rerun the dispatch-completion regression and the nearby FO guardrail suites that cover dispatch/wait behavior.

## Test Plan

- Reproduction: keep the original haiku workflow fixture that showed the flake, because the regression is about the FO's shutdown decision under the same conditions. Cost is moderate because it exercises a live model run.
- Verification: add or reuse a regression test that inspects the FO log for premature teardown and checks that the entity only advances after the worker's completion signal. Cost is moderate, complexity is moderate.
- Static checks: add a content assertion for the runtime wording so the guardrail cannot silently drift later. Cost is low.
- E2E coverage: yes, because this is a behavioral timing bug. Static wording checks alone do not prove the FO will keep waiting on haiku.
- Out-of-scope follow-up: telemetry or watchdog work can be explored later if the narrower runtime wording still flakes.

## Related

- Task 115 `fo-dispatch-template-completion-signal` keeps the worker-side completion instruction correct and should remain separate.
- `skills/first-officer/references/claude-first-officer-runtime.md` is the primary fix surface for task 117.

### Feedback Cycles

- Cycle 1 (2026-04-11): Validation REJECTED. Static/runtime checks passed, but the required live haiku regression (`tests/test_dispatch_completion_signal.py --model haiku`) did not complete within the bounded validation run, so AC3 and AC5 remain unproven. Route back to implementation to obtain completed haiku regression evidence or adjust the task/test plan if that live requirement is currently impractical.

## Stage Report: ideation

1. [DONE] Expanded the task body into a scoped ideation spec with a clearer problem statement, observed failure path, and root-cause framing. The write-up now distinguishes the FO-side premature teardown from task 115's worker completion-signal fix.

2. [DONE] Evaluated plausible fix surfaces and recommended a bounded approach. The spec compares guardrail wording, dispatch-adapter reinforcement, narrow teardown checks, and broader telemetry, then recommends the smallest FO-runtime-only fix.

3. [DONE] Added concrete acceptance criteria with test mapping. Each criterion now states how it will be tested, with static content checks for wording and E2E coverage for the behavioral flake.

4. [DONE] Wrote a proportional test plan. The plan covers reproduction, verification, static checks, and confirms that E2E coverage is required because the bug is behavioral and timing-sensitive.

5. [DONE] Kept scope bounded to task 117. The spec explicitly calls out task 115, telemetry/watchdog work, and upstream Claude Code investigation as out of scope.

6. [DONE] Appended a complete ideation `## Stage Report` section at the end of the entity body with every checklist item marked DONE.

7. [DONE] Committed the ideation work after updating the entity body.

## Implementation Summary

Strengthened the Claude first-officer runtime in two places only. The dispatch adapter's team-mode completion-signal block now reminds the FO that it keeps waiting for the worker's explicit completion message and that idle notifications are normal while it waits. The `DISPATCH IDLE GUARDRAIL` now explicitly says the FO keeps waiting after dispatch until an explicit completion message arrives and that idle notifications are not a reason to tear down the team.

Regression coverage was tightened in `tests/test_agent_content.py` so the assembled FO contract must keep both the stronger wait-until-completion wording and the dispatch-local reminder. The resulting code/test diff stayed limited to the FO runtime wording and task-117 static regression coverage; task 115's worker completion-signal template and any telemetry/watchdog work were left untouched.

## Stage Report: implementation

- [x] Implement the narrow fix described in the approved ideation: strengthen FO runtime waiting/idle guardrail wording, and reinforce it near dispatch if needed.
  Updated `skills/first-officer/references/claude-first-officer-runtime.md`; code changes committed in `4b3043c`.
- [x] Add or update tests proving the new wording is present and guarding against regression.
  Tightened `tests/test_agent_content.py` to assert explicit post-dispatch waiting, idle-is-normal wording, and dispatch-local reinforcement.
- [ ] SKIP: Run the relevant regression coverage for this task, including the dispatch-completion/FO wait behavior tests that are practical in this environment.
  `uv run --with pytest python -m pytest tests/test_agent_content.py` passed (`25 passed`), but the live harness runs for `tests/test_dispatch_completion_signal.py --model haiku` and `tests/test_team_dispatch_sequencing.py --model haiku` did not complete within extended waits in this session, so independent verification should rerun those model-backed checks.
- [x] Keep scope bounded: do not modify task 115’s worker completion-signal template or add telemetry/watchdog work.
  Diff stayed limited to the FO runtime reference and task-117 regression coverage.
- [x] Update the entity body with an implementation summary and append a complete `## Stage Report: implementation` with each checklist item marked DONE, SKIPPED, or FAILED.
  Added the implementation summary and this stage report to `docs/plans/fo-idle-guardrail-flake-on-haiku.md`.
- [x] Commit the implementation work in the worktree before reporting completion.
  Committed the runtime/test changes in `4b3043c` before writing this completion report.

### Summary

The fix stayed on the approved surface: the Claude FO runtime now states more directly that dispatch means wait for an explicit completion message, and that idle notifications are normal rather than evidence to tear the team down. Static regression coverage was updated and passes; the model-backed FO wait regressions were attempted here but remained inconclusive due long-running live harness execution, so they should be rerun during independent verification.
