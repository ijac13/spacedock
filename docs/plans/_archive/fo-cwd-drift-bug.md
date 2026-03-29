---
id: 072
title: First-officer cwd drift causes agents to spawn in wrong worktree
status: done
source: 033 ideation incident
started: 2026-03-28T00:00:00Z
completed: 2026-03-29T16:39:00Z
verdict: PASSED
score: 0.70
worktree:
---

When the first officer uses `cd` into a worktree directory (e.g., to check a branch), the Bash cwd persists. Subsequent Agent() calls inherit that cwd, causing non-worktree-stage agents (like ideation ensigns) to resolve relative paths against the wrong worktree instead of main.

## Incident

During 033 ideation, the FO ran `cd .worktrees/ensign-071-pr-merge-detection && git log ...` to check a rebase. The cwd stuck. When the 033 ideation ensign was spawned, it inherited cwd in the 071 worktree. The ensign read and wrote `docs/plans/graceful-degradation-without-teams.md` under the 071 worktree path instead of main. The content had to be manually copied over and the 071 branch reverted.

## Root cause

The FO template doesn't warn about cwd drift affecting Agent spawning. The Bash tool docs say "avoid usage of cd" but that's easy to violate when checking worktree branch state.

## Possible fixes

1. FO template: add explicit guidance to never `cd` into worktrees — always use absolute paths or run commands with `git -C {path}`
2. FO template: after any worktree-related Bash command, explicitly `cd` back to project root
3. Ensign template or dispatch prompt: always include an explicit absolute path for the entity file, not a relative one (this is already done for worktree stages but not for non-worktree stages like ideation)

## Ideation Analysis

### Root cause

The FO template has no guidance about cwd management. Specifically:

1. **No prohibition on `cd`** — The template never says "do not use `cd`" or "use absolute paths for Bash commands." When the FO needs to inspect a worktree (e.g., checking `git log` on a branch, reading an entity file in a worktree for orphan detection), it naturally reaches for `cd .worktrees/...` because that's the simplest way to run multiple commands in a directory.

2. **Bash cwd persists across tool calls** — Once the FO runs `cd .worktrees/ensign-071-...`, every subsequent Bash call starts in that directory. The Claude Code system prompt says "avoid usage of cd" but this is a soft suggestion easily overridden by task pressure.

3. **Agent() inherits Bash cwd** — When the FO dispatches an ensign via `Agent()`, the spawned agent's initial Bash cwd is whatever the parent's cwd was at dispatch time. If the FO drifted into a worktree, the ensign starts there.

4. **`{entity_file_path}` is under-specified** — The dispatch template uses `{entity_file_path}` but never says it must be absolute. The FO template at line 41 says "Read the entity file" but doesn't specify how to construct the path. For non-worktree stages, the FO likely constructs `{workflow_dir}/{slug}.md` which is relative to project root — but if cwd drifted, the ensign's `Read()` call resolves it against the wrong directory.

Evidence from templates:
- `first-officer.md` line 54: dispatch prompt uses `{entity_file_path}` — no guidance on whether it should be absolute
- `first-officer.md` lines 27-31: orphan detection requires reading entity files in worktrees and running `git log main..{branch}` — both are natural `cd` triggers
- `first-officer.md` line 46: `git worktree add .worktrees/...` uses relative paths, reinforcing the pattern
- `ensign.md` line 22: "Read the entity file at the path given in your assignment" — the ensign trusts whatever path the FO provides

### Proposed fix

A single addition to the FO template, in a new section between "Startup" and "Dispatch" (or at the top of "Dispatch"). The fix has two parts:

**Part 1: Add a "Working Directory" rule section after Startup**

Add this after the Startup section (after the `status --next` step, before `## Dispatch`):

```markdown
## Working Directory

Your Bash working directory MUST remain at the project root at all times. Never use `cd` to enter worktrees or subdirectories — cwd drift causes dispatched agents to spawn in the wrong directory. Instead:

- Use `git -C {path}` for git commands in other directories
- Use absolute paths with all Bash commands (derive from `$project_root`)
- Use the `Read` tool (which takes absolute paths) instead of `cat` for reading files
```

**Part 2: Clarify `{entity_file_path}` must be absolute in the dispatch template**

In the dispatch section step 7, change the dispatch prompt comment to make it explicit. Add a note above the `Agent()` call:

```
All paths in the dispatch prompt MUST be absolute (rooted at `$project_root`).
```

### Why not the other fixes?

- **Fix 2 (cd back after)** — fragile. If the FO forgets to `cd` back even once, the same bug recurs. Prevention is better than recovery.
- **Fix 3 (absolute path in ensign template)** — defense-in-depth, worth doing as a secondary measure, but the ensign can only work with what the FO gives it. The root cause is FO behavior.

### Edge cases

1. **Orphan detection reads worktree files** — The FO needs to read entity files inside worktrees during startup (line 31). With the fix, the FO uses `Read("{worktree_path}/{slug}.md")` with an absolute path instead of `cd`-ing into the worktree. This works because `Read` takes absolute paths.

2. **`git log main..{branch}`** — Doesn't need cwd in the worktree at all. This works from any directory because it references branch names, not paths.

3. **`git worktree add`** — Already uses relative paths from project root (`.worktrees/...`). No change needed as long as cwd stays at project root.

4. **Merge operations** — `git merge --no-commit {branch}` also works from any directory. No cwd dependency.

5. **Multiple dispatches in sequence** — If the FO dispatches several agents in a row, the fix ensures cwd never drifts between dispatches. Without the fix, the first dispatch into a worktree stage (which involves `git worktree add`) could potentially drift cwd for the second dispatch.

### Acceptance criteria

1. The FO template contains an explicit prohibition on `cd` into worktrees or subdirectories, with alternative patterns (`git -C`, absolute paths, `Read` tool)
2. The dispatch template explicitly requires `{entity_file_path}` to be an absolute path
3. No behavioral changes to the ensign template are required (ensign already trusts the path it's given)
4. The fix is template-wording only — no code changes, no new tooling

## Stage Report: ideation

- [x] Root cause confirmed with evidence from templates
  FO template has no cwd guidance; orphan detection and worktree ops naturally trigger `cd`; Agent() inherits drifted cwd; entity_file_path is unspecified as absolute vs relative
- [x] Proposed fix: specific wording changes to the FO template
  New "Working Directory" section with `cd` prohibition + alternative patterns; clarify absolute path requirement in dispatch template
- [x] Edge cases considered
  Orphan detection, git log, worktree add, merge ops, sequential dispatches — all work without `cd`
- [x] Acceptance criteria defined
  Four criteria: cd prohibition in template, absolute path requirement in dispatch, no ensign changes needed, template-only fix

### Summary

The root cause is that the FO template has no guidance about cwd management, and several FO operations (orphan detection, worktree inspection) naturally encourage `cd` into worktrees. The proposed fix adds a "Working Directory" section to the FO template that prohibits `cd` and prescribes `git -C`, absolute paths, and the `Read` tool as alternatives. A secondary clarification makes `{entity_file_path}` explicitly absolute in the dispatch prompt. The fix is minimal — two additions to the FO template, no code changes.

## Stage Report: implementation

- [x] "Working Directory" section added to FO template after Startup
  Added between Startup step 7 and Dispatch section at templates/first-officer.md:37-43
- [x] Absolute path requirement added to Dispatch step 7
  Appended "All paths in the dispatch prompt MUST be absolute (rooted at `$project_root`)." to step 7 at templates/first-officer.md:55
- [x] Commission test harness passes (no regression)
  65 passed, 0 failed (out of 65 checks) — RESULT: PASS
- [x] All changes committed to worktree branch
  Commit 6d2454c on ensign/072-fo-cwd-drift

### Summary

Added two targeted wording changes to `templates/first-officer.md`: a new "Working Directory" section after Startup that prohibits `cd` and prescribes `git -C`, absolute paths, and the `Read` tool as alternatives; and an absolute-path requirement appended to Dispatch step 7. Commission test harness passes with all 65 checks green.

## Stage Report: validation

- [x] Each acceptance criterion verified with evidence (line numbers, text matches)
  AC1: "Working Directory" section at first-officer.md:37-43 prohibits `cd`, prescribes `git -C`, absolute paths, `Read` tool. AC2: Absolute path requirement at first-officer.md:55 in Dispatch step 7. AC3: `git diff main -- templates/ensign.md` produces no output — unchanged. AC4: Commit 6d2454c touches only `templates/first-officer.md` — no code files.
- [x] Commission test harness passes (no regression)
  65 passed, 0 failed (out of 65 checks) — RESULT: PASS
- [x] Ensign template unchanged (verify no diff)
  `git diff 6d2454c main -- templates/ensign.md` produces empty output — identical to main
- [x] Recommendation: PASSED
  All four acceptance criteria met with clear evidence. Fix is minimal, targeted, and template-only.

### Summary

Validated the implementation against all four acceptance criteria. The Working Directory section (lines 37-43) contains the `cd` prohibition with three alternative patterns. The dispatch absolute-path requirement is at line 55. Ensign template is unchanged (zero diff vs main). The fix commit touches only `templates/first-officer.md` with no code changes. Commission test harness passes all 65 checks. Recommendation: PASSED.
