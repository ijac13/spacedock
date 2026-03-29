---
id: 073
title: Auto-bounce rejection at feedback stages without captain approval
status: ideation
source: 033 validation incident — FO waited for captain on a clear rejection
started: 2026-03-29T16:45:00Z
completed:
verdict:
score: 0.75
worktree:
---

When a feedback stage (one with `feedback-to`) has `gate: true` and the validator recommends REJECTED, the FO currently presents the rejection at the gate and waits for the captain to explicitly approve or reject. This is unnecessary — the validator already decided REJECTED with specific findings. The captain had to say "do that, and check the workflow to see why we think this needed to be raised."

## Problem

The FO template's gate flow treats approve and reject symmetrically:

1. Validator completes → FO presents stage report at gate
2. Captain says approve or reject
3. FO acts accordingly

But approve and reject are asymmetric in consequence:
- **Approve** is consequential — it advances state, triggers merge, creates PRs, archives entities. The captain should explicitly authorize this.
- **Reject with feedback-to** is just "try again" — it bounces findings back to the implementer. No state advances, no irreversible action. The captain doesn't need to authorize a retry.

## Observed incident

Task 033 validation: the validator returned REJECTED with 3 specific findings. The FO presented the gate review and waited. The captain had to explicitly say "it should go back to implementer without me deciding." The round-trip added no information — the captain would only intervene if they disagreed with the rejection, which is the rare case.

## Proposed behavior

When a feedback stage's validator recommends REJECTED:
- The FO automatically enters the Feedback Rejection Flow (send findings back to implementer)
- The FO informs the captain: "Validation rejected 033 — sending back to implementer with findings: [brief summary]"
- The captain can intervene if they disagree (e.g., "no, close it" or "no, approve it anyway")

When a feedback stage's validator recommends PASSED:
- The FO presents at the gate as today — captain explicitly approves or rejects
- This is the consequential path (merge, PR, archive)

The gate guardrail ("NEVER self-approve") still applies to PASSED recommendations. The change is: REJECTED recommendations at feedback stages skip the gate wait.
