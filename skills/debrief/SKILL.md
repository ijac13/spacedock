---
name: debrief
description: "This skill should be used when the user asks to \"debrief\", \"record what happened\", \"session summary\", \"write a debrief\", or wants to capture session activity (commits, task state changes, decisions, issues) into a structured record for the next session."
user-invocable: true
---

# Session Debrief

You are producing a session debrief — a structured record of what happened during a workflow session. The debrief captures commits, task state changes, gate decisions, issues found, and observations. It feeds forward into the next session so the first officer starts with context instead of cold.

Follow these phases in order. Do not skip or combine phases.

---

## Phase 1: Discovery

### Step 1 — Identify the workflow

The user may provide a workflow directory path as an argument. If they didn't, search for it:

1. Run `project_root="$(git rev-parse --show-toplevel)"`.
2. Search for README.md files with `commissioned-by: spacedock@` in frontmatter: `grep -rl '^commissioned-by: spacedock@' --include='README.md' --exclude-dir=node_modules --exclude-dir=.worktrees --exclude-dir=.git --exclude-dir=vendor --exclude-dir=dist --exclude-dir=build --exclude-dir=__pycache__ "$project_root"`.
3. If exactly one is found, use its directory as `{dir}`. If multiple, ask which one. If none, report "No Spacedock workflow found."

Store the confirmed path as `{dir}`.

### Step 2 — Determine session boundaries

Check for an existing debrief to anchor the session start:

1. Look for `{dir}/_debriefs/*.md` files. Sort by filename (lexicographic = chronological).
2. If a prior debrief exists, read the most recent one's YAML frontmatter and extract the `last-commit` field. The current session starts from the next commit after that hash.
3. If no prior debrief exists, fall back: use `git log --oneline --reverse -- {dir} | head -1` to find the first-ever commit in the workflow directory, or use commits from the last 24 hours if the history is large.

Derive `{from_commit}` (the starting boundary). Run:

```bash
git log {from_commit}..HEAD --oneline -- {dir}
```

Present the session boundary to the captain:

> **Session boundary**
>
> Since: `{from_commit}` ({date or description})
> Commits in scope: {count}
>
> Adjust? (confirm or provide a different starting commit)

Wait for confirmation before proceeding.

### Step 3 — Read workflow metadata

Read `{dir}/README.md` frontmatter to extract:
- Entity label and plural form
- Stage names and ordering
- Which stages are gates, have `feedback-to`, use worktrees

---

## Phase 2: Extract Session Data

All extraction uses git and local files only — no external services.

### 2a. Commits

```bash
git log {from_commit}..HEAD --oneline -- {dir}
```

Group commits by entity slug. Parse commit message prefixes to categorize:
- `dispatch:` — stage transitions
- `done:` — completed entities (archived)
- `fix:` — bug fixes
- `feat:` — features added
- `refit:` — scaffolding upgrades
- Other prefixes — list as-is

Store the full list and the first/last commit hashes for frontmatter.

### 2b. Task state changes

For each entity file in `{dir}/*.md` and `{dir}/_archive/*.md`, read the YAML frontmatter. Identify entities that changed status during this session by cross-referencing with commit messages containing `dispatch:` or `done:` prefixes.

For each changed entity, record:
- Entity slug, ID, and title
- Stage transitions that occurred (from commit messages)
- Current status
- Verdict (if completed)

### 2c. Gate decisions

Scan for gate-related activity:
- Entities that advanced past gated stages (approved gates)
- Entities that were rejected at gates (look for `feedback-to` cycles in commit messages or entity files with `### Feedback Cycles` sections)
- Extract reasoning from stage reports where available

### 2d. Issues found

Scan for issues:
- Commits with `fix:` prefix in the workflow directory
- Entity files whose `## Stage Report` sections contain `FAIL` items
- Any notable problems mentioned in stage reports

Categorize each issue into two buckets:

1. **Workflow-specific** — bugs or quirks in the user's pipeline (their stages, entities, agent instructions). These stay as local notes in the debrief.
2. **Spacedock issues** — bugs or limitations in the spacedock framework itself (first-officer template, commission skill, status script, ensign behavior, agent platform issues). These are candidates for GitHub issue filing.

### 2e. What's next

Run `{dir}/status --next` to find dispatchable entities. Also run `{dir}/status` to identify:
- Entities blocked at gates (waiting for captain)
- Entities with non-empty `worktree` field (in-progress or orphaned)
- Overall workflow state

---

## Phase 3: Draft and Review

### Step 1 — Present the draft

Assemble the extracted data into a draft debrief and present it to the captain:

> **Draft Debrief — {date} #{sequence}**
>
> ## Work Completed
> {list of entities that completed stages, with one-line summaries}
>
> ## Commits
> {grouped by entity}
>
> ## Decisions
> {placeholder — captain fills this in}
>
> ## Issues — Workflow
> {workflow-specific issues found}
>
> ## Issues — Spacedock
> {spacedock framework issues found}
>
> ## Observations
> {placeholder — captain fills this in}
>
> ## What's Next
> {dispatchable entities, gate-blocked entities, deferred items}
>
> ---
> Add your commentary to **Decisions** and **Observations**, or confirm as-is.

### Step 2 — Captain commentary

Wait for the captain to:
- Add decisions (why gates were approved/rejected, scope changes, course corrections)
- Add observations (design insights, process improvements, things to remember)
- Edit any section
- Or confirm the draft as-is

Incorporate the captain's input into the final debrief.

### Step 3 — Handle spacedock issues

For each issue categorized as a spacedock issue, offer to file a GitHub issue:

1. Read the spacedock repo URL from the plugin manifest. Find the Spacedock plugin directory by locating the `skills/` folder that contains this skill file. Read `.claude-plugin/plugin.json` from that directory and extract the `repository` field.

2. For each spacedock issue, draft an **anonymized** GitHub issue. The issue body must NOT contain:
   - The user's actual mission or workflow purpose
   - Entity titles or content
   - Specific domain details

   Instead, include:
   - Clear description of the bug or limitation
   - Reproduction steps (using generic terms like "entity", "stage", "workflow")
   - Scale context: entity count, stage count, linear vs branching flow
   - Spacedock version (from `commissioned-by` in `{dir}/README.md` frontmatter)

3. Present each draft issue to the captain:

> **File as GitHub issue?**
>
> **Title:** {issue title}
> **Body:**
> {anonymized issue body}
>
> (y/n/edit)

4. If yes: run `gh issue create --repo {repo_url} --title "{title}" --body "{body}"` and record the issue URL.
5. If edit: let the captain modify title/body, then file.
6. If no: note "not filed" in the debrief.

If `gh` is not authenticated or fails, report the error and suggest the captain file manually.

---

## Phase 4: Write Debrief File

### Step 1 — Determine sequence number

Look at existing files in `{dir}/_debriefs/` matching today's date pattern `{YYYY-MM-DD}-*.md`. The sequence number is one more than the highest existing sequence for today, or `1` if none exist.

### Step 2 — Calculate duration

Derive approximate session duration from the timestamp of the first and last commits in scope:

```bash
git log {from_commit}..HEAD --format='%ai' -- {dir} | head -1
git log {from_commit}..HEAD --format='%ai' -- {dir} | tail -1
```

Calculate the difference as a human-readable duration (e.g., `~2h30m`).

### Step 3 — Write the file

```bash
mkdir -p {dir}/_debriefs
```

Write the debrief to `{dir}/_debriefs/{date}-{sequence:02d}.md`:

```markdown
---
session-date: {YYYY-MM-DD}
sequence: {N}
first-commit: {hash}
last-commit: {hash}
duration: {approximate duration}
---

# Session Debrief — {YYYY-MM-DD} #{N}

## Work Completed
{entity entries with stage completions and one-line summaries}

## Commits
{grouped by entity slug, each commit as "- `{hash}` {message}"}

## Decisions
{captain-contributed content, or empty if none provided}

## Issues — Workflow
{workflow-specific issues, or "None identified." if empty}

## Issues — Spacedock
{spacedock issues with filing status: "filed as owner/repo#N" or "not filed"}
{or "None identified." if empty}

## Observations
{captain-contributed content, or empty if none provided}

## What's Next
{dispatchable entities, gate-blocked entities, deferred items}
```

### Step 4 — Commit the debrief

```bash
git add {dir}/_debriefs/{date}-{sequence:02d}.md
git commit -m "debrief: session {date} #{sequence} — {summary}"
```

Where `{summary}` is a brief count like "8 tasks completed, 3 new filed".

Report the file path to the captain:

> Debrief written to `{dir}/_debriefs/{date}-{sequence:02d}.md` and committed.
