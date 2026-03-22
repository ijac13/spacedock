---
title: Approval Gate Merge Bug
status: backlog
source: testflight-003
started:
completed:
verdict:
score:
worktree:
---

## Problem

The first-officer event loop merges pilot work to main unconditionally when a pilot completes, then checks approval gates when dispatching the next stage. This is wrong — when the next transition is approval-gated, the merge itself should wait for CL's approval.

Observed during testflight-003:
- **score-format-standardization** (validation → done gate): validation pilot completed with PASSED recommendation. First officer merged the branch, cleared the worktree, then asked CL for approval. The work was already on main before CL could review or reject.
- **refit-command** (ideation → implementation gate): ideation pilot completed. First officer merged the branch, advanced status to `implementation`, cleared the worktree, then asked CL for approval. Status was advanced past the gate without approval.

## Root Cause

The first-officer agent template (`agents/first-officer.md`) has the approval check in the Dispatching section (step 3), but the Event Loop's merge step (step 2) doesn't cross-reference it. The event loop says "Merge and finalize" unconditionally after pilot completion.

## Correct Behavior

When a pilot completes a stage and the next transition requires human approval:

1. Do NOT merge. Keep the worktree and branch alive.
2. Report the pilot's findings to CL.
3. Wait for CL's approval.
4. On approval: merge the branch, update frontmatter (advance status, set timestamps/verdict), commit atomically, clean up worktree.
5. On rejection: either discard the branch or re-dispatch the pilot with feedback, depending on CL's instructions.

The worktree is the isolation boundary. The merge IS the transition. Approval must come before the merge, not after.

## Files to Fix

- `agents/first-officer.md` — the generated first-officer template. The Event Loop section needs a gate check before merging.
- `skills/commission/SKILL.md` — the commission skill that generates the first-officer template. The embedded event loop template has the same gap.
