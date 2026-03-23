---
title: Address Human Partner as Captain by Default
status: ideation
source: commission seed
started:
completed:
verdict:
score: 0.68
---

Generated agents (first-officer, pilots) currently inherit whatever the user's CLAUDE.md says about how to address the human partner. This leaks personal config into generated pipelines.

## Proposal

Default to "captain" as the term of address in all generated agent prompts — fits the nautical theme (first officer reports to the captain).

During commission, add a lightweight preference question or note:
- "The first officer will address you as 'captain' — want a different title?"
- Store as `{captain_title}` and substitute into generated agent prompts

This makes pipelines portable (not dependent on the user's CLAUDE.md) while keeping the Spacedock personality consistent.
