---
id: 069
title: pr-merge mod shows draft PR and gets captain approval before pushing
status: implementation
source: https://github.com/clkao/spacedock/issues/10
started: 2026-03-29T03:12:00Z
completed:
verdict:
score: 0.85
worktree: .worktrees/ensign-069-pr-confirm
issue: "#10"
pr:
---

## Problem Statement

The pr-merge mod's `## Hook: merge` section pushes the worktree branch and creates a GitHub PR immediately after the validation gate approval, with no confirmation step. The captain has no opportunity to review what's about to be pushed or decline the PR.

This matters because pushing to remote and creating a PR are externally visible, hard-to-reverse actions. The captain should see what's going out before it goes. This matches the pattern established by the issue filing guardrail (task 059): draft content, present to captain, wait for explicit approval, then execute.

## Proposed Approach

One file change: replace the `## Hook: merge` section in `mods/pr-merge.md`. The updated hook adds a PR approval guardrail following the same bold ALL-CAPS pattern used by gate guardrails and the issue filing guardrail.

### Updated Hook: merge (exact text)

```markdown
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
```

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Captain approves | Push branch, create PR, set `pr` field — normal flow |
| Captain declines | Ask captain how to proceed (local merge or leave unmerged) — no default assumption |
| `gh` unavailable (after approval) | Warn captain, fall back to local merge |
| Push fails (after approval) | Report to captain, fall back to local merge |
| Gate approval just happened | Explicitly not treated as PR approval — separate concern (work quality vs push decision) |

## Acceptance Criteria

1. The `## Hook: merge` section in `mods/pr-merge.md` contains a PR approval guardrail with the bold ALL-CAPS pattern.
2. The hook presents a draft PR summary (title, branch, change count, file list) before pushing.
3. The hook waits for explicit captain approval — silence and gate approval do not count.
4. On approval: push, create PR, set `pr` field (existing behavior preserved).
5. On decline: ask captain for direction instead of assuming local merge.
6. Fallback behavior for `gh` unavailable and push failure is preserved.

## Stage Report: ideation

- [x] Problem statement with rationale
  Documented in "Problem Statement" section — externally visible action without confirmation, matches issue filing guardrail pattern from task 059
- [x] Proposed hook wording (exact text for the updated merge hook)
  Full replacement text for `## Hook: merge` provided in "Updated Hook: merge" section
- [x] Edge cases (captain declines, gh unavailable, push fails)
  Table covering 5 scenarios including gate-approval-is-not-PR-approval distinction
- [x] Acceptance criteria
  6 testable criteria covering guardrail pattern, draft summary content, approval semantics, decline behavior, and fallback preservation

### Summary

The pr-merge mod's merge hook needs a confirmation step before pushing and creating PRs. The proposed change replaces the `## Hook: merge` section with an updated version that adds a PR approval guardrail (bold ALL-CAPS pattern matching existing guardrails), presents a draft summary, and waits for explicit captain approval. On decline, the FO asks the captain how to proceed rather than assuming local merge. All existing fallback behavior (gh unavailable, push failure) is preserved.
