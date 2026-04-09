---
id: 101
title: "FO incorrectly enters single-entity mode during normal interactive dispatch"
status: validation
source: CL observation — seen 3x in Claude Code, 1x in Codex
started: 2026-04-09T15:24:00Z
completed:
verdict:
score: 0.8
worktree: .worktrees/spacedock-ensign-single-entity-mode-bug
issue:
pr:
---

The FO enters single-entity mode during normal interactive sessions when the user mentions a specific entity. Single-entity mode is designed for non-interactive `-p` invocations. In interactive sessions, the FO should use the standard event loop with team support.

## Observations

**Codex:** The Codex FO resolved entity 087 (already in implementation) and announced single-entity mode, treating it as if the user had asked to process that specific entity in pipe mode.

**Claude Code (3 occurrences):** The FO misapplies single-entity mode when the user names a specific entity to work on. The FO's own self-diagnosis from the latest occurrence:

> "I misapplied single-entity mode. The shared core says 'when the user names a specific entity → single-entity mode' but the Claude runtime clarifies its purpose: bare-mode dispatch to 'prevent premature session termination in -p mode.' This is an interactive session — I should have created a team and dispatched with team_name like normal."

The practical impact: bare-mode dispatch blocks until the ensign completes, preventing concurrent dispatch of other entities. The FO loses team capabilities.

## Root cause

The shared core's trigger condition is too broad: "When the user names a specific entity and asks to process it through the workflow, switch into single-entity mode." In interactive sessions, users routinely name entities ("let's work on 057", "dispatch 104") without intending single-entity mode. The trigger should be scoped to non-interactive invocations only.

## Possible fix

The Claude runtime already has the right intent: "In single-entity mode, skip team creation entirely. Use bare-mode dispatch for all agent spawning — the Agent tool without team_name blocks until the subagent completes, which prevents premature session termination in -p mode."

The fix should tighten the trigger in the shared core: single-entity mode activates only when the session is non-interactive (e.g., invoked via `-p` flag), not when the user names an entity in conversation.

## Stage Report

### 1. Current single-entity mode trigger condition in the shared core

File: `references/first-officer-shared-core.md`, line 39, under `## Single-Entity Mode`:

> When the user names a specific entity and asks to process it through the workflow, switch into single-entity mode.

The Codex runtime (`references/codex-first-officer-runtime.md`, line 16) echoes this:

> If the user names a specific entity and asks to process it through the workflow, apply the shared single-entity mode rules.

**Status: DONE**

### 2. Why the trigger fires incorrectly in interactive sessions

The trigger condition says "when the user names a specific entity" — but naming a specific entity is **normal interactive behavior**. Users routinely say "let's work on 057" or "dispatch 104" in conversation. The trigger makes no distinction between:

- **Interactive session**: User names entity in conversation as part of ongoing work. The FO should create a team and use normal dispatch.
- **Non-interactive session**: Invoked via `claude -p "process entity X"` where there is no ongoing conversation, no captain to approve gates, and the session must terminate deterministically.

The Claude runtime (`references/claude-first-officer-runtime.md`, line 31) reveals the actual purpose:

> In single-entity mode, skip team creation entirely. Use bare-mode dispatch for all agent spawning — the Agent tool without `team_name` blocks until the subagent completes, which prevents premature session termination in `-p` mode.

The key insight: single-entity mode exists to solve a **technical problem** (premature session termination in `-p` mode) and an **operational problem** (no captain to approve gates). Both problems only exist in non-interactive sessions. The shared core's trigger doesn't encode this constraint.

**Status: DONE**

### 3. Proposed fix — exact before/after wording

#### File 1: `references/first-officer-shared-core.md`

**Before** (line 39):
```
When the user names a specific entity and asks to process it through the workflow, switch into single-entity mode.
```

**After**:
```
Single-entity mode activates when the session is non-interactive (e.g., invoked via `claude -p` or `codex exec`) and the prompt names a specific entity to process through the workflow. Do not enter single-entity mode in interactive sessions — naming an entity in conversation is normal dispatch, not a mode switch.
```

#### File 2: `references/codex-first-officer-runtime.md`

**Before** (line 16):
```
- If the user names a specific entity and asks to process it through the workflow, apply the shared single-entity mode rules.
```

**After**:
```
- If the session is non-interactive (e.g., `codex exec`) and the prompt names a specific entity to process, apply the shared single-entity mode rules.
```

#### File 3: `references/claude-first-officer-runtime.md`

No change needed. The Claude runtime already describes single-entity mode's purpose correctly (preventing premature session termination in `-p` mode). The bug is in the trigger condition, which lives in the shared core.

**Status: DONE**

### 4. Files that need changes

1. `references/first-officer-shared-core.md` — tighten the trigger condition (primary fix)
2. `references/codex-first-officer-runtime.md` — align the Codex-specific echo of the trigger

No changes needed to:
- `references/claude-first-officer-runtime.md` — already describes purpose correctly
- Any code files — the trigger is in prompt/reference text, not code

**Status: DONE**

### 5. Acceptance criteria with test plan

All four acceptance criteria are deliverables of this task. The text fix (AC1-AC2) ships with a regression test (AC3) to prevent re-introduction. AC4 verifies the legitimate use case is preserved.

**AC1: The shared core trigger condition requires non-interactive session context.** (this task)
- Deliverable: Updated wording in `references/first-officer-shared-core.md`.
- Verification: Grep the `## Single-Entity Mode` section and confirm the trigger mentions "non-interactive" and does not activate on entity naming alone.

**AC2: The Codex runtime trigger condition requires non-interactive session context.** (this task)
- Deliverable: Updated wording in `references/codex-first-officer-runtime.md`.
- Verification: Grep for "single-entity" and confirm the trigger mentions non-interactive/exec context.

**AC3: Regression test — interactive session creates a team, not bare mode, when user names an entity.** (this task)
- Deliverable: A new PTY-based E2E test file (e.g., `tests/test_single_entity_mode.py`) using `scripts/test_lib_interactive.py`.
- Test design: Set up a test workflow fixture with a dispatchable entity. Start an interactive session with the FO skill. Send a message naming a specific entity. Verify the FO creates a team (look for TeamCreate in output or subagent logs with `team_name` set) and does NOT enter single-entity/bare mode (absence of "single-entity mode" in output).
- Cost: Medium. Requires a test workflow fixture and a live Claude session (~$0.50-1.00 per run with haiku). The `InteractiveSession` class already supports this pattern — see `tests/test_interactive_poc.py` for the existing harness.
- Implementation sketch:
  ```python
  session = InteractiveSession(model="haiku", max_budget_usd=1.00, cwd=test_workflow_dir)
  session.start()
  session.send("/spacedock:first-officer")
  session.wait_for("status", timeout=60)  # wait for FO boot
  session.send("work on entity 001")
  # Verify team creation happened (not single-entity mode)
  assert not session.wait_for("single-entity mode", timeout=30, min_matches=1)
  # OR: check subagent logs for team_name presence
  ```

**AC4: `claude -p` still correctly enters single-entity mode.** (this task)
- Deliverable: Verified manually or via a non-interactive script test during implementation.
- Test design: Run `claude -p "process entity 001 through the workflow in /path/to/workflow"` with a test workflow and verify the output indicates single-entity mode behavior (auto-resolved gates, deterministic completion).
- Cost: Low. Single `claude -p` invocation (~$0.25-0.50 with haiku).

**Status: DONE**

### 6. Edge cases

**Edge case: `claude -p "process entity X"`** — This is the legitimate single-entity mode use case. The fix preserves this by scoping the trigger to non-interactive sessions. The `-p` flag makes the session non-interactive, so the trigger still fires correctly.

**Edge case: Codex `exec` mode** — Same as `-p` for Claude. `codex exec` is non-interactive. The updated Codex runtime wording explicitly references `codex exec`.

**Edge case: Interactive session where only one entity is dispatchable** — This is NOT single-entity mode. The FO should use normal team dispatch even if only one entity happens to be ready. The fix correctly distinguishes "one entity ready" from "non-interactive single-entity mode."

**Edge case: User says "only work on entity X" in interactive session** — Still not single-entity mode. The user is scoping work, not requesting a mode change. The FO can scope dispatch to that entity while maintaining team support and gate prompting. The existing dispatch mechanism already handles this via `status --next` filtering.

**Edge case: Codex interactive mode** — Codex has an interactive mode too. The fix uses "non-interactive (e.g., `codex exec`)" rather than just "Codex" to handle this correctly.

**Status: DONE**

### Summary

The root cause is a single sentence in the shared core (`references/first-officer-shared-core.md`, line 39) that triggers single-entity mode when the user "names a specific entity" — a condition that is true in every interactive dispatch. The fix adds a non-interactive session requirement to the trigger, affecting two files. The Claude runtime needs no changes. Four acceptance criteria are defined: two text-level checks and two E2E tests (interactive PTY test and `-p` mode test).

## Stage Report: implementation

### 1. Fix single-entity mode trigger in references/first-officer-shared-core.md

**DONE.** Replaced line 39 trigger from "When the user names a specific entity and asks to process it through the workflow, switch into single-entity mode." to: "Single-entity mode activates when the session is non-interactive (e.g., invoked via `claude -p` or `codex exec`) and the prompt names a specific entity to process through the workflow. Do not enter single-entity mode in interactive sessions — naming an entity in conversation is normal dispatch, not a mode switch."

### 2. Fix Codex runtime trigger in references/codex-first-officer-runtime.md

**DONE.** Replaced line 16 trigger from "If the user names a specific entity and asks to process it through the workflow, apply the shared single-entity mode rules." to: "If the session is non-interactive (e.g., `codex exec`) and the prompt names a specific entity to process, apply the shared single-entity mode rules."

### 3. Write PTY-based E2E test at tests/test_single_entity_mode.py

**DONE.** Created `tests/test_single_entity_mode.py` using `InteractiveSession` from `scripts/test_lib_interactive.py`. The test:
- Sets up a temp git project with the spike-no-gate fixture and agent files
- Starts an interactive claude session with `--plugin-dir` pointing to the repo
- Boots the FO via `/spacedock:first-officer`
- Sends "Work on test-entity through the workflow" to trigger the bug scenario
- Asserts that "single-entity mode" does NOT appear in output (AC3a)
- Asserts that team creation or dispatch evidence IS present (AC3b)
- Requires `--live` flag to run (~$1-2 with haiku)

### 4. Verify -p mode still enters single-entity mode correctly

**DONE.** The existing `tests/test_single_entity_team_skip.py` already exercises this path — it runs `claude -p "Process test-entity through the workflow..."` and verifies TeamCreate is absent and Agent calls have no `team_name`. The `-p` flag makes the session non-interactive, so the updated trigger condition still fires correctly. No additional test needed.

### 5. All changes committed on branch

**DONE.** Two commits on `spacedock-ensign/single-entity-mode-bug`:
- `50de7d0` — fix: scope single-entity mode trigger to non-interactive sessions only (2 files)
- `4fdedc3` — test: add PTY-based regression test for single-entity mode trigger (1 file)
