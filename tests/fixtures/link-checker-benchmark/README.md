---
mission: Build a Markdown link checker CLI
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
    - name: ideation
      gate: true
    - name: implementation
    - name: validation
    - name: done
      terminal: true
---

# Markdown Link Checker CLI

Build a CLI utility that reads a Markdown file, extracts all `[text](url)` links, checks each URL for HTTP reachability, and reports broken links with line numbers.

## File Naming

Kebab-case slug: `my-task.md`

## Schema

```yaml
---
id: "001"
title: Short description
status: backlog
score: 0.50
source: benchmark
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

### ideation

Design the approach before implementation.

- **Inputs:** A task description with acceptance criteria
- **Outputs:** A concrete design appended to the task body, including: data structures, function signatures, error handling strategy, and trade-off analysis for key decisions
- **Good:** Specific design with named functions and clear data flow; acknowledges edge cases
- **Bad:** Vague hand-waving ("we'll handle errors"), no concrete function signatures, copy-paste of the task description

### implementation

Write the code described in the ideation design.

- **Inputs:** A task with an approved design from ideation
- **Outputs:** Working Python code in `src/linkcheck/` that implements the design. Code must be importable and runnable.
- **Good:** Clean, idiomatic Python; follows the approved design; handles the edge cases identified in ideation
- **Bad:** Ignores the design; no error handling; monolithic code with no structure

### validation

Write tests and verify the implementation works.

- **Inputs:** Implemented code from the implementation stage
- **Outputs:** Test files in `tests/` that cover happy path, edge cases, and failure modes. Test results appended to the task body.
- **Good:** Tests exercise real behavior (not mocks); cover edge cases identified in ideation; all tests pass
- **Bad:** Trivial tests that don't verify real behavior; tests that only check mocked returns; tests that fail

### done

Terminal stage. The task is complete.

## Testing Resources

Run tests with: `python3 -m pytest tests/ -v`

## Project Structure

```
src/
  linkcheck/
    __init__.py
    extract.py      # Link extraction from markdown
    check.py        # URL reachability checking
    report.py       # Output formatting
    cli.py          # CLI entry point
tests/
  test_extract.py
  test_check.py
  test_report.py
```

## Commit Discipline

Prefix commits with the stage name: `implementation: add link extraction module`

## Task Template

```markdown
---
id: "{id}"
title: "{title}"
status: backlog
score: 0.50
source: benchmark
started:
completed:
verdict:
worktree:
---

{description}
```
