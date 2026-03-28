---
id: 066
title: Fix workflow discovery — FO greps home directory instead of project root
status: ideation
source: 058 terminology experiment validation
started:
completed:
verdict:
score: 0.85
worktree:
issue:
pr:
---

The first-officer template's startup step 1 tells the FO to discover workflow directories by running `grep -rl '^commissioned-by: spacedock@' --include='README.md' .` from the project root. In practice, agents expand `.` to absolute paths or search from `~` instead of the project root, finding workflow READMEs outside the current project.

## Problem

Discovered during terminology experiment (058) validation. All 28 benchmark runs across 4 variants searched `/Users/clkao` (home directory) instead of `.` (project root). When multiple `commissioned-by:` READMEs exist on the machine, the FO may latch onto the wrong project's workflow — in this case, the real spacedock project instead of the test fixture.

Recovery is inconsistent: some runs notice the pwd mismatch and re-search locally, others proceed with the wrong project. This inconsistency caused kitchen variant runs to score lower on pipeline completion and role adherence — not because of terminology differences, but because of how each run handled the discovery failure.

## Impact

- **Test harness reliability**: Benchmark results are contaminated by discovery failures. The 058 experiment cannot produce clean results until this is fixed.
- **Production workflows**: Any machine with multiple spacedock-commissioned workflows risks cross-contamination.
- **Scoring validity**: Protocol compliance and role adherence scores are conflated with discovery success/failure.

## Scope

Fix the FO template's workflow discovery to be robust against path expansion. The fix should ensure the FO searches only within the project root, not the home directory or broader filesystem.

## Root Cause Analysis

The discovery instruction says:

> Use: `grep -rl '^commissioned-by: spacedock@' --include='README.md' .` from the project root.

The problem is the phrase "from the project root" combined with `.` as the search path. Claude Code agents have their working directory set to `~` (the user's home directory) by default, not the project root. When the FO reads "from the project root" it interprets that as a contextual hint but still runs `grep` with `.` as the literal argument, which expands to the cwd — which is `~`. The instruction never tells the FO to `cd` to the project root first or to substitute an absolute path for `.`.

This is **not a grep bug** — it's an ambiguity in the template instruction. The command `.` is relative to cwd, and the FO's cwd is not the project root.

Evidence from 058: all 28 runs across 4 variants searched `/Users/clkao` (the home directory). The FO faithfully ran the grep command as written — `.` expanded to `~` because that's where the agent's shell was.

## Proposed Fix

Replace the ambiguous "grep from project root" with an explicit `git rev-parse --show-toplevel` anchor. The template already uses `git rev-parse --show-toplevel` in step 3 (team creation), so the FO already knows the pattern.

### Template change (all variants)

**Before (step 1):**
```
1. **Discover workflow directory** — Search the project for README.md files
whose YAML frontmatter contains a `commissioned-by` field starting with
`spacedock@`. Use: `grep -rl '^commissioned-by: spacedock@' --include='README.md' .`
from the project root. If exactly one is found, use its directory as
`{workflow_dir}`. If multiple are found, list them and ask the captain which
to manage. If none are found, report "No Spacedock workflow found in this project."
```

**After (step 1):**
```
1. **Discover workflow directory** — Run `project_root="$(git rev-parse --show-toplevel)"`,
then search for README.md files whose YAML frontmatter contains a `commissioned-by`
field starting with `spacedock@`. Use: `grep -rl '^commissioned-by: spacedock@'
--include='README.md' "$project_root"`. If exactly one is found, use its directory
as `{workflow_dir}`. If multiple are found, list them and ask the captain which to
manage. If none are found, report "No Spacedock workflow found in this project."
```

Key changes:
1. Explicitly resolve `project_root` via `git rev-parse --show-toplevel` as the first action.
2. Replace `.` with `"$project_root"` in the grep command — an absolute path that doesn't depend on cwd.
3. Remove the ambiguous phrase "from the project root" since the path is now explicit.

This fix applies to all four variant templates (`templates/first-officer.md`, `templates-business/orchestrator.md`, `templates-functional/dispatcher.md`, `templates-kitchen/sous-chef.md`).

Additionally, the generated FO for any already-commissioned project (e.g., `/Users/clkao/git/spacedock/.claude/agents/first-officer.md`) will need a refit to pick up the change. This is the expected pattern — `spacedock refit` exists to propagate template updates.

## Test Harness Impact

### Benchmark harness (`scripts/terminology-benchmark.sh`)

The benchmark creates temp directories, runs `git init`, copies fixture files, and then runs the FO via `claude -p --agent`. The fix **works correctly** for this setup:

- `git rev-parse --show-toplevel` returns the temp project's git root (e.g., `/tmp/xxx/test-project`), not the real spacedock repo.
- The fixture's `README.md` with `commissioned-by: spacedock@` is inside that temp git root.
- The FO will grep within the temp git root and find exactly the fixture workflow.

This directly solves the 058 contamination problem: the FO can no longer escape the test project's git boundary.

### Gate guardrail test (`tests/test-gate-guardrail.sh`)

Same structure — temp git repo with fixture copied in. `git rev-parse --show-toplevel` returns the temp project path. Works correctly.

### Worktrees

`git rev-parse --show-toplevel` returns the **worktree path**, not the main repo path. Verified:
- Main repo: `/Users/clkao/git/spacedock`
- Worktree: `/Users/clkao/git/spacedock/.worktrees/ensign-terminology-exp`

This is correct behavior — a worktree-based dispatch should search within its own worktree root.

## Edge Cases

1. **Worktrees** — `git rev-parse --show-toplevel` returns the worktree-specific root. If the FO runs in a worktree, it finds the workflow within that worktree. Correct behavior.

2. **Multiple workflows in one project** — No change in behavior. `grep` still finds all matching READMEs; the FO still asks the captain which to manage. The scope is just properly bounded to the project.

3. **No workflows found** — No change in behavior. The "none found" path remains the same.

4. **Not a git repo** — `git rev-parse --show-toplevel` fails with a non-zero exit. The FO should handle this gracefully. The template could add a fallback: "If not in a git repo, use the current working directory." However, spacedock workflows are always in git repos (commission requires git), so this is a defensive edge case, not a practical one.

5. **Nested git repos / submodules** — `git rev-parse --show-toplevel` returns the innermost repo root. If a workflow is in a submodule, the FO finds it within the submodule. This is correct — the submodule is the project context.

## Acceptance Criteria

1. The FO template step 1 uses `git rev-parse --show-toplevel` to resolve an absolute project root path before running grep.
2. The grep command uses the resolved absolute path instead of `.`.
3. All four variant templates are updated with the same fix (nautical, business, functional, kitchen).
4. The existing gate guardrail test (`tests/test-gate-guardrail.sh`) passes with the updated template.
5. A benchmark run no longer finds workflows outside the test project's git root.

## Stage Report: ideation

- [x] Root cause analysis — why agents expand `.` to home directory
  Agent cwd defaults to `~`; the template says "from the project root" but `.` resolves to cwd, not the project root
- [x] Proposed fix with specific template wording changes
  Replace `.` with `"$project_root"` resolved via `git rev-parse --show-toplevel`; exact before/after wording provided above
- [x] Test harness impact analysis — will the fix work for benchmark fixture discovery?
  Yes — `git rev-parse --show-toplevel` returns the temp git root in benchmark/test harness setups, properly scoping discovery
- [x] Edge cases considered (worktrees, multiple workflows, no workflows)
  Worktrees return worktree-specific root (verified); multiple workflows still triggers captain prompt; no-workflow path unchanged; non-git-repo edge case noted
- [x] Acceptance criteria written
  Five concrete criteria covering template change, all variants, test pass, and benchmark isolation

### Summary

The root cause is that the FO template tells the agent to grep `.` "from the project root" but agents run with cwd set to `~`, so `.` expands to the home directory. The fix replaces `.` with an absolute path from `git rev-parse --show-toplevel`, which the template already uses elsewhere. This works correctly for benchmark fixtures, worktrees, and production workflows. All four variant templates need the same one-line change.
