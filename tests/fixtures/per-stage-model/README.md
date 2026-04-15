---
commissioned-by: spacedock@test
mission: Live test — stages.defaults.model: haiku propagates to dispatched ensign
entity-label: task
entity-label-plural: tasks
id-style: sequential
stages:
  defaults:
    worktree: false
    fresh: false
    gate: false
    concurrency: 1
    model: haiku
  states:
    - name: backlog
      initial: true
    - name: work
    - name: done
      terminal: true
---

# Per-Stage Model Test Workflow

A minimal no-gate workflow whose `stages.defaults.model` is `haiku`. Used by
`tests/test_claude_per_stage_model.py` to verify end-to-end that the
declared model propagates all the way to the dispatched ensign's runtime
model (the ensign's jsonl `message.model` should begin with `claude-haiku-`).

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

Do the trivial deliverable described in the task body.

- **Inputs:** A task description
- **Outputs:** A one-line summary appended to the task body
- **Good:** Summary matches the task description

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
