---
title: Fix approval gate placement and ensign lifecycle at gates
status: ideation
source: testflight sd6-test observation
started: 2026-03-24T03:30:00Z
completed:
verdict:
score: 0.88
worktree:
---

Two related issues with approval gate behavior observed in sd6-test commission.

## Bug: Approval gates placed on wrong stage

User specifies `approval gates: interview-prep -> interview, synthesis -> done`. The intent: review the OUTPUT of interview-prep before interview runs.

The generated README puts `Human approval: Yes` on `interview-prep` (the source), not `interview` (the target). The first-officer checks the NEXT stage's approval field before dispatching. So the gate fires BEFORE interview-prep work starts (user approves a blank entity) instead of AFTER (user reviews the persona/script). The user never sees the work before the interview runs.

The SKILL.md template instruction is correct: "If the transition INTO this stage is in approval_gates: Yes". But the LLM interprets "interview-prep -> interview" as "interview-prep has the gate" instead of "the transition into interview is gated."

## Enhancement: Ensign lifecycle at approval gates

Currently ensigns go idle after completing stage work — no explicit shutdown. The first-officer should manage ensign lifecycle based on approval gates:

- If outbound transition is approval-gated: keep ensign alive. CL may have questions, or reject and want the same ensign to redo with feedback (it has full context).
- If not gated: shutdown the ensign immediately. No review needed, free resources.
- On rejection + redo: send feedback to the SAME ensign rather than spawning a fresh one.
