---
title: Lazy Materialization for View Scripts
status: ideation
source: commission seed
started:
completed:
verdict:
score: 0.88
---

Instead of pre-generating status script implementations during commission, generate only the self-describing header (goal, instruction, constraints, valid status values) with a stub that errors out:

```bash
echo "This view is not yet materialized." >&2
exit 1
```

On first run, the user (or an agent) materializes it — reads the description and generates a working implementation. This keeps the PTP philosophy clean: English description is the spec, implementation is derived from it.

## Why

- Commission becomes simpler (no bash template to maintain in the skill)
- The self-describing header is the single source of truth
- Implementation can be regenerated from description if it drifts or breaks
- Different environments can materialize differently (bash 3 vs 4, macOS vs Linux)
- First-officer could auto-materialize views on startup as part of its bootstrap

## Impact on commission skill

Remove the bash template from SKILL.md. Replace with: generate the self-describing header + stub, mark as unmaterialized. The first-officer or pilot materializes it when first needed.
