---
title: Stage-specialized lieutenant agents
id: 035
status: backlog
source: CL
started:
completed:
verdict:
score: 0.80
worktree:
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
