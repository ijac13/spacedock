---
title: Use Domain Terminology Instead of "Entity" in Generated Output
status: ideation
source: commission seed
started: 2026-03-23T00:00:00Z
completed:
verdict:
score: 0.76
---

The PTP framework term "entity" leaks into all generated output — status script column headers, first-officer instructions, README prose. The user already tells us what to call their work items in Question 2 ("a design idea", "a bug report", etc.). We should use that.

## Problem

When a user says their work items are "design ideas", the generated pipeline still says "entity" everywhere. This makes the output feel generic and framework-flavored instead of domain-native. Concrete examples from the current Spacedock pipeline (entity_description = "a design/implementation task"):

- Status script column header: `ENTITY` (should be `TASK`)
- Status script variable: `entity=$(basename "$f" .md)` (cosmetic — internal, but still confusing if user reads the script)
- Status template comment: `# goal: Show one-line-per-entity pipeline overview` (should use label)
- README: "Each entity is a markdown file..." (9 occurrences of "entity" in generated README)
- README section header: `## Entity Template` (should be `## Task Template`)
- README field reference: "Human-readable entity name" (should be "Human-readable task name")
- README template body: `title: Entity name here` (should be `title: Task name here`)
- README prose: "Description of this entity and what it aims to achieve."
- First-officer prompt: "for each entity that is ready for its next stage" (~20 occurrences in generated first-officer)

## Where "entity" appears in SKILL.md (the generator)

Two categories:

**1. Internal PTP terminology (keep as-is):** The SKILL.md itself uses "entity" when describing the PTP framework to the LLM doing the generation. These are instructions *to* the generator, not output *from* the generator. Examples: "each file is a work entity", "seed entities", `{entity_description}`, `{seed_entities}`. These stay — they're the framework's own vocabulary.

**2. Template text that ends up in generated files (change to use label):** Text inside the README template, status template, and first-officer template that gets copied verbatim into the user's pipeline. These are the targets.

### Exhaustive list of generated-output occurrences in SKILL.md templates

**README template (section 2a):**
- Line 195: `Each entity is a markdown file named...`
- Line 199: `Every entity file has YAML frontmatter...`
- Line 219: `Human-readable entity name`
- Line 221: `Where this entity came from`
- Line 223: `When the entity reached terminal status`
- Line 234: `what it means for an entity to be in this stage`
- Line 262: `## Entity Template`
- Line 266: `title: Entity name here`
- Line 276: `Description of this entity and what it aims to achieve.`
- Line 282: `entity body updates`

**Status template (templates/status):**
- Line 5: `# goal: Show one-line-per-entity pipeline overview`
- Line 25 (generated): `printf ... "ENTITY"` column header

**First-officer template (section 2d):**
- Line 353: `For each entity that is ready for its next stage`
- Line 355: `Identify the entity's current stage`
- Line 361/365/375: `entity frontmatter`, `entity doesn't already have...`, etc.
- ~20 occurrences total in the first-officer template

## Design

### Deriving the label

During Phase 1 after Question 2, extract a short label from `{entity_description}`:

1. Strip leading articles ("a", "an", "the")
2. Strip leading adjectives by taking only the last word (the head noun)
3. Store result as `{entity_label}` (lowercase, singular)

Examples:
- "a design idea" → `idea`
- "a bug report" → `report`
- "a candidate feature" → `feature`
- "an implementation task" → `task`
- "a PR" → `pr`

**Edge case — compound nouns:** "a bug report" should become `report`, not `bug`. The last word is the head noun in English. If the user says just "bug", that's fine too — single word after article stripping stays as-is.

**Edge case — weird/long descriptions:** If the user gives something like "a thing that tracks customer complaints", the heuristic fails. Add a confirmation step: after deriving the label, show it to the user:

> I'll call each work item a **{entity_label}** throughout the pipeline. Sound right?

This costs one extra question but prevents bad labels. It can be combined with the design confirmation step to avoid an extra round-trip — show it in the summary as `**Item label:** {entity_label}` and let the user correct it there.

### Storage

`{entity_label}` is a design-phase variable, same as `{mission}` or `{captain}`. It gets baked into the generated files.

For downstream use (refit, multi-entity support), store in the README frontmatter as a longer descriptive slug:

```yaml
<!-- commissioned-by: spacedock@0.1.2 -->
<!-- entity-type: marketing_campaign_idea -->
<!-- entity-label: idea -->
<!-- entity-label-plural: ideas -->
```

The `entity-type` is a longer slug (snake_case, derived from the full description) that serves as a stable identifier for the entity type. This supports future multi-entity pipelines where a single pipeline might have multiple entity types (e.g., `bug_report` and `feature_request`). The short `entity-label` is for prose substitution; the longer `entity-type` is for programmatic identity.

### Substitution points

Use `{entity_label}` (lowercase) and `{Entity_label}` (capitalized) in templates:

| Location | Before | After (entity_label=idea) |
|----------|--------|---------------------------|
| README: File Naming | "Each entity is a markdown file" | "Each idea is a markdown file" |
| README: Schema intro | "Every entity file has YAML frontmatter" | "Every idea file has YAML frontmatter" |
| README: Field ref title | "Human-readable entity name" | "Human-readable idea name" |
| README: Field ref source | "Where this entity came from" | "Where this idea came from" |
| README: Field ref completed | "When the entity reached terminal status" | "When the idea reached terminal status" |
| README: Stage descriptions | "what it means for an entity to be in this stage" | "what it means for an idea to be in this stage" |
| README: Template header | "## Entity Template" | "## Idea Template" |
| README: Template placeholder | "title: Entity name here" | "title: Idea name here" |
| README: Template body | "Description of this entity..." | "Description of this idea..." |
| README: Commit Discipline | "entity body updates" | "idea body updates" |
| Status: goal comment | "one-line-per-entity" | "one-line-per-idea" |
| Status: column header | "ENTITY" | "IDEA" |
| Status: variable name | `entity=...` | `idea=...` (optional — cosmetic) |
| First-officer: all prose | "entity" → "{entity_label}" throughout |

### What NOT to change

- YAML field names (`status`, `title`, etc.) — these are schema, not prose
- `{entity_description}` variable name in SKILL.md — this is internal framework vocabulary
- `{entity_label}` variable name — this is the mechanism, not the output
- `{seed_entities}` — internal variable
- Git branch/worktree names (`ensign-{entity-slug}`) — these use the slug, not the label
- The word "entity" in SKILL.md instructions to the generator LLM (Phase 1 questions, batch mode docs, etc.)

## Acceptance Criteria

1. After commission, the word "entity" does not appear in any generated file (README, status script, first-officer) except inside `<!-- commissioned-by -->` comments or YAML field names
2. The label is derived from `{entity_description}` and confirmed with the user during the design summary
3. The label is embedded in a README comment (`<!-- entity-label: {label} -->`) for future tooling
4. Status script column header uses `{ENTITY_LABEL}` (uppercased) instead of `ENTITY`
5. All README prose uses `{entity_label}` instead of "entity"
6. First-officer prose uses `{entity_label}` instead of "entity"
7. Existing test harness (if it checks for "entity" strings) is updated to use the label
8. The label derivation handles: single words, multi-word descriptions with articles, and confirms with the user

## Open Questions (resolved)

- **Q: Should we also derive a plural form?** A: Yes — store `{entity_label_plural}` (append "s" by default, confirm with user). Needed for: "Find ideas in a specific stage", "seed entities" → "seed ideas" in generated output. Simple "add s" heuristic works for most English nouns; the confirmation step catches exceptions.
- **Q: Change internal SKILL.md terminology too?** A: No. "Entity" is fine as the PTP framework's own vocabulary. Only generated output changes.
