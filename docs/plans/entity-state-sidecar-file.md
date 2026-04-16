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

## Proposed v1 direction (Option a)

Ship a sidecar state file. Scope, with ideation to sharpen:

1. **New file:** `docs/plans/.state.yaml` (YAML for readability; SQLite can come later if performance demands). Schema: top-level keys are entity slugs; values are state records with fields `status`, `worktree`, `pr`, `mod-block`, `verdict`, `started`, `completed`.
2. **`status --set` changes:** writes the sidecar, not frontmatter. One atomic write (rename) per invocation. Stdout still emits `field: old -> new` lines per #159.
3. **`status --boot` / `status --next` / `status --where`:** read the sidecar. No entity-file scan for state.
4. **Entity frontmatter:** keeps static metadata only (id, title, source, score, issue). No status / worktree / pr / mod-block / verdict / completed / started.
5. **Refit migration:** one-time scan that reads each entity's current frontmatter, writes to sidecar, strips the transient fields from frontmatter, commits.
6. **Consistency repair:** new `status repair` subcommand that reconciles sidecar vs frontmatter if they drift (should not happen in normal flow, but defends against external edits).

Ideation will pin open questions:
- YAML vs SQLite vs JSON (lean YAML for readability).
- Whether `_archive/` entities also live in sidecar or get a separate archive state store.
- How the FO's existing "read entity file, see status" pattern degrades (pointer prose in shared-core: "current status is in `.state.yaml`, not frontmatter").
- Refit UX: one-shot migration or gradual per-entity promotion?
- Impact on plugin-per-workflow direction from CL's earlier design discussion (sidecar file lives in the workflow instance's project tree, not in the template plugin).

## Acceptance Criteria (provisional — sharpen in ideation)

1. **AC-sidecar-exists:** `docs/plans/.state.yaml` is created by refit (or at commission time for new workflows). Schema documented in workflow README.
2. **AC-status-set-targets-sidecar:** `status --set {slug} field=value` writes to sidecar, not to the entity's frontmatter. Entity file on disk is unchanged after the call. *Verified by* static test: pre-hash entity file, run `--set`, post-hash — must match.
3. **AC-status-boot-reads-sidecar:** `status --boot` produces identical output with and without entity-file frontmatter containing state fields (tolerates-either-location during migration window, or strictly-sidecar post-migration). *Verified by* a parametrized test.
4. **AC-status-repair:** `status repair` detects sidecar-vs-frontmatter drift on a synthetic fixture and reports / fixes it. *Verified by* a static test with known drift.
5. **AC-refit-migration:** a commissioned workflow with state-in-frontmatter entities can run `refit` and end up with state-in-sidecar + clean frontmatter. *Verified by* an integration test using a pre-migration fixture.
6. **AC-main-log-clean:** a representative feedback-cycle sequence (advance → reject → advance) produces 3 commits editing `.state.yaml` only (no entity-file diffs). *Verified by* a static test that runs the sequence against a fixture and checks `git diff` file list.

Test plan will be sharpened in ideation; provisional shape is primarily static (parser + helper behavior) with one integration test for refit migration.

## Out of Scope

- **Codex runtime equivalents.** Codex has its own state-discovery path; if this lands for Claude first, file a sibling task for Codex once the sidecar format is stable.
- **SQLite backend.** Start with YAML. SQLite is a follow-up if we need query patterns YAML can't serve (unlikely for the entity counts Spacedock workflows see).
- **Multi-workflow sidecar aggregation.** One sidecar per workflow. Cross-workflow views come later.
- **Historical state rewrite.** This task ships going forward; existing commit history on main with state in frontmatter stays as-is. Future commits use the sidecar.

## Deferred follow-ups (file after this ships)

- Codex sidecar parity.
- Sidecar performance at scale (100+ entities).
- Cross-workflow aggregation for plugin-per-workflow distribution.
- Archive-state storage (do `_archive/` entities stay in sidecar or get a separate `.archive-state.yaml`?).
