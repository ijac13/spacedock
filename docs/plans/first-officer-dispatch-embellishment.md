---
title: Prevent LLM from embellishing first-officer dispatch template
status: ideation
source: testflight fresh commission observation
started: 2026-03-24T19:25:00Z
completed:
verdict:
score: 0.82
worktree:
---

The first-officer template in SKILL.md section 2d contains an ensign dispatch prompt with `{Copy the full stage definition from the README here: inputs, outputs, good, bad}`. This is a runtime instruction to the first-officer (copy at dispatch time), but the LLM generating the first-officer reads it as a generation-time variable and expands it into pipeline-specific dispatch logic.

Observed: generated first-officer had sections like "### Intake Read Strategy (for intake stage)" — hardcoded stage-specific logic that should only live in the README.

The template is supposed to be copied literally with variable substitution, per the instruction "Use the following template, filling ALL {variables} from the design phase." But the `{Copy...}` text looks like a variable, so the LLM "helpfully" expands it.

## Design

Two changes in SKILL.md section 2d, applied to both ensign dispatch prompt templates (Worktree: No and Worktree: Yes):

### Change 1: Replace the ambiguous marker

In both prompt templates, replace:
```
{Copy the full stage definition from the README here: inputs, outputs, good, bad}
```
with:
```
[STAGE_DEFINITION — at dispatch time, copy the full stage definition from the README: inputs, outputs, good, bad]
```

Square brackets + ALL_CAPS prefix clearly distinguishes this from `{named_variables}` that the LLM fills at generation time. The explanatory text remains so the first-officer knows what to do at runtime.

### Change 2: Add guardrail comment above the template

Above each `Agent(...)` call block, add a one-line instruction to the generating LLM:

> **Copy the ensign prompt template exactly as written. Only fill `{named_variables}` — do not expand, rewrite, or customize any other text (including bracketed placeholders).**

This is belt-and-suspenders: even if the marker format doesn't fully prevent expansion, the explicit instruction catches it.

### Change 3: Agent file protection guardrail

Add to each ensign prompt template, after the "Do NOT modify YAML frontmatter" line:
```
Do NOT modify files under .claude/agents/ — agent files are updated via refit, not direct editing.
```

## Acceptance Criteria

1. Both ensign dispatch prompt templates (Worktree: No at ~line 416, Worktree: Yes at ~line 448) use `[STAGE_DEFINITION — ...]` instead of `{Copy the full stage definition...}`.
2. Each template block has a guardrail comment above it instructing the generating LLM to copy verbatim.
3. Both prompt templates include the agent-file protection line.
4. No other changes to SKILL.md — the fix is minimal and scoped to section 2d.
