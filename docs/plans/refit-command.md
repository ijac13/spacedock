---
title: Refit Command
status: ideation
source: commission seed
started: 2026-03-22T00:00:00Z
worktree: .worktrees/pilot-refit-command
completed:
verdict:
score: 15
---

## Problem

As Spacedock evolves, pipelines commissioned with older versions fall behind. The status script might gain features, the README template might improve, the first-officer agent prompt might get smarter. Users need a way to upgrade their pipelines without losing their customizations — custom stages, modified scoring rubrics, additional schema fields. Manual upgrades are error-prone and tedious.

## Proposed Approach

1. **`/spacedock refit` skill** that takes a pipeline directory path and upgrades it.

2. **Three-way diff strategy:**
   - A: What Spacedock generated at commission time (reconstructed from version stamp + templates)
   - B: What the user has now (current files on disk)
   - C: What Spacedock would generate today (current templates)
   - Apply changes from A→C that don't conflict with A→B (user changes).

3. **Depends on version recording** (see `record-spacedock-version-used-for-the-commission`). Without the version stamp, refit can't reconstruct the baseline and must fall back to a simpler "show diff, let user decide" mode.

4. **Scope for first implementation:**
   - Upgrade the status script (replace entirely — users rarely customize it)
   - Upgrade the first-officer agent prompt (replace entirely unless user modified it)
   - Show diff for README changes (user likely customized stages/schema)
   - Do not touch entity files — those are user data

5. **Not in v0.** The spec explicitly defers this. Design now, implement when version recording is in place.

## Acceptance Criteria

- [ ] Design covers: detection of commissioned version, three-way diff strategy, conflict resolution
- [ ] Defines which files are "safe to replace" vs "show diff for user review"
- [ ] Handles the case where no version stamp exists (pre-refit pipelines)
- [ ] Does not modify entity files
- [ ] Skill definition is drafted (inputs, outputs, interactive flow)

## Scoring Breakdown

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Edge | 3 | Non-destructive upgrades are table stakes for mature tools |
| Fitness | 3 | Important for longevity, not urgent for v0 |
| Parsimony | 2 | Three-way diff is inherently complex |
| Testability | 3 | Can test with known before/after states |
| Novelty | 4 | Applying three-way merge to agent prompt templates is interesting |
