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

Under the current design, the entity gets archived as `done` with `completed` timestamp and `verdict: PASSED` at the moment the merge hooks fire — before the PR is even created, let alone merged. The startup hook on the *next* FO session can detect merged PRs, but by then the entity is already archived with `done` status. This creates a semantic mismatch: `status: done` while the code hasn't landed on main. Any `status` query shows the entity as finished when it isn't.

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

**On next startup:** The pr-merge mod's startup hook already says "scan all entity files for entities with a non-empty `pr` field and a non-terminal status" — this wording already covers the new scenario where PR-pending entities sit at a non-terminal stage like `validation`. No change to the startup hook's scan criteria is needed. When the PR is detected as merged, the hook advances the entity to the terminal stage with `completed` timestamp and `verdict: PASSED`, archives it, and cleans up the worktree/branch.

The startup hook also needs to handle one additional PR state: `CLOSED` (without merge). If a PR was closed without merging (e.g., abandoned, superseded), the entity is stuck — it can't advance via merge detection and it's not dispatchable. The startup hook should report closed PRs to the captain with options: reopen and fix, create a new PR, or fall back to local merge.

**Exactly where this changes in the FO template:**

The critical change is in `## Completion and Gates`, in the gate-approval path. Currently the "Approve" bullet says: "Shut down the agent. Dispatch a fresh agent for the next stage." And the "If no gate" path says: "If terminal, proceed to merge." Both funnel into `## Merge and Cleanup`, which triggers merge hooks only when the entity *reaches* the terminal stage.

The problem: merge hooks fire inside "Merge and Cleanup," which is entered *after* terminal advancement. We need merge hooks to fire *before* terminal advancement when a PR might be created.

The fix restructures the gate-approval "Approve" path into three cases:

- **Approve + next stage is terminal + current stage has worktree:** Run merge hooks *here*, in the gate-approval path, before any status change. If a merge hook set the `pr` field (indicating a PR was created), do NOT advance to terminal. The entity stays at its current stage. Shut down the agent. Report to the captain that the PR is pending and will be detected on next startup. If no merge hook set `pr` (no pr-merge mod installed, or captain declined the push), fall through to the existing "Merge and Cleanup" section for local merge.
- **Approve + next stage is terminal + no worktree:** Fall through to existing "Merge and Cleanup" for terminal advancement and archival (no code to merge, no PR needed).
- **Approve + next stage is NOT terminal:** Advance and dispatch as today (mid-pipeline gates like ideation).

The `## Merge and Cleanup` section itself is unchanged — it still handles local merge for entities that reach terminal without a PR. The change is that the gate-approval path can now short-circuit before reaching it.

The pr-merge mod's `## Hook: merge` also needs a wording update. It currently says "Do NOT archive yet. The entity stays in its terminal stage with `pr` set until the PR is merged." The updated behavior: the entity stays in its *current* stage (not terminal) with `pr` set until the PR is merged. The mod doesn't need to know about archival timing — it just sets `pr` and the FO handles the rest.

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

### Part 2b: `status --next` and concurrency implications

When an entity stays at `validation` with `pr` set and `worktree` still populated (worktree is kept alive for post-PR fixes like CI failures or code review feedback):

- **Not dispatchable:** Validation has `gate: true`, so `status --next` Rule 2 (not gate-blocked) filters it out. Correct — we don't want it redispatched.
- **Concurrency slot occupied:** The non-empty `worktree` counts toward validation's `active_counts`, consuming a concurrency slot. This is intentional — the worktree is still alive and may need an agent dispatched into it for PR fixes. The slot should stay occupied until the PR merges and the worktree is cleaned up.
- **Orphan detection interaction:** On next startup, this entity has non-empty `worktree` and non-terminal status, which matches the orphan detection criteria. However, it also has `pr` set. Orphan detection must explicitly skip entities with non-empty `pr` — these are PR-pending, not orphaned. The ordering (startup PR hook runs before orphan detection) provides defense in depth, but the orphan detector itself should also check for `pr` to avoid misclassification if the startup hook doesn't clear the entity (e.g., PR is still open).

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
   | Worktree exists, any | Yes | PR-pending entity — skip orphan handling entirely. Handled by the startup PR hook (merged/open/closed detection). |
   | Worktree exists, no stage report | No | Report to captain: "Orphan {title} was in-progress at {stage} with no stage report. Work may be partial." Captain decides: redispatch (start fresh in same worktree), or clean up. |
   | Worktree missing | No | Stale metadata. Clear `worktree` field, report to captain. |
   | Worktree missing | Yes | PR was pushed but worktree was cleaned up (partial cleanup from crash). Handled by startup PR hook — the branch exists on remote even though the local worktree is gone. If PR is merged, advance to done. If open/closed, report to captain. |

4. **Do NOT auto-redispatch.** Always report to captain and wait for direction. Auto-redispatch risks duplicating partial work or ignoring completed-but-unreviewed results.

### Where this changes in the FO template

- **Startup step 6** currently says "check for orphans: entities with active status and non-empty `worktree` field indicate a crashed worker. Report orphans to the captain before dispatching." This needs expansion to the detection matrix above.
- The orphan check runs after the startup PR hook (step 5 runs startup hooks including pr-merge's startup hook), so PR-pending entities are already handled before orphan detection runs.

## Acceptance Criteria

1. When a gated worktree stage is approved and the next stage is terminal, the FO runs merge hooks in the gate-approval path (not in "Merge and Cleanup"). If a merge hook set the `pr` field, the entity stays at its current stage — no terminal advancement. If no `pr` was set, fall through to existing "Merge and Cleanup" for local merge.
2. When a gated worktree stage is approved and the next stage is NOT terminal, the FO advances normally (no change).
3. When a gated non-worktree stage is approved, the FO advances normally (no change).
4. The pr-merge startup hook's existing "non-terminal status" scan criteria already covers PR-pending entities at non-terminal stages — no scan change needed, but confirm this in implementation.
5. The pr-merge startup hook handles `CLOSED` (without merge) PRs: report to captain with options (reopen, new PR, or local merge).
6. The pr-merge mod's merge hook documentation is updated: entity stays at current stage (not terminal) while PR is pending.
7. On FO startup, entities with non-empty `worktree`, non-terminal status, and empty `pr` are detected as orphans. Entities with `pr` set are PR-pending, not orphans.
8. Orphans are categorized by worktree state (exists/missing) and stage report presence, and reported to the captain with actionable options.
9. The FO does not auto-redispatch orphans — captain approval is required.
10. Orphan detection runs after startup hooks (defense in depth), and also explicitly skips entities with non-empty `pr` (primary guard).

## Stage Report: ideation

- [x] Problem statement grounded in the specific lifecycle mismatch (with concrete examples from how 069 played out)
  Documented the exact flow: validation approved -> entity set to done -> PR still open. Described as the expected behavior under the current design (the pr-merge mod was only just implemented with 069).
- [x] Proposed approach for representing "gate approved, PR pending" state — with rationale for why this approach over alternatives
  Use existing `pr` field at a non-terminal stage as the state signal. Four alternatives evaluated and rejected (new field, status suffix, new hook, delay archival with done status). The key insight: decouple gate approval from terminal advancement. Merge hooks fire in the gate-approval path, not in "Merge and Cleanup."
- [x] How PR creation integrates with the stage/gate flow without breaking non-worktree gates (like ideation)
  The PR-pending hold only applies when: approved stage has `worktree: true` AND next stage is terminal. Ideation gates, mid-pipeline worktree stages all advance normally. Concurrency slot stays occupied (worktree kept alive for post-PR fixes). Orphan detection explicitly skips pr-pending entities.
- [x] Proposed approach for startup orphan detection — what the FO checks, what actions it takes
  Detection matrix: scan for non-empty worktree + non-terminal status + empty pr. Five scenarios with specific actions (including worktree-missing+pr-set edge case). Never auto-redispatch — always report to captain. Startup PR hook handles closed-without-merge PRs.
- [x] Acceptance criteria — testable conditions for "done"
  Ten acceptance criteria covering gate-approval flow (3 cases), startup PR hook confirmation, closed-PR handling, mod documentation, and orphan detection (4 criteria).

### Summary

The core design decision is to decouple gate approval from terminal advancement by moving merge hook execution into the gate-approval path in "Completion and Gates." When a gated worktree stage is approved and the next stage is terminal, the FO runs merge hooks before any status change. If a PR was created (`pr` field set), the entity stays at its current stage — the worktree remains alive for post-PR fixes. The pr-merge startup hook already scans "non-terminal status" entities, so it covers the new scenario without scan changes; it also needs to handle `CLOSED` (without merge) PRs. Orphan detection explicitly skips entities with `pr` set (PR-pending, not orphaned) and categorizes the rest by worktree state and stage report presence.
