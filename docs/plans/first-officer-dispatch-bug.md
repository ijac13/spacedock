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

## Analysis

### Root cause

The SKILL.md template (section 2d, line ~406) and the generated `.claude/agents/first-officer.md` both already specify `subagent_type="general-purpose"` in the `Agent()` code block. The template was correct before testflight-001. The first-officer agent ignored its own template and used `subagent_type="first-officer"` instead.

Two contributing factors:

1. **No negative guardrail.** The template provides the correct example but never explicitly prohibits `subagent_type="first-officer"`. The agent sees itself as a "first-officer," the dispatch code block contains unfilled `{variables}` making it look like a loose pattern rather than a strict contract, and without an explicit prohibition the agent defaulted to spawning copies of itself.

2. **Possible pattern contamination from commission context.** The commission skill's Phase 3 (SKILL.md line 506) correctly uses `Agent(subagent_type="first-officer", ...)` to launch the first-officer itself. If any of this context leaks into the first-officer's conversation window (e.g., through system prompt history or agent memory), the agent may have mimicked this `subagent_type="first-officer"` pattern for its own dispatch calls. The negative guardrail addresses this regardless of contamination path.

The redundant status reporting has a simpler cause: the "idle" instruction (SKILL.md Event Loop, line 440) says "report the current state to CL and wait for instructions" but never says "only once." The agent interpreted "wait" as a loop and kept re-reporting.

### Audit of current code

**Fix 1 — Negative guardrail for `subagent_type`**

| Location | Current state | Needed? |
|----------|---------------|---------|
| `skills/commission/SKILL.md` section 2d, step 6 (line 402-411) | `Agent()` block uses `subagent_type="general-purpose"` but has no warning text prohibiting `subagent_type="first-officer"` | YES |
| `agents/first-officer.md` Dispatch Lifecycle step 3 (line 32-33) | Says "Dispatch pilot" with worktree path; no mention of `subagent_type` at all | YES |

**Fix 2 — Report-once instruction**

| Location | Current state | Needed? |
|----------|---------------|---------|
| `skills/commission/SKILL.md` section 2d, Event Loop (line 440) | "report the current state to CL and wait for instructions" — no "once" or "do not re-report" language | YES |
| `agents/first-officer.md` | No report-once guidance anywhere | YES |

**Fix 3 — Code block formatting**

The dispatch example in SKILL.md is already a fenced code block. No change needed. Already correct.

### Scope note

The commission skill's Phase 3 (SKILL.md line 506) uses `subagent_type="first-officer"` to launch the first-officer agent from the commission conversation. This is correct and MUST NOT be changed — the fix only applies to the first-officer template's dispatch of pilot workers.

## Proposed Fix

### Fix 1 — Explicit negative guardrail in the dispatch section

Add a bold warning immediately before the `Agent()` code block:

> **You MUST use `subagent_type="general-purpose"` when dispatching pilots. NEVER use `subagent_type="first-officer"` — that would clone yourself instead of dispatching a worker.**

Insertion points:
- `skills/commission/SKILL.md` line ~403, between step 6 text ("Dispatch pilot in the worktree:") and the `Agent()` code block
- `agents/first-officer.md` Dispatch Lifecycle step 3 — append to the existing step text, specifying that pilots use `subagent_type="general-purpose"`

### Fix 2 — Report-once instruction for approval gates and idle state

Replace the bare "report and wait" sentence with explicit once-only language:

> Report pipeline state ONCE when you reach an approval gate or idle state. Do NOT send additional status messages while waiting — CL will respond when ready.

Insertion points:
- `skills/commission/SKILL.md` section 2d, Event Loop final paragraph (line 440) — replace "report the current state to CL and wait for instructions"
- `agents/first-officer.md` — add an "Idle Behavior" subsection after Dispatch Lifecycle

### Fix 3 — No change needed

Code block formatting is already correct.

### Files to change

| File | Section | Change |
|------|---------|--------|
| `skills/commission/SKILL.md` | Section 2d, Dispatching step 6 (before `Agent()` block) | Add negative guardrail warning |
| `skills/commission/SKILL.md` | Section 2d, Event Loop final paragraph (line 440) | Replace "report...wait" with report-once instruction |
| `agents/first-officer.md` | Dispatch Lifecycle step 3 (line 32-33) | Add `subagent_type="general-purpose"` requirement and negative guardrail |
| `agents/first-officer.md` | After Dispatch Lifecycle section | Add "Idle Behavior" subsection with report-once note |

## Acceptance Criteria

- [ ] SKILL.md template includes explicit `NEVER use subagent_type="first-officer"` warning before the `Agent()` code block in section 2d
- [ ] SKILL.md template Event Loop section says "Report pipeline state ONCE" with "Do NOT re-report" language
- [ ] `agents/first-officer.md` Dispatch Lifecycle step 3 specifies `subagent_type="general-purpose"` and prohibits `subagent_type="first-officer"`
- [ ] `agents/first-officer.md` includes idle behavior / report-once guidance
- [ ] Commission skill Phase 3 (`subagent_type="first-officer"`) is left unchanged
- [ ] Validated in a future testflight: only one first-officer in the team UI, pilots dispatched as `general-purpose`, status reported once at gates
