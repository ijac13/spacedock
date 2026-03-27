---
id: 047
title: Checklist as scannable gate artifact
status: ideation
source: adoption feedback, CL
started: 2026-03-27T00:00:00Z
completed:
verdict:
score: 0.75
worktree:
---

The current checklist review has the first officer doing 2-3 rounds of SendMessage back-and-forth per ensign per stage: check completeness, challenge skip rationales, triage failures. Each round eats tokens and risks the first officer losing track of overall pipeline state while deep in one entity's checklist negotiation.

Instead: the ensign writes the structured completion report into the entity file body. The first officer reads it once and presents it to the captain at the gate. Skip rationale judgment moves to the gate review with the captain, rather than the first officer playing arbiter alone.

One read, no negotiation rounds.

Motivated by adoption feedback: "Make the checklist a gate artifact, not a conversation."

Also incorporates task 044 (checklist report format): the format should be tight and scannable — not prose-heavy. Status markers (DONE/SKIPPED/FAILED) at a glance, not buried in paragraphs. Domain-agnostic — a legal review pipeline and a software dev pipeline use the same report structure. Reference: superpowers plugin patterns (status enums, emoji markers, bullet lists with specific references).

Questions to explore:
- What's the right structural format for checklist items + status + evidence?
- How verbose should evidence be? One-line reference vs. paragraph?
- Should the first officer's gate report to the captain use the same format or a summarized view?
