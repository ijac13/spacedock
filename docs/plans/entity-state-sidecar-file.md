---
id: 165
title: "Move entity current-state out of frontmatter into a sidecar file to reduce main-branch state-churn commits"
status: backlog
source: "CL observation during 2026-04-16 session — state-change commits on main during worktree-backed stages clutter main's log and complicate rebase/force-push scenarios (#163 extraction made this acute)"
started:
completed:
verdict:
score: 0.70
worktree:
issue:
pr:
---

## Problem Statement

Spacedock treats entity YAML frontmatter as the canonical store for current state (status, worktree, pr, mod-block, verdict, completed). Every state change the FO makes produces a commit on main that edits a single frontmatter line in one entity file. During worktree-backed stages (implementation, validation), real work lives in the worktree branch while main accumulates a steady stream of frontmatter-only commits: `dispatch:`, `advance:`, `feedback:`, `mod-block:`, `dispatch: PR opened`, `merge: archived`. The audit trail splits between main (state) and the worktree branch (work). Main's log fills with transitions that are internal to the FO state machine — not meaningful code or content changes. Rebase and force-push scenarios (such as extracting an unrelated entity's commits from main, as happened in this session for #163) are painful because state commits from multiple in-flight entities interleave with each other and with real work.

## Context

This task surfaced during the 2026-04-16 session after the #163 `kilocode-support` concurrent-session interleaving forced a main-branch force-push to extract the task onto its own branch. The captain observed that state-change commits on main during worktree-backed stages feel awkward: the worktree holds the actual work while main holds the state transitions, splitting the audit trail and producing commit noise that obscures what shipped. Two patterns from this session illustrate the pain: feedback cycles produce bidirectional frontmatter commits (status advances, reverts on rejection, then advances again — three commits per cycle bounce), and mod-block pairs (one commit to set `mod-block`, another to clear it) are set-and-revert on a single field. Both are useful audit events, but they flood main with state churn.

## Approach tradeoffs

Four architectural alternatives, not mutually exclusive:

**(a) Sidecar state file.** Move current-state tracking out of entity frontmatter into a single `docs/plans/.state.yaml` (or SQLite). The FO edits one file; main gets one-line diffs per transition. Entity files stay content-focused; their frontmatter keeps static metadata (id, title, source, score). `status --boot` reads the sidecar directly and is faster (one file vs. scanning every entity). Costs: entity files lose the "open-and-know-everything" property (current status lives elsewhere); refit migration must backfill the sidecar from existing frontmatter; atomic consistency between sidecar and frontmatter requires a `status repair` subcommand for drift. Recommended as the v1 target — smallest conceptual change, cleanest git log, easiest rebase recovery.

**(b) State transitions live in the worktree during worktree-backed stages.** The FO writes frontmatter to the worktree copy during implementation and validation; main sees no state updates until PR merge. Main's log stays pristine during in-flight work. Costs: `status --boot` and `status --where` today scan main-branch frontmatter and cannot see in-flight state; they would need to scan active `.worktrees/` or maintain an in-flight registry. Discovery becomes more expensive and error-prone across runtime failures (orphan worktrees become harder to detect).

**(c) Batch-commit state transitions.** The FO accumulates state changes in memory and commits a summary at natural boundaries (end-of-session, gate decisions, archival). Main's log shows fewer commits, each representing a cluster of transitions. Costs: fine-grained audit is lost; a crashed session drops pending transitions; session-boundary semantics are poorly defined for long-running orchestration.

**(d) Separate `fo/state` branch.** State transitions land on a parallel `fo/state` branch that merges to main only at archival boundaries. Main stays focused on real work; state history lives on its own branch. Costs: the most git-unfamiliar shape; merge logic is complex; `status --boot` must read from two branches; captains unfamiliar with the pattern get lost quickly.

All four options address the core asymmetry — during worktree-backed stages, work lives in one place but state lives in another — by either consolidating state into a single file (a), moving state to where work is (b), reducing state commit frequency (c), or segregating state onto a dedicated branch (d). Option (a) is the recommended v1 because it changes least about how the FO thinks about state while eliminating most of the commit noise.

## Open questions for ideation

Ideation will choose an option and pin answers to these questions for the chosen direction:

- **Which of the four options (or a hybrid)?** Tradeoffs are above; ideation weighs them against this workflow's specific pain and operational constraints.
- **What state fields move?** Candidates: `status`, `worktree`, `pr`, `mod-block`, `verdict`, `started`, `completed`. Some may stay in frontmatter (e.g. `completed` as permanent audit), others move to the new store.
- **What stays in entity frontmatter?** Static metadata is the obvious keep (`id`, `title`, `source`, `score`, `issue`). Anything else?
- **Migration strategy.** One-shot refit, gradual per-entity promotion, or new-workflows-only? How does existing workflow history stay intact?
- **Consistency enforcement.** How does the helper detect drift if state lives in two places during a migration window? What does a `repair` subcommand do?
- **Discovery performance.** If state scanning moves to one file, does `status --boot` become cheap enough that we can afford richer queries? Does this change the status script's architecture?
- **Interaction with plugin-per-workflow direction.** Per earlier captain design discussion, workflows may become distributable plugins. Where does state live — in the workflow plugin itself, in a user-project sidecar, or elsewhere?
- **Codex runtime parity.** Does any chosen option generalize cleanly to the Codex runtime adapter's state-discovery path, or does each runtime need its own mechanism?
