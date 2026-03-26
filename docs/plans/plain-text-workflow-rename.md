---
id: 041
title: Rename PTP to plain text workflow throughout codebase
status: validation
source: CL
started: 2026-03-26T17:10:00Z
completed:
verdict:
score: 0.85
worktree: .worktrees/ensign-ptp-rename
---

## Problem

The codebase uses "PTP (Plain Text Pipeline)" as the core term, but the project README now frames Spacedock as creating "plain text workflows." The commission skill greeting still says "We're going to design a Plain Text Pipeline (PTP) together" — that's the first thing users see. A fresh commission generates READMEs with "entity" and "pipeline" terminology instead of "task" and "workflow."

## Scope

### User-facing (must update)

1. **`skills/commission/SKILL.md`** — greeting, skill description, README template (section 2a), and all generated output should use "workflow" instead of "pipeline" and the entity label instead of hardcoded "entity"
2. **`skills/refit/SKILL.md`** — ABOUTME, description, heading

### Internal (update for consistency)

3. **`v0/test-commission.sh`** — test prompt mentions "PTP pipelines"
4. **`v0/test-harness.md`** — test prompt mentions "PTP pipelines"
5. **`references/codex-tools.md`** — codex reference uses PTP extensively

### Leave as-is

- `v0/spec.md` — historical spec, PTP is fine
- Archived entities — historical records
- Active entities that discuss PTP as a concept (e.g., pipeline-catalog.md)

## Acceptance Criteria

1. Commission skill greeting uses "plain text workflow" not "PTP pipeline"
2. Freshly commissioned README uses "task" (or the user's entity label) instead of hardcoded "entity"
3. Freshly commissioned README uses "workflow" instead of "pipeline" in prose
4. Refit skill description uses "workflow" not "PTP pipeline"
5. Test harness and test script updated to match
6. Commission test harness still passes (59 checks)
