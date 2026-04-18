---
id: 193
title: "Separate acceptance criteria (entity-level) from checklist (stage-level)"
status: ideation
source: "captain observation during #186 gate-review triage — current practice conflates 'acceptance criteria' (when the task is done) with 'checklist' (what this dispatch does). Ensigns treat AC items as stage-level todos, making 'defer to validation' feel legitimate even when the AC belongs to the overall entity. Cleaner separation: AC lives at entity level (properties of the final outcome), checklist lives at stage level (mechanical steps for this dispatch)."
started: 2026-04-18T05:50:46Z
completed:
verdict:
score: 0.7
worktree:
issue:
pr:
mod-block:
---

## Why this matters

Today both `docs/plans/README.md` and `skills/first-officer/references/first-officer-shared-core.md` use "acceptance criteria" as a term, and the FO builds dispatch checklists from "stage outputs and entity acceptance criteria" (shared-core line 60). In practice this conflates two different concepts:

- **AC (entity-level):** "when is THIS TASK done?" — properties of the final deliverable or outcome. Verifiable from the entity's end state regardless of which stage ran. Example: "Branch on main shows `OPUS_MODEL ?= opus`" or "`test_standing_teammate_spawn` passes on opus-4-7."
- **Checklist (stage-level):** "what does THIS DISPATCH do?" — mechanical steps for this specific invocation. Example: "run make test-live-claude-opus, capture fo-log citations, revert if red." Doesn't persist past the dispatch.

When the two are conflated, problems follow:

1. **Ensigns treat ACs as stage-level to-dos** and feel free to "defer" one to a later stage — but an entity-level AC is a property of done-ness, not a task, so deferral makes no sense.
2. **Gate reviews check stage-reports against stage-AC lists** instead of against entity-AC coverage, missing ACs that span stages.
3. **Entity body growth is uneven** — some ACs are properly entity-level ("file exists at path X"), others are really ideation/implementation to-do items ("run diagnosis 3×") that shouldn't be ACs at all.
4. **Validation lacks a clean contract** — is it checking "every AC has evidence from some stage" or "every AC was verified in validation specifically"? Unclear today.

**Concrete example from this session:** #186 cycle-2 ideation wrote AC-5 as "3× `test_standing_teammate_spawn` runs on opus-4-7." The ensign read that as "work to do during implementation" and deferred it. If AC-5 had been framed as the entity-level property "`test_standing_teammate_spawn` passes reliably on opus-4-7," the deferral wouldn't have made sense — the ENTITY isn't done until that holds, regardless of which stage verifies it.

## Proposed approach (to be refined in ideation)

### Core distinction

- **AC** = properties of the deliverable/outcome. "Task is done when …"
- **Checklist** = per-dispatch mechanical steps. "For this stage, do …"
- **Stage outputs** (workflow README) describe what each stage must produce — feed both AC coverage and checklist items but are neither.

### Where the distinction lives

Ideation to decide:
- **In the workflow README** — update stage definitions and entity template to reflect that ACs are entity-level properties
- **In shared-core** — update dispatch contract (currently line 60 says "Build a numbered checklist from stage outputs and entity acceptance criteria") to clarify how ACs inform checklists without being them
- **In the entity template** — the seed entity YAML/markdown should have an explicit "Acceptance criteria (entity-level)" section and a convention for where per-stage checklists live (they're dispatch inputs, maybe not in the entity body at all)

### Validation semantics

Validation's job becomes clearly: "pull every entity-level AC from the entity body; confirm evidence exists for each across the stage reports." Not "did this stage verify its own AC list."

### Gate review semantics

FO at every gate: "has the stage moved the entity closer to satisfying every relevant AC? Is there a named AC left unaddressed that this stage was the right place to address?" Not "did the stage complete all items in its dispatch checklist."

## Workflow-specific latitude

This separation is strict in how the terms are used, but different workflows may choose different conventions for:
- How rich entity-level ACs should be (some workflows might use them lightly, others rigorously)
- Whether ACs should be numbered, labeled, or prose
- Whether stage outputs should be separate from ACs or embedded

Ideation should propose a DEFAULT convention shipped in the commission scaffold while leaving clear override points in the workflow README frontmatter (similar to #192's `dispatch.checklist.max-items` override).

## Questions for ideation

1. **Entity template shape** — should `docs/plans/README.md` stipulate a specific "Acceptance criteria" section with a specific format in entity bodies? Or keep it loose?
2. **Migration** — existing entities (this session filed 7+) mix the concepts. Do we retrofit or let them age out?
3. **Per-stage AC subset** — sometimes an AC genuinely belongs to a specific stage (e.g., "ideation produces a test plan"). How does that fit the entity-level framing? Stage outputs? Or a sub-section of ACs flagged by stage?
4. **Validation's job post-change** — does validation still have its own AC-list, or does it just cross-check entity-level ACs across all prior stages?
5. **Interaction with #192** — the 3-item checklist cap. #192 caps the CHECKLIST. This entity clarifies WHY the checklist should be small: because the AC lives separately at entity level. These are distinct but compatible.
6. **Workflow-specific override shape** — what frontmatter key (if any) lets a workflow customize the AC convention?

## Acceptance criteria (entity-level, draft — ideation refines)

**AC-1 (entity-level) — Core distinction documented in shared-core.** `skills/first-officer/references/first-officer-shared-core.md` describes AC as entity-level properties and checklist as per-dispatch mechanical steps; distinct sections for each; line 60's current framing updated.

**AC-2 (entity-level) — Workflow README scaffolds the distinction.** `docs/plans/README.md` (and the commission-generated template) has an entity-body template with an explicit "Acceptance criteria" section format and NO mention of per-stage AC subsets (unless the ideation decides otherwise).

**AC-3 (entity-level) — FO gate-review discipline updated.** `first-officer-shared-core.md`'s completion/gate section adds a cross-check rule: "at gate, review every entity AC against evidence from this stage's report and from prior stages; any AC without evidence is REJECT."

**AC-4 (entity-level) — Commission scaffold emits the updated template.** `skills/commission/SKILL.md` generates new workflows with the entity-template convention. A newly commissioned workflow's sample entity body demonstrates the shape.

**AC-5 (entity-level) — This entity (#193) itself adopts the distinction.** Its own AC list is entity-level (done-when properties), not a mix of todos. Validated at gate.

**AC-6 (entity-level) — Static suite green.** Existing contract tests (commission-generated template, scaffolding guardrails) still pass.

## Test plan (draft — ideation refines)

- **Static:** commission test harness validates new template shape. Scaffolding guardrail tests confirm generated workflows match the new entity-body convention.
- **Behavioral:** commission a sample workflow using the updated skill; verify a dispatched stage produces a stage report that cleanly separates checklist completion from AC coverage.
- **Cost estimate:** ~$2-5 (one commission-harness run + one live sanity dispatch).

## Out of scope

- Retrofitting every existing entity body this session. Entities already in flight or archived stay as-is.
- Per-AC enforcement mechanisms (e.g., "every AC must have a test name"). Could be a follow-up.
- Auto-generating ACs from stage outputs. Different problem.
- Rewiring `claude-team build` to separately accept `acceptance_criteria` vs `checklist` input JSON keys — ideation decides whether that's part of this or a follow-up.

## Cross-references

- **#192** — 3-item checklist cap. Tightly related. #192's checklist cap makes more sense once the AC/checklist distinction is clear. #192 covers HOW to constrain the checklist; #193 covers WHY the checklist is constrained (AC lives elsewhere).
- **#186** — concrete case that surfaced the confusion. AC-5's "3× test_standing_teammate_spawn" was stage-level to-do framed as entity-level AC; ensign deferred it; CI found what AC-5 would have caught.
- **#191** — commission skill UX revisit. Any commission-skill changes here might interact.
- `docs/plans/README.md` — workflow README to update
- `skills/first-officer/references/first-officer-shared-core.md` — dispatch + gate review prose
- `skills/commission/SKILL.md` — generated template
- `skills/commission/bin/claude-team` — may need input-JSON field changes depending on ideation's scope decision
