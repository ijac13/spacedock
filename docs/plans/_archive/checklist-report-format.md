---
id: 044
title: Tighten checklist report format for scannability
status: done
source: CL
started:
completed: 2026-03-27T03:20:00Z
verdict: PASSED
score: 0.75
worktree:
---

The current checklist completion reports from ensigns are paragraph-heavy — status words like "DONE" are buried in prose. The format should be an actual scannable checklist, not an essay with status markers scattered in.

Reference: superpowers plugin uses tight, scannable formats — status enums (DONE/DONE_WITH_CONCERNS/BLOCKED/NEEDS_CONTEXT), emoji markers (checkmark/cross), bullet lists with specific references. Our reports should be similarly quick to parse at a glance.

Key constraint: the commissioned README can be domain-specific (not just software development). The checklist format is about the structural level — how items and their statuses are presented — not the actual checklist content. A legal review pipeline and a software dev pipeline should use the same report structure, just with different items. Design the format at the template level (first-officer template, ensign prompt), not tied to any specific domain.

Questions to explore:
- What's the right structural format for checklist items + status + evidence?
- How verbose should evidence be? One-line reference vs. paragraph?
- Should the first officer's gate report to the captain use the same format or a summarized view?
- How do status enums interact with the existing DONE/SKIPPED/FAILED markers?
