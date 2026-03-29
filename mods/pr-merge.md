---
name: pr-merge
description: Push branches and create/track GitHub PRs for workflow entities
version: 0.8.0
---

# PR Merge

Manages the PR lifecycle for workflow entities processed in worktree stages. Pushes branches, creates PRs, detects merged PRs, and advances entities accordingly.

## Hook: startup

Scan all entity files (in the workflow directory only, not `_archive/`) for entities with a non-empty `pr` field and a non-terminal status. For each, extract the PR number (strip any `#`, `owner/repo#` prefix) and check: `gh pr view {number} --json state --jq '.state'`.

If `MERGED`, advance the entity to its terminal stage: set `status` to the terminal stage, `completed` to ISO 8601 now, `verdict: PASSED`, clear `worktree`, archive the file, and clean up any worktree/branch. Report each auto-advanced entity to the captain.

If `gh` is not available, warn the captain and skip PR state checks.

## Hook: merge

**PR APPROVAL GUARDRAIL — Do NOT push or create a PR without explicit captain approval.** Before pushing, present a draft PR summary to the captain:

- **Title:** {entity title}
- **Branch:** {branch} -> main
- **Changes:** {N} file(s) changed across {N} commit(s)
- **Files:** {list of changed files}

Wait for the captain's explicit approval before pushing. Do NOT infer approval from silence, acknowledgment of the summary, or the gate approval that preceded this step — only an explicit "push it", "go ahead", "yes", or equivalent counts.

**On approval:** Push the worktree branch: `git push origin {branch}`. If the push fails (no remote, auth error), report to the captain and fall back to local merge.

Create a PR: `gh pr create --base main --head {branch} --title "{entity title}" --body "Workflow entity: {entity title}"`. If `gh` is not available, warn the captain and fall back to local merge.

Set the entity's `pr` field to the PR number (e.g., `#57`). Report the PR to the captain.

**On decline:** Do NOT automatically fall back to local merge. Ask the captain how to proceed — options include local merge or leaving the branch unmerged. Only act on the captain's explicit choice.

Do NOT archive yet. The entity stays in its terminal stage with `pr` set until the PR is merged. The startup hook will detect the merge on next FO startup.
