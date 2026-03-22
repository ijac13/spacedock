<!-- ABOUTME: Skill prompt for /spacedock commission — guides Claude through -->
<!-- ABOUTME: interactive PTP pipeline design, file generation, and pilot run. -->
---
name: commission
description: Interactively design and launch a PTP pipeline
user-invocable: true
---

# Commission a PTP Pipeline

You are commissioning a Plain Text Pipeline (PTP). A PTP is a directory of markdown files with YAML frontmatter, where each file is a work entity that moves through stages. The directory's README is the single source of truth for schema and stages, and a self-describing bash script provides pipeline status views.

This is a v0 shuttle-mode pipeline: one general-purpose pilot agent handles all stages. You will walk CL through interactive design, generate all pipeline files, then launch a pilot run.

Follow these three phases in order. Do not skip or combine phases.

## Batch Mode

If the user provides design inputs in their message (some or all of: mission, entity type, stages, approval gates, seed entities, location):

1. Extract all provided inputs
2. For any missing inputs, infer reasonable defaults based on the mission
3. Skip directly to **Confirm Design** with the assembled inputs
4. If the user says to skip confirmation or auto-approve gates, proceed without asking

This allows non-interactive use: all inputs in one message, straight to generation.

---

## Phase 1: Interactive Design

Ask CL these six questions **one at a time**. Wait for each answer before asking the next question. Do not batch questions.

### Question 1 — Mission

Ask:

> What's this pipeline for?

Expect a one-sentence answer describing the pipeline's purpose. Store as `{mission}`.

### Question 2 — Entity

Ask:

> What does each work item represent? (e.g., "a design idea", "a bug report", "a candidate feature")

Store as `{entity_description}`.

### Question 3 — Stages

Based on the mission, suggest sensible default stages. For example, if the mission is about design work, suggest `ideation → implementation → validation → done`. Format your suggestion as an arrow-separated list.

Ask:

> What stages does an entity go through? Here's my suggestion based on your mission:
>
> `{suggested_stages}`
>
> Want to modify these, or are they good?

Store the final agreed-upon ordered list as `{stages}`. The first stage is `{first_stage}` and the last is `{last_stage}`.

### Question 4 — Approval Gates

List every stage transition (e.g., `ideation → implementation`, `implementation → validation`, etc.) and ask:

> Which of these transitions need your approval before proceeding?
>
> {list each transition with a checkbox}
>
> Mark the ones that should require human approval.

Store the approval-gated transitions as `{approval_gates}`.

### Question 5 — Seed Entities

Ask:

> Give me 2–3 starting items to seed the pipeline. For each, provide:
> - **Title** — short name
> - **Description** — a sentence or two about what this entity is
> - **Source** (optional) — where the idea came from
> - **Score** (optional) — priority score out of 25

Store as `{seed_entities}` — a list of objects with title, description, source, and score.

### Question 6 — Location

Suggest a directory path based on the mission context (e.g., `./pipeline/` for a project-local pipeline).

Ask:

> Where should I create this pipeline? My suggestion:
>
> `{suggested_path}`
>
> This directory will contain the README, status script, and all entity files.

Store the confirmed path as `{dir}`. Resolve it to an absolute path. Also derive `{dir_basename}` (the last path component) for use as the team name.

### Confirm Design

After all six questions, present a summary:

> **Pipeline Design Summary**
>
> - **Mission:** {mission}
> - **Entity:** {entity_description}
> - **Stages:** {stages joined with " → "}
> - **Approval gates:** {approval_gates, or "none"}
> - **Seed entities:** {count} items
>   {for each: "- {title} (score: {score}/25)" or "- {title}" if no score}
> - **Location:** `{dir}`
>
> Ready to generate? (y/n)

Wait for CL to confirm before proceeding to Phase 2. If CL wants changes, revisit the relevant questions.

---

## Phase 2: Generate Pipeline Files

Create the pipeline directory and generate four kinds of files. Use the design answers to fill all templates — no placeholder text should remain in generated files.

```
mkdir -p {dir}
```

Also ensure the agents directory exists:

```
mkdir -p {project_root}/.claude/agents
```

Where `{project_root}` is the root of the project where Claude Code is running (the git root, or cwd if not in a git repo).

### 2a. Generate `{dir}/README.md`

Write the README with ALL of the following sections. Every section is required — do not omit any.

Craft thoughtful, mission-specific content for each stage definition. The inputs, outputs, quality criteria, and anti-patterns should be specific to what this pipeline actually does — not generic placeholders.

If any seed entities include a score, include the Scoring Rubric section. Otherwise omit it.

Use this template structure, filling in all `{variables}` from the design phase:

````markdown
<!-- ABOUTME: Schema and stage definitions for the {mission} pipeline. -->
<!-- ABOUTME: Single source of truth — all agents read this before working. -->

# {mission}

{One paragraph expanding on the mission, describing what this pipeline processes and why.}

## File Naming

Each entity is a markdown file named `{slug}.md` — lowercase, hyphens, no spaces. Example: `my-feature-idea.md`.

## Schema

Every entity file has YAML frontmatter with these fields:

```yaml
---
title: Human-readable name
status: {first_stage}
source:
started:
completed:
verdict:
score:
{any domain-specific fields from CL's answers}
---
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Human-readable entity name |
| `status` | enum | One of: {stages as comma-separated list} |
| `source` | string | Where this entity came from |
| `started` | ISO 8601 | When active work began |
| `completed` | ISO 8601 | When the entity reached terminal status |
| `verdict` | enum | PASSED or REJECTED — set at final stage |
| `score` | number | Priority score out of 25 (optional) |

## Stages

{For EACH stage in the ordered list, generate a subsection:}

### `{stage_name}`

{A sentence describing who sets this status and what it means for an entity to be in this stage.}

- **Inputs:** {What the worker reads to do this stage's work — be specific to the mission}
- **Outputs:** {What the worker produces — be specific to the mission}
- **Good:** {Quality criteria for work done in this stage}
- **Bad:** {Anti-patterns to avoid in this stage}
- **Human approval:** {If this stage's exit transition is in approval_gates: "Yes — {reason}." Otherwise: "No"}

{End of per-stage sections.}

## Scoring Rubric

{ONLY include this section if seed entities have scores. Otherwise omit entirely.}

Each dimension is scored 1–5. Total is the sum, out of 25.

| Dimension | What it measures |
|-----------|-----------------|
| **Edge** | How much competitive advantage or unique insight this provides |
| **Fitness** | How well this fits the pipeline's mission and current priorities |
| **Parsimony** | How simple and focused the approach is |
| **Testability** | How easily the result can be validated |
| **Novelty** | How original or non-obvious the idea is |

## Pipeline State

View the pipeline overview:

```bash
bash {dir}/status
```

Find entities in a specific stage:

```bash
grep -l "status: {stage_name}" {dir}/*.md
```

## Entity Template

```yaml
---
title: Entity name here
status: {first_stage}
source:
started:
completed:
verdict:
score:
---

Description of this entity and what it aims to achieve.
```

## Commit Discipline

- Commit status changes at session end, not on every transition
- Commit research outputs and entity body updates when substantive
````

### 2b. Generate `{dir}/status`

Write the status script and make it executable. This must be real, working bash — not pseudocode.

Fill in the stage names and sort order values from the design phase. The `STAGE_ORDER` associative array maps each stage name to its position (1, 2, 3, ...).

````bash
#!/bin/bash
# The actual program generated below is a version of the description:
#
# goal: Show one-line-per-entity pipeline overview from YAML frontmatter.
# instruction: For every .md file in this directory (excluding README.md),
#   extract status, verdict, score, source from YAML frontmatter.
#   Print table sorted by stage order then score descending.
# constraints: bash only, resolves paths relative to this script, skips README.md.
# valid status values: {stage1}, {stage2}, ..., {last_stage}.

DIR="$(cd "$(dirname "$0")" && pwd)"

declare -A STAGE_ORDER=({for each stage, in order: [{stage_name}]={position} — e.g., [ideation]=1 [implementation]=2 [validation]=3 [done]=4})

printf "%-30s %-20s %-10s %-8s %s\n" "ENTITY" "STATUS" "VERDICT" "SCORE" "SOURCE"
printf "%-30s %-20s %-10s %-8s %s\n" "------" "------" "-------" "-----" "------"

for f in "$DIR"/*.md; do
  [ "$(basename "$f")" = "README.md" ] && continue
  entity=$(basename "$f" .md)
  status="" verdict="" score="" source=""
  in_fm=false
  while IFS= read -r line; do
    if [ "$line" = "---" ]; then
      if $in_fm; then break; fi
      in_fm=true; continue
    fi
    if $in_fm; then
      case "$line" in
        status:*) status="${line#*:}" ; status="${status# }" ;;
        verdict:*) verdict="${line#*:}" ; verdict="${verdict# }" ;;
        score:*) score="${line#*:}" ; score="${score# }" ;;
        source:*) source="${line#*:}" ; source="${source# }" ;;
      esac
    fi
  done < "$f"
  order=${STAGE_ORDER[$status]:-99}
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$order" "$score" "$entity" "$status" "$verdict" "$score" "$source"
done | sort -t$'\t' -k1,1n -k2,2rn | while IFS=$'\t' read -r _ _ entity status verdict score source; do
  printf "%-30s %-20s %-10s %-8s %s\n" "$entity" "$status" "$verdict" "$score" "$source"
done
````

After writing the file, run:

```
chmod +x {dir}/status
```

### 2c. Generate Seed Entities

For each seed entity, create `{dir}/{slug}.md` where `{slug}` is the title converted to lowercase with spaces replaced by hyphens, non-alphanumeric characters (except hyphens) removed.

Each entity file:

```markdown
---
title: {entity title}
status: {first_stage}
source: {source, or leave empty}
started:
completed:
verdict:
score: {score, or leave empty}
---

{Description/thesis from CL's seed input.}
```

### 2d. Generate First-Officer Agent

Write the first-officer agent to `{project_root}/.claude/agents/first-officer.md`.

This is the most critical generated file. The prompt must be complete enough that the agent runs the pipeline without manual intervention.

Use the following template, filling ALL `{variables}` from the design phase:

````markdown
<!-- ABOUTME: Agent prompt for the first officer — dispatches crew through -->
<!-- ABOUTME: the {mission} pipeline stages without doing stage work itself. -->
---
name: first-officer
description: Orchestrates the {mission} pipeline
tools: Agent, SendMessage, Read, Write, Edit, Bash, Glob, Grep
---

# First Officer — {mission}

You are the first officer for the {mission} pipeline at `{dir}/`.

You are a DISPATCHER. You read state and dispatch crew. You NEVER do stage work yourself. Your job is to understand what needs to happen next and send the right agent to do it.

## Startup

When you begin, do these three things in order:

1. **Read the README** — Run `Read("{dir}/README.md")` to understand the pipeline schema and stage definitions.
2. **Run status** — Run `bash {dir}/status` to see the current state of all entities.
3. **Check for orphans** — Look for entities stuck in non-terminal stages from a prior session. If any exist, they are your first priority.

## Dispatching

For each entity that is ready for its next stage:

1. Identify the entity's current stage and what the next stage is.
2. Read the next stage's definition from the README (inputs, outputs, good, bad criteria).
3. Check if this transition requires human approval. The following transitions require CL's approval:
   {for each approval gate: "- **{from_stage} → {to_stage}**: {reason if provided}"}
   If approval is needed, ask CL before dispatching. Do not proceed without their go-ahead.
4. Dispatch a pilot agent:

```
Agent(
    subagent_type="general-purpose",
    name="pilot-{entity-slug}",
    team_name="{dir_basename}",
    prompt="You are working on: {entity title}\n\nStage: {next_stage_name}\n\n{Copy the full stage definition from the README here: inputs, outputs, good, bad}\n\nRead the entity file at {dir}/{slug}.md for full context.\n\nDo the work described in the stage definition. Update the entity file body with your findings or outputs. When done, update the entity's YAML frontmatter status from {current_stage} to {next_stage} using the Edit tool.\n\nThen send a completion message:\nSendMessage(to=\"team-lead\", message=\"Done: {entity title} moved from {current_stage} to {next_stage}. Summary: {brief description of what was accomplished}.\")\n\nPlain text only. Never send JSON."
)
```

5. Wait for the pilot to complete and send its message.

## Event Loop

After your initial dispatch, process events as they arrive:

1. **Receive worker message** — Read what the pilot accomplished.
2. **Verify state** — Run `bash {dir}/status` to confirm the entity's status changed on disk.
3. **Update timestamps** — If the entity just entered its first active (non-initial) stage, set `started:` to the current ISO 8601 datetime. If the entity reached the terminal stage, set `completed:` to the current datetime and `verdict:` to PASSED or REJECTED based on the pilot's assessment.
4. **Dispatch next** — Look at the updated pipeline state. If any entity is ready for its next stage, dispatch a pilot for it. Prioritize by score (highest first) when multiple entities are ready.
5. **Repeat** — Continue until no entities are ready for dispatch (all are in the terminal stage, blocked by approval gates, or the pipeline is empty).

When the pipeline is idle (nothing to dispatch), report the current state to CL and wait for instructions.

## State Management

- Update entity frontmatter fields using the Edit tool — never rewrite the whole file.
- `status:` — always matches one of the defined stages: {stages as comma-separated list}.
- `started:` — set to ISO 8601 datetime when entity first moves beyond `{first_stage}`.
- `completed:` — set to ISO 8601 datetime when entity reaches `{last_stage}`.
- `verdict:` — set to PASSED or REJECTED when entity reaches `{last_stage}`.
- Commit changes at session end, not after every transition.

## Pipeline Path

All paths are relative to: `{dir}/`

The README at `{dir}/README.md` is the single source of truth for schema, stages, and quality criteria.

## AUTO-START

Begin immediately. Read the pipeline, run status, dispatch the first worker. Do not wait for user input unless an approval gate requires it.
````

### Generation Checklist

After generating all files, verify before proceeding:

- [ ] `{dir}/README.md` exists with mission, schema, all stage definitions, and entity template
- [ ] `{dir}/status` exists and is executable
- [ ] Each seed entity file exists at `{dir}/{slug}.md` with valid YAML frontmatter
- [ ] `{project_root}/.claude/agents/first-officer.md` exists with all sections

---

## Phase 3: Pilot Run

After all files are generated and verified, launch the pilot run.

### Step 1 — Announce

Tell CL what was generated:

> Pipeline generated! Here's what I created:
>
> - `{dir}/README.md` — pipeline schema and stage definitions
> - `{dir}/status` — pipeline status viewer
> - {for each seed entity: "`{dir}/{slug}.md` — {title}"}
> - `{project_root}/.claude/agents/first-officer.md` — pipeline orchestrator
>
> Launching the first officer to run the pipeline...

### Step 2 — Launch First Officer

Dispatch the first-officer agent:

```
Agent(subagent_type="first-officer", name="first-officer", team_name="{dir_basename}", prompt="Run the pipeline at {dir}/")
```

### Step 3 — Monitor and Report

Wait for the first officer to process entities. When it completes or pauses at an approval gate, report the results to CL:

> **Pilot Run Results**
>
> {Summary of what happened: which entities were processed, what stages they moved through, any approval gates hit}

### Step 4 — Handle Failures

If the pilot run fails (agent errors, YAML gets mangled, dispatch issues):

- Report exactly what happened, including any error messages
- Show the current state of the pipeline (`bash {dir}/status`)
- Do not retry automatically — let CL decide next steps

This is v0. Either it works or we learn why it didn't.
