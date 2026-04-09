---
id: 113
title: Status script misparses quoted YAML IDs
status: backlog
source: CL — observed agent workaround for ID sequencing, 2026-04-09
started:
completed:
verdict:
score:
worktree:
issue:
pr:
---

The status script's NEXT_ID calculation likely mishandles quoted vs unquoted IDs in YAML frontmatter. YAML treats `id: 001` as integer 1 and `id: "001"` as string "001" — if the script doesn't normalize these, it can miscalculate the next available ID or skip entities during scans.

Observed symptom: an agent saw existing entities going up to 010 and chose to start at 011, suggesting the ID sequence was misread (the actual next ID should have been much higher).
