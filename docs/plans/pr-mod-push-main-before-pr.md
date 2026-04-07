---
id: 090
title: PR merge mod should push main before creating PRs
status: validation
source: CL — observed PR conflicts from unpushed main state commits
started: 2026-04-06T00:00:00Z
completed:
verdict:
score: 0.65
worktree: .worktrees/spacedock-ensign-pr-mod-push-main-before-pr
issue:
pr:
---

# PR merge mod should push main before creating PRs

The FO commits entity state changes (status, worktree, pr fields) to local main throughout a session. The `pr-merge` mod's merge hook pushes the worktree branch and creates a PR, but doesn't ensure origin/main is up to date first. This causes PR conflicts when the branch was created from an earlier main and both sides modified entity files.

Observed in PRs #35 and #36 — both had conflicts in `docs/plans/` entity files because origin/main was behind local main's state commits.

The fix: the merge hook should `git push origin main` before pushing the branch. This ensures origin/main has all the frontmatter state changes, so the PR branch's rebase/merge is clean.

## Problem Statement

The first officer commits entity state changes (status, worktree, pr, started fields) to local main throughout a session. These are small frontmatter-only commits that track dispatch boundaries and stage transitions. When the `pr-merge` mod's merge hook fires, it pushes the worktree branch and creates a PR against `main` on GitHub. But at that point, `origin/main` may be several commits behind `local main` — it still reflects the state from when the session started (or the last explicit push).

This creates PR merge conflicts: the worktree branch was created from local main at some point during the session, and both the branch and `origin/main` have diverging versions of the same entity files. The branch has the entity's implementation work, while `origin/main` is missing the frontmatter state commits that local main accumulated. GitHub sees conflicting changes to the same files and marks the PR as having conflicts.

Observed concretely in PRs #35 and #36, where both had conflicts in `docs/plans/` entity files.

## Analysis of Current Merge Hook Flow

The `pr-merge` mod's `## Hook: merge` section (in `mods/pr-merge.md`) currently does:

1. Present a draft PR summary to the captain and wait for explicit approval
2. **On approval:** `git push origin {branch}` — push the worktree branch
3. `gh pr create --base main --head {branch} ...` — create the PR
4. Set the entity's `pr` field and report to captain

The gap: between steps 1 and 2, there is no `git push origin main`. The FO has been committing state changes to local main, but those commits never reach `origin/main` until something else pushes them. By the time the PR is created, `origin/main` is stale and the PR has conflicts.

## Proposed Approach

Add a single line to the `## Hook: merge` section's "On approval" block, before pushing the branch.

### Before (current wording in `mods/pr-merge.md`, line 38):

```
**On approval:** Push the worktree branch: `git push origin {branch}`. If the push fails (no remote, auth error), report to the captain and fall back to local merge.
```

### After (proposed wording):

```
**On approval:** First, push main to ensure the remote is up to date with local state commits: `git push origin main`. Then push the worktree branch: `git push origin {branch}`. If either push fails (no remote, auth error), report to the captain and fall back to local merge.
```

This is a one-line behavioral change to the mod template. The same change applies to both:
- The canonical mod at `mods/pr-merge.md` (source of truth for new installs and refits)
- The installed copy at `docs/plans/_mods/pr-merge.md` (this project's live copy)

The version field should be bumped from `0.9.0` to `0.9.1` in the canonical mod to signal the change.

## Acceptance Criteria

1. **The canonical mod (`mods/pr-merge.md`) instructs the FO to push main before pushing the branch.** Test: static text check — the `## Hook: merge` section contains `git push origin main` before `git push origin {branch}`.

2. **The installed mod (`docs/plans/_mods/pr-merge.md`) matches the canonical mod.** Test: diff the two files; they should be identical.

3. **The version field is bumped to `0.9.1`.** Test: check the `version` frontmatter in the canonical mod.

4. **No other behavioral changes.** Test: diff the before/after of the canonical mod; only the "On approval" paragraph and version field should differ.

5. **E2E test passes: main is pushed before the branch during merge hook execution.** Test: `tests/test_push_main_before_pr.py` — uses a bare repo remote and git wrapper to verify push ordering. The git push log must show `git push origin main` before `git push origin {branch}`.

## Edge Cases

1. **What if `git push origin main` fails?** The existing fallback already covers this: "If the push fails (no remote, auth error), report to the captain and fall back to local merge." The proposed wording extends this to cover either push failing. If main can't be pushed, the branch push would also likely fail (same remote, same auth), so falling back to local merge is correct.

2. **Force-push safety.** The instruction is a plain `git push origin main`, not `--force`. If origin/main has commits that local main doesn't (e.g., another collaborator pushed), the push will fail with a non-fast-forward error. This is the safe default — the FO should report the failure to the captain rather than force-pushing. No change needed here.

3. **Repos without a remote.** The existing mod already handles this: "If the push fails (no remote, auth error), report to the captain and fall back to local merge." A repo without a remote configured for `origin` will fail the push, triggering the existing fallback. No special handling needed.

4. **Main branch has no unpushed commits.** `git push origin main` when already up-to-date is a no-op ("Everything up-to-date"). No harm done.

5. **Concurrent sessions pushing main.** If two FO sessions both push main, the second push will either fast-forward cleanly (if the first session's commits are ancestors) or fail with non-fast-forward. The fail case triggers the existing fallback. This is acceptable — concurrent PR creation from multiple sessions is an edge case that doesn't need special handling beyond the existing error reporting.

## Test Plan

### Static validation

- Verify the canonical mod's `## Hook: merge` section contains `git push origin main` before `git push origin {branch}` in the "On approval" block.
- Verify the installed mod matches the canonical mod.
- Verify the version bump to `0.9.1`.
- Verify no other sections of the mod changed.

### E2E test: `tests/test_push_main_before_pr.py`

Verifies that the FO pushes main before pushing the branch during the pr-merge mod's merge hook. Uses a local bare repo as the "remote" so no real GitHub remote is needed. The `gh pr create` step is handled by stubbing `gh` with a script that records invocations and exits successfully.

**Fixture:** `tests/fixtures/push-main-pipeline/`

A minimal no-gate workflow (like `merge-hook-pipeline`) with the `pr-merge` mod installed in `_mods/`. The entity starts at `backlog`, flows through `work` (worktree stage), and reaches terminal `done`. The pr-merge mod's merge hook fires at the terminal boundary.

Fixture files:
- `README.md` — workflow definition: backlog -> work (worktree) -> done (terminal), no gates
- `_mods/pr-merge.md` — copy of the updated canonical mod (with `git push origin main`)
- `push-main-entity.md` — entity in backlog, high score so it gets dispatched
- `status` — status script (copied from existing fixtures)

**Test phases:**

1. **Setup bare remote and test project:**
   - `git init --bare {test_dir}/remote.git` — create a local bare repo as the remote
   - `create_test_project(t)` — create the test project with initial commit
   - `git remote add origin {test_dir}/remote.git` — point origin at the bare repo
   - `git push origin main` — push the initial commit so origin/main exists
   - Copy the `push-main-pipeline` fixture into the test project
   - Make a state-simulating commit on main (e.g., update frontmatter `status: work`, `started:` timestamp) to create the "unpushed state commits on main" condition — this is the commit that would cause conflicts if main isn't pushed before the branch
   - Do NOT push this commit — origin/main is now behind local main (the core of the bug)
   - `git_add_commit(...)` to commit the fixture + state change

2. **Stub `gh`:**
   - Create a `gh` stub script at `{test_dir}/bin/gh` that logs invocations to `{test_dir}/gh-calls.log` and exits 0, printing a fake PR URL (`https://github.com/test/test/pull/99`)
   - Prepend `{test_dir}/bin` to `PATH` in the FO invocation environment so the stub is found before real `gh`
   - Note: the existing `run_first_officer` helper uses `_clean_env()` which strips `CLAUDECODE`. The `PATH` override needs to be passed via `extra_args` or by modifying the environment. If `_clean_env()` doesn't support custom PATH, the test can write the stub into a location already on PATH, or the implementation can add a small env-override capability. Alternatively, the stub can be placed at `{test_project_dir}/.local/bin/gh` and prepended to PATH in the prompt itself (instruct the FO to use that PATH).
   - Simpler approach: since `claude -p` with `--permission-mode bypassPermissions` runs bash commands, we can instruct the FO prompt to set `PATH={test_dir}/bin:$PATH` before running git/gh commands. Or, since the test controls the environment, modify the test to pass the custom PATH.

3. **Create a git push recording mechanism:**
   - Instead of (or in addition to) the `gh` stub, wrap `git` with a thin wrapper that logs push commands while passing them through to real git. Place at `{test_dir}/bin/git`:
     ```bash
     #!/bin/bash
     if [ "$1" = "push" ]; then
       echo "$(date +%s.%N) git push $*" >> {test_dir}/git-push-log.txt
     fi
     exec /usr/bin/git "$@"
     ```
   - This records timestamped push commands so we can verify ordering: `git push origin main` appears before `git push origin {branch}`.

4. **Run the FO:**
   - Use `run_first_officer()` with a prompt like: "Process the entity `push-main-entity` through the workflow at {abs_workflow}/ to completion. When the pr-merge merge hook fires and asks for approval, approve the push immediately."
   - Pass `--model haiku --effort low --max-budget-usd 2.00`
   - The FO should: dispatch the entity to `work`, do the trivial work, reach terminal `done`, fire the pr-merge merge hook, get "auto-approval" from the prompt, push main, push branch, create PR (via stubbed gh), set `pr` field.

5. **Validate push ordering:**
   - Read `{test_dir}/git-push-log.txt`
   - Assert it contains at least two push lines
   - Assert a line matching `git push origin main` appears before a line matching `git push origin {branch_name}`
   - This is the core assertion: main was pushed first

6. **Validate remote state:**
   - In the bare repo, verify that `origin/main` has the state commit: `git -C {test_dir}/remote.git log --oneline main` should show the state-simulating commit
   - Verify the branch exists on the remote: `git -C {test_dir}/remote.git branch --list {branch_name}` should be non-empty

7. **Validate PR creation:**
   - Read `{test_dir}/gh-calls.log`
   - Assert it contains a `pr create` invocation with `--base main --head {branch}`

8. **Validate entity state:**
   - The entity should have a non-empty `pr` field (set by the mod after PR creation)
   - The entity should NOT be archived yet (per mod instructions — it stays until PR is merged)

**Key design decisions:**
- The `git` wrapper + `gh` stub approach avoids needing a real GitHub remote while still testing the actual push ordering behavior.
- The test uses the real `pr-merge` mod (not a test-hook), so it validates the actual wording change.
- Auto-approval in the prompt sidesteps the interactive approval guardrail. Since we're testing push ordering, not the approval flow, this is acceptable.
- Budget cap of $2.00 keeps cost low for a simple workflow.

**Estimated cost:** ~$0.50-1.00 per run (haiku, low effort, simple 3-stage workflow with trivial work).

## Stage Report: ideation

1. Problem statement clarifying why unpushed main causes PR conflicts — DONE
2. Analysis of the current pr-merge mod merge hook flow — DONE
3. Proposed approach with specific before/after wording for the mod change — DONE
4. Acceptance criteria with test plans (how to verify the fix works) — DONE
5. Edge case analysis — DONE (push failure, force-push safety, no remote, no-op push, concurrent sessions)
6. Test plan: whether existing E2E tests cover this or new ones are needed — DONE (E2E test designed: `tests/test_push_main_before_pr.py` using bare repo remote, git push wrapper for ordering verification, and gh stub for PR creation. Follows existing test patterns from `test_merge_hook_guardrail.py`. New fixture at `tests/fixtures/push-main-pipeline/`.)

## Stage Report: implementation

1. Canonical mod (`mods/pr-merge.md`) updated with `git push origin main` before branch push, version bumped to 0.9.1 — DONE
2. Installed mod (`docs/plans/_mods/pr-merge.md`) matches canonical mod — DONE (verified via `diff`; files are identical)
3. E2E test fixture created at `tests/fixtures/push-main-pipeline/` — DONE (README.md workflow, push-main-entity.md, _mods/pr-merge.md, status script)
4. E2E test created at `tests/test_push_main_before_pr.py` — DONE (verifies push ordering via git wrapper and bare repo remote; validates remote state, PR creation via gh stub, and entity state)
5. All changes committed on the worktree branch — DONE (commit 536fd3d on `spacedock-ensign/pr-mod-push-main-before-pr`)

## Stage Report: validation

1. AC1: Canonical mod has push-main-before-branch wording — DONE. Line 38 of `mods/pr-merge.md` reads: `**On approval:** First, push main to ensure the remote is up to date with local state commits: \`git push origin main\`. Then push the worktree branch: \`git push origin {branch}\`.` — `git push origin main` appears before `git push origin {branch}` in the same sentence.

2. AC2: Installed mod matches canonical mod — DONE. `diff mods/pr-merge.md docs/plans/_mods/pr-merge.md` produces no output; files are identical. The test fixture mod (`tests/fixtures/push-main-pipeline/_mods/pr-merge.md`) also matches.

3. AC3: Version bumped to 0.9.1 — DONE. Line 4 of canonical mod: `version: 0.9.1`. Git diff confirms `0.9.0` -> `0.9.1`.

4. AC4: No other behavioral changes — DONE. `git diff main -- mods/pr-merge.md` shows exactly two hunks: (a) version `0.9.0` -> `0.9.1` in frontmatter, (b) the "On approval" paragraph reworded to add `git push origin main` before branch push and change "the push" to "either push". No other lines changed. Same diff applies to `docs/plans/_mods/pr-merge.md`.

5. E2E test passes — DONE. `unset CLAUDECODE && uv run tests/test_push_main_before_pr.py` ran successfully: 10 passed, 0 failed. Key results:
   - Push log shows `git push origin main` (timestamp 1775522232) before `git push origin spacedock-ensign/push-main-entity` (timestamp 1775522234)
   - Remote main has the state commit (verified via bare repo log)
   - Worktree branch `spacedock-ensign/push-main-entity` pushed to remote
   - `gh pr create --base main --head spacedock-ensign/push-main-entity` was called
   - Entity `pr` field set to `"#99"`

6. Recommendation: **PASSED**
