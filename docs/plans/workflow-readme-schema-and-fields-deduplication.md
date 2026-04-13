---
id: 144
title: "Workflow README — `## Schema` YAML and `### Field Reference` table are redundant"
status: backlog
source: CL observation on a fresh commissioned workflow README during 2026-04-13 session
started:
completed:
verdict:
score: 0.45
worktree:
issue:
pr:
---

A freshly commissioned workflow README emits two adjacent sections that describe the same per-entity fields:

1. `## Schema` — a YAML frontmatter block that lists every field with an empty value, e.g.

   ```yaml
   id:
   title: Human-readable name
   status: backlog
   source:
   ...
   ```

2. `### Field Reference` — a table that lists the same fields again with `Field | Type | Description` columns.

The duplication is observable in `docs/plans/README.md` (this very workflow) but it ships from the `commission` skill, so every newly commissioned workflow inherits it. Maintainers have to update fields in two places, and readers see the same information twice.

This task should pick one canonical representation in the commission skill's emitted README template and remove the other. Candidates:

- Keep the `### Field Reference` table only — richer (Type column, longer descriptions) and more discoverable for someone scanning the doc.
- Keep the `## Schema` YAML block only — closer to the actual on-disk shape; can serve as a copy-paste template.
- Keep both but clearly mark one as authoritative and the other as derived (the "## Task Template" section near the bottom of the README is already a copy-paste template, so the YAML in `## Schema` is the redundant copy).

The likely answer is to drop the YAML block from `## Schema` and let the `## Task Template` section near the bottom serve as the copy-paste shape. `## Schema` becomes an introductory sentence pointing at the table.

Scope:

- Edit the README template in the commission skill so future workflows ship with one representation.
- Decide whether to retroactively fix `docs/plans/README.md` and any other already-commissioned workflows in the repo, or leave them.
- Static test (or doc lint) asserting the emitted README does not duplicate field listings.
