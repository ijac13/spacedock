---
id: 111
title: Status script reports worktree branches as missing when they exist
status: implementation
source: FO boot anomaly — 2026-04-09
started: 2026-04-09T22:00:38Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-status-script-branch-detection
issue:
pr:
---

The `status --boot` ORPHANS section reports `BRANCH_EXISTS: no` for entities whose branches actually exist both as local branches and as git worktrees.

Observed during boot:
- 088 restore-initial-prompt: `BRANCH_EXISTS: no`, but `git branch --list` shows `spacedock-ensign/restore-initial-prompt` and `git worktree list` confirms the worktree is linked to that branch.
- 058 terminology-experiment: `BRANCH_EXISTS: no`, but `git branch --list` shows `ensign/terminology-exp` and `git worktree list` confirms it.

The branch detection logic in `skills/commission/bin/status` likely checks for the branch in a way that misses worktree-linked branches (e.g., checking `.git/refs/heads/` directly instead of using `git branch --list`, or a path-construction mismatch between the worktree field and the actual branch name).

## Stage Report

### 1. Root cause — DONE

The bug is in `scan_orphans()` at `skills/commission/bin/status:336`:

```python
branch_name = os.path.basename(wt) if '/' in wt else wt
branch_exists = 'yes' if branch_name in worktree_branches else 'no'
```

The function correctly parses `git worktree list --porcelain` output to collect branch names (lines 314-325), building a set like `{'main', 'ensign/terminology-exp', 'spacedock-ensign/restore-initial-prompt', ...}`.

However, the lookup uses `os.path.basename()` on the entity's worktree directory path to guess the branch name. Since worktree directories encode branch `/` separators as `-`, the basename never matches:

| Entity | Worktree field | `os.path.basename()` | Actual branch |
|--------|---------------|----------------------|---------------|
| 088 | `.worktrees/spacedock-ensign-restore-initial-prompt` | `spacedock-ensign-restore-initial-prompt` | `spacedock-ensign/restore-initial-prompt` |
| 058 | `.worktrees/ensign-terminology-exp` | `ensign-terminology-exp` | `ensign/terminology-exp` |

The `-` to `/` mapping is ambiguous (e.g., `ensign-terminology-exp` could be `ensign/terminology-exp` or `ensign-terminology/exp`), so guessing is not viable.

### 2. Problem statement with evidence — DONE

The `scan_orphans()` function in the status script reports `BRANCH_EXISTS: no` for entities whose git worktree branches exist. This happens because it derives the branch name from the worktree directory name using `os.path.basename()`, but worktree directories replace `/` with `-` in their names, so the derived name never matches branches containing `/` (which is standard for namespaced branches like `ensign/feature-name`).

Evidence from live system:
- `git worktree list --porcelain` shows `.worktrees/ensign-terminology-exp` is on branch `refs/heads/ensign/terminology-exp`
- `scan_orphans` looks up `ensign-terminology-exp` (no match) instead of `ensign/terminology-exp`

### 3. Proposed fix — DONE

Change `scan_orphans()` to build a **path-to-branch mapping** from the porcelain output instead of a branch-name set. The porcelain format groups `worktree <path>` and `branch <ref>` lines per entry. Then look up the entity's worktree by its resolved absolute path rather than guessing the branch name from the directory name.

Specifically:
1. Parse `git worktree list --porcelain` into a dict mapping `worktree_path -> branch_short_name`
2. For each entity, resolve `os.path.join(git_root, wt)` and look it up in the dict
3. If found, `branch_exists = 'yes'`; if not found, `branch_exists = 'no'`

This is ~10 lines changed in a single function, no other code paths affected.

### 4. Acceptance criteria with test plan — DONE

**AC1**: `scan_orphans()` correctly reports `BRANCH_EXISTS: yes` for entities whose worktree directories are linked to git branches with `/` in the name.
- *Test*: Unit test that mocks `subprocess.run` to return porcelain output containing a branch like `refs/heads/ensign/feature-name` linked to a worktree path, and an entity with `worktree: .worktrees/ensign-feature-name`. Assert `branch_exists == 'yes'`.

**AC2**: `scan_orphans()` correctly reports `BRANCH_EXISTS: no` for entities whose worktree directories do not correspond to any git worktree.
- *Test*: Unit test with porcelain output that does NOT contain the entity's worktree path. Assert `branch_exists == 'no'`.

**AC3**: `scan_orphans()` still correctly reports `BRANCH_EXISTS: yes` for branches without `/` in the name (no regression).
- *Test*: Unit test with a simple branch name like `remove-codex-dispatcher` (no namespace separator). Assert `branch_exists == 'yes'`.

**AC4**: `DIR_EXISTS` behavior is unchanged.
- *Test*: Covered by verifying the function still checks `os.path.isdir(dir_path)` — no changes to that code path.

**Estimated complexity**: Small. Single-function change, ~10 lines modified. No E2E test needed — the fix is a data-structure change in a pure function that can be fully validated with unit tests.

### 5. Scope assessment — DONE

This is a simple, self-contained fix. Only `scan_orphans()` in `skills/commission/bin/status` needs to change. No other code paths reference this function's internals. The fix changes how the function indexes and looks up branch data — from a set-based lookup by guessed name to a dict-based lookup by resolved path. No changes needed to callers, output format, or other functions.
