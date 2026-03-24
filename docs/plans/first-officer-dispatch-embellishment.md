---
title: Prevent LLM from embellishing first-officer dispatch template
status: backlog
source: testflight fresh commission observation
started:
completed:
verdict:
score: 0.82
worktree:
---

The first-officer template in SKILL.md section 2d contains an ensign dispatch prompt with `{Copy the full stage definition from the README here: inputs, outputs, good, bad}`. This is a runtime instruction to the first-officer (copy at dispatch time), but the LLM generating the first-officer reads it as a generation-time variable and expands it into pipeline-specific dispatch logic.

Observed: generated first-officer had sections like "### Intake Read Strategy (for intake stage)" — hardcoded stage-specific logic that should only live in the README.

The template is supposed to be copied literally with variable substitution, per the instruction "Use the following template, filling ALL {variables} from the design phase." But the `{Copy...}` text looks like a variable, so the LLM "helpfully" expands it.

Fix: use a marker that clearly isn't a template variable (e.g., `[STAGE_DEFINITION_PLACEHOLDER]`) with a comment explaining it's filled at runtime. Or add a guardrail: "Do NOT expand or customize the ensign prompt template — copy it exactly, only filling {named_variables}."
