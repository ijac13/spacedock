---
title: First Officer Dispatch Bug
status: ideation
source: testflight-001
started: 2026-03-22T21:47:00Z
worktree:
completed:
verdict:
score:
---

## Problem

During testflight-001, the first officer spawned 3 agents all typed as `first-officer` instead of dispatching pilots as `subagent_type="general-purpose"`. The Claude Code UI showed:

```
@first-officer: 0 tool uses · 44.8k tokens    (coordinator — did nothing)
@first-officer: 38 tool uses · 53.3k tokens   (did ideation work)
@first-officer: 39 tool uses · 55.6k tokens   (did ideation work)
```

The first officer is supposed to be a DISPATCHER that never does stage work itself. Instead it cloned itself, wasting tokens on duplicate agent prompts and confusing the team UI.

Additionally, the first officer sent 3 redundant status reports while waiting at the approval gate instead of reporting once and staying idle.

## Evidence

Session logs in `testflight-001/` — main session + 4 subagent JSONL files.

## Root Cause

The SKILL.md template (section 2d, line ~406) and generated `.claude/agents/first-officer.md` already have `subagent_type="general-purpose"` in the `Agent()` code block. The positive example was correct before testflight-001. The first-officer agent ignored it and used `subagent_type="first-officer"` instead.

Why: The template provides the correct positive example but lacks **negative guardrails**. The agent identifies as "first-officer" and the dispatch code block contains unfilled `{variables}`, so it interprets the block as a loose pattern rather than a strict contract. Without an explicit prohibition, it defaults to spawning copies of itself — the identity it knows.

Secondary issue: The "idle" instruction says "report the current state to CL and wait for instructions" but has no de-duplication constraint, leading to repeated status messages while blocked at an approval gate.

## Analysis

### What is already correct

- SKILL.md template section 2d, Dispatching step 6: `Agent()` call uses `subagent_type="general-purpose"` (line 406)
- agents/first-officer.md: describes the first officer as "a dispatcher" that "never performs stage work itself" (lines 14-15)
- The dispatch example is a fenced code block, not pseudocode — formatting is fine

### What is missing

**Fix 1 — Negative guardrail for dispatch type.** Neither file explicitly prohibits `subagent_type="first-officer"`. The agent needs a direct "NEVER do X" instruction, not just a positive example of "do Y".

- In SKILL.md template: add a bold warning immediately before the `Agent()` code block in section 2d, Dispatching step 6.
- In agents/first-officer.md: add a note in the Dispatch Lifecycle, step 3.
- Text: `"You MUST use subagent_type='general-purpose' when dispatching pilots. NEVER use subagent_type='first-officer' — that clones yourself instead of dispatching a worker."`

**Fix 2 — Report-once constraint for idle/approval-gate states.** The Event Loop section's idle paragraph (SKILL.md line 440, agents/first-officer.md equivalent) lacks a de-dup instruction.

- In SKILL.md template: append to the "pipeline is idle" sentence in the Event Loop section.
- In agents/first-officer.md: add a note under the Role section or Dispatch Lifecycle.
- Text: `"Report pipeline state ONCE when you reach an approval gate or idle state. Do NOT send additional status messages while waiting — CL will respond when ready."`

**Fix 3 — No change needed.** Code block formatting is already correct. The issue was not formatting but the absence of negative guardrails (addressed by Fix 1).

## Proposed Fix

| # | Change | File | Location |
|---|--------|------|----------|
| 1a | Add negative guardrail warning before `Agent()` call | `skills/commission/SKILL.md` | Section 2d, Dispatching step 6 |
| 1b | Add negative guardrail note | `agents/first-officer.md` | Dispatch Lifecycle step 3 |
| 2a | Add report-once instruction to idle paragraph | `skills/commission/SKILL.md` | Section 2d, Event Loop final paragraph |
| 2b | Add report-once note | `agents/first-officer.md` | Role section or Dispatch Lifecycle |

Total: 4 surgical edits across 2 files. No structural changes.

## Acceptance Criteria

- [ ] SKILL.md template includes explicit `NEVER use subagent_type='first-officer'` warning before the `Agent()` code block in Dispatching step 6
- [ ] SKILL.md template includes report-once instruction in the Event Loop idle paragraph
- [ ] agents/first-officer.md includes the same negative guardrail in Dispatch Lifecycle step 3
- [ ] agents/first-officer.md includes report-once note
- [ ] First officer dispatches pilots as `subagent_type="general-purpose"` with distinct names like `pilot-{slug}`
- [ ] Only one first-officer agent appears in the team UI
- [ ] First officer reports pipeline state once at an approval gate, then waits without re-reporting
- [ ] Validated in a future testflight
