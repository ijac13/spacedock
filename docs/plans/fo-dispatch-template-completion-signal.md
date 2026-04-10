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
