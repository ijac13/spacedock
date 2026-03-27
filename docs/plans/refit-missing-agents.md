---
id: 056
title: Refit skill does not regenerate ensign or lieutenant agents
status: implementation
source: CL
started: 2026-03-27T08:00:00Z
completed:
verdict:
score:
worktree: .worktrees/ensign-refit-agents
---

The refit skill (`skills/refit/SKILL.md`) regenerates the first-officer and status script but completely ignores the ensign agent and any lieutenant agents. After a refit, `.claude/agents/ensign.md` stays stale — it still has the old version stamp and old content even when `templates/ensign.md` has changed.

## What needs to change

1. Add ensign regeneration to refit Phase 2 classification table and Phase 3 execution
2. Add lieutenant regeneration — scan the README frontmatter for stages with `agent:` properties, regenerate each referenced lieutenant from its template
3. Both should follow the same pattern as the first-officer: sed from template, show diff, ask captain to confirm

## Acceptance Criteria

- [ ] Refit regenerates `.claude/agents/ensign.md` from `templates/ensign.md`
- [ ] Refit regenerates lieutenant agents referenced in README stage definitions from their templates
- [ ] Both show diffs and ask captain for confirmation before replacing
- [ ] Version stamps are updated on regenerated agents
- [ ] Agents not referenced by any stage (orphaned lieutenants) are reported but not deleted

## Stage Report: implementation

- [x] Phase 1: ensign and lieutenant discovery added (version stamp extraction)
  Added items 4 and 5 to Phase 1 Step 2 — ensign reads `ensign.md`, lieutenant scans README `stages.states` for `agent:` properties
- [x] Phase 2: ensign and lieutenant rows added to classification table
  Added rows to both the strategy rationale table and the captain-facing upgrade plan table
- [x] Phase 3d: ensign regeneration section added (sed from template, diff, confirm)
  Section 3d follows the same pattern as 3b — sed `templates/ensign.md` with `__MISSION__`, `__ENTITY_LABEL__`, `__SPACEDOCK_VERSION__`, show diff, wait for confirmation
- [x] Phase 3e: lieutenant regeneration section added (scan README stages, sed from template, diff, confirm, warn if template missing)
  Section 3e iterates over `stages.states` entries with `agent:` property, checks for template existence, handles both existing and new agent files
- [x] Phase 5: summary table updated with ensign and lieutenant rows
  Added `ensign.md` and `{lieutenant}.md` rows between first-officer and README in the finalization summary
- [x] All changes committed
  Commit dcf247c on branch `ensign/refit-agents`

### Summary

Added ensign and lieutenant agent handling to all five phases of the refit skill. The changes follow the same patterns established by the existing first-officer regeneration — sed from template, show diff, ask captain. Degraded Mode stamp-only option was also updated to cover ensign and lieutenant agents. The acceptance criterion about orphaned lieutenants is addressed by the discovery phase noting missing files without attempting deletion.

## Stage Report: validation

- [x] Phase 1: ensign and lieutenant discovery present with version stamp extraction
  SKILL.md lines 34-36: items 4 (ensign) and 5 (lieutenant) added to Step 2, both extract `commissioned-by` version stamps
- [x] Phase 2: classification table includes ensign and lieutenant with Regenerate strategy
  SKILL.md lines 60-61 (strategy rationale) and lines 72-73 (captain-facing upgrade plan) both include ensign and lieutenant rows
- [x] Phase 3d: ensign regeneration follows first-officer pattern (sed, diff, confirm)
  SKILL.md lines 153-171: extracts Mission and Entity label, sed substitutes `__MISSION__`, `__ENTITY_LABEL__`, `__SPACEDOCK_VERSION__` — all three match the actual `templates/ensign.md` variables exactly
- [x] Phase 3e: lieutenant regeneration scans README stages, handles missing templates
  SKILL.md lines 175-201: scans `stages.states` for `agent:` properties, warns and skips if template missing, shows diff for existing agents, shows full content for new agents
- [x] Phase 5: summary table includes ensign and lieutenant rows
  SKILL.md lines 259-261: `ensign.md` and `{lieutenant}.md` rows added between first-officer and README
- [x] No other files modified
  `git diff --name-only dcf247c~1..dcf247c` shows only `skills/refit/SKILL.md` changed in the implementation commit
- [x] PASSED recommendation
  Test harness passes 64/64 (no regressions). All five acceptance criteria are addressed: ensign regeneration from template, lieutenant regeneration from README stage references, both show diffs with captain confirmation, version stamps updated via sed `__SPACEDOCK_VERSION__`, and orphaned lieutenants handled by discovery-only (no deletion). Degraded Mode stamp-only also covers ensign and lieutenant agents (lines 291-292).

### Summary

Validated the refit skill changes against all acceptance criteria. The implementation correctly mirrors the existing first-officer regeneration pattern for both ensign and lieutenant agents across all five phases, including Degraded Mode. Template variable substitution (`__MISSION__`, `__ENTITY_LABEL__`, `__SPACEDOCK_VERSION__`) matches the actual `templates/ensign.md` markers exactly. Lieutenant handling gracefully degrades when templates are missing. The commission test harness passes 64/64 with no regressions. Recommendation: PASSED.
