# Spacedock v0 — Spec

## Overview

Spacedock is a Claude Code plugin. `/spacedock commission` interactively designs a PTP (Plain Text Pipeline) with the user, generates the directory, and runs a pilot to prove it's executable.

PTP: entity = markdown file with YAML frontmatter, directory = pipeline, README = schema + stages, views = self-describing scripts.

## Plugin Structure

```
spacedock/
├── plugin.json
├── skills/
│   └── commission/
│       └── commission.md          # /spacedock commission skill
├── agents/
│   └── first-officer.md           # Generic pipeline orchestrator (generated per pipeline)
└── v0/
    └── spec.md                    # This file
```

### plugin.json

```json
{
  "name": "spacedock",
  "description": "Build and launch PTP pipelines",
  "version": "0.1.0",
  "skills": ["commission"]
}
```

## `/spacedock commission`

### Interactive Design Phase

The commission skill asks CL one question at a time:

1. **Mission:** "What's this pipeline for?" → one sentence
2. **Entity:** "What does each work item represent?" → e.g., "a design idea"
3. **Stages:** "What stages does an entity go through?" → suggest defaults, CL modifies
4. **Approval gates:** "Which transitions need your approval?"
5. **Seed entities:** "Give me 2-3 starting items."
6. **Location:** "Where should I create this?" → suggest path

v0 is shuttle-only (one pilot agent handles all stages). Starship mode (specialized crew per stage) is deferred to v1.

### Generation Phase

After CL confirms, generate:

#### `{dir}/README.md`

Single source of truth. Contains:

- **Mission** — one paragraph
- **File naming** — `{slug}.md`, lowercase, hyphens
- **Schema** — YAML frontmatter template:
  ```yaml
  ---
  title: Human-readable name
  status: {first_stage}           # REQUIRED — from stage enum
  source:                         # where the idea came from
  started:                        # ISO 8601
  completed:                      # ISO 8601
  verdict:                        # PASSED | REJECTED — set by validation stage
  score:                          # 0.0–1.0 (optional, for prioritization)
  ---
  ```
  Domain-specific fields added based on CL's answers.

- **Stages** — one section per status value:
  ```markdown
  ### `{stage_name}`

  {Set by whom}. {What's complete when this status is set}.

  - **Inputs:** what the worker reads
  - **Outputs:** what the worker produces
  - **Good:** quality criteria
  - **Bad:** anti-patterns
  - **Human approval:** {yes: reason / no}
  ```

- **Scoring rubric** — omitted by default. Scoring uses a simple 0.0–1.0 float for prioritization. Pipelines that need more rigorous prioritization can upgrade to a multi-dimension rubric (e.g., 5 dimensions, each 1–5, sum/25) by documenting it in their README.

- **Pipeline state query:**
  ```bash
  bash {dir}/status
  grep -l "status: {stage}" {dir}/*.md
  ```

- **Entity template** — ready to copy
- **Commit discipline** — status changes at session end, research outputs when substantive

#### `{dir}/status`

Self-describing view script:

```bash
#!/bin/bash
# The actual program generated below is a version of the description:
#
# goal: Show one-line-per-entity pipeline overview from YAML frontmatter.
# instruction: For every .md file in this directory (excluding README.md),
#   extract status, verdict, score, source from YAML frontmatter.
#   Print table sorted by stage order then score descending.
# constraints: bash only, resolves paths relative to this script, skips README.md.
# valid status values: {stage1}, {stage2}, ..., done.

... (materialized implementation matching the orb-backtest status script pattern)
```

Columns: ENTITY, STATUS, VERDICT, SCORE, SOURCE.

#### `{dir}/{seed-1}.md`, `{seed-2}.md`, ...

Seed entities with valid frontmatter and `status: {first_stage}`. Body contains thesis/description.

#### `.claude/agents/first-officer.md`

Generated at `{project_root}/.claude/agents/first-officer.md` (standard Claude Code agent location, relative to the project where Claude Code is running).

This is the critical file — the prompt must be complete enough that the agent runs the pipeline without manual fixup.

```yaml
---
name: first-officer
description: Orchestrates the {mission} pipeline
tools: Agent, SendMessage, Read, Write, Edit, Bash, Glob, Grep
---
```

The prompt body:

```markdown
# First Officer — {Mission}

You are the first officer for the {mission} pipeline at `{dir}/`.
You are a DISPATCHER. You read state and dispatch crew. You never do stage work yourself.

## Startup

1. Read `{dir}/README.md` for schema and stage definitions
2. Run `bash {dir}/status` for pipeline overview
3. Check for orphaned entities (stuck in non-terminal status from prior session)

## Event Loop

After initial dispatch, every time a worker completes:
1. Process the worker's message (update entity frontmatter)
2. Re-run `bash {dir}/status`
3. Dispatch next worker based on pipeline state
4. Repeat until pipeline is empty or CL stops you

## Dispatching

For each entity ready for the next stage:
1. Read the stage definition from `{dir}/README.md`
2. Dispatch a pilot agent:
   ```
   Agent(
       subagent_type="general-purpose",
       name="pilot-{entity-slug}",
       team_name="{pipeline-name}",
       prompt="You are working on: {entity title}\n\nStage: {stage_name}\n\n{stage definition from README: inputs, outputs, good, bad}\n\nRead the entity file at {dir}/{slug}.md for context.\nWhen done, update the entity's status to {next_stage} and SendMessage to team-lead with a plain text summary.\n\nPlain text only. Never send JSON."
   )
   ```
3. For approval-gated transitions: ask CL before dispatching

## State Management

- Update entity frontmatter when workers complete (edit `status:` field)
- Set `started:` when moving to first active stage
- Set `completed:` and `verdict:` when moving to done
- Commit at session end, not on every status change

## Pipeline Path

All paths relative to: `{dir}/`

## AUTO-START

Begin immediately. Read the pipeline, run status, dispatch first worker. Do not wait for user input unless an approval gate requires it.
```

### Pilot Run Phase

After generating all files, the commission skill launches the first officer:

1. Commission skill calls `Agent(subagent_type="first-officer", name="first-officer", team_name="{dir_basename}", prompt="Run the pipeline at {dir}/")` to start the orchestrator
2. First officer reads README, runs status, sees seed entities
3. First officer picks highest-scored entity in first stage
4. First officer dispatches a pilot agent with stage context from README
5. Pilot agent reads entity file, does the work (for dogfood: writes design notes in the entity body), updates frontmatter to next stage
6. Pilot sends `SendMessage(to="team-lead", message="Done: {entity title} moved to {next_stage}")` — plain text only
7. First officer receives message, re-runs status, reports to CL

The pilot succeeds when the entity's `status:` field has changed in the file on disk.

### Error Handling (v0: minimal)

If the pilot fails (agent misparses, YAML gets mangled, dispatch doesn't work):
- The commission skill reports what happened
- CL can inspect the generated files and fix manually
- No retry logic in v0 — either it works or we learn why it didn't

## Test Case: Dogfood

### Commission Inputs

- **Mission:** "Design and build Spacedock — a Claude Code plugin for creating PTP pipelines"
- **Entity:** "A design idea or feature for Spacedock"
- **Stages:** ideation → implementation → validation → done
- **Approval gates:** ideation → implementation (new features), validation → done (merging)
- **Seed entities:**
  1. `full-cycle-test.md` — "Prove the full ideation → implementation → validation → done cycle works end-to-end" (score: 0.9)
  2. `refit-command.md` — "Add /spacedock refit for examining and upgrading existing pipelines" (score: 0.7)
  3. `multi-pipeline.md` — "Support multiple interconnected pipelines (shuttle feeding starship)" (score: 0.6)
- **Location:** `~/git/spacedock/pipeline/`

### Success Criteria

1. `~/git/spacedock/pipeline/README.md` exists with schema + 4 stage definitions (ideation, implementation, validation, done)
2. `~/git/spacedock/pipeline/status` is executable and prints a 3-row table with columns ENTITY, STATUS, VERDICT, SCORE, SOURCE
3. Three `.md` files exist with valid YAML frontmatter (`status: ideation`, title, score)
4. `.claude/agents/first-officer.md` exists with correct pipeline path
5. Pilot: `full-cycle-test.md` frontmatter changes from `status: ideation` to `status: implementation`
6. First officer reports the transition to CL

### What Good Looks Like

- Generated README is complete enough to follow without the plugin
- Status script works on first run
- First officer dispatches a pilot instead of doing the work itself
- Entity frontmatter stays valid YAML through the transition
- No manual intervention needed from commission to pilot completion

### What Bad Looks Like

- README has placeholder text
- Status script errors
- First officer does stage work itself
- YAML frontmatter gets mangled
- Pilot requires manual fix-up
- Hardcoded paths from templates leak into generated files

## Not in v0

- Starship mode (specialized crew per stage)
- `/spacedock refit`
- Maintenance/debrief automation
- Multi-pipeline orchestration
- Channel/Telegram integration
- Pipeline templates library
