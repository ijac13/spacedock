---
title: Use initialPrompt frontmatter for first-officer auto-start
id: 033
status: done
source: Claude Code changelog
started: 2026-03-25T19:00:00Z
completed: 2026-03-26T14:55:00Z
verdict: PASSED
score: 0.45
worktree:
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

1. Generated first-officer frontmatter includes `initialPrompt: "Report pipeline status."`
2. Generated first-officer body does NOT contain an `## AUTO-START` section
3. `agents/first-officer.md` reference doc reflects the new `initialPrompt` approach
4. Test harness checks for `initialPrompt` instead of `AUTO-START`
5. All existing test checks still pass (the other guardrails are unchanged)
6. The first-officer file is generated deterministically (not LLM-generated prose)

## Implementation Summary

### Done

1. **`skills/commission/SKILL.md`** — Added `initialPrompt: "Report pipeline status."` to the generated first-officer frontmatter. Removed the `## AUTO-START` section from the body. Refactored the template to use `${VAR}` bash variable substitution for commission-time variables (mission, dir, entity_label, etc.) while runtime variables (`{slug}`, `{next_stage}`) pass through unchanged.

2. **`agents/first-officer.md`** — Updated to note that `initialPrompt` triggers the startup sequence.

3. **`v0/test-commission.sh`** — Replaced `AUTO-START` check with `initialPrompt` check.

### Blocking issue: commission LLM ignores the heredoc template

The commission LLM rewrites the first-officer content instead of using the bash heredoc with variable substitution, even with explicit "do NOT rewrite" instructions. The generated first-officer is missing `initialPrompt`, `commissioned-by`, and `TeamCreate` in tools — the LLM writes its own version.

This is the same root cause as the dispatch-embellishment problem, but worse: guardrail comments can prevent expansion of placeholders, but they can't force the LLM to use a heredoc instead of writing content directly.

### Proposed solution: extract template to a separate file

Extract the first-officer template from SKILL.md into a standalone file (e.g., `skills/commission/first-officer.tmpl`). The commission skill tells the LLM to:

1. Set bash variables from the design phase
2. Run `sed` substitutions on the template file
3. Write the result to `.claude/agents/first-officer.md`

The LLM's only job is computing variable VALUES, not touching template CONTENT. The template file is copied verbatim with mechanical substitution — no LLM involvement in the output.

This is architecturally equivalent to treating commission as a compiler: the template is a binary format, the LLM handles the frontend (gathering inputs), and sed/bash handles the backend (emitting output).

## Validation Report

### Test results

Ran `bash v0/test-commission.sh` — all 59 checks passed, 0 failed.

### Acceptance criteria verification

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | Generated first-officer frontmatter includes `initialPrompt: "Report pipeline status."` | PASS | `templates/first-officer.md` line 6 contains the field; test check "first-officer contains 'initialPrompt'" passed |
| 2 | Generated first-officer body does NOT contain `## AUTO-START` section | PASS | `grep AUTO-START templates/first-officer.md` returns no matches; section fully removed |
| 3 | `agents/first-officer.md` reference doc reflects `initialPrompt` approach | PASS | Lines 17-18 now mention `initialPrompt` triggers startup; line 85 lists it in frontmatter fields |
| 4 | Test harness checks for `initialPrompt` instead of `AUTO-START` | PASS | `test-commission.sh` line 189 keyword changed from `AUTO-START\|auto-start` to `initialPrompt` |
| 5 | All existing test checks still pass | PASS | 59/59 checks passed including all guardrails, frontmatter, leaked variable, and absolute path checks |
| 6 | First-officer file is generated deterministically (not LLM-generated prose) | PASS | SKILL.md section 2d now uses `sed` substitution on `templates/first-officer.md` with `__VAR__` markers; no LLM prose generation |

### Additional observations

- The implementation went beyond the original acceptance criteria by extracting the first-officer template from SKILL.md into `templates/first-officer.md`. This was necessary because the LLM was rewriting the heredoc template content instead of using it verbatim. The template extraction is a sound architectural improvement that directly addresses criterion 6 (deterministic generation).
- The test harness documentation (`v0/test-harness.md` line 139) still references "AUTO-START instruction" as a check item, but this is a prose description, not an executable check. The actual test script was correctly updated. This is a minor documentation inconsistency — not a failure.

### Recommendation: PASSED
