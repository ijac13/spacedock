---
id: 108
title: Cross-file deduplication in FO reference files
status: validation
source: CL — PR #57
started: 2026-04-09T18:16:10Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-cross-file-dedup-fo-references
issue:
pr: "#57"
---

PR #57 proposes cross-file deduplication in FO reference files. Needs E2E testing on both haiku and opus/low to verify behavior is preserved after the dedup.

## Acceptance criteria

1. E2E tests pass on haiku model
2. E2E tests pass on opus model with low effort
3. No behavioral regression from the deduplication
