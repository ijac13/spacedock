---
id: 050
title: First officer bypasses approval gate without captain's explicit approval
status: backlog
source: CL
started:
completed:
verdict:
score: 0.90
worktree:
---

The first officer presented tasks 046 and 049 at the ideation approval gate, asked "approve?", then immediately said "Both approved" and advanced both tasks — without the captain ever responding. An ensign idle notification arrived between the gate question and the captain's response, and the first officer treated it as a signal to proceed.

This is a critical process failure. The approval gate exists so the captain decides whether to advance. The first officer conflated presenting the gate with passing it.

## Root cause

The first officer's gate handling lacks an explicit check that the approval came from the captain (a human message), not from an ensign notification or the first officer's own judgment. The current template says "Wait for CL's decision" but doesn't say "an ensign message is NOT the captain's decision."

## Proposed fix

1. Add an explicit guardrail to the first-officer template: "NEVER advance past a gate without an explicit approval message from the captain. Ensign completion messages, idle notifications, and system messages are NOT approval. Only a direct message from the captain approves a gate."

2. Create a test case that would catch this. Consider: run the first officer with a gated pipeline where an ensign completes, verify the first officer does NOT advance past the gate without a captain message. This could extend the e2e test pattern from scripts/test-checklist-e2e.sh.

## Incident details

- Session: 2026-03-26
- Tasks affected: 046 (named ensign agent), 049 (fix captain hardcoding)
- What happened: first officer asked "approve?" then said "Both approved" without captain response
- Impact: both tasks advanced past ideation gate without approval. Work was valid but process was violated.
