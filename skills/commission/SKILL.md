---
name: commission
description: "This skill should be used when the user asks to \"commission a workflow\", \"create a workflow\", \"design a workflow\", \"launch a workflow\", or wants to interactively design and generate a plain text workflow with stages, entities, and a first-officer agent."
user-invocable: true
---

# Commission a Plain Text Workflow

You are commissioning a plain text workflow. A plain text workflow is a directory of markdown files with YAML frontmatter, where each file is a work entity that moves through stages. The directory's README is the single source of truth for schema and stages, and the Spacedock plugin provides the plugin-shipped status viewer and plugin-shipped PR merge mod at runtime.

This is a v0 shuttle-mode workflow: an ensign agent handles all stages, with optional mods that inject behavior at lifecycle points (e.g., PR creation at merge time). You will walk {captain} through interactive design, generate all workflow files, then launch a pilot run.

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

Before asking Question 1, greet {captain} with the following (skip this greeting entirely in batch mode):

> Welcome to Spacedock! We're going to design a plain text workflow together.
>
> I'll walk you through three phases:
> 1. **Design** — a few questions to shape the workflow
> 2. **Generate** — I'll create all the workflow files
> 3. **Pilot run** — I'll launch the workflow to process your seed entities
>
> Throughout this workflow, you'll be addressed as **{captain}** (the workflow operator).
>
> Let's start designing.

### Args Extraction

If the user's invocation message contains text beyond the command name (e.g.,
`/spacedock:commission product idea to simulated customer interview`), treat
that text as the mission statement.

- Extract `{mission}` from the args
- Proceed to Question 1 but present the extracted mission for confirmation
  rather than asking from scratch:

  > I'll use this as the workflow mission: "{extracted_mission}"
  >
  > What does each work item represent?

This skips the "what's this workflow for?" half of Q1 and goes straight to
the entity-type follow-up.

Ask {captain} the remaining questions **one at a time**. Wait for each answer before asking the next question. Do not batch questions.

### Question 1 — Mission + Entity

Ask:

> What's this workflow for, and what does each work item represent?
>
> Example: "Track design ideas through review stages" — the workflow is for tracking, each item is a design idea.

Extract `{mission}` and `{entity_description}` from the answer. If the answer clearly covers both mission and entity, proceed. If only the mission is clear, ask a brief follow-up:

> Got it. What does each work item in this workflow represent? (e.g., "a design idea", "a bug report", "a candidate feature")

**Derive the entity label** from `{entity_description}`:

1. Strip leading articles ("a", "an", "the")
2. Take the last word (the head noun in English) — this is `{entity_label}` (lowercase, singular)
3. Derive `{entity_label_plural}` by appending "s" to `{entity_label}`
4. Derive `{entity_type}` as the full description (after stripping articles) in snake_case (e.g., "a design idea" → `design_idea`)

Examples:
- "a design idea" → label: `idea`, plural: `ideas`, type: `design_idea`
- "a bug report" → label: `report`, plural: `reports`, type: `bug_report`
- "an implementation task" → label: `task`, plural: `tasks`, type: `implementation_task`
- "a PR" → label: `pr`, plural: `prs`, type: `pr`

### Question 2 — Stages

Based on the mission, suggest default stages. Present them as an itemized list and ask {captain} to review:

> Based on your workflow mission, here are the stages I'd suggest:
>
> {for each stage: "1. **{stage_name}** — {one-line description}"}
>
> Would you like to modify, add, or remove any stages? (confirm or describe changes)

Store the confirmed stages as `{stages}`. The first stage is `{first_stage}` and the last is `{last_stage}`.

### Question 3 — Seed Entities

Ask:

> Give me 2–3 starting items to seed the workflow. For each, provide:
> - **Title** — short name
> - **Description** — a sentence or two about what this entity is
> - **Score** (optional) — priority from 0.0 to 1.0

Store as `{seed_entities}` — a list of objects with title, description, and score. Default `source` to "commission seed" for all seed entities.

If {captain} references an external source for seed data (e.g., "find the info in ~/git/spacedock"
or "see the backlog in project X"), read the referenced files directly using Read/Glob.
Do NOT spawn an Agent for this — a direct file read is sufficient. Look for:
- README files in the referenced directory
- Markdown files with YAML frontmatter (existing entities)
- Any obvious manifest or index file

### Confirm Design

After collecting answers, derive all remaining values from the mission context:

- `{approval_gates}` — default: gate before the terminal stage (e.g., the last stage before terminal).
- `{rejection_flow}` — for each approval gate, determine which earlier stage gets bounced back to on rejection (default: the stage immediately before the gated stage).
- `{dir}` — `docs/{mission-slug}/` where `{mission-slug}` is the mission condensed to a short lowercase hyphenated directory name.
- `{captain}` — "Captain".

Present the full summary with all derived values. Use plain language for stage behavior — do not expose implementation vocabulary like `worktree`, `gate`, `fresh`, or `feedback-to`:

> I'll call you {captain} — let me know if you prefer something else.
>
> For each run, we process {entity_description_as_item_label} going through the following stages:
>
> {for each stage: "{letter}. {stage_name} — {stage_description}"}
>
> {if any gates: "If you reject at {gated_stage}, it goes back to {target_stage} for revision."}
>
> {if domain_specific_fields: "With the following custom fields:"}
> {for each field: "- {field_name}: {field_description}"}
>
> Our pilot run will be with:
> {for each seed: "- {title}"}
>
> All files will be created in `{dir}` for you to review.
>
> Accept this design, or tell me what to change.

Wait for {captain} to confirm before proceeding to Phase 2. If {captain} wants changes, apply them and re-present the summary.

---

## Phase 2: Generate Workflow Files

### Ensure Git Repository

Before generating files, ensure the project has a git repository:

1. Check if the current directory is inside a git repo (`git rev-parse --git-dir`).
2. If not, initialize one silently: `git init && git add -A && git commit --allow-empty -m "initial commit"`.
3. Do NOT ask {captain} for permission — a workflow requires git.

### Generation Discipline

Generate all workflow files without creating tasks or updating progress trackers.
Do NOT use TaskCreate, TaskUpdate, or TodoWrite during file generation — these
create visible noise in {captain}'s UI. The generation checklist at the end of
Phase 2 is sufficient for tracking completion.

### Read Spacedock Version

Before generating any files, read the Spacedock plugin manifest to get the current version:

1. Read `.codex-plugin/plugin.json` from the Spacedock plugin directory (the directory containing the `skills/` folder — resolve from your own plugin context). `.claude-plugin/plugin.json` is the synchronized legacy mirror during migration.
2. Extract the `version` field and store it as `{spacedock_version}`.

This version will be embedded in each generated scaffolding file.

### Generate Files

Create the workflow directory and generate the workflow files. Use the design answers to fill all templates — no placeholder text should remain in generated files.

```
mkdir -p {dir}
```

Also ensure `.worktrees/` is in the project's `.gitignore` (worktrees should never be committed):

```
# If .gitignore doesn't exist, create it. If it exists, append only if .worktrees/ isn't already listed.
grep -qxF '.worktrees/' {project_root}/.gitignore 2>/dev/null || echo '.worktrees/' >> {project_root}/.gitignore
```

### 2a. Generate `{dir}/README.md`

Write the README with ALL of the following sections. Every section is required — do not omit any.

Craft thoughtful, mission-specific content for each stage definition. The inputs, outputs, quality criteria, and anti-patterns should be specific to what this workflow actually does — not generic placeholders.

Do NOT include a Scoring Rubric section by default. Scoring uses a simple 0.0–1.0 float — no rubric needed. If {captain} explicitly asks for a multi-dimension rubric, include a Scoring Rubric section documenting their chosen dimensions.

Use this template structure, filling in all `{variables}` from the design phase:

````markdown
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
    - name: {first_stage}
      initial: true
    {For each middle stage, add an entry with per-stage overrides only when different from defaults:}
    - name: {stage_name}
      {worktree: true — only if the stage modifies code or produces artifacts beyond the entity file}
      {fresh: true — only if an independent perspective matters (e.g., a feedback stage that should assess without prior context)}
      {feedback-to: {target_stage} — if this stage has a rejection flow that bounces back to {target_stage}. Infer from the rejection_flow derived in Confirm Design.}
      {gate: true — if this stage is an approval gate}
      {agent: {agent-name} — only if {captain} specifies a non-default agent for this stage. Omit to use the default ensign. The value is the agent file basename without .md.}
    - name: {last_stage}
      terminal: true
  transitions:
    {Omit this block entirely for linear workflows.}
    {For non-linear flows, add explicit edges:}
    - from: {source_stage}
      to: {target_stage}
      label: {human-readable label}
---

# {mission}

{One paragraph expanding on the mission, describing what this workflow processes and why.}

## File Naming

Each {entity_label} is a markdown file named `{slug}.md` — lowercase, hyphens, no spaces. Example: `my-feature-idea.md`.

## Schema

Every {entity_label} file has YAML frontmatter. Fields are documented below; see **{Entity_label} Template** for a copy-paste starter.

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier, format determined by id-style in README frontmatter |
| `title` | string | Human-readable {entity_label} name |
| `status` | enum | One of: {stages as comma-separated list} |
| `source` | string | Where this {entity_label} came from |
| `started` | ISO 8601 | When active work began |
| `completed` | ISO 8601 | When the {entity_label} reached terminal status |
| `verdict` | enum | PASSED or REJECTED — set at final stage |
| `score` | number | Priority score, 0.0–1.0 (optional). Workflows can upgrade to a multi-dimension rubric in their README. |
| `worktree` | string | Worktree path while a dispatched agent is active, empty otherwise |
| `issue` | string | GitHub issue reference (e.g., `#42` or `owner/repo#42`). Optional cross-reference, set manually. |
| `pr` | string | GitHub PR reference (e.g., `#57` or `owner/repo#57`). Set when a PR is created for this entity's worktree branch. |

## Stages

{For EACH stage in the ordered list, generate a subsection:}

### `{stage_name}`

{A sentence describing who sets this status and what it means for an {entity_label} to be in this stage.}

- **Inputs:** {What the worker reads to do this stage's work — be specific to the mission}
- **Outputs:** {What the worker produces — be specific to the mission. Keep bullets concise and verifiable — these become checklist items at dispatch time. Focus on non-obvious requirements that catch skipping, not obvious actions like "write code."}
- **Good:** {Quality criteria for work done in this stage}
- **Bad:** {Anti-patterns to avoid in this stage}

{End of per-stage sections.}

## Scoring

{ONLY include this section if {captain} explicitly requests a multi-dimension rubric. Otherwise omit entirely — the 0.0–1.0 float is self-explanatory from the schema.}

## Workflow State

View the workflow overview:

```bash
{spacedock_plugin_dir}/skills/commission/bin/status --workflow-dir {dir}
```

Output columns: ID, SLUG, STATUS, TITLE, SCORE, SOURCE.

Include archived {entity_label_plural} with `--archived`:

```bash
{spacedock_plugin_dir}/skills/commission/bin/status --workflow-dir {dir} --archived
```

Find dispatchable {entity_label_plural} ready for their next stage:

```bash
{spacedock_plugin_dir}/skills/commission/bin/status --workflow-dir {dir} --next
```

Find {entity_label_plural} in a specific stage:

```bash
grep -l "status: {stage_name}" {dir}/*.md
```

## {Entity_label} Template

```yaml
---
id:
title: {Entity_label} name here
status: {first_stage}
source:
started:
completed:
verdict:
score:
worktree:
issue:
pr:
---

Description of this {entity_label} and what it aims to achieve.
```

## Commit Discipline

- Commit status changes at dispatch and merge boundaries
- Commit {entity_label} body updates when substantive
````

### 2b. Generate Seed Entities

For each seed entity, create `{dir}/{slug}.md` where `{slug}` is the title converted to lowercase with spaces replaced by hyphens, non-alphanumeric characters (except hyphens) removed.

The `title` field is the human-readable name (e.g., "Full Cycle Test"). The filename `{slug}.md` is derived from it (lowercase, hyphens).

Each entity file gets a sequential ID, starting at `001`:

```markdown
---
id: {next sequential id, zero-padded to 3 digits}
title: {entity title — human-readable, not the slug}
status: {first_stage}
source: {source if provided, otherwise "commission seed"}
started:
completed:
verdict:
score: {score, or leave empty}
worktree:
issue:
pr:
---

{Description/thesis from {captain}'s seed input.}
```

### 2c. Install Mods (conditional)

Check the README frontmatter for any stages with `worktree: true`. If at least one stage uses a worktree, offer the pr-merge mod:

> This workflow has worktree stages. Install the **pr-merge** mod? (Pushes branches and creates GitHub PRs for completed entities.)
>
> (y/n, default: y)

In batch mode, install pr-merge by default for workflows with worktree stages. If the user explicitly says "no mods" or "no pr-merge", skip.

If installing, copy the mod:

```bash
mkdir -p {dir}/_mods
cp "{spacedock_plugin_dir}/mods/pr-merge.md" {dir}/_mods/pr-merge.md
```

If no stage uses a worktree, skip this step entirely — do not offer pr-merge.


### Generation Checklist

After generating all files, verify before proceeding:

- [ ] `{dir}/README.md` exists with mission, schema, all stage definitions, and {entity_label} template
- [ ] Each seed entity file exists at `{dir}/{slug}.md` with valid YAML frontmatter
- [ ] `{dir}/_mods/pr-merge.md` exists (only if a worktree stage exists and pr-merge was accepted)
- [ ] `.worktrees/` is in `{project_root}/.gitignore`

### Agent Warnings

After generation, check the README frontmatter for any stages with an `agent:` property. For each such referenced agent, check whether `{project_root}/.claude/agents/{agent}.md` exists. If a referenced agent file does not exist, warn {captain}:

> Stage '{stage_name}' references agent '{agent}' but `{project_root}/.claude/agents/{agent}.md` does not exist. You'll need to create this file before running the workflow.

This is a warning, not a blocker — proceed with the pilot run regardless. The first officer will fall back to dispatching `ensign` if the referenced agent file is not found at runtime.

---

## Phase 3: Pilot Run

After all files are generated and verified, launch the pilot run.

### Step 1 — Announce

Tell {captain} what was generated:

> Workflow generated! Here's what I created:
>
> - `{dir}/README.md` — workflow schema and stage definitions
> - {for each seed entity: "`{dir}/{slug}.md` — {title}"}
> - {if pr-merge mod was installed: "`{dir}/_mods/pr-merge.md` — PR merge mod"}
>
> Agents are shipped with the Spacedock plugin — no local agent files needed:
> - `spacedock:first-officer` — workflow orchestrator
> - `spacedock:ensign` — stage worker agent
>
> To run this workflow in future sessions, start Claude Code with:
>
> ```
> claude --agent spacedock:first-officer
> ```
>
> Starting the initial run now...

### Step 2 — Assume First-Officer Role

Do not spawn a subagent. Instead, the commission skill itself takes on the first-officer role for the initial run:

1. Read the first-officer agent file at `{spacedock_plugin_dir}/agents/first-officer.md`.
2. Follow its instructions: read the reference files (shared core, guardrails, Claude runtime), then read the workflow README, run the status script, and dispatch agents for entities ready to advance.

Execute the first-officer startup procedure directly. You are now the first officer for the remainder of this session.

### Step 3 — Team Probe

Before any dispatch:

1. Run `ToolSearch(query="select:TeamCreate", max_results=1)`.
2. If the result contains a TeamCreate definition, run `TeamCreate(...)` per the Claude Code runtime adapter's Team Creation section, and record the returned `team_name`. Forward that `team_name` into every subsequent dispatch input JSON.
3. If ToolSearch returns no match, enter bare mode explicitly (`team_name: null, bare_mode: true` on dispatch inputs) and report the mode to {captain}.

This step is mandatory. Skipping it and defaulting to bare is the failure mode #201 addresses — a commissioned FO that silently omits TeamCreate loses access to team-mode primitives (spawn-standing, concurrent dispatch, SendMessage coordination).

### Step 4 — Monitor and Report

Process entities following the first-officer event loop. When the workflow reaches an idle state or pauses at an approval gate, report the results to {captain}:

> **Pilot Run Results**
>
> {Summary of what happened: which entities were processed, what stages they moved through, any approval gates hit}

### Step 5 — Handle Failures

If the pilot run fails (agent errors, YAML gets mangled, dispatch issues):

- Report exactly what happened, including any error messages
- Show the current state of the workflow with `{spacedock_plugin_dir}/skills/commission/bin/status --workflow-dir {dir}`
- Do not retry automatically — let {captain} decide next steps

This is v0. Either it works or we learn why it didn't.

### Step 6 — Post-Completion Guidance

After Step 4 or Step 5 (whether the pilot run succeeded or failed), always conclude with:

> **What's next?** To continue working this workflow in a future session, start Claude Code with:
>
> ```
> claude --agent spacedock:first-officer
> ```
>
> The first officer will read the workflow state, pick up where things left off, and dispatch agents for any entities ready for their next stage.
