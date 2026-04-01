---
mission: Spike termination test (no gates)
commissioned-by: spacedock@0.8.4
entity-label: task
entity-label-plural: tasks
id-style: sequential
stages:
  defaults:
    worktree: false
    fresh: false
    gate: false
    concurrency: 1
  states:
    - name: backlog
      initial: true
    - name: work
    - name: done
      terminal: true
---

# Spike Termination Test (No Gates)

A minimal workflow for testing session termination behavior in `claude -p` mode.

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
