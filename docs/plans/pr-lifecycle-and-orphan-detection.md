---
id: 070
title: PR lifecycle timing and startup orphan detection
status: ideation
source: CL
started: 2026-03-28T12:00:00Z
completed:
verdict:
score: 0.80
worktree:
issue:
pr:
---

When a gated worktree stage (e.g., validation) is approved, the pr-merge mod should create the PR before advancing to the terminal stage. Currently the merge hook fires at the terminal stage, which means the entity is marked `done` while the PR is still open — semantically wrong. The entity should stay at its current stage until the PR merges.

The core problem: there's no metadata to distinguish "at a stage" vs "ready to transition to the next stage." The FO needs a way to know that a gated stage has been approved but the entity shouldn't advance yet because a PR is pending.

Additionally, startup orphan detection needs improvement. When the FO starts a new session, it should reliably detect entities with worktrees assigned but no active agents (crashed workers from previous sessions) and handle them — either re-dispatching or reporting to the captain.

## Problem Statement

When a gated worktree stage (validation) is approved by the captain, the FO currently advances the entity straight to `done` (the terminal stage), which triggers the merge hooks. The pr-merge mod fires at `done`, presents a draft PR, gets captain approval, pushes, and creates the PR. But by that point the entity already has `status: done`, `completed` timestamp, and `verdict: PASSED` — while the PR is still open and unmerged.

This happened concretely with task 069 (pr-merge-confirmation): the entity was archived as `done` even though the PR hadn't merged yet. The startup hook on the *next* FO session detects merged PRs, but the entity has already been archived with `done` status. This creates a semantic mismatch: the entity says "done" but the code hasn't landed on main.

The root cause is that there's no state between "gate approved" and "terminal/done." When the captain approves at a gate, the FO has two things to do: (1) advance the entity and (2) merge the code. Currently these are conflated — advancement to `done` triggers the merge, but `done` semantically means "finished." The entity needs to stay in a non-terminal state while the PR is pending.

### Second problem: startup orphan detection

When the FO starts a new session, entities with a non-empty `worktree` field but no active agent represent crashed workers from previous sessions. The FO template (startup step 6) says to "check for orphans" and "report orphans to the captain before dispatching" — but the detection heuristic is incomplete. There's no reliable way to distinguish between:
- An entity with a worktree that has an active agent (current session)
- An entity with a worktree whose agent crashed (previous session)

Since the FO always starts fresh in a new session, any entity with a non-empty `worktree` field at startup is definitionally an orphan — no agents from previous sessions survive. The FO should detect these and handle them before dispatching new work.

## Proposed Approach

### Part 1: Decouple gate approval from terminal advancement

**Introduce a `pr` field convention as the state signal.** No new frontmatter fields needed.

When a gated worktree stage is approved by the captain, instead of immediately advancing to the terminal stage, the FO:

1. Runs the merge hooks (which includes pr-merge)
2. The pr-merge mod pushes the branch, creates the PR, sets the `pr` field
3. The entity stays at its current stage (e.g., `validation`) with the `pr` field set
4. The entity is NOT advanced to `done` yet — it waits for the PR to merge

The `pr` field being non-empty while the entity is at a non-terminal gated stage means "gate approved, PR pending." This is the "ready to transition" signal — no new field needed.

**On next startup:** The existing startup hook already scans for entities with non-empty `pr` fields and checks merge status via `gh pr view`. When the PR is detected as merged, *then* the entity advances to `done` with `completed` timestamp and `verdict: PASSED`, gets archived, and worktree/branch are cleaned up.

**Where this changes in the FO template:**

The "Completion and Gates" section currently says: when a gate is approved, "dispatch a fresh agent for the next stage." For the case where the next stage is terminal, it says "proceed to merge." The change is:

- **Gate approved + next stage is terminal + worktree stage:** Run merge hooks first. If a merge hook created a PR (indicated by `pr` field becoming non-empty), do NOT advance to terminal. The entity stays at its current stage. Report to the captain that the PR is pending.
- **Gate approved + next stage is terminal + no worktree:** Advance to terminal as today (no code to merge, no PR needed).
- **Gate approved + next stage is NOT terminal:** Advance and dispatch as today (mid-pipeline gates like ideation don't trigger merge).

This means the pr-merge mod's `## Hook: merge` needs a small update too: the hook currently says "Do NOT archive yet. The entity stays in its terminal stage with `pr` set until the PR is merged." The updated behavior is: the entity stays in its *current* stage (not terminal) with `pr` set until the PR is merged.

### Why this approach over alternatives

**Alternative A: New frontmatter field (e.g., `gate-approved: true`)** — Adds schema complexity for a state that can be inferred from `pr` being non-empty at a non-terminal stage. More fields to maintain, more edge cases in tooling. Rejected.

**Alternative B: Status suffix (e.g., `validation:approved`)** — Breaks status as an enum. Every tool that reads `status` would need to parse suffixes. The status view, `--next` dispatch rules, and all grep-based queries would break. Rejected.

**Alternative C: New lifecycle hook (`post-gate` or `transition`)** — Adds a new hook point, but the real problem isn't when the hook fires — it's what happens after. The merge hook already fires at the right time. The issue is that the FO advances to terminal too early. The fix is in the FO's gate-approval logic, not in hook timing. Rejected.

**Alternative D: Delay archival but keep `done` status** — This is what the current pr-merge mod attempts ("entity stays in its terminal stage with `pr` set until the PR is merged"). The problem is that `done` + `completed` timestamp semantically means the work is finished. If someone runs `status`, they see `done` for an entity whose code hasn't landed. The entity should look in-progress until it actually is done. Rejected.

### Part 2: Non-worktree gates are unaffected

Ideation is gated but has no worktree — the entity is on main, no branch to merge. When the captain approves ideation, the FO advances to the next stage (implementation) as it does today. The PR-pending hold only applies when:
- The approved stage has `worktree: true` in the stages block, AND
- The next stage is terminal

This is the minimal, stage-aware condition. Mid-pipeline worktree stages (like implementation, which feeds into validation) don't trigger it either — they advance normally because the next stage isn't terminal (the worktree carries forward to validation).

### Part 3: Startup orphan detection

On FO startup, after reading the README and discovering mods, but before running `status --next`:

1. **Scan for orphans:** Find all entity files with a non-empty `worktree` field and a non-terminal, non-empty `status`. At startup, no agents are alive from previous sessions, so every such entity is an orphan.

2. **For each orphan, check worktree state:**
   - Does the worktree directory exist? (`ls {worktree_path}`)
   - Does the branch have a stage report committed? (Read the entity file in the worktree for a `## Stage Report` section)
   - Does the entity have a `pr` field set? (PR-pending entity — handle via existing startup PR hook)

3. **Actions based on state:**

   | Worktree state | Entity has `pr`? | Action |
   |----------------|-----------------|--------|
   | Worktree exists, stage report present | No | Report to captain: "Orphan {title} has completed {stage} work but was never reviewed. Stage report is present." Captain decides: review the report (re-enter gate flow), or redispatch. |
   | Worktree exists, stage report present | Yes | PR-pending entity — handled by existing startup PR merge detection hook. No additional action needed. |
   | Worktree exists, no stage report | No | Report to captain: "Orphan {title} was in-progress at {stage} with no stage report. Work may be partial." Captain decides: redispatch (start fresh in same worktree), or clean up. |
   | Worktree missing | No | Stale metadata. Clear `worktree` field, report to captain. |

4. **Do NOT auto-redispatch.** Always report to captain and wait for direction. Auto-redispatch risks duplicating partial work or ignoring completed-but-unreviewed results.

### Where this changes in the FO template

- **Startup step 6** currently says "check for orphans: entities with active status and non-empty `worktree` field indicate a crashed worker. Report orphans to the captain before dispatching." This needs expansion to the detection matrix above.
- The orphan check runs after the startup PR hook (step 5 runs startup hooks including pr-merge's startup hook), so PR-pending entities are already handled before orphan detection runs.

## Acceptance Criteria

1. When a gated worktree stage is approved and the next stage is terminal, the FO runs merge hooks but does NOT advance to the terminal stage if a PR was created. The entity stays at its current stage with `pr` set.
2. When a gated worktree stage is approved and the next stage is NOT terminal, the FO advances normally (no change).
3. When a gated non-worktree stage is approved, the FO advances normally (no change).
4. The FO startup PR hook detects merged PRs for entities at non-terminal stages (not just terminal stages as today) and advances them to done with proper cleanup.
5. The pr-merge mod's merge hook documentation is updated: entity stays at current stage (not terminal) while PR is pending.
6. On FO startup, entities with non-empty `worktree` and non-terminal status are detected as orphans.
7. Orphans are categorized by worktree state (exists/missing) and stage report presence, and reported to the captain with actionable options.
8. The FO does not auto-redispatch orphans — captain approval is required.
9. Orphan detection runs after startup hooks (so PR-pending entities are handled first).

## Stage Report: ideation

- [x] Problem statement grounded in the specific lifecycle mismatch (with concrete examples from how 069 played out)
  Documented the exact flow: validation approved -> entity set to done -> PR still open. Task 069 was the concrete example where this mismatch was observable.
- [x] Proposed approach for representing "gate approved, PR pending" state — with rationale for why this approach over alternatives
  Use existing `pr` field at a non-terminal stage as the state signal. Four alternatives evaluated and rejected (new field, status suffix, new hook, delay archival with done status). The key insight: decouple gate approval from terminal advancement.
- [x] How PR creation integrates with the stage/gate flow without breaking non-worktree gates (like ideation)
  The PR-pending hold only applies when: approved stage has `worktree: true` AND next stage is terminal. Ideation gates, mid-pipeline worktree stages all advance normally.
- [x] Proposed approach for startup orphan detection — what the FO checks, what actions it takes
  Detection matrix: scan for non-empty worktree + non-terminal status. Categorize by worktree existence and stage report presence. Four scenarios with specific actions. Never auto-redispatch — always report to captain.
- [x] Acceptance criteria — testable conditions for "done"
  Nine acceptance criteria covering gate-approval flow (3 cases), startup PR detection update, mod documentation, and orphan detection (4 criteria).

### Summary

The core design decision is to decouple gate approval from terminal advancement. When a gated worktree stage is approved and the next stage is terminal, the FO runs merge hooks (creating the PR) but keeps the entity at its current stage. The `pr` field being non-empty at a non-terminal stage is the "gate approved, PR pending" signal — no new schema fields needed. The startup hook already checks PR merge status; it just needs to handle entities at non-terminal stages too. Non-worktree gates and mid-pipeline gates are unaffected. Orphan detection is a separate startup step that categorizes stranded entities by worktree state and stage report presence, always deferring to the captain for action.
