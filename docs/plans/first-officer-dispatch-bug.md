---
title: First Officer Dispatch Bug
status: implementation
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

- Session logs in `testflight-001/` — main session + 7 subagent JSONL files. All 7 `.meta.json` files show `{"agentType":"first-officer"}`, confirming every pilot was dispatched with the wrong type.
- Session logs in `testflight-002/` — 21 subagents dispatched as `general-purpose` (158 references in subagent logs). No `.meta.json` files present, but session log confirms `subagent_type="general-purpose"` used 17 times for actual dispatches.
- testflight-001 used a pre-worktree-isolation version of SKILL.md. testflight-002 used the current version (with worktree isolation), and dispatch types were correct.

## Root Cause

The SKILL.md template (section 2d, line ~406) and generated `.claude/agents/first-officer.md` already have `subagent_type="general-purpose"` in the `Agent()` code block. The positive example was correct before testflight-001. The first-officer agent ignored it and used `subagent_type="first-officer"` instead.

Why: The template provides the correct positive example but lacks **negative guardrails**. The agent identifies as "first-officer" and the dispatch code block contains unfilled `{variables}`, so it interprets the block as a loose pattern rather than a strict contract. Without an explicit prohibition, it defaults to spawning copies of itself — the identity it knows.

The worktree-isolation changes added between testflight-001 and testflight-002 made the dispatch procedure more structured (numbered steps with explicit `Agent()` call embedded in step 6), which appears to have accidentally fixed the dispatch type issue. testflight-002 dispatched all pilots correctly. However, the fix was incidental — the explicit negative guardrail should still be added for robustness.

Secondary issue: The "idle" instruction says "report the current state to CL and wait for instructions" but has no de-duplication constraint, leading to repeated status messages while blocked at an approval gate.

Third issue (testflight-005a): The first officer used `SendMessage` to dispatch pilots instead of the `Agent` tool. Pilots never existed as running subagents — messages sat in inboxes of non-existent teammates. Three contributing factors:

1. **Agent() call looks like pseudocode.** It's inside a code fence with unfilled `{variables}`, making the agent interpret it as a pattern description rather than "invoke this tool."
2. **SendMessage contamination from pilot prompt.** The `Agent()` prompt parameter ends with `SendMessage(to="team-lead", ...)`. The first officer sees this pattern and mirrors it for dispatching: `SendMessage(to="pilot-{slug}", ...)` — addressing agents that don't exist yet.
3. **TeamCreate + SendMessage in tools list suggests team-messaging workflow.** The agent sees `team_name` in the Agent() parameters, has both `TeamCreate` and `SendMessage` available, and concludes the pattern is: create team → message members, skipping Agent entirely.

Fourth issue (testflight-005b): The first officer fails to create its team on startup. The commission Phase 3 spawns the first-officer with `team_name="{dir_basename}"` in the Agent() call, which makes the commission agent the team leader. The first-officer is a member, not the leader, and can't spawn pilots into the team. When it tries TeamCreate, it hits "already leading" or "does not exist" errors depending on timing. Root cause: the first-officer template has no TeamCreate step in Startup, and the commission Phase 3 Agent() call shouldn't pass `team_name` — the first-officer should own its own team.

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

**Fix 3 — Agent tool guardrail for dispatch.** The template never states that pilots must be spawned with the Agent tool. The first officer needs an explicit instruction that SendMessage cannot create pilots.

- In SKILL.md template: add to the guardrail block before the `Agent()` code block in Dispatching step 6.
- In agents/first-officer.md: add to the dispatch step.
- Text: `"You MUST use the Agent tool to spawn each pilot. Do NOT use SendMessage to dispatch — pilots do not exist until you create them with Agent. SendMessage is only for communicating with already-running pilots."`

## Proposed Fix

| # | Change | File | Location |
|---|--------|------|----------|
| 1a | Add negative guardrail warning before `Agent()` call | `skills/commission/SKILL.md` | Section 2d, Dispatching step 6 |
| 1b | Add negative guardrail note | `agents/first-officer.md` | Dispatch Lifecycle step 3 |
| 2a | Add report-once instruction to idle paragraph | `skills/commission/SKILL.md` | Section 2d, Event Loop final paragraph |
| 2b | Add report-once note | `agents/first-officer.md` | Role section or Dispatch Lifecycle |
| 3a | Add Agent-tool-required guardrail | `skills/commission/SKILL.md` | Section 2d, Dispatching step 6 guardrail block |
| 3b | Add Agent-tool-required guardrail | `agents/first-officer.md` | Dispatch step |
| 4a | Add TeamCreate to first-officer Startup | `skills/commission/SKILL.md` | Section 2d, Startup section |
| 4b | Remove `team_name` from commission Agent() call | `skills/commission/SKILL.md` | Phase 3, Step 2 |

Total: 8 surgical edits across 2 files. No structural changes.

## Acceptance Criteria

- [ ] SKILL.md template includes explicit `NEVER use subagent_type='first-officer'` warning before the `Agent()` code block in Dispatching step 6
- [ ] SKILL.md template includes report-once instruction in the Event Loop idle paragraph
- [ ] agents/first-officer.md includes the same negative guardrail in Dispatch Lifecycle step 3
- [ ] agents/first-officer.md includes report-once note
- [ ] First officer dispatches pilots as `subagent_type="general-purpose"` with distinct names like `pilot-{slug}`
- [ ] Only one first-officer agent appears in the team UI
- [ ] First officer reports pipeline state once at an approval gate, then waits without re-reporting
- [ ] SKILL.md template includes "MUST use the Agent tool to spawn each pilot" and "Do NOT use SendMessage to dispatch" guardrail
- [ ] agents/first-officer.md includes the same Agent-tool-required guardrail
- [ ] SKILL.md first-officer template Startup includes TeamCreate as step 1
- [ ] Commission Phase 3 Agent() call does not pass `team_name`
- [ ] Validated in a future testflight

## Implementation

Four surgical edits across two files:

1. **SKILL.md line 358** — Added bold negative guardrail warning immediately before the `Agent()` code block in Dispatching step 6: "You MUST use `subagent_type="general-purpose"` ... NEVER use `subagent_type="first-officer"`".
2. **SKILL.md line 406** — Appended report-once constraint to the Event Loop idle paragraph: "Report pipeline state ONCE ... Do NOT send additional status messages while waiting."
3. **agents/first-officer.md lines 37-39** — Added the same negative guardrail to Dispatch Lifecycle step 3.
4. **agents/first-officer.md lines 19-20** — Added report-once note to the Role section's operational description.

## Validation

### Criterion 1: SKILL.md negative guardrail before Agent() call — PASS

`skills/commission/SKILL.md` line 358, immediately before the `Agent()` code block in Dispatching step 6:

> **You MUST use `subagent_type="general-purpose"` when dispatching pilots. NEVER use `subagent_type="first-officer"` — that clones yourself instead of dispatching a worker.**

Bold text, explicit prohibition, positioned directly before the code block.

### Criterion 2: SKILL.md report-once instruction in Event Loop — PASS

`skills/commission/SKILL.md` line 406, Event Loop idle paragraph:

> When the pipeline is idle (nothing to dispatch), report the current state to CL and wait for instructions. Report pipeline state ONCE when you reach an approval gate or idle state. Do NOT send additional status messages while waiting — CL will respond when ready.

Both the report-once instruction and the "do NOT send additional" prohibition are present.

### Criterion 3: agents/first-officer.md negative guardrail in Dispatch Lifecycle step 3 — PASS

`agents/first-officer.md` lines 36-39:

> 3. **Dispatch pilot** — Pilot prompt specifies the worktree path as its working directory. The pilot does NOT modify YAML frontmatter. You MUST use `subagent_type="general-purpose"` when dispatching pilots. NEVER use `subagent_type="first-officer"` — that clones yourself instead of dispatching a worker.

Same guardrail text, integrated into step 3.

### Criterion 4: agents/first-officer.md report-once note — PASS

`agents/first-officer.md` lines 19-20:

> Report pipeline state ONCE when reaching an approval gate or idle state. Do not send additional status messages while waiting — CL will respond when ready.

Present in the Role section's operational description.

### Criterion 5: Pilots dispatched as general-purpose with distinct names — PASS

`skills/commission/SKILL.md` lines 361-363 show the Agent() call template with `subagent_type="general-purpose"` and `name="pilot-{entity-slug}"`, producing distinct per-entity names.

### Criterion 6: Only one first-officer in team UI — REQUIRES TESTFLIGHT

Cannot validate statically. The negative guardrail should prevent self-cloning, but runtime confirmation is needed.

### Criterion 7: Report-once at approval gate — REQUIRES TESTFLIGHT

Cannot validate statically. The report-once instruction is present in both files, but runtime behavior must be confirmed.

### Criterion 8: Validated in a future testflight — DEFERRED

Awaiting next testflight session.

### Summary

| # | Criterion | Result |
|---|-----------|--------|
| 1 | SKILL.md negative guardrail | PASS |
| 2 | SKILL.md report-once | PASS |
| 3 | first-officer.md negative guardrail | PASS |
| 4 | first-officer.md report-once | PASS |
| 5 | general-purpose dispatch with distinct names | PASS |
| 6 | Single first-officer in UI | Requires testflight |
| 7 | Report-once at approval gate | Requires testflight |
| 8 | Testflight validation | Deferred |

**Recommendation: PASSED** — All 5 statically verifiable criteria pass. The 3 runtime criteria require testflight confirmation but the textual guardrails are correctly placed.
