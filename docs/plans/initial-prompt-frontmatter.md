---
title: Use initialPrompt frontmatter for first-officer auto-start
id: 033
status: implementation
source: Claude Code changelog
started: 2026-03-25T19:00:00Z
completed:
verdict:
score: 0.45
worktree: .worktrees/ensign-init-prompt
---

## Problem

Claude Code now supports `initialPrompt` in agent frontmatter. When present, it auto-submits the prompt as the first user turn without waiting for input. The first-officer agent currently relies on a `## AUTO-START` section in the body that instructs the LLM to "begin immediately." This is a prompt convention — the LLM can ignore it. Using `initialPrompt` makes auto-start a platform feature: Claude Code itself submits the first turn, guaranteeing the agent starts working.

Current state in `skills/commission/SKILL.md` (the generated first-officer template):
- Frontmatter has: `name`, `description`, `tools`, `commissioned-by`
- Body ends with a `## AUTO-START` section containing: "Begin immediately. Read the pipeline, run status, dispatch the first worker. Do not wait for user input unless an approval gate requires it."

## Proposed Approach

### 1. `skills/commission/SKILL.md` — first-officer template (section 2d, lines ~386-611)

**Frontmatter change:** Add `initialPrompt` field to the generated frontmatter:

```yaml
---
name: first-officer
description: Orchestrates the {mission} pipeline
tools: Agent, TeamCreate, SendMessage, Read, Write, Edit, Bash, Glob, Grep
commissioned-by: spacedock@{spacedock_version}
initialPrompt: "Begin pipeline dispatch."
---
```

**Body change:** Remove the `## AUTO-START` section entirely (lines 607-610 of SKILL.md). The section is:

```markdown
## AUTO-START

Begin immediately. Read the pipeline, run status, dispatch the first worker. Do not wait for user input unless an approval gate requires it.
```

This section is redundant once `initialPrompt` handles auto-start. The body already has a detailed `## Startup` section that tells the agent exactly what to do — the AUTO-START section was only there to trigger that sequence without user input.

### 2. `agents/first-officer.md` — reference doc

Update the reference doc to mention that `initialPrompt` in frontmatter triggers the startup sequence. Currently line 17 says "On startup it reads the pipeline README, runs the status script..." — add a note that startup is triggered by `initialPrompt` frontmatter.

In the "Full Template Specification" section (line 82), add a note that the template includes `initialPrompt` in frontmatter.

### 3. `v0/test-commission.sh` — test harness

**Current check (line 189):** Looks for `AUTO-START|auto-start` in the generated first-officer file as a content completeness check.

**Change:** Replace the AUTO-START check with a check for `initialPrompt` in the frontmatter. The new check should verify that the first-officer frontmatter contains an `initialPrompt` field:

```bash
# Replace this line in the KEYWORD loop:
# "AUTO-START|auto-start"
# With:
"initialPrompt"
```

This stays in the existing completeness check loop structure — just swap the keyword.

### 4. `initialPrompt` value

**CL direction:** The initial prompt should trigger a status report, not directly start dispatching. The first officer reads the pipeline and reports state — CL then decides what to dispatch.

The value should be: `"Report pipeline status."`

This triggers the Startup sequence (read README, run status, check orphans) and the first officer reports the current state to CL before dispatching anything. CL retains control over what moves next.

### 5. Backward compatibility

Existing commissioned pipelines that already have the `## AUTO-START` body section will continue to work — the LLM still reads that section and starts. They just won't benefit from the platform-level `initialPrompt` trigger. No migration is needed; existing pipelines can be updated via a future `refit` command or manually.

## Acceptance Criteria

1. Generated first-officer frontmatter includes `initialPrompt: "Begin pipeline dispatch."`
2. Generated first-officer body does NOT contain an `## AUTO-START` section
3. `agents/first-officer.md` reference doc reflects the new `initialPrompt` approach
4. Test harness checks for `initialPrompt` instead of `AUTO-START`
5. All existing test checks still pass (the other guardrails are unchanged)

## Implementation Summary

Three files changed:

1. **`skills/commission/SKILL.md`** — Added `initialPrompt: "Report pipeline status."` to the generated first-officer frontmatter (after `commissioned-by`). Removed the `## AUTO-START` section from the generated body.

2. **`agents/first-officer.md`** — Updated the Role section to note that `initialPrompt` triggers the startup sequence. Added the full list of generated frontmatter fields (`name`, `description`, `tools`, `commissioned-by`, `initialPrompt`) to the Full Template Specification section.

3. **`v0/test-commission.sh`** — Replaced `"AUTO-START|auto-start"` with `"initialPrompt"` in the keyword completeness check loop (line 189).
