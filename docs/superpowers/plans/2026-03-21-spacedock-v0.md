# Spacedock v0 Plugin Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Spacedock Claude Code plugin — `plugin.json`, the `/spacedock commission` skill, and the first-officer agent reference — so that CL can interactively design and launch PTP pipelines.

**Architecture:** Spacedock is a Claude Code plugin. The commission skill is a markdown prompt that guides Claude through three phases: (1) interactive design — asking CL six questions one at a time, (2) file generation — producing README, status script, seed entities, and a first-officer agent, and (3) pilot run — launching the first-officer to process the first entity. All generated file content is templated within the skill itself.

**Tech Stack:** Claude Code plugin system (plugin.json + skill markdown files), Bash (generated status scripts), YAML frontmatter (entity metadata)

---

## File Structure

| File | Responsibility | Create/Modify |
|------|---------------|---------------|
| `plugin.json` | Plugin manifest — name, description, version, skills | Create |
| `skills/commission/commission.md` | Commission skill — interactive design, file generation, pilot launch | Create |
| `agents/first-officer.md` | First-officer agent reference documenting the generated-per-pipeline pattern | Create |

## Chunk 1: Full Implementation

### Task 1: Create plugin.json

**Files:**
- Create: `plugin.json`

- [ ] **Step 1: Create the plugin manifest**

Create `plugin.json` at the repo root. Note: JSON does not support comments, so the ABOUTME rule does not apply to this file.

```json
{
  "name": "spacedock",
  "description": "Build and launch PTP pipelines",
  "version": "0.1.0",
  "skills": ["commission"]
}
```

- [ ] **Step 2: Verify valid JSON**

Run: `python3 -m json.tool plugin.json`
Expected: Pretty-printed JSON output, exit 0

- [ ] **Step 3: Commit**

```bash
git add plugin.json
git commit -m "feat: add spacedock plugin manifest"
```

---

### Task 2: Create commission skill

**Files:**
- Create: `skills/commission/commission.md`

**Context:** This is the core deliverable — a Claude Code skill prompt that orchestrates the entire `/spacedock commission` workflow. When invoked, Claude follows these instructions to design a pipeline with CL, generate all pipeline files, and launch a pilot run.

The skill must be completely self-contained. It includes full templates for every generated file (README, status script, entities, first-officer agent) with `{variable}` placeholders that Claude fills from the interactive design answers.

**Key spec constraints:**
- v0 is shuttle-only: one pilot agent per stage, no specialized crew
- The first-officer is a DISPATCHER — never does stage work itself
- Entity = markdown file with YAML frontmatter
- Status script: self-describing bash (comments describe what it does, then implementation)
- README = single source of truth for schema + stages
- First-officer dispatches pilots via Agent() and receives results via SendMessage

**The commission.md skill file must contain ALL of the following sections. Do not omit or abbreviate any section.**

- [ ] **Step 1: Create skill file with frontmatter**

Create `skills/commission/commission.md`. Since this is a markdown file, use HTML comments for ABOUTME lines (placed before the YAML frontmatter):

```markdown
<!-- ABOUTME: Skill prompt for /spacedock commission — guides Claude through -->
<!-- ABOUTME: interactive PTP pipeline design, file generation, and pilot run. -->
---
name: commission
description: Interactively design and launch a PTP pipeline
---
```

- [ ] **Step 2: Write the Interactive Design Phase**

After the frontmatter, add the Phase 1 section. The skill instructs Claude to ask CL these questions **one at a time**, waiting for each answer before proceeding:

1. **Mission:** "What's this pipeline for?" → Expect one sentence describing the pipeline's purpose.
2. **Entity:** "What does each work item represent?" → e.g., "a design idea", "a bug report", "a candidate feature"
3. **Stages:** "What stages does an entity go through?" → Suggest sensible defaults based on the mission (e.g., `ideation → implementation → validation → done`). CL can modify.
4. **Approval gates:** "Which stage transitions need your approval?" → List the transitions and let CL mark which ones require human approval.
5. **Seed entities:** "Give me 2-3 starting items." → For each: title, brief description, and optionally source and score (N/25).
6. **Location:** "Where should I create this?" → Suggest a path based on the mission context.

After all questions answered, the skill instructs Claude to present a summary of the design and ask CL to confirm before generating files.

- [ ] **Step 3: Write the Generation Phase — README template**

Add the README generation template. The generated `{dir}/README.md` must contain ALL these sections (per spec):

- **Mission** — one paragraph from CL's answer
- **File naming** — `{slug}.md`, lowercase, hyphens
- **Schema** — YAML frontmatter template showing all fields:
  ```yaml
  ---
  title: Human-readable name
  status: {first_stage}
  source:
  started:
  completed:
  verdict:
  score:
  ---
  ```
  Plus domain-specific fields based on CL's answers.
- **Stages** — one section per status value, formatted as:
  ```markdown
  ### `{stage_name}`

  {Set by whom}. {What's complete when this status is set}.

  - **Inputs:** what the worker reads
  - **Outputs:** what the worker produces
  - **Good:** quality criteria
  - **Bad:** anti-patterns
  - **Human approval:** {yes: reason / no}
  ```
  Claude must craft stage definitions appropriate to the pipeline's mission. Each stage should have thoughtful, specific inputs/outputs/good/bad criteria — not generic placeholders.
- **Scoring rubric** — if CL wants prioritization, include Edge/Fitness/Parsimony/Testability/Novelty (each 1-5, sum/25). Otherwise omit.
- **Pipeline state query** — show `bash {dir}/status` and `grep -l "status: {stage}" {dir}/*.md`
- **Entity template** — ready-to-copy template with frontmatter and body placeholder
- **Commit discipline** — "status changes at session end, research outputs when substantive"

- [ ] **Step 4: Write the Generation Phase — status script template**

Add the status script generation template. The generated `{dir}/status` must be:

- Self-describing: starts with `#!/bin/bash` and comments that explain the goal, instruction, constraints, and valid status values (per the spec's self-describing pattern)
- Implementation: extracts `status`, `verdict`, `score`, `source` from YAML frontmatter of every `.md` file in the directory (excluding `README.md`)
- Output: prints a table with columns ENTITY, STATUS, VERDICT, SCORE, SOURCE
- Sorting: by stage order (using the stages CL defined) then score descending
- Paths: resolved relative to the script itself (`DIR="$(cd "$(dirname "$0")" && pwd)"`)
- Must be generated with execute permission (`chmod +x`)

The skill should contain a complete, working bash script template — not pseudocode. Here is a reference implementation pattern that the skill should adapt (parameterizing stage names and sort order from the design phase):

```bash
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

# Stage order for sorting (filled in from design phase)
declare -A STAGE_ORDER=([{stage1}]=1 [{stage2}]=2 [{stage3}]=3 [{last_stage}]=4)

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
        status:*) status="${line#*: }" ;;
        verdict:*) verdict="${line#*: }" ;;
        score:*) score="${line#*: }" ;;
        source:*) source="${line#*: }" ;;
      esac
    fi
  done < "$f"
  order=${STAGE_ORDER[$status]:-99}
  printf "%s\t%s\t%s\t%s\t%s\t%s\n" "$order" "$score" "$entity" "$status" "$verdict" "$source"
done | sort -t$'\t' -k1,1n -k2,2rn | while IFS=$'\t' read -r _ _ entity status verdict score source; do
  printf "%-30s %-20s %-10s %-8s %s\n" "$entity" "$status" "$verdict" "$score" "$source"
done
```

The skill's template should use this pattern with `{variable}` placeholders for stage names and their sort order values. Claude fills these in from the design phase answers.

- [ ] **Step 5: Write the Generation Phase — seed entity template**

Add the seed entity generation template. Each generated `{dir}/{slug}.md` must have:

- Valid YAML frontmatter with: `title`, `status` (set to first stage), `source` (if provided), `score` (if provided)
- Body: the description/thesis from CL's seed input
- Filename: slugified title (lowercase, hyphens, `.md` extension)

- [ ] **Step 6: Write the Generation Phase — first-officer agent template**

Add the first-officer agent generation template. The generated `{project_root}/.claude/agents/first-officer.md` must contain:

Frontmatter:
```yaml
---
name: first-officer
description: Orchestrates the {mission} pipeline
tools: Agent, SendMessage, Read, Write, Edit, Bash, Glob, Grep
---
```

Prompt body must include ALL these sections (from spec):
- **Identity** — "You are the first officer for the {mission} pipeline at `{dir}/`."
- **Dispatcher rule** — "You are a DISPATCHER. You read state and dispatch crew. You never do stage work yourself."
- **Startup** — (1) Read `{dir}/README.md` for schema and stage definitions, (2) Run `bash {dir}/status` for pipeline overview, (3) Check for orphaned entities
- **Event Loop** — After dispatch, every time a worker completes: (1) Process worker's message (update entity frontmatter), (2) Re-run status, (3) Dispatch next worker, (4) Repeat until pipeline empty or CL stops
- **Dispatching** — For each entity ready: (1) Read stage definition from README, (2) Dispatch pilot agent:
  ```
  Agent(
      subagent_type="general-purpose",
      name="pilot-{entity-slug}",
      team_name="{pipeline-name}",
      prompt="You are working on: {entity title}\n\nStage: {stage_name}\n\n{stage definition from README: inputs, outputs, good, bad}\n\nRead the entity file at {dir}/{slug}.md for context.\nWhen done, update the entity's status to {next_stage} and SendMessage to team-lead with a plain text summary.\n\nPlain text only. Never send JSON."
  )
  ```
  (3) For approval-gated transitions: ask CL before dispatching
- **State Management** — Update entity frontmatter on completion (status field). Set `started:` on first active stage. Set `completed:` and `verdict:` on done. Commit at session end.
- **Pipeline Path** — "All paths relative to: `{dir}/`"
- **AUTO-START** — "Begin immediately. Read the pipeline, run status, dispatch first worker. Do not wait for user input unless an approval gate requires it."

- [ ] **Step 7: Write the Pilot Run Phase**

After generating all files, the skill instructs Claude to:

1. Announce that all files have been generated and list them
2. Launch the first officer. The commission skill generates `.claude/agents/first-officer.md` in Step 6, which registers "first-officer" as a valid agent type in Claude Code:
   ```
   Agent(subagent_type="first-officer", name="first-officer", team_name="{dir_basename}", prompt="Run the pipeline at {dir}/")
   ```
3. Monitor pilot execution and report results to CL
4. Minimal error handling: if the pilot fails, report what happened. No retry logic in v0.

- [ ] **Step 8: Review the complete skill file**

Read through the entire `skills/commission/commission.md` and verify:
- All phases are present: Interactive Design → Confirm → Generate → Pilot Run
- All generated file templates are complete (README, status, entities, first-officer)
- Templates are properly parameterized with `{variable}` syntax
- No placeholder text, TODOs, or abbreviations remain
- The status script template is a real, working bash script pattern
- The first-officer template includes ALL sections from the spec
- Instructions are clear enough that Claude can follow them without external context

- [ ] **Step 9: Commit**

```bash
git add skills/commission/commission.md
git commit -m "feat: add commission skill for PTP pipeline creation"
```

---

### Task 3: Create first-officer agent reference

**Files:**
- Create: `agents/first-officer.md`

**Context:** The spec's plugin structure includes `agents/first-officer.md`. This file in the plugin directory serves as documentation for the first-officer agent pattern — the actual operational agent is generated per-pipeline by the commission skill at `{project_root}/.claude/agents/first-officer.md` in the target project. This reference exists because the spec mandates it in the plugin structure, and it documents the generated-per-pipeline pattern.

- [ ] **Step 1: Create the reference file**

Create `agents/first-officer.md` with:
- ABOUTME comment explaining what this file is
- Brief explanation that the first-officer is generated per-pipeline by `/spacedock commission`
- Note that the generated agent is placed at `.claude/agents/first-officer.md` in the target project
- Reference to `v0/spec.md` for the full template specification

Keep this file short (under 30 lines). It's documentation, not a template.

- [ ] **Step 2: Commit**

```bash
git add agents/first-officer.md
git commit -m "docs: add first-officer agent reference"
```

---

## Testing

**Manual dogfood test for CL to run after implementation:**

Run `/spacedock commission` and provide these inputs when prompted:

| Question | Answer |
|----------|--------|
| Mission | "Design and build Spacedock — a Claude Code plugin for creating PTP pipelines" |
| Entity | "A design idea or feature for Spacedock" |
| Stages | ideation → implementation → validation → done |
| Approval gates | ideation → implementation (new features), validation → done (merging) |
| Seed entities | (1) `full-cycle-test` — "Prove the full ideation → implementation → validation → done cycle works end-to-end" (score: 22/25), (2) `refit-command` — "Add /spacedock refit for examining and upgrading existing pipelines" (score: 18/25), (3) `multi-pipeline` — "Support multiple interconnected pipelines" (score: 16/25) |
| Location | `~/git/spacedock/pipeline/` |

**Success criteria (from spec):**

1. `~/git/spacedock/pipeline/README.md` exists with schema + 4 stage definitions (ideation, implementation, validation, done)
2. `~/git/spacedock/pipeline/status` is executable and prints a 3-row table with columns ENTITY, STATUS, VERDICT, SCORE, SOURCE
3. Three `.md` files exist with valid YAML frontmatter (`status: ideation`, title, score)
4. `.claude/agents/first-officer.md` exists with correct pipeline path
5. Pilot: `full-cycle-test.md` frontmatter changes from `status: ideation` to `status: implementation`
6. First officer reports the transition to CL

**What good looks like:**
- Generated README is complete enough to follow without the plugin
- Status script works on first run
- First officer dispatches a pilot instead of doing the work itself
- Entity frontmatter stays valid YAML through the transition
- No manual intervention needed from commission to pilot completion

**What bad looks like:**
- README has placeholder text
- Status script errors
- First officer does stage work itself
- YAML frontmatter gets mangled
- Pilot requires manual fix-up
- Hardcoded paths from templates leak into generated files
