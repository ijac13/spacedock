---
title: Structured stage definitions in README frontmatter
id: 034
status: ideation
source: email-triage feature request + CL
started: 2026-03-25T19:00:00Z
completed:
verdict:
score: 0.75
worktree:
---

Move stage properties (worktree, gate, concurrency, fresh, terminal) from prose bullet points in README stage sections into structured YAML in the README frontmatter. The first officer currently parses prose to extract boolean dispatch properties — fragile and mixes concerns.

## Problem

The first officer's startup step 3 (SKILL.md line 406) says "Parse stage properties — For each stage defined in the README, extract Worktree, Fresh, Approval gate." These are boolean dispatch decisions stored as markdown bullet points inside free-text stage sections. The first officer scans prose to find patterns like `- **Worktree:** Yes` and `- **Approval gate:** No`.

This causes three concrete problems:

1. **Fragile extraction.** The existing deployed first-officer (`.claude/agents/first-officer.md`) uses `Human approval` while the SKILL.md template uses `Approval gate`. The naming has already drifted. Any rewording, reordering, or formatting change in the prose breaks extraction.

2. **Mixed concerns.** Each stage section interleaves dispatch properties (worktree, fresh, gate) with work instructions (inputs, outputs, good/bad). The first officer needs only the former; ensigns need only the latter. Both parse past irrelevant content.

3. **No machine-readable graph.** Stage ordering is implicit (section order). Transitions, concurrency limits, and defaults have no structured representation — they exist only in scattered prose and the Concurrency section.

## Design

Follows the states + transitions pattern from Symfony Workflow and pytransitions — the most battle-tested YAML state machine formats.

```yaml
stages:
  defaults:
    worktree: false
    concurrency: 2
  states:
    - name: backlog
      initial: true
    - name: ideation
      gate: true
    - name: implementation
      worktree: true
    - name: validation
      worktree: true
      fresh: true
      gate: true
    - name: done
      terminal: true
  transitions:
    # omit for linear (inferred from states order)
    # explicit only for non-linear flows:
    - from: validation
      to: implementation
      label: rejected
```

### Gate semantic

`gate: true` on a state means "captain approval required before advancing FROM this state." The gate fires after the ensign completes work in the gated state. This matches the SKILL.md dispatch logic (step 6a: "Read the Approval gate field of the stage the ensign just completed") and the README generation template (line 271: "If this stage is the SOURCE in an approval_gates transition").

In the dogfood pipeline example above:
- `ideation` has `gate: true` — captain reviews the ideation output before advancing to implementation
- `validation` has `gate: true` — captain reviews validation results before advancing to done

Note: The existing dogfood pipeline (`docs/plans/README.md`) places `Human approval: Yes` on the DESTINATION stages (`implementation` and `done`). This is a semantic inconsistency with the SKILL.md dispatch logic that has been working by coincidence (the deployed first-officer at `.claude/agents/first-officer.md` uses different parsing logic). Migration must fix this by moving gates to the correct source states.

### Key decisions

- **States list + transitions list, kept separate.** States have node properties (worktree, fresh, terminal). Transitions have edge properties (label). Follows the pattern every practical state machine schema converges on.
- **`gate` is a state property, not a transition property.** It means "captain approval required before advancing FROM this state." This is cleaner than attaching it to an edge because: (a) approval applies to the state's output regardless of which transition follows, (b) the first officer checks it after the ensign completes, keyed on the state just finished, and (c) the SKILL.md dispatch logic (step 6a) already checks the gate on the completed stage, not the transition.
- **Default transitions inferred from states order.** If `transitions` is omitted, linear chain: states[0] → states[1] → ... → states[n]. If present, it supplements the linear chain with additional edges. Simple pipelines stay simple.
- **`defaults` block** sets baseline properties for all states. Per-state overrides make exceptions visible.
- **`initial` and `terminal` are explicit markers.** `initial: true` on the first state, `terminal: true` on the last. These are redundant for linear pipelines (first/last in the array) but make the schema self-documenting and support future non-linear graphs.
- **`id-style`** stays in README frontmatter at the top level (already implemented in entity-organization).
- **Prose stage sections remain** for work instructions (inputs, outputs, good/bad criteria) — these are for ensigns, not the first officer.
- **Concurrency moves to `defaults` block** and can be overridden per-state. The separate `## Concurrency` prose section in the README becomes redundant for the first officer (though it can remain as human-readable documentation).

### Naming note

The feature request (`/tmp/spacedock-feature-request.md`) uses `pipeline` as the list key. The entity design uses `states`. Sticking with `states` — it's the standard term in state machine literature and avoids overloading `pipeline` (which is the whole directory).

The feature request uses `gate: true` on states. The entity design also puts gate on states. The SKILL.md template currently uses `Approval gate` in prose. Standardizing to `gate` in the structured block.

### State property reference

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `name` | string | required | Stage name (must match the `### name` prose section heading) |
| `initial` | bool | false | First stage — entities start here |
| `terminal` | bool | false | Final stage — entities are archived when they reach here |
| `worktree` | bool | from defaults | Stage work runs in a git worktree |
| `fresh` | bool | false | Dispatch a fresh ensign (no context from prior stages) |
| `gate` | bool | false | Captain approval required before advancing from this stage |
| `concurrency` | int | from defaults | Max entities in this stage simultaneously |

### Transition property reference

| Property | Type | Description |
|----------|------|-------------|
| `from` | string | Source state name |
| `to` | string | Target state name |
| `label` | string | Human-readable label for the edge (e.g., "rejected") |

### Impact

- **First officer startup** simplifies from "parse stage properties from prose" to "read `stages` from README frontmatter"
- **Commission skill** collects stage names and properties during interview, writes structured YAML
- **README stage sections** drop the Worktree/Gate/Fresh/Human approval bullets (moved to frontmatter), keep only work instructions (Inputs, Outputs, Good, Bad)
- **Mermaid/Graphviz visualization** becomes trivial to generate from the structured data
- **Refit skill** (`skills/refit/SKILL.md` line 85) currently looks for `Human approval: Yes` in prose — will need updating to read frontmatter

### Future: DOT diagram (not in scope for this entity)

A DOT digraph can be generated from the YAML and embedded in the README body as a visual aid. When we add this:
- YAML frontmatter is the SSOT for the pipeline graph
- DOT diagram is a rendered view, not authoritative
- If the user changes the workflow, the first officer (or a refit command) must regenerate the DOT to keep it in sync
- The instruction set should explicitly document this: "edit the frontmatter stages block, then regenerate the diagram"

## Acceptance Criteria

### AC1: README frontmatter schema

The `stages` block is added to README YAML frontmatter, below the existing fields (`commissioned-by`, `entity-type`, `entity-label`, `entity-label-plural`, `id-style`).

Exact schema:

```yaml
---
commissioned-by: spacedock@{spacedock_version}
entity-type: {entity_type}
entity-label: {entity_label}
entity-label-plural: {entity_label_plural}
id-style: sequential
stages:
  defaults:
    worktree: false
    concurrency: 2
  states:
    - name: {stage_name}
      initial: true
    - name: {stage_name}
      # per-stage overrides only when different from defaults
    - name: {stage_name}
      terminal: true
  transitions:
    # omitted for linear pipelines
    # explicit entries only for non-linear edges
---
```

Rules:
- `defaults.worktree` defaults to `false` if not specified by captain
- `defaults.concurrency` defaults to `2` if not specified by captain
- Per-state properties are only written when they differ from defaults (except `initial`, `terminal`, `gate`, `fresh` which have no default override — they're always explicit when true)
- `transitions` block is omitted entirely for linear pipelines
- Boolean values use YAML `true`/`false`, not `Yes`/`No`

### AC2: SKILL.md README generation template changes

In `skills/commission/SKILL.md` section "2a. Generate `{dir}/README.md`":

1. **Add `stages` block to frontmatter template** (after `id-style: sequential`).
2. **Remove dispatch-property bullets from stage section template.** The per-stage template currently has:
   - `- **Worktree:** ...` (line 269)
   - `- **Fresh:** ...` (line 270)
   - `- **Approval gate:** ...` (line 271)

   These are replaced by the `stages` frontmatter block. The stage prose sections keep only:
   - `- **Inputs:** ...`
   - `- **Outputs:** ...`
   - `- **Good:** ...`
   - `- **Bad:** ...`

3. **Remove the separate `## Concurrency` section** from the README template (lines 319-322). Concurrency is now in `stages.defaults.concurrency` (and per-state overrides). The README can include a brief note that concurrency is configured in frontmatter, or just drop the section entirely.

### AC3: SKILL.md first-officer template changes

In `skills/commission/SKILL.md` section "2d. Generate First-Officer Agent":

1. **Startup step 3** (line 406-409): Replace "Parse stage properties — For each stage defined in the README, extract Worktree, Fresh, Approval gate" with "Read the `stages` block from README frontmatter. This gives you the state machine: stage names, ordering, per-stage properties (worktree, fresh, gate, concurrency), defaults, and any non-linear transitions."

2. **Startup step 4** (line 411): Replace "Read concurrency limit — Find the `## Concurrency` section" with "Concurrency is already in the `stages` block read in step 3 (`defaults.concurrency`, with optional per-state overrides)." This step can be merged into step 3 or removed.

3. **Dispatching step 2** (line 420): Currently says to read the full stage subsection including "Worktree, Fresh, Approval gate" bullets. Update to: "Read the next stage's prose subsection from the README for the ensign prompt (Inputs, Outputs, Good, Bad). Read the stage's dispatch properties from the `stages` frontmatter block."

4. **Dispatching step 5** (line 423): Currently says "Read the next stage's `Worktree` field from the README." Update to: "Read the next stage's `worktree` property from the `stages` frontmatter block."

5. **After dispatch step 6a** (line 498): Currently says "Read the `Approval gate` field of the stage the ensign just completed." Update to: "Read the `gate` property of the completed stage from the `stages` frontmatter block."

6. **Ensign reuse logic** (lines 503-504): Currently references `Worktree` mode and `Fresh: Yes` from prose. Update to reference `worktree` and `fresh` properties from frontmatter.

### AC4: Prose stage sections — what stays vs moves

**Stays in prose (ensign instructions):**
- `### {stage_name}` heading and description sentence
- `- **Inputs:** ...`
- `- **Outputs:** ...`
- `- **Good:** ...`
- `- **Bad:** ...`

**Moves to frontmatter (dispatch properties):**
- `- **Worktree:** Yes/No` → `worktree: true/false` in states list
- `- **Fresh:** Yes` → `fresh: true` in states list
- `- **Approval gate:** Yes/No` → `gate: true` in states list
- `- **Human approval:** Yes/No` → same (this is the old name used in the dogfood pipeline)
- Concurrency limit → `concurrency` in defaults/per-state

### AC5: Commission interview changes

The commission interview does NOT need new questions. The existing flow already collects:
- Stage names and ordering (Question 2)
- Approval gates (derived in "Confirm Design")

The commission skill's generation phase already knows which stages need worktrees (stages that modify code) and which need fresh dispatch (validation stages). These are currently inferred and written as prose bullets — the same inference just writes structured YAML instead.

One minor change: if we want to support per-stage concurrency overrides or explicit non-linear transitions, those would need new questions. But per YAGNI, the defaults (worktree inferred from stage purpose, concurrency=2, linear transitions) cover v0. Non-linear transitions can be added by editing the README frontmatter directly.

### AC6: Migration path

**This pipeline (`docs/plans/README.md`):**
1. Convert HTML comment frontmatter to YAML frontmatter (the dogfood pipeline predates the YAML frontmatter convention)
2. Add `stages` block reflecting current stage definitions
3. Remove `Worktree:`, `Human approval:` bullets from stage prose sections
4. Remove `## Concurrency` section (or replace with a note pointing to frontmatter)

Migrated frontmatter for this pipeline:

```yaml
---
commissioned-by: spacedock@0.2.1
entity-type: entity
entity-label: entity
entity-label-plural: entities
id-style: sequential
stages:
  defaults:
    worktree: false
    concurrency: 2
  states:
    - name: backlog
      initial: true
    - name: ideation
      gate: true
    - name: implementation
      worktree: true
    - name: validation
      worktree: true
      fresh: true
      gate: true
    - name: done
      terminal: true
---
```

**The deployed first-officer (`.claude/agents/first-officer.md`):**
- Update startup step to read from frontmatter instead of parsing `Human approval` from prose
- This file is generated per-pipeline, so the template change in SKILL.md handles future pipelines; the existing deployed file needs a one-time manual update (or refit)

**Other commissioned pipelines (outside this repo):**
- Pipelines without a `stages` block continue to work — the first officer falls back to prose parsing. This is backward compatibility, not a feature to maintain long-term. The refit skill should flag these as needing migration.

### AC7: Backward compatibility

When a pipeline README has no `stages` block in frontmatter:
- The first officer template should include a fallback: "If `stages` is not present in frontmatter, parse stage properties from prose sections (Worktree, Fresh, Approval gate / Human approval bullets)."
- This is a transitional measure. The refit skill should recommend adding the `stages` block.
- New pipelines commissioned after this change always get the `stages` block.

## Edge Cases

### Two-stage pipeline
A pipeline with only 2 stages (e.g., `intake` → `done`) works fine:
```yaml
stages:
  states:
    - name: intake
      initial: true
    - name: done
      terminal: true
```
Linear transitions inferred: intake → done. No transitions block needed. Defaults apply.

### Defaults block — which properties can be defaulted
- `worktree`: yes (most common default is `false`)
- `concurrency`: yes (most common default is `2`)
- `fresh`: no — `fresh` is an exceptional property (only validation-type stages). Defaulting it to `true` would be unusual. Keep it per-state only.
- `gate`: no — gates are exceptional. Defaulting all stages to gated would be impractical.
- `initial`/`terminal`: no — these are structural markers, not defaults.

### Gate as a state property vs transition property
Gate is correctly a state property. Reasoning:
- The first officer checks gate AFTER an ensign completes a stage (SKILL.md step 6a: "Read the Approval gate field of the stage the ensign just completed").
- Gate means "captain reviews this stage's output before the entity advances." It's a property of the state's exit, not of a specific transition.
- If a state has multiple outbound transitions (e.g., validation → done or validation → implementation), the gate applies to ALL of them — captain decides which transition to take.
- Putting gate on transitions would require duplicating it on every outbound edge from a gated state.

### id-style coexistence
`id-style` stays at the top level of README frontmatter, outside the `stages` block. They're orthogonal concerns:
- `id-style` controls entity identification (sequential, uuid, etc.)
- `stages` controls the state machine

No interaction between them.

### transitions block interaction with gates
The `transitions` block defines non-linear edges (e.g., validation → implementation for rejected work). Gates are orthogonal — a gate on a state applies regardless of which transition is taken from that state. The transitions block doesn't need a `gate` property; it's always read from the source state.

Example: validation has `gate: true`. If captain approves, the entity follows the default linear transition (validation → done). If captain rejects, the entity follows the explicit transition (validation → implementation, label: "rejected"). The gate fires in both cases because it's on the validation state.

## Scope

- Update SKILL.md README frontmatter template to include `stages` block
- Update SKILL.md stage section template to drop dispatch-property bullets
- Update SKILL.md first-officer template to read from frontmatter
- Migrate `docs/plans/README.md` as reference implementation
- Update `.claude/agents/first-officer.md` deployed instance
- Update refit skill (`skills/refit/SKILL.md`) to read from frontmatter
- Add backward-compatibility fallback for pipelines without `stages` block
- Test harness updates for the new README format
