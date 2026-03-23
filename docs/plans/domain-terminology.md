---
title: Use Domain Terminology Instead of "Entity" in Generated Output
status: ideation
source: commission seed
started:
completed:
verdict:
score: 0.76
---

The PTP framework term "entity" leaks into all generated output — status script column headers, first-officer instructions, README prose. The user already tells us what to call their work items in Question 2 ("a design idea", "a bug report", etc.). We should use that.

## Proposal

Derive a short label from `{entity_description}` during the design phase:
- "a design idea" → `idea`
- "a bug report" → `bug`
- "a candidate feature" → `feature`

Store as `{entity_label}` and substitute throughout generated files:
- Status script: `IDEA` column instead of `ENTITY`
- First-officer: "for each idea ready for the next stage"
- README: "Each idea is a markdown file..."
- Entity template section header: "Idea Template"

"Entity" becomes an internal PTP concept that never surfaces in generated pipelines.
