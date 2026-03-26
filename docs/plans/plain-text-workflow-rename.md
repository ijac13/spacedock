---
id: 041
title: Rename PTP to plain text workflow throughout codebase
status: implementation
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

## Implementation Summary

Updated 5 files, 80 line replacements (balanced insertions/deletions):

### `skills/commission/SKILL.md`
- ABOUTME: "PTP pipeline" -> "plain text workflow"
- Skill description: removed PTP references, uses "workflow" throughout
- Heading: "Commission a PTP Pipeline" -> "Commission a Plain Text Workflow"
- Greeting: "Plain Text Pipeline (PTP)" -> "plain text workflow"
- All user-facing prose: "pipeline" -> "workflow" (design phases, questions, confirm, generate, pilot)
- README template (section 2a): "Pipeline State" -> "Workflow State", "pipeline" -> "workflow" in prose, "Pipelines can upgrade" -> "Workflows can upgrade"
- Template variables like `{entity_label}` already used throughout — no hardcoded "entity" instances found in the template prose

### `skills/refit/SKILL.md`
- ABOUTME: "PTP pipeline" -> "workflow"
- Skill description: "PTP pipeline" -> "workflow"
- Heading: "Refit a PTP Pipeline" -> "Refit a Workflow"
- All prose references: "pipeline directory" -> "workflow directory", "Pipeline-specific" -> "Workflow-specific", etc.
- Preserved `## Pipeline Path` section reference (points to first-officer template section name)

### `v0/test-commission.sh`
- Test prompt: "PTP pipelines" -> "plain text workflows"
- Seed entity descriptions: "existing pipelines" -> "existing workflows", "interconnected pipelines" -> "interconnected workflows"
- Comment: "pre-stages pipelines" -> "pre-stages workflows"

### `v0/test-harness.md`
- Test prompt: same changes as test-commission.sh
- Section reference: "Pipeline State" -> "Workflow State"
- Prose: "follow the pipeline" -> "follow the workflow"

### `references/codex-tools.md`
- ABOUTME: "PTP pipeline" -> "plain text workflow"
- Heading: removed "PTP" from title
- All PTP references replaced with "workflow"
- Solo operator prompt: "pipeline schema" -> "workflow schema"

### Not modified (per scope)
- `v0/spec.md` — historical spec
- `templates/first-officer.md` — not in scope; still uses "pipeline" in template text
- `.claude/agents/` — excluded per instructions
- Archived entities
