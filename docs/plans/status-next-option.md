---
id: 045
title: Add --next option to status script for dispatchable entity detection
status: ideation
source: adoption feedback
started: 2026-03-26T00:00:00Z
completed:
verdict:
score: 0.85
worktree:
---

The first officer currently scans entity frontmatter manually to determine what's dispatchable. This is mechanical work (check stage ordering, concurrency limits, worktree status) that an LLM does unreliably — it's branching logic over structured data.

Add a `--next` option to the status script that outputs which entities are ready for their next stage. The status script already parses frontmatter; this extends it with stage ordering and concurrency awareness.

Motivated by adoption feedback: "Move the mechanical parts into code. The status script already exists — extend that pattern."

## Problem Statement

The first officer's dispatch loop requires determining which entities are ready for their next stage. This involves: reading stage ordering, checking concurrency limits, detecting gate-blocked entities, and identifying active worktrees. The first officer does this by reading raw frontmatter and applying branching logic — exactly the kind of mechanical work LLMs do poorly. Mistakes here mean dispatching into full concurrency slots, re-dispatching gated entities, or missing ready entities.

## Proposed Approach

### Parse stage metadata from README at runtime

The README frontmatter is the single source of truth for stage definitions. The `--next` option reads the `stages` block from `README.md` at runtime so that changes to stage properties (gates, concurrency, worktree flags) take effect immediately without re-commissioning or refitting.

### Language choice: bash+python3 hybrid vs. full Python rewrite

**Option A: Bash script with inline python3 for `--next`** (recommended)

The existing status view stays pure bash. When `--next` is passed, the bash script delegates to an inline `python3 -c '...'` block that handles README parsing, entity scanning, dispatch logic, and output. The description-header template pattern is unchanged.

Pros:
- Minimal change to existing pattern — the base status view is untouched
- No impact on existing commissioned pipelines — `bash {dir}/status` still works
- The first-officer template calls `bash __DIR__/status`; no need to update

Cons:
- Two languages in one file (bash shell + inline python3)
- python3 dependency for `--next` (not for base status)

**Option B: Full Python rewrite**

Replace the entire status script with Python. Both the base status view and `--next` are Python. The template becomes `#!/usr/bin/env python3` with description-header comments.

Pros:
- Single language, cleaner long-term
- Python handles both flat entity YAML and nested README YAML naturally
- Easier to add future options

Cons:
- **Breaking change**: Every existing commissioned pipeline has `bash __DIR__/status` hardcoded in its first-officer agent file. A Python script invoked as `bash {dir}/status` would fail. This requires updating the first-officer template AND refitting all existing pipelines.
- Changes the commission template pattern (materialization target language)
- python3 becomes a hard dependency for all status operations, not just `--next`
- PyYAML (`import yaml`) is not in Python stdlib — still need string-based YAML parsing or add a dependency

**Recommendation: Option A.** The breaking-change cost of a full rewrite isn't justified for adding one option. The hybrid approach is pragmatic — bash for the simple stuff, python3 for the one thing bash can't do. If the script accumulates more options that need structured data, a full rewrite can be reconsidered then.

### Architecture

When `--next` is passed, the bash script delegates to an inline python3 block that:

1. Reads `README.md` frontmatter and extracts the `stages` block (defaults + states list)
2. Scans all `*.md` files (excluding README.md) and extracts each entity's `id`, `status`, `score`, `worktree` from frontmatter
3. Applies dispatch eligibility rules
4. Outputs the formatted table

This keeps the `--next` logic self-contained in python3 rather than splitting it across bash and python. The existing status view (no `--next`) remains pure bash.

### Dispatch eligibility rules

An entity is dispatchable if ALL of the following are true:

1. **Not terminal** — its current stage has a defined next stage
2. **Not gate-blocked** — its current stage does NOT have `gate: true` (gate means "awaiting approval to leave this stage")
3. **Not actively worked** — entity does NOT have a non-empty `worktree` field in its frontmatter (worktree = ensign currently active)
4. **Concurrency available** — the count of entities already in the next stage is below that stage's concurrency limit

### Output format

When invoked with `--next`, the script outputs a table:

```
ID     SLUG                 CURRENT        NEXT           WORKTREE
--     ----                 -------        ----           --------
001    my-feature           backlog        ideation       no
012    other-task           implementation validation     yes
```

Columns:
- **ID** — entity identifier
- **SLUG** — entity filename without .md
- **CURRENT** — current stage
- **NEXT** — stage the entity would advance to
- **WORKTREE** — whether the next stage uses a worktree ("yes"/"no")

Sorted by score descending (highest priority first), matching the first officer's dispatch priority.

When no entities are dispatchable, output the header row and no data rows (consistent with the main status view behavior).

### README frontmatter parsing

The python3 code needs to parse this structure from README.md:

```yaml
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
    - name: done
      terminal: true
```

Parsing strategy (no `import yaml` needed):
1. Extract frontmatter (between first and second `---`)
2. Find the `stages:` block by indentation
3. Extract `defaults:` values
4. Split `states:` on `- name:` boundaries
5. For each state, read properties as key-value pairs, applying defaults for missing values
6. Build ordered stage list with properties

### What changes where

1. **`templates/status`** — Add `--next` option to the description header comments, documenting the runtime README parsing, dispatch rules, output format, and python3 dependency.
2. **`skills/commission/SKILL.md`** — Update section 2b materialization instructions to include the `--next` implementation. The commission generates the python3 inline block alongside the existing bash implementation.
3. **`docs/plans/status`** (the live instance) — Recompile from updated template for this pipeline, validating the implementation end-to-end.

### Edge cases

- **Non-linear transitions** — The README frontmatter supports a `transitions` block for non-linear flows. For v0, all pipelines are linear (the transitions block is "omit for linear workflows"). The `--next` option only needs to handle linear stage ordering. If `transitions` exists, that's a future concern.
- **Entities in `_archive/`** — Never dispatchable. The `--next` option only scans the main directory, matching the first officer's behavior ("only scan the main directory — the `_archive/` subdirectory holds terminal entities and is ignored for dispatch").
- **Empty worktree field** — YAML `worktree:` with nothing after the colon means empty (no active worktree). The python3 code treats empty/missing worktree as "no active ensign."
- **Stage not found** — If an entity's status doesn't match any known stage, skip it (not dispatchable).
- **python3 not available** — Print an error message and exit non-zero. python3 is available on macOS (ships with Xcode CLI tools) and virtually all Linux distros where Claude Code runs.
- **No `stages` block in README** — Print an error and exit non-zero. The `--next` option requires structured stage metadata.

## Acceptance Criteria

1. `bash {dir}/status --next` outputs a table of dispatchable entities with columns: ID, SLUG, CURRENT, NEXT, WORKTREE
2. Stage metadata (ordering, gate, terminal, worktree, concurrency) is parsed from README frontmatter at runtime
3. Entities in terminal stages are excluded
4. Entities in gated stages are excluded
5. Entities with non-empty worktree fields are excluded
6. Entities whose next stage is at concurrency capacity are excluded
7. Output is sorted by score descending (highest priority first)
8. The template (`templates/status`) is updated with the `--next` description
9. The commission skill generates the `--next` implementation correctly for any pipeline
10. Graceful error if python3 is unavailable or README lacks a stages block
