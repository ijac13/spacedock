<!-- ABOUTME: Skill prompt for /spacedock refit — guides Claude through -->
<!-- ABOUTME: upgrading existing workflow scaffolding to the current Spacedock version. -->
---
name: refit
description: "This skill should be used when the user asks to \"refit a workflow\", \"upgrade a workflow\", \"update workflow scaffolding\", or wants to bring an existing workflow's scaffolding files up to date with the current Spacedock version."
user-invocable: true
---

# Refit a Workflow

You are refitting (upgrading) an existing workflow to match the current Spacedock version. This covers scaffolding files (status script, first-officer agent, README) and, when schema changes require it, migrating entity frontmatter data.

Follow these five phases in order. Do not skip or combine phases.

---

## Phase 1: Discovery

### Step 1 — Identify the workflow

The user must provide a workflow directory path. If they didn't, ask:

> Which workflow directory should I refit?

Store the confirmed path as `{dir}`. Resolve it to an absolute path. Also derive `{project_root}` (git root or cwd) and `{dir_basename}` (last path component).

### Step 2 — Read current scaffolding and extract version stamps

Read each scaffolding file and extract its version stamp:

1. **README** — Read `{dir}/README.md`. Extract version from YAML frontmatter `commissioned-by: spacedock@X.Y.Z`. Store as `{readme_version}`.
2. **Status script** — Read `{dir}/status`. Extract version from `# commissioned-by: spacedock@X.Y.Z`. Store as `{status_version}`.
3. **Agent files** — Agent templates are static (no version stamps). For each agent (`first-officer.md`, `ensign.md`, and any lieutenants referenced in README `stages.states`), check if `{project_root}/.claude/agents/{agent}.md` exists. Compare its content to the corresponding template at `{spacedock_plugin_dir}/templates/{agent}.md`. Store whether each agent matches its template or differs.

If a file doesn't exist, note it as missing and skip it.

### Step 3 — Read current Spacedock version

Read `.claude-plugin/plugin.json` from the Spacedock plugin directory (the directory containing the `skills/` folder — resolve from your own plugin context). Extract the `version` field. Store as `{current_version}`.

### Step 4 — Evaluate

- If all version stamps match `{current_version}` and all agent files match their templates: report "Workflow is already up to date." and stop.
- If no stamps were found on any versioned file (README, status): enter **Degraded Mode** (see below).
- Otherwise: proceed to Phase 2 with the list of outdated files and mismatched agents.

---

## Phase 2: Classify Files by Upgrade Strategy

Each scaffolding file gets a specific upgrade strategy based on how safe it is to auto-replace:

| File | Strategy | Rationale |
|------|----------|-----------|
| `status` | **Replace** | Mechanical script. Workflow-specific content (stage names) is extracted from the README. Users rarely customize beyond what's generated. |
| `first-officer.md` | **Copy if changed** | Static template — compare on-disk to template, show diff and ask the captain for confirmation before replacing. |
| `README.md` | **Show diff** | Users customize stages, schema fields, quality criteria. Too risky to auto-replace. Show what the current template would produce and let the captain decide. |
| `ensign.md` | **Copy if changed** | Static template — compare on-disk to template, show diff and ask the captain for confirmation before replacing. |
| `{lieutenant}.md` | **Copy if changed** | Static template. Only present for stages that reference a lieutenant agent. Show diff and ask the captain for confirmation before replacing. |

Present the classification to the captain:

> **Upgrade plan:**
>
> | File | Current State | Strategy |
> |------|--------------|----------|
> | `status` | {status_version or "no stamp"} | Replace |
> | `first-officer.md` | {matches template / differs from template / missing} | Copy if changed |
> | `README.md` | {readme_version or "no stamp"} | Show diff (manual review) |
> | `ensign.md` | {matches template / differs from template / missing} | Copy if changed |
> | `{lieutenant}.md` (for each) | {matches template / differs from template / missing} | Copy if changed |
>
> Proceed?

Only include lieutenant rows for agents actually referenced in the README `stages.states` entries. Omit agent rows where the on-disk file already matches the template.

Wait for the captain to confirm before proceeding.

---

## Phase 3: Execute Upgrades

### Extract workflow-specific values from README

Before generating any files, read `{dir}/README.md` and extract:

1. **Mission** — from the `# {title}` heading (first H1).
2. **Stages** — from the `## Stages` section. Each `### \`{stage_name}\`` subsection is a stage, in order. For each stage, extract:
   - Stage name
   - Inputs, Outputs, Good, Bad descriptions
   - Whether "Human approval: Yes" appears (indicates an approval gate for the transition INTO this stage)
3. **Schema fields** — from the `## Schema` section's YAML block.
4. **Entity description** — from the first paragraph after the H1.

### 3a. Status Script (Replace + Materialize)

Generate the status script from the reference template at `templates/status` (relative to the Spacedock plugin directory).

1. Read the template file.
2. Fill in the two variable fields:
   - `{current_version}` — the target Spacedock version
   - `{stage1}, {stage2}, ..., {last_stage}` — the workflow's stage names in order (extracted from README)
3. Show the captain the diff between the old status script's description header and the new one. (Only the header matters — the implementation will be regenerated regardless.)
4. Replace `{dir}/status` with the filled-in template.
5. Preserve the executable bit (`chmod +x`).
6. **Materialize** — read back the description header and replace the stub body with a working bash implementation that satisfies the description. The implementation must work on bash 3.2+ (no associative arrays, no bash 4+ features). Keep the description header intact — only replace everything after it.

### 3b. First-Officer Agent (Copy if changed)

1. Compare `{project_root}/.claude/agents/first-officer.md` to the template at `{spacedock_plugin_dir}/templates/first-officer.md`.

2. If they match, skip. If they differ, show the captain a diff:

> **First-officer changes:**
> {diff output}
>
> Replace the first-officer agent? (y/n)

3. Wait for the captain's confirmation before replacing.

If the user added custom sections to the first-officer (sections not in the standard template), warn the captain:

> **Warning:** The existing first-officer has custom sections that aren't in the standard template. These will be lost if you replace it:
> {list of custom section headings}

### 3c. README (Show Diff)

1. Generate what the current commission template would produce for this workflow, using the extracted values (mission, stages, schema, etc.).
2. Diff it against the user's current README.
3. Present the diff to the captain, noting which differences are likely template changes vs user customizations:

> **README template diff:**
>
> The following differences exist between your README and what the current template would generate. Differences may be template improvements or your intentional customizations.
>
> {diff output}
>
> I have NOT modified your README. Review the diff and apply any changes you want manually, or tell me which specific changes to make.

Do NOT auto-modify the README. The captain decides what to adopt.

### 3d. Ensign Agent (Copy if changed)

1. Compare `{project_root}/.claude/agents/ensign.md` to the template at `{spacedock_plugin_dir}/templates/ensign.md`.

2. If they match, skip. If they differ, show the captain a diff:

> **Ensign agent changes:**
> {diff output}
>
> Replace the ensign agent? (y/n)

3. Wait for the captain's confirmation before replacing `{project_root}/.claude/agents/ensign.md`.

### 3e. Lieutenant Agents (Copy if changed)

Scan the README frontmatter `stages.states` for entries with an `agent:` property. For each referenced lieutenant agent:

1. Check if the template exists at `{spacedock_plugin_dir}/templates/{agent}.md`. If the template does not exist, warn the captain and skip:

> **Warning:** Stage '{stage_name}' references agent '{agent}' but no template exists at `templates/{agent}.md`. Skipping — the existing agent file (if any) will not be updated.

2. If the template exists, compare `{project_root}/.claude/agents/{agent}.md` to the template. If they match, skip. If they differ, show the captain a diff:

> **{agent} agent changes:**
> {diff output}
>
> Replace the {agent} agent? (y/n)

3. Wait for the captain's confirmation before replacing `{project_root}/.claude/agents/{agent}.md`.

If the agent file does not currently exist at `{project_root}/.claude/agents/{agent}.md`, show the full template content and ask:

> **{agent} agent is new** (referenced by stage '{stage_name}' but not yet installed):
> {full content}
>
> Create the {agent} agent? (y/n)

---

## Phase 4: Migrate Entity Data

After upgrading scaffolding, check whether schema changes require migrating existing entity data.

### Step 1 — Detect schema changes

Compare the old README's `## Schema` and `### Field Reference` sections against the new version. Look for:

- **Changed field types or ranges** (e.g., score changed from integer/25 to float/0.0–1.0)
- **Renamed fields** (e.g., `priority` → `score`)
- **Removed fields** (fields in entities that are no longer in the schema)
- **New required fields** (fields added to the schema that existing entities lack)

If no schema changes affect entity data, skip to Phase 5.

### Step 2 — Scan entities

For each detected schema change, scan all entity files in `{dir}/*.md` (excluding README.md) and identify which entities have values in the affected fields.

Present findings to the captain:

> **Schema migration needed:**
>
> {description of what changed in the schema}
>
> **Affected entities:**
> {list of entities with current values that need migration}
>
> **Proposed migration:**
> {what the migration would do — e.g., "Convert score from /25 to 0.0–1.0 by dividing by 25"}
>
> Apply this migration? (y/n)

### Step 3 — Execute migration

On the captain's approval, update the affected entity frontmatter fields. Use the Edit tool — never rewrite whole entity files. Only touch the specific fields identified in the migration plan.

Show a summary of what was migrated:

> **Migrated {N} entities:**
> {list of entity: old_value → new_value}

---

## Phase 5: Finalize

1. Update version stamps to `{current_version}` in versioned files that were replaced (status script, README).
2. For the README (if the captain didn't request changes), update only the version stamp in YAML frontmatter: `commissioned-by: spacedock@{current_version}`.
3. Show a summary:

> **Refit complete:**
>
> | File | Action |
> |------|--------|
> | `status` | Replaced |
> | `first-officer.md` | {Replaced / Already current / Skipped} |
> | `ensign.md` | {Replaced / Already current / Skipped} |
> | `{lieutenant}.md` (for each) | {Replaced / Already current / Created / Skipped} |
> | `README.md` | {Stamp updated / User-reviewed / No changes} |
>
> Suggest committing:
> ```
> git commit -m "refit: upgrade workflow scaffolding to spacedock@{current_version}"
> ```

---

## Degraded Mode (No Version Stamp)

When no version stamps are found on the README or status script, the original baseline cannot be determined. Inform the captain and offer two options:

> **No version stamps found.** This workflow was commissioned before version stamping was implemented, or the stamps were removed. I can't determine what the original scaffolding looked like.
>
> Two options:
>
> 1. **Stamp only** — Add version stamps to existing files without changing anything else. This establishes a baseline for future refits.
> 2. **Full refit with review** — Generate what the current templates would produce and show a full diff for every scaffolding file. You review and approve each change.
>
> Which option?

### Option 1: Stamp Only

Add version stamps to versioned files without modifying anything else:

- **README.md** — Add YAML frontmatter with `commissioned-by: spacedock@{current_version}` (wrap in `---` delimiters if frontmatter doesn't exist).
- **status** — Insert `# commissioned-by: spacedock@{current_version}` as the second line (after `#!/bin/bash`).

Agent files are static templates and do not carry version stamps. They are updated by comparing to the template content.

### Option 2: Full Refit with Review

Execute Phase 3, but show a full diff for every file (including status and first-officer) and require the captain's explicit approval before replacing each one. Never auto-replace files without a version stamp — the risk of overwriting customizations is too high.

---

## Safety Rules

- **Never modify entity file bodies** — only frontmatter, and only during an approved schema migration.
- **Never auto-replace without a version stamp** — always enter degraded mode.
- **Always show diffs** — even for "replace" strategy files, show the diff before replacing.
- **Git is the safety net** — remind the captain they can `git diff` or `git checkout` to recover.
