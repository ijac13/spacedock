---
title: Fix test harness path and false positive issues
status: implementation
source: testflight-005
started: 2026-03-23T20:20:00Z
completed:
verdict:
score:
worktree: .worktrees/ensign-rename-and-test-fixes
---

The test harness (`v0/test-commission.sh`) has three issues discovered when running against a branch with recent changes:

1. **first-officer.md location**: The test expects it at `v0-test-1/.claude/agents/first-officer.md` but the commission may place it at the project root's `.claude/agents/`. The path assumption needs to match actual commission behavior.

2. **`{slug}` false positive**: The README's File Naming section documents the `{slug}` pattern as intentional user-facing documentation. The test flags it as a leaked template variable. The check needs to exclude known documentation contexts.

3. **Scoring section check**: The test asserts a 'Scoring' section exists in the generated README. This may be a generation variance or the check may be too strict. Needs investigation to determine correct behavior and fix accordingly.

## Implementation

Fixed all three issues in `v0/test-commission.sh` and updated `v0/test-harness.md` to match:

1. **first-officer.md location**: Changed path from `$PIPELINE_DIR/.claude/agents/first-officer.md` to `$TEST_DIR/.claude/agents/first-officer.md`. The commission writes first-officer to the project root (which is `$TEST_DIR` in the test), not inside the pipeline directory. Updated both the file existence check and the `$FO` variable used for completeness/guardrail checks. Test harness doc paths updated similarly.

2. **{slug} false positive**: Added `| grep -v 'slug'` to the leaked template variable check pipeline. The README File Naming section intentionally documents `{slug}.md` as the naming pattern — not a leaked template variable.

3. **Scoring section**: Removed "Scoring" from the required README sections list. The SKILL.md template explicitly says to omit the Scoring section unless the captain requests a multi-dimension rubric, so it won't appear in default generation. Updated test harness doc to note Scoring is conditional.

## Validation

Test results before final fix: 41/42 passed, 1 failed. The single failure was the `Agent()` regex check in [First-Officer Completeness] — the pattern `Agent\(\)` looked for literal `Agent()` but the generated first-officer template contains `Agent(` with parameters (e.g., `Agent(\n    subagent_type=...`).

Fix: changed the KEYWORD pattern from `Agent\(\)` to `Agent\(` so it matches `Agent(` regardless of what follows the opening parenthesis. With this fix, all 42 checks pass.
