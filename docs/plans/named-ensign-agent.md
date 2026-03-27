---
id: 046
title: Named ensign agent to replace prompt-within-a-prompt dispatch
status: validation
source: adoption feedback
started: 2026-03-26T00:00:00Z
completed:
verdict:
score: 0.80
worktree: .worktrees/ensign-named-ensign-agent
---

The first officer currently copies a ~25-line prompt template verbatim when dispatching ensigns, filling named variables. The template says "copy exactly as written" three times — fighting the LLM's tendency to paraphrase or "improve." In practice, the first officer drifts: rewording instructions, dropping lines, injecting extra context.

Replace with a named ensign agent file that defines the behavior contract once. The first officer's dispatch becomes context injection ("entity X, stage Y, pipeline at Z") rather than template reproduction.

Motivated by adoption feedback: "Simplify the ensign prompt to a reference, not inline text."

## Problem Statement

The first-officer template contains four distinct prompt constructions for ensign dispatch:

1. **Main dispatch** (Worktree: No) — ~25-line prompt template in the `Agent()` call (lines 61–66 of template)
2. **Worktree dispatch** (Worktree: Yes) — ~25-line variant with worktree path injection (lines 98–105)
3. **Validation insertion** — a multi-line block conditionally spliced into both templates above
4. **SendMessage reuse** — a shortened version of the prompt sent to an existing ensign for stage continuation (line 133)

All four share the same behavioral contract (read entity, do stage work, report via checklist, send completion message) but differ in path resolution and preamble. The first officer must copy each verbatim, filling `{named_variables}` while leaving `[BRACKETED_PLACEHOLDERS]` intact. Despite three "copy exactly" guardrails, the LLM regularly drifts — rewording, dropping the checklist protocol, or injecting pipeline-specific logic.

The root problem: the first-officer template is doing double duty as both orchestration logic AND ensign behavior specification. The ensign's behavior contract is embedded in the orchestrator's instructions as a prompt-within-a-prompt.

## Proposed Approach

### Named ensign agent file

Create a new template at `templates/ensign.md` that defines the ensign behavior contract as a Claude Code agent file. At commission time, `sed` substitutes `__VAR__` markers (same pattern as the first-officer template). At dispatch time, the first officer uses `subagent_type="ensign"` and passes only context via the `prompt` parameter.

The agent file goes to `{project_root}/.claude/agents/ensign.md` alongside `first-officer.md`.

### Agent file content

The ensign agent file defines the behavior that is currently duplicated across the four prompt constructions:

```markdown
---
name: ensign
description: Executes pipeline stage work for __MISSION__
tools: Read, Write, Edit, Bash, Glob, Grep, SendMessage
commissioned-by: spacedock@__SPACEDOCK_VERSION__
---

# Ensign — __MISSION__

You are an ensign executing stage work for the __MISSION__ pipeline.

## Your Assignment

Read the assignment context from your dispatch prompt. It tells you:
- What __ENTITY_LABEL__ you are working on
- What stage to execute
- The stage definition (inputs, outputs, quality criteria)
- Where the pipeline lives
- The completion checklist to report against

## Working

1. Read the __ENTITY_LABEL__ file at the path given in your assignment.
2. If working in a worktree, all file reads and writes MUST use paths under the worktree path given in your assignment.
3. Do the work described in the stage definition.
4. Update the __ENTITY_LABEL__ file body (not frontmatter) with your findings or outputs.
5. Commit your work before sending your completion message.

## Rules

- Do NOT modify YAML frontmatter in __ENTITY_LABEL__ files.
- Do NOT modify files under .claude/agents/ — agent files are updated via refit, not direct editing.
- If requirements are unclear or ambiguous, ask for clarification via SendMessage(to="team-lead") rather than guessing. Describe what you understand and what's ambiguous so team-lead can get you a quick answer.

## Completion Protocol

When your work is done, report the status of every checklist item from your assignment.
Mark each: DONE, SKIPPED (with rationale), or FAILED (with details).

Send a completion message:
SendMessage(to="team-lead", message="Done: {entity title} completed {stage}.

### Checklist

{numbered checklist with each item followed by — DONE, SKIPPED: rationale, or FAILED: details}

### Summary
{brief description of what was accomplished}")

Every checklist item must appear in your report. Do not omit items.
Plain text only. Never send JSON.
```

### First-officer dispatch change

The first officer's dispatch simplifies from "copy this 25-line template verbatim" to "pass context to a named agent":

**Main dispatch (Worktree: No):**
```
Agent(
    subagent_type="ensign",
    name="ensign-{slug}",
    team_name="__PROJECT_NAME__-__DIR_BASENAME__",
    prompt="You are working on: {entity title}

Stage: {next_stage_name}

### Stage definition:

[STAGE_DEFINITION]

Pipeline path: __DIR__/
Read the __ENTITY_LABEL__ file at __DIR__/{slug}.md for full context.

### Completion checklist

[CHECKLIST]"
)
```

**Worktree dispatch (Worktree: Yes):**
```
Agent(
    subagent_type="ensign",
    name="ensign-{slug}",
    team_name="__PROJECT_NAME__-__DIR_BASENAME__",
    prompt="You are working on: {entity title}

Stage: {next_stage_name}

### Stage definition:

[STAGE_DEFINITION]

Your working directory is {worktree_path}
All file reads and writes MUST use paths under {worktree_path}.
Read the __ENTITY_LABEL__ file at {worktree_path}/{relative_pipeline_dir}/{slug}.md for full context.

### Completion checklist

[CHECKLIST]"
)
```

**SendMessage reuse:**
```
SendMessage(to="ensign-{slug}", message="Next stage: {next_stage_name}

### Stage definition:

[STAGE_DEFINITION]

Continue working on {entity title}.

### Completion checklist

[CHECKLIST]")
```

The dispatch prompt shrinks from ~25 lines of behavioral instructions to ~10 lines of pure context. The behavioral contract (working rules, completion protocol, frontmatter prohibition) lives in the agent file and is automatically loaded by Claude Code.

### Validation stage handling

The validation insertion block currently gets spliced into the ensign prompt template. With a named agent, it moves into the dispatch prompt's stage definition section — the first officer includes it between the stage definition and the checklist when dispatching a validation stage. This is still a conditional insertion by the first officer, but it's a shorter block injected into a context section, not a behavioral instruction that needs verbatim reproduction.

Alternatively, the validation instructions could live in the ensign agent file itself with a conditional: "If the stage you are executing is a validation stage, also do the following..." This eliminates the conditional insertion entirely but makes the ensign file longer and couples it to the validation concept. The first approach (keep it in dispatch context) is simpler and more extensible — future stage-specific instructions follow the same pattern.

### What changes where

1. **`templates/ensign.md`** (new) — The ensign agent file template with `__VAR__` markers for commission-time substitution.
2. **`templates/first-officer.md`** — Replace the four prompt constructions with the simplified dispatch calls above. The "Dispatch on main" and "Dispatch in worktree" sections shrink significantly. The SendMessage reuse path simplifies. The validation insertion instruction remains but injects into a shorter context block.
3. **`skills/commission/SKILL.md`** — Add a new generation step (2e) to produce the ensign agent file via `sed` substitution from the template, same pattern as step 2d for the first-officer. Update the generation checklist. Update the Phase 3 announcement to mention the ensign agent file.

### How context flows at runtime

1. Commission generates `ensign.md` with pipeline-specific values baked in (`__MISSION__`, `__ENTITY_LABEL__`, etc.)
2. First officer dispatches with `subagent_type="ensign"` — Claude Code loads the agent file, giving the ensign its behavioral contract
3. The `prompt` parameter provides the context-specific assignment: which entity, which stage, stage definition, file paths, checklist
4. The ensign reads its agent file (behavior) + dispatch prompt (context) and executes

### Relationship to task 035 (lieutenant agents)

Task 035 proposes stage-specialized lieutenant agents. The named ensign agent (this task) is the v0 version: one generic agent file for all stages, with stage-specific behavior coming from the stage definition in the dispatch prompt. Lieutenants are a future upgrade where stage-specific methodology moves from the dispatch prompt into the agent file. The named ensign is a stepping stone — it establishes the pattern of "agent file = behavior, dispatch prompt = context" that lieutenants will build on.

### Relationship to task 048 (simplify first officer)

Task 048 depends on this task. Once the named ensign agent exists, the first officer sheds ~60 lines of prompt template copying (4 variants) and replaces them with ~30 lines of simplified dispatch calls. This is a prerequisite for the first officer reaching the target ~80 lines from ~285.

## Acceptance Criteria

1. A new template exists at `templates/ensign.md` defining the ensign behavior contract (working rules, completion protocol, clarification protocol, frontmatter prohibition)
2. The first-officer template dispatches with `subagent_type="ensign"` instead of `subagent_type="general-purpose"` with inline behavioral instructions
3. The dispatch `prompt` parameter contains only context (entity title, stage name, stage definition, file paths, checklist) — no behavioral instructions
4. The commission skill generates `{project_root}/.claude/agents/ensign.md` alongside the first-officer agent file
5. The SendMessage reuse path (ensign continuation) uses the same simplified context-only format
6. The validation stage insertion still works — either via the dispatch prompt or the agent file
7. The ensign agent file uses `__VAR__` markers for commission-time substitution, matching the first-officer template pattern
