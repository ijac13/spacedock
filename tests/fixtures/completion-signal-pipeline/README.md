---
commissioned-by: spacedock@test
mission: Team dispatch completion-signal regression test
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
      worktree: true
    - name: done
      terminal: true
---

# Team Dispatch Completion-Signal Test Workflow

A minimal no-gate workflow with one worktree-enabled stage. Used to regression-test
that a team-dispatched ensign actually signals completion so the first officer can
advance the entity past the `work` stage without manual captain intervention.

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

Do the trivial deliverable described in the task body. This stage runs in a worktree.

- **Inputs:** A task description
- **Outputs:** The deliverable file committed to the worktree and a one-line summary appended to the task body
- **Good:** File exists with the exact content requested
- **Bad:** File missing or content differs

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
