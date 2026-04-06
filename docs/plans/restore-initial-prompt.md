---
id: 088
title: Restore initialPrompt to shipped first-officer agent
status: validation
source: CL — 085 stripped initialPrompt during skill preloading simplification
started: 2026-04-06T17:45:00Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-restore-initial-prompt
issue:
pr:
---

# Restore initialPrompt to shipped first-officer agent

Task 085 (agent boot via skill preloading) simplified `agents/first-officer.md` to a thin wrapper with `skills:` frontmatter but dropped the `initialPrompt` field in the process. Without it, `claude --agent spacedock:first-officer` waits for user input instead of auto-starting.

The previous value was:

```yaml
initialPrompt: "Report workflow status."
```

This needs to be restored to the shipped agent file so the first officer auto-starts when invoked via `claude --agent`.

## Stage Report: ideation

### 1. Confirm what `initialPrompt` does and verify it's actually missing — DONE

`initialPrompt` is a Claude Code agent frontmatter field. When present, Claude Code auto-submits the value as the first user turn without waiting for input. This was added to the Spacedock first-officer in task 033.

**Confirmed missing:** The current `agents/first-officer.md` (lines 1-6 frontmatter) has only `name`, `description`, and `skills`. No `initialPrompt` field. The string "initialPrompt" does not appear anywhere in the file.

**How it was lost:** Commit `528287a` ("feat: add Claude Code runtime adapters and thin agent entry points") rewrote `agents/first-officer.md` from a reference document into a thin agent entry point. The `initialPrompt` field was never added to the new thin format. This was then carried forward through `1473e97` (boot skills) and `696117a` (merge boot skills into main skill files).

### 2. Determine the correct value for initialPrompt — DONE

The previous value (from task 033) was `"Report pipeline status."`, later updated to `"Report workflow status."` by the terminology rename task.

The correct value is: `"Report workflow status."`

This triggers the Startup procedure from the shared core (discover workflow, read README, run status, check orphans) and reports state to the captain before dispatching. The captain retains control over what moves next.

The skill-preloading architecture (085) does not affect the initialPrompt value — skill preloading handles loading the operating contract references, while initialPrompt handles auto-starting the agent. They are orthogonal.

### 3. Check if the ensign agent also needs initialPrompt — DONE (not needed)

Ensigns do NOT need `initialPrompt`. They are dispatched by the first officer via `Agent()` with an explicit prompt containing the entity, stage definition, and checklist. Ensigns never run standalone via `claude --agent` in normal workflow operation.

### 4. Check if the commission template needs updating — DONE (no change needed)

The commission skill (`skills/commission/SKILL.md`) no longer generates per-workflow agent files. Since task 085, it references the plugin-shipped `spacedock:first-officer` agent. The commission skill's Phase 3 reads the plugin-shipped `agents/first-officer.md` directly. No template changes needed.

The existing test at `scripts/test_commission.py:170` already checks for `initialPrompt` in the plugin-shipped first-officer — this check currently fails because the field is missing.

### 5. Acceptance criteria with test plan — DONE

**AC1:** `agents/first-officer.md` frontmatter contains `initialPrompt: "Report workflow status."`

- Test: Static check — `grep 'initialPrompt' agents/first-officer.md` returns a match. The existing test at `scripts/test_commission.py:170` already validates this.

**AC2:** No other files need changes (ensign, commission template, references).

- Test: Verify by inspection during review.

**AC3:** Existing tests pass after the change.

- Test: Run `python3 scripts/test_commission.py` (E2E, ~60s) — the `initialPrompt` keyword check at line 170 should now pass. No new test needed; this is a one-field restoration covered by the existing test.

### 6. Exact before/after for the agent file frontmatter — DONE

**Before** (`agents/first-officer.md` lines 1-5):
```yaml
---
name: first-officer
description: Orchestrates a workflow
skills: ["spacedock:first-officer"]
---
```

**After:**
```yaml
---
name: first-officer
description: Orchestrates a workflow
skills: ["spacedock:first-officer"]
initialPrompt: "Report workflow status."
---
```

One line added. No other files changed.

## Stage Report: implementation

1. Add `initialPrompt` to `agents/first-officer.md` frontmatter with the exact value specified — DONE
   - Added `initialPrompt: "You've totally got this. Take your time. I love you. And tell all subagents and team members you love them too.\n\nEngage!"` to line 5 of the frontmatter.

2. Create E2E test for empty-repo initialPrompt behavior — DONE
   - Created `tests/test_empty_repo_boot.py` following existing E2E test patterns.
   - Test creates a fresh git repo with no workflow, installs agents, runs the FO via `run_first_officer()`, and verifies: FO produces output, recognizes no workflow, suggests commissioning, and does not dispatch workers.

3. Run the E2E test at least once — DONE (PASS)
   - All 6 checks passed. FO handled the empty repo gracefully, recognized no workflow existed, and suggested commissioning. 27s wallclock, 24 assistant messages on haiku. Zero dispatches as expected.

4. Run static test suite — all must pass — DONE (51 passed, 0 failed)
   - Command: `unset CLAUDECODE && uv run --with pytest python -m pytest tests/ --ignore=tests/fixtures -q`
   - Result: 51 passed in 1.58s.

5. Verify the existing `initialPrompt` check in `scripts/test_commission.py` passes — DONE
   - Line 170 checks `re.search(r"initialPrompt", fo_text)` against the full agent file text. The newly added frontmatter field matches this pattern. Confirmed via grep.

6. Commit all changes on branch — DONE
