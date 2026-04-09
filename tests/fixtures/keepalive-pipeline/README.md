---
commissioned-by: spacedock@test
mission: Feedback keepalive test
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
    - name: implementation
      worktree: true
    - name: validation
      worktree: true
      fresh: true
      feedback-to: implementation
      gate: true
    - name: done
      terminal: true
---

# Feedback Keepalive Test Workflow

A minimal workflow for testing that the first officer keeps the implementation agent alive when dispatching validation (which has `feedback-to: implementation`), and routes rejection feedback to the kept-alive agent via SendMessage.

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

- **Inputs:** None — this is the initial state
- **Outputs:** A seed task file with title, source, and brief description

### implementation

Complete the work described in the task.

- **Inputs:** A task description with acceptance criteria
- **Outputs:** Deliverables committed to the worktree
- **Good:** Deliverables that satisfy the acceptance criteria
- **Bad:** Missing or incorrect deliverables

### validation

Verify the implementation meets the acceptance criteria.

- **Inputs:** The implementation and acceptance criteria from the task body
- **Outputs:** A PASSED/REJECTED recommendation with evidence
- **Good:** Thorough testing, clear evidence of pass/fail
- **Bad:** Rubber-stamping without testing

### done

Terminal stage. The task is complete.

## Testing Resources

| Resource | Path | Covers |
|----------|------|--------|
| Add test | `tests/test_add.py` | Tests for add function (deliberately buggy — forces validation rejection) |

## Commit Discipline

Prefix commits with the stage name: `implementation: did the thing`

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
