---
mission: Push main before PR test
entity-label: task
entity-label-plural: tasks
id-style: sequential
commissioned-by: spacedock@test
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
      worktree: true
    - name: done
      terminal: true
---

# Push Main Before PR Test Workflow

A minimal no-gate workflow for testing that the pr-merge mod pushes main before pushing the branch.

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
pr:
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
pr:
---

{description}
```
