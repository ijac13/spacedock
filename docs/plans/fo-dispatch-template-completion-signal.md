---
id: 115
title: FO dispatch template missing completion-signal instruction
status: validation
source: CL diagnosis during 2026-04-10 boot session
started: 2026-04-10T15:41:22Z
completed:
verdict:
score: 0.90
worktree: .worktrees/spacedock-ensign-fo-dispatch-template-completion-signal
issue:
pr:
---

Team-dispatched ensigns finish their stage work and then go idle silently, and the FO sits waiting indefinitely. This is the "FO idle after ensign completion" pattern observed across several recent sessions.

## Root Cause

The `SendMessage(to="team-lead", ...)` completion-signal instruction exists only in `skills/ensign/references/claude-ensign-runtime.md` ("## Completion Signal" section). Due to Claude Code bug #30703 (documented in task 107), team-dispatched agents silently lose their `agents/{name}.md` body and their declared skills — so team-dispatched ensigns never see that instruction.

The FO dispatch prompt template in `skills/first-officer/references/claude-first-officer-runtime.md` ("## Dispatch Adapter", the `Agent(...)` template) tells the ensign to write a `## Stage Report` section in the entity file, but contains **no** completion-signal wording. After the ensign finishes writing the report, its turn ends. The FO's DISPATCH IDLE GUARDRAIL (commit `3728d6a`, 2026-04-08) correctly waits for a `SendMessage` that physically cannot arrive.

This was previously masked because bare-mode `Agent()` returns inline (no SendMessage needed), and before `3728d6a` the FO sometimes interpreted idle as completion by accident. The idle guardrail now exposes the bug cleanly.

Task 107's claim that "Completion protocol — SendMessage back to FO works (learned from dispatch prompt)" is incorrect. The dispatch prompt does not carry the instruction.

## Proposed Approach

1. Add an explicit team-mode completion-signal instruction to the Claude Code FO dispatch prompt template in `skills/first-officer/references/claude-first-officer-runtime.md`. Emit it only when dispatching with `team_name` — bare-mode dispatch is unaffected because it returns inline.
2. Extend `tests/test_agent_content.py` with a static assertion that the assembled team-mode dispatch template contains the completion-signal wording, and that bare-mode does not require it.
3. Add an E2E regression test that drives an FO through a team-dispatched worktree stage and asserts the FO advances the entity's status without manual captain intervention. This is the symptom we actually observed; the test must fail on the parent commit and pass after the fix.

Scope: completion-signal only. The other 3 missing protocol items listed in task 107 (captain communication, clarification escalation, feedback interaction) are out of scope here and remain tracked by 107.

## Acceptance Criteria

1. The assembled Claude Code FO dispatch prompt contains an explicit `SendMessage(to="team-lead", ...)` completion-signal instruction when dispatching in team mode.
   - Test: `tests/test_agent_content.py` asserts the string is present in the team-mode template branch.
2. The completion-signal instruction is gated on team mode (not emitted in bare mode).
   - Test: `tests/test_agent_content.py` asserts the template branches correctly.
3. A team-dispatched ensign actually calls `SendMessage(to="team-lead", ...)` on completion, and the FO advances the entity to the next stage without manual captain intervention.
   - Test: new E2E regression test that runs an FO via `claude -p` (or the existing harness used by `tests/test_rejection_flow.py`), dispatches an ensign to a worktree stage, and asserts the entity's frontmatter `status` transitioned to the next stage. **Must fail on the parent commit and pass after the fix.** This is the explicit E2E coverage the captain asked for.
4. Existing suites still pass.
   - Test: `uv run tests/test_agent_content.py`, `uv run tests/test_rejection_flow.py`, `uv run tests/test_merge_hook_guardrail.py`, and any other suite touched by the template change.

## Test Plan

- Static template coverage: extend `tests/test_agent_content.py` — low cost, low complexity. Asserts assembled prompt string content.
- E2E regression: new test (suggested name `tests/test_dispatch_completion_signal.py`) driven via `claude -p`. Medium cost, medium complexity. Reuse an existing fixture if one fits, otherwise create a minimal one. This test IS the proof that the symptom is actually fixed — it must demonstrate a failing-then-passing transition across the fix commit.
- No browser/UI E2E.

## Related

- Task 107 `team-agent-skill-loading-bug` — the broader upstream bug. This task is the narrow fix for the completion-signal symptom only. Task 107 should be updated after this lands to correct the "dispatch prompt is self-contained" assumption.

## Stage Report: implementation

1. [x] Read `skills/first-officer/references/claude-first-officer-runtime.md` in full and confirmed the pre-fix `Agent(...)` template in the `## Dispatch Adapter` section contained no completion-signal wording for team-dispatched workers. The only `SendMessage` reference in that section was the header sentence "SendMessage is only used in the completion path to advance a reused agent to its next stage" (which describes FO→ensign reuse messaging, not worker→FO completion signalling). The surrounding `## Captain Interaction` and `DISPATCH IDLE GUARDRAIL` sections confirmed the FO would wait indefinitely for a worker completion SendMessage after the ensign went idle.

2. [x] Added `test_assembled_claude_first_officer_dispatch_template_has_team_mode_completion_signal` in `tests/test_agent_content.py`. It extracts the `## Dispatch Adapter` section from `skills/first-officer/references/claude-first-officer-runtime.md` and asserts the team-mode Agent(...) prompt template contains `SendMessage(to="team-lead"` (allowing for escaped inner quotes because the instruction lives inside the `prompt="..."` literal), and that the instruction is gated on team mode.

   Pre-fix run (stashed template fix, ran the single new test):
   ```
   FAILED tests/test_agent_content.py::test_assembled_claude_first_officer_dispatch_template_has_team_mode_completion_signal
   AssertionError: Dispatch Adapter section must instruct team-dispatched workers to SendMessage(to="team-lead", ...) on completion.
   assert None
    +  where None = re.search('SendMessage\\(to=\\\\?"team-lead\\\\?"', '\nUse the Agent tool to spawn each worker. ... Dispatch one entity at a time and process completions inline.\n')
   1 failed in 0.02s
   ```

3. [x] Added `tests/test_dispatch_completion_signal.py` and a minimal `tests/fixtures/completion-signal-pipeline/` fixture (backlog → work (worktree) → done, no gates) with a one-line `completion-signal-task.md` entity. The test boots a project, dispatches the FO via `claude -p` with an all-tasks prompt (plural, so the FO stays in normal team-mode dispatch instead of single-entity mode), and asserts three things: the FO exited cleanly within the 600s timeout, the entity was archived without manual captain intervention, and the dispatched ensign prompt carries the `SendMessage(to="team-lead"` completion-signal instruction.

   Pre-fix run against the original template (model haiku, budget $3.00):
   ```
   === Dispatch Completion-Signal E2E Test (claude) ===
   --- Phase 1: Set up test project from fixture ---
     PASS: status script runs without errors
   --- Phase 2: Run first officer (claude) ---
     TIMEOUT: first officer exceeded 600s limit
     (first officer exit code 124 — may be expected for the pre-fix hang case)
   --- Phase 3: Validation ---
   [Entity Advancement]
     PASS: FO dispatched at least one ensign
     PASS: entity advanced and was archived without manual captain intervention
     FAIL: dispatched ensign prompt does NOT carry SendMessage(to="team-lead", ...) instruction — the FO dropped the completion signal from its dispatch template.
   === Results ===
     3 passed, 1 failed
   RESULT: FAIL
   ```
   Analysis of the pre-fix failure mode: the FO was able to poll the entity file and detect completion indirectly after the ensign wrote its `## Stage Report` section, which is why the archive assertion still passed — but it could NOT cleanly shut down the lingering team-dispatched ensign because the ensign never emitted a SendMessage, so the FO spent the rest of its 600s budget trying to clean up before timing out. After adding the `first officer exited cleanly within timeout` assertion, the pre-fix test also fails on that check (exit code 124 ≠ 0).

4. [x] Updated the `Agent(...)` prompt template at `skills/first-officer/references/claude-first-officer-runtime.md:53` to append a team-mode-only `### Completion Signal` section to the end of the worker prompt. The instruction is conditional on team mode (`{if not bare mode: '...'}`) so bare-mode dispatch, which returns inline and does not need SendMessage, is unchanged.

   Before (line 53, relevant tail of the `prompt="..."` literal):
   ```
   ...Every checklist item must appear in your report. Do not omit items."
   ```

   After (line 53, same literal):
   ```
   ...Every checklist item must appear in your report. Do not omit items.{if not bare mode: '\n\n### Completion Signal\n\nThis is a team-mode dispatch. When you finish (after all commits and stage report writes are done), your last action MUST be:\n\n    SendMessage(to=\"team-lead\", message=\"Done: {entity title} completed {next_stage_name}. Report written to {entity_file_path}.\")\n\nPlain text only. No JSON. Until you send this message, the first officer cannot observe your completion and the entity will not advance to the next stage.'}"
   ```

5. [x] Reran both tests post-fix.

   Static test:
   ```
   $ unset CLAUDECODE && uv run --with pytest python tests/test_agent_content.py -q
   ...
   tests/test_agent_content.py .................                            [100%]
   17 passed, 1 warning in 0.04s
   ```

   E2E test (model haiku, budget $3.00):
   ```
   === Dispatch Completion-Signal E2E Test (claude) ===
   --- Phase 2: Run first officer (claude) ---
   === Stats: fo ===
     Wallclock:        242s
   PASS: first officer exited cleanly within timeout (no pre-fix hang)
   --- Phase 3: Validation ---
   [Entity Advancement]
     PASS: FO dispatched at least one ensign
     PASS: entity advanced and was archived without manual captain intervention
     PASS: dispatched ensign prompt carries SendMessage completion-signal instruction
   === Results ===
     5 passed, 0 failed (out of 5 checks)
   RESULT: PASS
   ```
   Wallclock dropped from 600s (timeout) pre-fix to 242s post-fix — the FO cleanly shuts down the ensign as soon as the SendMessage arrives.

6. [x] Ran broader regression suites.

   Static agent content suite:
   ```
   $ unset CLAUDECODE && uv run --with pytest python tests/test_agent_content.py -q
   17 passed, 1 warning in 0.02s
   ```

   Rejection flow E2E:
   ```
   $ unset CLAUDECODE && uv run tests/test_rejection_flow.py
   === Rejection Flow E2E Test (claude) ===
   PASS: status script runs without errors
   PASS: status --next detects dispatchable entity
   PASS: FO dispatched an ensign for validation stage
   PASS: reviewer stage report contains REJECTED recommendation
   PASS: FO dispatched ensign for fix after rejection (4 total ensign dispatches)
   === Results ===
     5 passed, 0 failed
   RESULT: PASS
   ```

   Merge hook guardrail E2E (hook mod run + no-mods fallback run):
   ```
   $ unset CLAUDECODE && uv run tests/test_merge_hook_guardrail.py
   === Merge Hook Guardrail E2E Test (claude) ===
   [Merge Hook Execution]
     PASS: merge hook fired marker exists
     PASS: merge hook fired marker contains entity slug
     PASS: entity was archived (merge completed after hook)
     PASS: worktree cleaned up after merge hook run
     PASS: temporary branch cleaned up after merge hook run
   [Fixture Setup — No Mods]
     PASS: status script runs without errors (no-mods)
   [No-Mods Fallback]
     PASS: no merge hook marker exists in no-mods run
     PASS: entity was archived via local merge (no-mods fallback works)
     PASS: worktree cleaned up after no-mods fallback
     PASS: temporary branch cleaned up after no-mods fallback
   === Results ===
     11 passed, 0 failed
   RESULT: PASS
   ```

7. [x] Committed work in two logical commits on branch `spacedock-ensign/fo-dispatch-template-completion-signal`:
   - `a9ba14f test: failing regressions for FO dispatch template completion signal` (adds the fixture, the static assertion, and the E2E regression test — fails on the parent commit)
   - `e9db417 fix: add team-mode completion signal to FO dispatch prompt template` (the one-line template change that satisfies both tests)

8. [x] This stage report was written with per-item evidence, an explicit before/after diff of the template change (item 4), and the concrete test commands that were run (items 2, 3, 5, 6).
