<!-- ABOUTME: Skill prompt for /spacedock refit — guides Claude through -->
<!-- ABOUTME: upgrading existing PTP pipeline scaffolding to the current Spacedock version. -->
---
name: refit
description: "This skill should be used when the user asks to \"refit a pipeline\", \"upgrade a pipeline\", \"update pipeline scaffolding\", or wants to bring an existing PTP pipeline's scaffolding files up to date with the current Spacedock version."
user-invocable: true
---

# Refit a PTP Pipeline

You are refitting (upgrading) an existing PTP pipeline's scaffolding files to match the current Spacedock version. Entity files are never touched — only the scaffolding infrastructure: the status script, the first-officer agent, and the README.

Follow these four phases in order. Do not skip or combine phases.

---

## Phase 1: Discovery

### Step 1 — Identify the pipeline

The user must provide a pipeline directory path. If they didn't, ask:

> Which pipeline directory should I refit?

Store the confirmed path as `{dir}`. Resolve it to an absolute path. Also derive `{project_root}` (git root or cwd) and `{dir_basename}` (last path component).

### Step 2 — Read current scaffolding and extract version stamps

Read each scaffolding file and extract its version stamp:

1. **README** — Read `{dir}/README.md`. Extract version from `<!-- commissioned-by: spacedock@X.Y.Z -->`. Store as `{readme_version}`.
2. **Status script** — Read `{dir}/status`. Extract version from `# commissioned-by: spacedock@X.Y.Z`. Store as `{status_version}`.
3. **First-officer agent** — Read `{project_root}/.claude/agents/first-officer.md`. Extract version from YAML frontmatter `commissioned-by: spacedock@X.Y.Z`. Store as `{agent_version}`.

If a file doesn't exist, note it as missing and skip it.

### Step 3 — Read current Spacedock version

Read `.claude-plugin/plugin.json` from the Spacedock plugin directory (the directory containing the `skills/` folder — resolve from your own plugin context). Extract the `version` field. Store as `{current_version}`.

### Step 4 — Evaluate

- If all found stamps match `{current_version}`: report "Pipeline is already up to date." and stop.
- If no stamps were found on any file: enter **Degraded Mode** (see below).
- Otherwise: proceed to Phase 2 with the list of outdated files.

---

## Phase 2: Classify Files by Upgrade Strategy

Each scaffolding file gets a specific upgrade strategy based on how safe it is to auto-replace:

| File | Strategy | Rationale |
|------|----------|-----------|
| `status` | **Replace** | Mechanical script. Pipeline-specific content (stage names) is extracted from the README. Users rarely customize beyond what's generated. |
| `first-officer.md` | **Regenerate** | Standard template structure with pipeline-specific values extracted from the existing README and agent. Show diff and ask CL for confirmation before replacing. |
| `README.md` | **Show diff** | Users customize stages, schema fields, quality criteria. Too risky to auto-replace. Show what the current template would produce and let CL decide. |

Present the classification to CL:

> **Upgrade plan:**
>
> | File | Current Version | Strategy |
> |------|----------------|----------|
> | `status` | {status_version or "no stamp"} | Replace |
> | `first-officer.md` | {agent_version or "no stamp"} | Regenerate (with diff review) |
> | `README.md` | {readme_version or "no stamp"} | Show diff (manual review) |
>
> Proceed?

Wait for CL to confirm before proceeding.

---

## Phase 3: Execute Upgrades

### Extract pipeline-specific values from README

Before generating any files, read `{dir}/README.md` and extract:

1. **Mission** — from the `# {title}` heading (first H1).
2. **Stages** — from the `## Stages` section. Each `### \`{stage_name}\`` subsection is a stage, in order. For each stage, extract:
   - Stage name
   - Inputs, Outputs, Good, Bad descriptions
   - Whether "Human approval: Yes" appears (indicates an approval gate for the transition INTO this stage)
3. **Schema fields** — from the `## Schema` section's YAML block.
4. **Entity description** — from the first paragraph after the H1.

Also extract from the existing first-officer (if present):
- **Pipeline absolute path** — from the `## Pipeline Path` section.

### 3a. Status Script (Replace + Materialize)

Generate the status script from the reference template at `templates/status` (relative to the Spacedock plugin directory).

1. Read the template file.
2. Fill in the two variable fields:
   - `{current_version}` — the target Spacedock version
   - `{stage1}, {stage2}, ..., {last_stage}` — the pipeline's stage names in order (extracted from README)
3. Show CL the diff between the old status script's description header and the new one. (Only the header matters — the implementation will be regenerated regardless.)
4. Replace `{dir}/status` with the filled-in template.
5. Preserve the executable bit (`chmod +x`).
6. **Materialize** — read back the description header and replace the stub body with a working bash implementation that satisfies the description. The implementation must work on bash 3.2+ (no associative arrays, no bash 4+ features). Keep the description header intact — only replace everything after it.

### 3b. First-Officer Agent (Regenerate)

1. Extract pipeline-specific values:
   - **Mission** — from README H1
   - **Pipeline directory** — `{dir}` (absolute path)
   - **Stage list** — from README stage sections
   - **Approval gates** — from README stage sections (transitions where "Human approval: Yes")
   - **Team name** — `{dir_basename}`
   - **Stages as comma-separated list** — for state management section
   - **First stage** and **last stage** — first and last in the ordered stage list

2. Generate a new first-officer using the template from the commission skill (the full template in section 2d of `skills/commission/SKILL.md`), filling in all extracted values.

3. Show CL a diff of the old vs new first-officer:

> **First-officer changes:**
> {diff output}
>
> Replace the first-officer agent? (y/n)

4. Wait for CL's confirmation before replacing.

If the user added custom sections to the first-officer (sections not in the standard template), warn CL:

> **Warning:** The existing first-officer has custom sections that aren't in the standard template. These will be lost if you replace it:
> {list of custom section headings}

### 3c. README (Show Diff)

1. Generate what the current commission template would produce for this pipeline, using the extracted values (mission, stages, schema, etc.).
2. Diff it against the user's current README.
3. Present the diff to CL, noting which differences are likely template changes vs user customizations:

> **README template diff:**
>
> The following differences exist between your README and what the current template would generate. Differences may be template improvements or your intentional customizations.
>
> {diff output}
>
> I have NOT modified your README. Review the diff and apply any changes you want manually, or tell me which specific changes to make.

Do NOT auto-modify the README. CL decides what to adopt.

---

## Phase 4: Finalize

1. Update all version stamps to `{current_version}` in files that were replaced or regenerated.
2. For the README (if CL didn't request changes), update only the version stamp comment: `<!-- commissioned-by: spacedock@{current_version} -->`.
3. Show a summary:

> **Refit complete:**
>
> | File | Action | Version |
> |------|--------|---------|
> | `status` | Replaced | spacedock@{current_version} |
> | `first-officer.md` | {Regenerated or Skipped} | spacedock@{current_version} |
> | `README.md` | {Stamp updated / User-reviewed / No changes} | spacedock@{current_version} |
>
> Suggest committing:
> ```
> git commit -m "refit: upgrade pipeline scaffolding to spacedock@{current_version}"
> ```

---

## Degraded Mode (No Version Stamp)

When no version stamps are found on any scaffolding file, the original baseline cannot be determined. Inform CL and offer two options:

> **No version stamps found.** This pipeline was commissioned before version stamping was implemented, or the stamps were removed. I can't determine what the original scaffolding looked like.
>
> Two options:
>
> 1. **Stamp only** — Add version stamps to existing files without changing anything else. This establishes a baseline for future refits.
> 2. **Full refit with review** — Generate what the current templates would produce and show a full diff for every scaffolding file. You review and approve each change.
>
> Which option?

### Option 1: Stamp Only

Add version stamps to each file without modifying anything else:

- **README.md** — Insert `<!-- commissioned-by: spacedock@{current_version} -->` as the first line.
- **status** — Insert `# commissioned-by: spacedock@{current_version}` as the second line (after `#!/bin/bash`).
- **first-officer.md** — Add `commissioned-by: spacedock@{current_version}` to the YAML frontmatter.

### Option 2: Full Refit with Review

Execute Phase 3, but show a full diff for every file (including status and first-officer) and require CL's explicit approval before replacing each one. Never auto-replace files without a version stamp — the risk of overwriting customizations is too high.

---

## Safety Rules

- **Never modify entity files** — only scaffolding (status, first-officer, README).
- **Never auto-replace without a version stamp** — always enter degraded mode.
- **Always show diffs** — even for "replace" strategy files, show the diff before replacing.
- **Git is the safety net** — remind CL they can `git diff` or `git checkout` to recover.
