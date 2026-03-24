<!-- commissioned-by: spacedock@0.1.3 -->
<!-- entity-type: entity -->
<!-- entity-label: entity -->
<!-- entity-label-plural: entities -->

# Design and Build Spacedock - Plain Text Pipeline for Agents

Spacedock is a Claude Code plugin that turns directories of markdown files into lightweight project pipelines. This pipeline tracks the design and implementation tasks for building Spacedock itself — from initial concepts through validated, shippable features.

## File Naming

Each entity is a markdown file named `{slug}.md` — lowercase, hyphens, no spaces. Example: `pilot-worktree-isolation.md`.

## Schema

Every entity file has YAML frontmatter with these fields:

```yaml
---
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
| `title` | string | Human-readable entity name |
| `status` | enum | One of: backlog, ideation, implementation, validation, done |
| `source` | string | Where this entity came from |
| `started` | ISO 8601 | When active work began |
| `completed` | ISO 8601 | When the entity reached terminal status |
| `verdict` | enum | PASSED or REJECTED — set at final stage |
| `score` | number | Priority score, 0.0–1.0 (optional). Pipelines can upgrade to a multi-dimension rubric in their README. |
| `worktree` | string | Worktree path while an ensign is active, empty otherwise |

## Stages

### `backlog`

An entity enters backlog when it is first proposed. It has a seed description but no design work has been done yet.

- **Inputs:** None — this is the initial state
- **Outputs:** A seed entity file with title, source, and brief description
- **Good:** Clear enough to understand what the entity is about
- **Bad:** N/A — backlog is a holding state, not an action
- **Human approval:** No

### `ideation`

A task moves to ideation when a pilot starts fleshing out the idea: clarify the problem, explore approaches, and produce a concrete description of what "done" looks like.

- **Inputs:** The seed description and any relevant context (existing code, user feedback, related tasks)
- **Outputs:** A fleshed-out entity body with problem statement, proposed approach, acceptance criteria, and any open questions resolved
- **Good:** Clearly scoped, actionable, addresses a real need, considers edge cases
- **Bad:** Vague hand-waving, scope creep, solving problems that don't exist yet, no clear definition of done
- **Human approval:** No

### `implementation`

A task moves to implementation once its design is approved. The work here is to write the code, create the files, or make whatever changes the task describes.

- **Inputs:** The fleshed-out entity body from ideation with approach and acceptance criteria
- **Outputs:** Working code or artifacts committed to the repo, with a summary of what was built and where
- **Good:** Minimal changes that satisfy acceptance criteria, clean code, tests where appropriate
- **Bad:** Over-engineering, unrelated refactoring, skipping tests, ignoring edge cases identified in ideation
- **Human approval:** Yes — CL approves the design before implementation begins.

### `validation`

A task moves to validation after implementation is complete. The work here is to verify the implementation meets the acceptance criteria defined in ideation.

- **Inputs:** The implementation summary and the acceptance criteria from the entity body
- **Outputs:** A validation report: what was tested, what passed, what failed, and a PASSED/REJECTED recommendation
- **Good:** Thorough testing against acceptance criteria, clear evidence of pass/fail, honest assessment
- **Bad:** Rubber-stamping without actually testing, ignoring failing edge cases, validating against wrong criteria
- **Human approval:** No

### `done`

A task reaches done when validation is complete and CL approves the result. The entity is closed with a verdict of PASSED or REJECTED.

- **Inputs:** The validation report with PASSED/REJECTED recommendation
- **Outputs:** Final verdict set in frontmatter, completed timestamp recorded
- **Good:** Clear resolution, lessons learned captured if relevant
- **Bad:** Closing without reading the validation report, overriding a REJECTED recommendation without reason
- **Human approval:** Yes — CL approves the final verdict before the task is closed.

## Pipeline State

View the pipeline overview:

```bash
bash docs/plans/status
```

Find entities in a specific stage:

```bash
grep -l "status: ideation" docs/plans/*.md
```

## Entity Template

```yaml
---
title: Entity name here
status: backlog
source:
started:
completed:
verdict:
score:
worktree:
---

Description of this entity and what it aims to achieve.
```

## Testing Resources

Validation pilots should use these when verifying implementation work:

| Resource | Path | Covers |
|----------|------|--------|
| Commission test harness | `v0/test-harness.md` | Batch-mode commission invocation, generated file validation, guardrail checks |

The test harness documents how to run `claude -p` with `--plugin-dir` for non-interactive commission testing, plus structural and guardrail assertions against the generated output. Use it for any entity that changes `skills/commission/SKILL.md` or the first-officer template.

## Concurrency

Maximum 2 entities per stage at any time. The first officer must check stage counts before dispatching and hold entities in their current stage until a slot opens.

## Commit Discipline

- Commit status changes at session end, not on every transition
- Commit research outputs and entity body updates when substantive
