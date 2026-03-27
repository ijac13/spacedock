---
id: 038
title: Add id column to status template
status: done
source: refit gap analysis
started:
completed: 2026-03-27T03:50:00Z
verdict: PASSED
score: 0.5
worktree:
---

The status script template (`templates/status`) does not extract or display the `id` field, even though `id` is a standard schema field in every entity. The template outputs columns: SLUG, STATUS, TITLE, SCORE, SOURCE.

The `docs/plans/` pipeline's status script was manually updated to include an ID column (ID, SLUG, STATUS, TITLE, SCORE, SOURCE), but newly commissioned pipelines won't get it.

Fix: update `templates/status` to extract `id` from frontmatter and include it as the first column. Also update the example output in the description header to show the ID column.
