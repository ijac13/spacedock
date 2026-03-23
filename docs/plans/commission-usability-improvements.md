---
title: Commission Usability Improvements
status: implementation
source: testflight-001 feedback
started: 2026-03-22T21:17:00Z
worktree: .worktrees/pilot-commission-usability-improvements
completed:
verdict:
score:
---

## Problem

The commission skill drops the user straight into questions without any greeting or context. After generation and pilot run, it doesn't tell the user what to do next — specifically how to launch a fresh session with the first-officer agent to continue working the pipeline.

Two gaps identified from testflight-001:

1. **Cold start** — Phase 1 jumps directly to "Ask CL these six questions one at a time." There is no preamble explaining what a PTP pipeline is, what the commission process involves (3 phases: design, generate, pilot run), or how long it will take. Users unfamiliar with PTP have no orientation.

2. **Dead end** — Phase 3 ends with either a pilot run results summary or a failure report. Neither path tells the user what happens next. The whole point of commissioning is to produce a pipeline the user operates going forward, but the skill never hands off.

## Approach

### Change 1: Add a greeting block before Phase 1

Insert a new section between the Batch Mode section and Phase 1 header in SKILL.md. When invoked in interactive mode (not batch), the skill should output a greeting before asking Question 1.

Proposed wording:

> Welcome to Spacedock! We're going to design a Plain Text Pipeline (PTP) together.
>
> I'll walk you through three phases:
> 1. **Design** — I'll ask you six questions to shape the pipeline
> 2. **Generate** — I'll create all the pipeline files
> 3. **Pilot run** — I'll launch the pipeline to process your seed entities
>
> Let's start designing.

Placement: This should be a directive in the skill prompt, not a hardcoded template. Add it as a "Phase 0: Greet" or as instructions at the top of Phase 1 ("Before asking Question 1, greet CL..."). The latter is simpler — just prepend a paragraph to the Phase 1 section.

For batch mode, skip the greeting — batch callers already know what they're doing.

### Change 2: Add a Step 5 to Phase 3 for post-completion guidance

After Step 4 (Handle Failures), add a final step that always runs (whether the pilot succeeded or failed). This step tells the user how to continue working the pipeline in future sessions.

Proposed wording:

> **What's next?** To continue working this pipeline in a future session, start Claude Code and use the first-officer agent:
>
> ```
> claude --agent first-officer
> ```
>
> The first officer will read the pipeline state, pick up where things left off, and dispatch pilots for any entities ready for their next stage.

This wording references the actual CLI flag (`--agent`) and the agent name (`first-officer`) so the user has a copy-pasteable command. The agent file was generated at `{project_root}/.claude/agents/first-officer.md` in Phase 2, so this name is guaranteed to resolve.

## Acceptance Criteria

- [ ] In interactive mode, the commission skill outputs a greeting explaining PTP and the 3-phase process before asking Question 1
- [ ] In batch mode, the greeting is skipped
- [ ] After Phase 3 completes (success or failure), the skill tells the user how to launch a fresh session with the first-officer agent
- [ ] The post-completion guidance includes the exact CLI command: `claude --agent first-officer`
- [ ] Both changes are prompt directives within SKILL.md (no code changes outside the skill file)

## Implementation Summary

Two prompt directive changes in `skills/commission/SKILL.md`:

1. **Greeting block** (line 32): Added a directive at the top of Phase 1 that instructs the agent to greet CL with a welcome message explaining PTP and the three-phase process before asking Question 1. The directive explicitly says to skip the greeting in batch mode.

2. **Post-completion guidance** (Step 5, line 502): Added a new Step 5 to Phase 3 that always runs after Step 3 or Step 4, telling the user how to continue working the pipeline with `claude --agent first-officer`. Includes a copy-pasteable command and a brief explanation of what the first officer does.
