---
id: 042
title: GitHub issue reference and PR workflow integration
status: ideation
source: CL
started: 2026-03-26T00:00:00Z
completed:
verdict:
score:
worktree:
---

How should Spacedock pipelines incorporate GitHub issue references and PR workflows? Tasks in a pipeline often correspond to GitHub issues, and implementation work naturally produces PRs. Currently there's no structured way to link these.

## Problem Statement

Pipeline tasks and GitHub artifacts are separate worlds with no linkage:

1. **Issue tracking duplication** — A task exists in the pipeline (`docs/plans/foo.md`) and may also exist as a GitHub issue. There's no way to cross-reference them. The `source` field sometimes says "CL" or "testflight-005" but never links to an issue number.

2. **Worktree branches have no PRs** — The first officer creates `ensign/{slug}` branches for worktree stages and merges them with `git merge --no-commit` at the terminal stage. These branches never become PRs, so there's no GitHub-native review surface, no CI checks, and no record in the repo's PR history.

3. **Validation gate vs. PR review** — The pipeline has an approval gate at validation where the captain reviews the ensign's work. GitHub has PR review. These are parallel review mechanisms that could be unified or at least connected.

## Analysis

### What's the actual pain?

Looking at the Spacedock pipeline itself (42 tasks processed), the practical gaps are:

- **No way to reference the upstream issue** that motivated a task. When CL files a task based on a GitHub issue, the connection is informal (the `source` field or a mention in the body text).
- **No PR for code review**. Worktree branches get merged directly. For Spacedock's own development this has been fine (CL reviews via the approval gate), but for team projects where PRs are the standard review surface, this is a gap.
- **No CI integration**. Worktree branches aren't pushed, so CI never runs on them. Validation relies entirely on the ensign running tests locally.

### What's NOT a pain (yet)?

- Automatic issue creation from tasks — YAGNI. Tasks are already well-structured markdown files. Creating a GitHub issue for every task would be duplication.
- Bidirectional sync between issues and tasks — way too complex for v0. Issues and tasks serve different audiences (GitHub users vs. pipeline operators).

## Proposed Approach

### Part 1: Cross-reference fields (this task)

Add `issue` and `pr` as optional fields to the entity schema:

```yaml
---
id: 042
title: GitHub issue reference and PR workflow integration
status: ideation
source: CL
started: 2026-03-26T00:00:00Z
completed:
verdict:
score:
worktree:
issue:
pr:
---
```

- **`issue`** — A GitHub issue reference (e.g., `#42` or `owner/repo#42`). Set manually when creating a task from an issue, or by the captain at any time. Never auto-created.
- **`pr`** — A GitHub PR reference (e.g., `#57` or `owner/repo#57`). Set when a PR is created for the task's worktree branch. Can be set by the first officer or manually.

Both fields are plain strings. No validation, no API calls to verify they exist. The value is human-readable cross-reference, not programmatic integration. Actions on issues/PRs (closing, commenting) are left to the captain or future automation — not prescribed here.

### Part 2: PR workflow via lieutenant agents (depends on task 035)

Rather than a pipeline-level `pr-workflow: true` flag with PR logic hardcoded into the first officer, the PR workflow is handled by a **stage-specialized lieutenant agent** (see task 035). The stage declares which agent to dispatch, and the agent contains the full methodology.

#### How it works

A stage in the README frontmatter references a lieutenant:

```yaml
stages:
  states:
    - name: implementation
      worktree: true
      agent: pr-lieutenant
    - name: validation
      worktree: true
      fresh: true
      gate: true
```

The `pr-lieutenant` agent file (`.claude/agents/pr-lieutenant.md`) contains the methodology for:

1. **Doing the implementation work** (same as a generic ensign today)
2. **Pushing the branch**: `git push origin ensign/{slug}`
3. **Creating the PR**: `gh pr create --base main --head ensign/{slug} --title "{entity title}" --body "..."`
4. **Setting the `pr` field** in the entity frontmatter (or reporting it to the first officer to set)
5. **Responding to PR review comments** — the lieutenant can read review comments via `gh pr view` and address them with additional commits

The first officer doesn't need to know about GitHub at all. It dispatches the lieutenant per the stage's `agent` property. The lieutenant handles the full PR lifecycle.

#### Why this is better than a pipeline flag

- **Same extensibility mechanism as everything else** — stages reference agents, agents contain methodology. No special-case flags.
- **The PR behavior is in the agent, not the orchestrator** — the first officer stays a pure dispatcher. Different pipelines can use different PR agents (one that creates draft PRs early, one that also runs CI, one that handles specific review conventions).
- **Composable** — a pipeline could use `pr-lieutenant` for implementation but a different agent for validation. Or skip it entirely for stages that don't produce code.

#### Merge boundary change

When a stage uses a PR lieutenant, the first officer's merge step (step 7) changes: instead of `git merge --no-commit`, it checks whether a PR exists for the entity (the `pr` field is set). If so:

- Check PR merge status: `gh pr view {pr_number} --json state`
- If merged: clean up worktree/branch, archive entity
- If open: report to captain, wait
- If not yet created (lieutenant didn't create one): fall back to local merge

On startup, the first officer checks all entities with non-empty `pr` fields for merged PRs — this handles the case where PRs were merged between sessions.

#### Approval gate unification

When PR workflow is active, the validation gate and PR review can be the **same review**:

- Captain reviews on GitHub (sees diff, CI results)
- Merging the PR signals approval — the first officer detects this and advances to `done`
- Requesting changes signals rejection — the first officer can re-dispatch or relay feedback

This is optional behavior, not enforced. The captain can still approve via the conversation if they prefer.

### Scenarios

**Spacedock's own development:** Commission with `agent: pr-lieutenant` on the implementation stage. Ensign does the work in a worktree, pushes the branch, creates a PR. CL reviews on GitHub, merges. Next session, the first officer detects the merge and archives the entity.

**Incoming GitHub issue:** CL creates a task with `issue: "#23"`. The connection is documented in frontmatter. When the entity reaches `done`, CL closes the issue (or a future lieutenant could auto-close it).

**Incoming PR from a contributor (future):** CL creates a task with `pr: "#45"` pointing at the contributor's PR. A specialized lieutenant checks out the PR branch, runs validation, and reports. This inverts the normal flow (PR already exists, pipeline reviews it) and needs a different dispatch pattern — out of scope for this task.

### What changes where

| Component | Change |
|-----------|--------|
| **README schema** | Add `issue` and `pr` as optional fields in the entity template. Document them in the Field Reference. |
| **First-officer template** | Add PR-aware merge step: check `pr` field, detect merged PRs on startup, fall back to local merge when no PR exists. |
| **Commission SKILL.md** | Add `issue` and `pr` to generated entity template. |
| **Status script** | No change needed. |

The `pr-lieutenant` agent file and the `agent` stage property are part of task 035 (lieutenant agents), not this task. This task provides the schema fields and the first officer's awareness of PRs.

## Scope

**This task:**
- `issue` and `pr` frontmatter fields (passive cross-references)
- First officer checks `pr` field at merge boundary — if set, check PR state instead of local merge
- First officer detects merged PRs on startup
- Commission generates `issue` and `pr` fields in entity template

**Task 035 (lieutenant agents):**
- `agent` stage property in README frontmatter
- PR lieutenant agent file with push/create-PR/review-comments methodology
- Commission generates lieutenant agent files

**Future (not scoped):**
- Inbound PR workflow (contributor opens PR, pipeline reviews it)
- Auto-close issues when entities reach terminal
- PR review comment parsing for automated redo
- CI status checks as validation input

## Acceptance Criteria

- [ ] Entity schema includes optional `issue` and `pr` string fields
- [ ] First-officer template checks `pr` field at merge boundary: if set and PR is merged, skip local merge; if set and PR is open, wait; if unset, local merge as today
- [ ] First-officer template detects merged PRs on startup and advances entities to terminal stage
- [ ] Commission skill generates `issue` and `pr` fields in entity template
- [ ] Existing pipelines continue to work unchanged (no PR field = local merge)
- [ ] PR body (when created by a lieutenant, not this task) includes entity title and link back to entity file

## Open Questions

1. **`gh` CLI availability** — The first officer's PR state checking requires `gh`. If `gh` is not available and `pr` is set, should it warn and skip, or error? Leaning toward: warn and fall back to asking the captain for manual status.

2. **PR number format** — Should the `pr` field store just the number (`57`), the GitHub shorthand (`#57`), or a full reference (`owner/repo#57`)? The shorthand `#57` is most natural for single-repo use. Full reference is needed for cross-repo. Leaning toward: accept any format, parse as needed when calling `gh`.
