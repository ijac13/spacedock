---
mission: Dispatch name uniqueness test
entity-label: task
entity-label-plural: tasks
id-style: sequential
stages:
  defaults:
    worktree: false
    fresh: false
    gate: false
    concurrency: 2
  states:
    - name: backlog
      initial: true
    - name: work
    - name: review
    - name: done
      terminal: true
---

# Dispatch Name Uniqueness Test Pipeline

A minimal no-gate pipeline for testing that each dispatch uses a unique agent name.

## File Naming

Kebab-case slug: `my-task.md`

## Schema

```yaml
---
id: "001"
title: Short description
status: backlog
score: 0.50
source: test
started:
completed:
verdict:
worktree:
---
```

## Stages

### backlog

The initial holding stage.

- **Inputs:** A task description
- **Outputs:** The task exists with status backlog

### work

The task is actively being worked on.

- **Inputs:** A task in backlog
- **Outputs:** A brief summary of work done appended to the task body
- **Good:** Clear, concise summary
- **Bad:** No summary, or unrelated changes

### review

Verify the work is acceptable.

- **Inputs:** A task with work completed
- **Outputs:** A brief review note appended to the task body
- **Good:** Confirms work meets requirements
- **Bad:** Rubber-stamp with no substance

### done

Terminal stage. The task is complete.

## Commit Discipline

Prefix commits with the stage name: `work: did the thing`

## Task Template

```markdown
---
id: "{id}"
title: "{title}"
status: backlog
score: 0.50
source: test
started:
completed:
verdict:
worktree:
---

{description}
```
