---
id: 072
title: First-officer cwd drift causes agents to spawn in wrong worktree
status: backlog
source: 033 ideation incident
started:
completed:
verdict:
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
