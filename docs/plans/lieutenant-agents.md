---
title: Stage-specialized lieutenant agents
id: 035
status: implementation
source: CL
started: 2026-03-27T00:00:00Z
completed:
verdict:
score: 0.80
worktree: .worktrees/ensign-lieutenant-agents
---

Replace generic ensigns with stage-specialized lieutenant agents. Each lieutenant has its own agent file with full methodology instructions, dispatched by the first officer for its specific stage.

### Current model

First officer dispatches generic ensigns with the stage definition copy-pasted into the prompt. Stage instructions are limited to what fits in the README's prose section (inputs/outputs/good/bad). Complex methodologies (TDD, brainstorming, systematic debugging) can't be embedded without bloating the README.

### Proposed model

- **Lieutenant agent files** — `.claude/agents/{stage}-lieutenant.md` (or pipeline-scoped equivalent) containing full methodology for a stage. E.g., `brainstorming-lieutenant.md` has the complete brainstorming process, `tdd-lieutenant.md` has the full TDD discipline.
- **First officer dispatches by agent type** — `subagent_type="brainstorming-lieutenant"` instead of `subagent_type="general-purpose"` with a generic prompt.
- **README stays concise** — stage definitions have inputs/outputs/good/bad criteria. The lieutenant agent file has the detailed how-to.
- **Lieutenants are team members** — they join the team, can talk directly to the captain for interactive stages, and report completion to the first officer.

### Hierarchy

Captain → First Officer → Lieutenants (stage-specialized)

Instead of: Captain → First Officer → generic ensigns

### Connection to other entities

- **Pipeline export (031)** — compiling skills (e.g., superpowers) into lieutenant agent files is the export mechanism. The compilation target is agent files, not README sections.
- **Interactive stages (019)** — lieutenants can talk directly to the captain. No special dispatch mode needed — they're team members with direct captain access.
- **Structured stage definitions (034)** — the stages frontmatter could reference which lieutenant agent to dispatch per stage.
- **Instruction files gap** (from pipeline-export spike) — resolved. The agent file IS the instruction file.

### Scope

- Design the lieutenant agent file format and naming convention
- Update the first-officer template to dispatch by agent type per stage
- Update the commission skill to generate lieutenant agent files alongside the first officer
- Define how the stages frontmatter references lieutenant agents (e.g., `agent: brainstorming-lieutenant`)
- Ensure lieutenants work as team members with direct captain communication

---

## Ideation

### Problem statement

The ensign is a generic worker — it reads a stage definition pasted into its dispatch prompt and does whatever the stage says. This works when stage instructions are short (inputs/outputs/good/bad bullets), but breaks down when a stage needs complex methodology. Examples:

- A **TDD stage** needs a multi-step discipline (write failing test, confirm failure, write minimal code, confirm pass, refactor). This doesn't fit in README prose bullets.
- A **PR workflow stage** needs to push branches, create PRs, handle review comments. These are mechanical steps that belong in an agent's instructions, not a README definition.
- A **brainstorming stage** needs interactive techniques (divergent generation, convergence, ranking). Too much for a few bullets.

The README should declare *what* a stage produces and *what good looks like*. The *how* — the detailed methodology — belongs in the agent file.

### Design: How the README frontmatter declares a stage's agent

Add an optional `agent` property to each stage in the `stages.states` block:

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
      agent: pr-lieutenant
    - name: validation
      worktree: true
      fresh: true
      gate: true
    - name: done
      terminal: true
```

Rules:
- `agent` is optional. When absent, the first officer dispatches the default `ensign` agent (current behavior).
- The value is the agent file's basename without `.md` — e.g., `agent: pr-lieutenant` maps to `.claude/agents/pr-lieutenant.md`.
- No `agent` property in `defaults` — the ensign default is hardcoded in the first officer, not configurable via defaults. This avoids confusion about what "default agent" means vs. "no agent specified."

### Design: Lieutenant agent file format

Lieutenant agent files live at `.claude/agents/{name}.md` alongside the first-officer and ensign. They use the same YAML frontmatter structure as the ensign, with the same fields:

```yaml
---
name: pr-lieutenant
description: Handles implementation with branch push and PR creation for {mission}
tools: Read, Write, Edit, Bash, Glob, Grep, SendMessage
commissioned-by: spacedock@{spacedock_version}
---
```

The body contains the full methodology for the stage. It includes:

1. **Assignment protocol** — Same as the ensign: read the dispatch prompt for entity path, stage definition, completion checklist. This is shared boilerplate.
2. **Stage methodology** — The detailed how-to that differentiates this lieutenant from a generic ensign. This is the payload — the reason the lieutenant exists.
3. **Rules** — Same as the ensign: don't modify frontmatter, don't modify agent files, ask for clarification rather than guessing.
4. **Completion protocol** — Same as the ensign: write a stage report, send a completion message.

The key insight: **a lieutenant IS an ensign with a methodology section inserted.** The assignment protocol, rules, and completion protocol are identical. The only difference is the methodology block between "read your assignment" and "write your report."

### Design: Lieutenant template structure

Create `templates/lieutenant.md` as a base template. It's structurally identical to `templates/ensign.md` but with a `## Methodology` section placeholder:

```markdown
---
name: __LIEUTENANT_NAME__
description: __LIEUTENANT_DESCRIPTION__
tools: Read, Write, Edit, Bash, Glob, Grep, SendMessage
commissioned-by: spacedock@__SPACEDOCK_VERSION__
---

# __LIEUTENANT_NAME__ — __MISSION__

You are a __LIEUTENANT_NAME__ executing stage work for the __MISSION__ pipeline.

## Your Assignment

{same as ensign — read dispatch prompt for entity, stage, checklist}

## Methodology

__METHODOLOGY__

## Working

{same as ensign — read entity file, do work, update entity, commit}

## Rules

{same as ensign — don't modify frontmatter, don't modify agent files, ask for clarification}

## Completion Protocol

{same as ensign — stage report format, completion message}
```

However, there's a question about whether we need a template at all for v0. Two options:

**Option A: Template + methodology injection.** The commission skill has a lieutenant template. For each stage with `agent:`, it generates a lieutenant file by injecting the methodology content. The methodology would need to come from somewhere — the commission skill would need to ask the captain, or the stage definition would need to reference an external source (e.g., a skill from another plugin).

**Option B: Lieutenants are hand-authored or sourced from skills.** No template — lieutenant agent files are either written by hand or compiled from pipeline-export (task 031). The commission skill only generates the first-officer and ensign. If a stage references an `agent:` that doesn't exist as a file, the commission warns but doesn't block.

For v0, **Option B is the right approach**. Reasons:
- The whole point of lieutenants is complex methodology that can't be auto-generated from a few questions. Asking the captain "what methodology should the brainstorming lieutenant use?" during commission would produce generic instructions — no better than the ensign.
- Pipeline-export (task 031) is the proper mechanism: compile a skill (like a TDD discipline or PR workflow) into a lieutenant agent file. That's a different task.
- Hand-authoring works for early adopters. CL writes `pr-lieutenant.md` with the PR workflow, drops it in `.claude/agents/`, and references it from the stage.

The commission skill's job for lieutenants is limited to:
1. **Generate the stage frontmatter** with `agent:` properties when the captain specifies a lieutenant for a stage.
2. **Warn if a referenced lieutenant file doesn't exist** after generation — "Stage 'implementation' references agent 'pr-lieutenant' but `.claude/agents/pr-lieutenant.md` does not exist. You'll need to create this file before running the workflow."
3. **Do not generate lieutenant agent files.** That's pipeline-export's job, or the captain's.

### Design: First officer dispatch changes

The first officer's dispatch logic changes minimally. Currently it hardcodes `subagent_type="ensign"`. The change:

1. When preparing to dispatch for a stage, read the stage's `agent` property from the README frontmatter.
2. If `agent` is set (e.g., `agent: pr-lieutenant`):
   - Use `subagent_type="{agent_value}"` instead of `subagent_type="ensign"`.
   - Use `name="{agent_value}-{slug}"` instead of `name="ensign-{slug}"`.
   - The dispatch prompt is identical — the stage definition, entity path, and completion checklist are the same regardless of which agent handles them.
3. If `agent` is not set: use `subagent_type="ensign"` as today.

This means the first officer template needs:
- The dispatch `Agent()` calls to use a variable agent type instead of hardcoded `"ensign"`.
- The worktree path and naming to use the agent name instead of hardcoded `ensign-` prefix: `.worktrees/{agent}-{slug}` and branch `{agent}/{slug}`.
- References to "ensign" in prose that actually mean "the dispatched worker" should be updated to be agent-agnostic, or kept as "ensign" with a note that lieutenants follow the same protocol.

The worktree/branch naming change is important: if a stage uses `pr-lieutenant`, the worktree should be `.worktrees/pr-lieutenant-{slug}` and the branch `pr-lieutenant/{slug}`, not `ensign/{slug}`. This makes it clear which agent is operating in that worktree.

Wait — this creates a problem. If an entity moves through multiple worktree stages with different agents (e.g., `implementation` uses `pr-lieutenant`, `validation` uses default `ensign`), the worktree and branch names change between stages. The current model creates one worktree per entity and reuses it across consecutive worktree stages. With different agent names, the worktree path would need to change at agent boundaries.

Simpler approach: **keep the worktree/branch naming entity-scoped, not agent-scoped.** Use `.worktrees/wt-{slug}` and branch `work/{slug}`. The agent name doesn't appear in the worktree path — it only affects `subagent_type` at dispatch time. This decouples worktree lifecycle from agent identity.

Actually, looking at the current first-officer template more carefully, the worktree is already entity-scoped conceptually — it's `ensign-{slug}` only because `ensign` is the only agent type. The `ensign-` prefix is effectively a namespace. If we drop the agent prefix entirely, worktrees are purely entity-scoped: `.worktrees/{slug}` and branch `work/{slug}`.

### Design: Ensign-lieutenant behavioral relationship

A lieutenant follows the **same behavioral contract** as an ensign:
- Reads dispatch prompt for assignment context
- Reads the entity file
- Does the work (stage-specific)
- Updates the entity file body (not frontmatter)
- Writes a stage report
- Sends a completion message

The only difference is **what "does the work" means** — the lieutenant has a methodology section that the ensign lacks. The ensign does whatever the stage definition says. The lieutenant does whatever its methodology says, guided by the stage definition.

This means:
- The completion protocol is identical — the first officer doesn't need to know whether it's talking to an ensign or a lieutenant. The message format, stage report format, and shutdown protocol are the same.
- The first officer's event loop, stage report review, gate handling, orphan detection, and merge procedures are all unchanged. The only change is which `subagent_type` to dispatch.

### Design: Concrete example — PR lieutenant

`pr-lieutenant.md` methodology section:

1. Read the entity file and implementation plan from ideation.
2. Do the implementation work (write code, tests, etc.) per the stage definition.
3. Push the worktree branch: `git push origin work/{slug}`.
4. Create a PR: `gh pr create --base main --head work/{slug} --title "{entity title}" --body "{entity description}"`.
5. Report the PR number to team-lead so the first officer can set the `pr` field.
6. If PR review comments exist (`gh pr view --comments`), address them with additional commits and push.

This methodology is specific to the PR workflow. A generic ensign doesn't know about `gh`, PR creation, or push. The PR lieutenant does.

### Design: Concrete example — TDD lieutenant

`tdd-lieutenant.md` methodology section:

1. Read the entity file and acceptance criteria.
2. For each acceptance criterion:
   a. Write a failing test that validates the criterion.
   b. Run the test to confirm it fails.
   c. Write the minimal code to make it pass.
   d. Run the test to confirm it passes.
   e. Refactor if needed, keeping tests green.
3. All tests must pass before completion.

This enforces TDD discipline that a generic ensign wouldn't follow. The stage definition says "write code and tests" — the lieutenant says *how* to write code and tests.

### What changes where

| Component | Change |
|-----------|--------|
| **README stages frontmatter** | Add optional `agent` property per stage |
| **First-officer template** | Read `agent` property; dispatch with variable `subagent_type` instead of hardcoded `"ensign"` |
| **First-officer template** | Change worktree/branch naming from `ensign-{slug}` to entity-scoped naming (e.g., `wt-{slug}` / `work/{slug}`) |
| **Commission SKILL.md** | Accept `agent:` in stage definitions during interactive design; warn if referenced agent file doesn't exist |
| **Ensign template** | No change — ensign remains the default agent |
| **Lieutenant template** | Not needed for v0 — lieutenants are hand-authored or compiled from skills |

### Open questions

1. **Worktree naming convention.** Current: `.worktrees/ensign-{slug}`, branch `ensign/{slug}`. Options:
   - Entity-scoped: `.worktrees/{slug}`, branch `work/{slug}` (decoupled from agent identity)
   - Agent-scoped: `.worktrees/{agent}-{slug}`, branch `{agent}/{slug}` (current pattern, extended)

   Leaning toward entity-scoped — it's simpler and avoids naming changes when different agents work the same entity across stages. But this is a breaking change for existing pipelines that have active worktrees with `ensign-{slug}` names.

2. **Multiple lieutenants for same stage across entities.** If different entities in the same pipeline want different agents for the same stage (e.g., some entities use `pr-lieutenant` for implementation, others use plain `ensign`), the `agent` property is on the stage definition, not the entity. All entities in a stage use the same agent. Is this too rigid? For v0, stage-level seems right — entity-level overrides add complexity with no demonstrated need.

3. **Lieutenant tools list.** The ensign has a fixed tools list. Should lieutenants declare their own tools? A PR lieutenant might need `Bash` for `gh` commands. A research lieutenant might not need `Write`. For v0, keep the same tools list as the ensign — all lieutenants get the full set. Optimize later.

4. **How does the commission skill ask about lieutenants?** During interactive design, does the commission ask "do any stages need a specialized agent?" for each stage? Or does it only ask if the captain brings it up? Leaning toward: don't ask proactively. Lieutenant usage is an advanced feature. If the captain specifies `agent: foo` in their stage definition, the commission accepts it. Otherwise, it defaults to ensign.

### Acceptance Criteria

- [ ] README stages frontmatter supports an optional `agent` property per stage state
- [ ] First-officer template reads the `agent` property and dispatches with the specified `subagent_type` (falls back to `ensign` when absent)
- [ ] Agent dispatch name follows pattern `{agent}-{slug}` for both ensigns and lieutenants
- [ ] Worktree and branch naming is consistent regardless of agent type
- [ ] Commission skill accepts `agent:` in stage state definitions and passes it through to the generated README
- [ ] Commission skill warns when a referenced lieutenant agent file does not exist after generation
- [ ] The ensign template is unchanged — lieutenants are a separate mechanism, not a modification to ensigns
- [ ] Lieutenant agent files follow the same behavioral contract as ensigns (same completion protocol, same stage report format, same rules about frontmatter)
- [ ] Existing pipelines without `agent:` properties continue to work unchanged (all stages dispatch ensign by default)
