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
