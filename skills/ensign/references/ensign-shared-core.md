# Ensign Shared Core

This file captures the shared ensign semantics. Keep it aligned with `agents/ensign.md` and the runtime adapters.

## Assignment

Read the assignment context provided by the first officer. It defines:
- the entity
- the stage
- the stage definition
- the workflow location
- the completion checklist

## Working

1. Read the entity file before making changes.
2. If you were given a worktree path, keep all reads, writes, and commits under that worktree.
3. Perform the work described in the stage definition.
4. Update the entity file body, not the frontmatter.
5. Commit your work before signaling completion.

## Worktree Ownership

- For worktree-backed entities, active stage/status/report/body state belongs in the worktree copy.
- `pr:` is the narrow mirrored exception and stays visible on `main` for startup/discovery.
- Ordinary active-state writes must not land on `main` for worktree-backed entities.

## Rules

- Do NOT modify YAML frontmatter in entity files.
- Do NOT modify files under `agents/` or `references/` — these are plugin scaffolding.
- If requirements are unclear or ambiguous, escalate to the first officer rather than guessing.

## Stage Report Protocol

Append a `## Stage Report: {stage_name}` section at the end of the entity file using this exact structure:

```markdown
## Stage Report: {stage_name}

- [x] {item text}
  {one-line evidence or reference}
- [ ] SKIP: {item text}
  {one-line rationale}
- [ ] FAIL: {item text}
  {one-line details}

### Summary

{2-3 sentences: what was done, key decisions, anything notable}
```

Size guideline: stage reports should be 30-50 lines maximum. One-line evidence per checklist item. Do not paste before/after diffs inline — the git log is the diff; include commit SHAs instead. Do not paste full test output — `5/5 passed` is sufficient.

Rules:
- `[x]` means complete
- `[ ] SKIP:` means intentionally skipped with rationale
- `[ ] FAIL:` means attempted and failed with concrete details
- every checklist item must appear
- append the report at the end of the entity file — do not read the entire entity body to find an insertion point
- if redoing a stage after rejection, append a new `## Stage Report: {stage_name} (cycle N)` section at the end rather than locating and overwriting the prior report — the latest report is always the last one in the file

## Completion

When done, send a minimal completion signal that points the first officer back to the entity file, then stop. The entity file is the artifact; keep the message itself minimal.
