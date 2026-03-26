---
commissioned-by: spacedock@0.4.1
entity-type: entity
entity-label: task
entity-label-plural: tasks
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

# Design and Build Spacedock - Plain Text Pipeline for Agents

Spacedock is a Claude Code plugin that turns directories of markdown files into structured workflows operated by AI agents. This workflow tracks the design and implementation tasks for building Spacedock itself — from initial concepts through validated, shippable features.

## File Naming

Each task is a markdown file named `{slug}.md` — lowercase, hyphens, no spaces. Example: `pilot-worktree-isolation.md`.

The `_archive/` subdirectory holds tasks removed from the active view. Archived tasks keep their original status in frontmatter — the directory is a noise reduction mechanism, not a status. Use `git mv {slug}.md _archive/{slug}.md` to archive and `git mv _archive/{slug}.md {slug}.md` to restore.

## Schema

Every task file has YAML frontmatter with these fields:

```yaml
---
id:
title: Human-readable name
status: backlog
source:
started:
completed:
verdict:
score:
worktree:
---
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier, format determined by id-style in README frontmatter |
| `title` | string | Human-readable task name |
| `status` | enum | One of: backlog, ideation, implementation, validation, done |
| `source` | string | Where this task came from |
| `started` | ISO 8601 | When active work began |
| `completed` | ISO 8601 | When the task reached terminal status |
| `verdict` | enum | PASSED or REJECTED — set at final stage |
| `score` | number | Priority score, 0.0–1.0 (optional). Workflows can upgrade to a multi-dimension rubric in their README. |
| `worktree` | string | Worktree path while an ensign is active, empty otherwise |

## Stages

### `backlog`

A task enters backlog when it is first proposed. It has a seed description but no design work has been done yet.

- **Inputs:** None — this is the initial state
- **Outputs:** A seed task file with title, source, and brief description
- **Good:** Clear enough to understand what the task is about
- **Bad:** N/A — backlog is a holding state, not an action

### `ideation`

A task moves to ideation when a pilot starts fleshing out the idea: clarify the problem, explore approaches, and produce a concrete description of what "done" looks like.

- **Inputs:** The seed description and any relevant context (existing code, user feedback, related tasks)
- **Outputs:** A fleshed-out task body with problem statement, proposed approach, acceptance criteria, and any open questions resolved
- **Good:** Clearly scoped, actionable, addresses a real need, considers edge cases
- **Bad:** Vague hand-waving, scope creep, solving problems that don't exist yet, no clear definition of done

### `implementation`

A task moves to implementation once its design is approved. The work here is to write the code, create the files, or make whatever changes the task describes.

- **Inputs:** The fleshed-out task body from ideation with approach and acceptance criteria
- **Outputs:** Working code or artifacts committed to the repo, with a summary of what was built and where
- **Good:** Minimal changes that satisfy acceptance criteria, clean code, tests where appropriate
- **Bad:** Over-engineering, unrelated refactoring, skipping tests, ignoring edge cases identified in ideation

### `validation`

A task moves to validation after implementation is complete. The work here is to verify the implementation meets the acceptance criteria defined in ideation.

- **Inputs:** The implementation summary and the acceptance criteria from the task body
- **Outputs:**
  - Run applicable tests from the Testing Resources section and report results
  - Verify each acceptance criterion with evidence
  - A PASSED/REJECTED recommendation
- **Good:** Thorough testing against acceptance criteria, clear evidence of pass/fail, honest assessment
- **Bad:** Rubber-stamping without actually testing, ignoring failing edge cases, validating against wrong criteria

### `done`

A task reaches done when validation is complete and CL approves the result. The task is closed with a verdict of PASSED or REJECTED.

- **Inputs:** The validation report with PASSED/REJECTED recommendation
- **Outputs:** Final verdict set in frontmatter, completed timestamp recorded
- **Good:** Clear resolution, lessons learned captured if relevant
- **Bad:** Closing without reading the validation report, overriding a REJECTED recommendation without reason

## Workflow State

View the workflow overview:

```bash
bash docs/plans/status
```

Output columns: ID, SLUG, STATUS, TITLE, SCORE, SOURCE.

Include archived tasks with `--archived`:

```bash
bash docs/plans/status --archived
```

Find tasks in a specific stage:

```bash
grep -l "status: ideation" docs/plans/*.md
```

## Task Template

```yaml
---
id:
title: Task name here
status: backlog
source:
started:
completed:
verdict:
score:
worktree:
---

Description of this task and what it aims to achieve.
```

## Testing Resources

Validation pilots should use these when verifying implementation work:

| Resource | Path | Covers |
|----------|------|--------|
| Commission test harness | `scripts/test-harness.md` | Batch-mode commission invocation, generated file validation, guardrail checks |

The test harness documents how to run `claude -p` with `--plugin-dir` for non-interactive commission testing, plus structural and guardrail assertions against the generated output. Use it for any task that changes `skills/commission/SKILL.md` or the first-officer template.

## Commit Discipline

- Commit status changes at dispatch and merge boundaries
- Commit task body updates when substantive
