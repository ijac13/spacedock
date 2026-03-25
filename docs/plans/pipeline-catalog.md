---
id: 031
title: Pipeline export and release builder
status: ideation
source: CL
started: 2026-03-25T20:00:00Z
completed:
verdict:
score:
worktree:
---

Build a mechanism to export/compile a working pipeline into a standalone, distributable folder. Not a catalog/marketplace — focus on the build step.

### Practical examples

**1. Email-triage pipeline** — a commissioned pipeline with custom stages (intake → review → execute), gws-cli integration, multi-account support. Can we build a standalone folder from it that someone else drops into their project?

**2. Superpowers skills as pipeline agents** — superpowers has skills (brainstorming, TDD, debugging, etc.) with graphviz workflows and detailed instructions. Can we package ("compile") them into a self-contained `docs/plans/superpowers/` directory where those skills become agent teammate instructions within a pipeline?

### What "export" means

Strip a working pipeline down to its reusable parts:
- README (schema + stages) — the pipeline definition
- Status script — the view
- First-officer template — the orchestrator
- Stage-specific agent instructions (compiled from skills or custom prompts)
- Manifest with metadata (name, description, required tools/integrations)
- NOT the entity instances (the actual work items) — those are project-specific

The output is a folder that can be dropped into a new project, commissioned from, or shared.

---

## Spike: Superpowers Skills as a PTP Pipeline

### Analysis of Superpowers Skill Structure

Superpowers v5.0.2 contains 14 skills. Each skill is a markdown file with YAML frontmatter (`name`, `description`) and a detailed prompt body. The body contains:

- **Purpose statement** and overview
- **When-to-use guidance** (often with graphviz decision trees)
- **Step-by-step process** (checklists, phases, numbered procedures)
- **Quality criteria** (good/bad examples, red flags, rationalizations tables)
- **Integration references** to other skills (e.g., "invoke writing-plans skill")
- **Graphviz workflow diagrams** defining decision trees and process flows

Skills fall into three categories:

1. **Process orchestrators** — `using-superpowers` (router), `brainstorming` (ideation), `writing-plans` (planning), `executing-plans`/`subagent-driven-development` (execution), `finishing-a-development-branch` (completion)
2. **Discipline enforcers** — `test-driven-development`, `systematic-debugging`, `verification-before-completion` (cross-cutting quality gates)
3. **Workflow utilities** — `using-git-worktrees`, `dispatching-parallel-agents`, `requesting-code-review`, `receiving-code-review`, `writing-skills`

The key structural insight: superpowers is already a pipeline. The `using-superpowers` skill is a router that selects other skills based on context. `brainstorming` flows to `writing-plans` flows to `subagent-driven-development` flows to `finishing-a-development-branch`. This is a linear pipeline with conditional branches (debugging as a side-loop, code review as quality gates at multiple points).

The inter-skill invocation model is: skill A tells the agent "invoke skill B next." The agent loads skill B via the Skill tool and follows its instructions. This is dynamic dispatch — the agent decides which skill applies based on runtime context.

### Prototype Sketch: Superpowers as Pipeline

#### What are the entities?

Each entity is a **feature** (or bug fix, or task) — a unit of work that progresses from idea to merged code. This maps directly to what superpowers already processes.

#### What are the stages?

Mapping superpowers' natural flow to pipeline stages:

```
brainstorming → planning → implementation → validation → done
```

- **brainstorming** — explore the idea, clarify requirements, write a design spec (brainstorming skill content becomes the stage definition)
- **planning** — create a detailed implementation plan from the spec (writing-plans skill)
- **implementation** — execute the plan using TDD (subagent-driven-development + test-driven-development skills)
- **validation** — verify the implementation (verification-before-completion + requesting-code-review skills)
- **done** — merged, branch cleaned up (finishing-a-development-branch skill)

#### Proposed directory layout

```
docs/superpowers/
├── README.md              # Schema + 5 stage definitions
├── status                 # Status viewer
├── _archive/              # Completed entities
└── *.md                   # Active feature entities
```

#### Where skill content ends up

Each stage definition in the README would embed the relevant skill's instructions as the stage's Inputs/Outputs/Good/Bad criteria. For example, the `brainstorming` stage definition would contain the brainstorming skill's checklist, process flow, and key principles — not as a skill reference, but as literal stage instructions that an ensign follows.

Cross-cutting skills (TDD, debugging, verification) would be referenced in multiple stage definitions. The `implementation` stage would embed TDD instructions. The `validation` stage would embed verification-before-completion instructions.

#### What the first officer does

The first officer dispatches ensigns per-stage as it does today. For the brainstorming stage, an ensign gets the brainstorming instructions and works with the captain interactively. For implementation, the ensign gets TDD + subagent-driven-development instructions.

### Technical Gap Analysis

**1. Interactive stages are the hard problem.**

Brainstorming requires interactive dialogue with the user — asking questions one at a time, proposing approaches, presenting design sections for approval. PTP ensigns are currently fire-and-forget: dispatch, do work, report back. An ensign running brainstorming would need to send multiple messages to the captain and receive responses mid-execution. The first officer currently handles this via SendMessage relay, but the brainstorming process requires a sustained, multi-turn conversation — not just a one-off clarification.

This is the biggest gap. The current model assumes an ensign can do its stage work independently. Brainstorming fundamentally cannot.

**2. Stage definitions would be very long.**

Superpowers skill files are 100-370 lines each. Embedding full skill content into a README stage definition makes the README unwieldy (potentially 1000+ lines). The current README format assumes stage definitions are concise (5-10 lines of inputs/outputs/good/bad).

Options: (a) keep stage defs concise and reference external instruction files, (b) accept a giant README. Option (a) requires a new PTP convention for "instruction files" alongside the README — currently not part of the spec.

**3. Conditional transitions and decision trees.**

Superpowers skills contain graphviz decision trees: "if bug, invoke debugging; if feature, invoke brainstorming." PTP stages are linear with approval gates. There's no mechanism for conditional stage transitions based on entity type or runtime assessment.

For example: `systematic-debugging` is invoked when a test fails during implementation. In PTP, this would mean an entity in the `implementation` stage could loop back to itself (or enter a `debugging` sub-stage) based on runtime conditions. PTP doesn't support this — the first officer would need custom logic.

**4. Sub-agent dispatch within a stage.**

The `subagent-driven-development` skill dispatches multiple sub-agents per task (implementer + spec reviewer + code quality reviewer). A PTP ensign is a single agent. Either the ensign itself needs to dispatch sub-agents (which it can — it has the Agent tool), or the pipeline needs to model the review loop as separate stages. The former works but means the stage definition becomes a mini-orchestration prompt. The latter bloats the stage count.

**5. Skills that are meta-instructions, not work instructions.**

`using-superpowers` is a router — it tells the agent how to select skills. `using-git-worktrees` is infrastructure setup. `receiving-code-review` is behavioral guidance for how to handle feedback. These don't map to pipeline stages at all. They're system-level configuration, not entity-processing steps. In a pipeline, they'd need to be embedded as general agent behavior rules rather than stages.

### UX Assessment

**What you gain from superpowers-as-pipeline:**

- **Visibility** — `bash status` shows where every feature is in the process. With skill invocation, there's no persistent state; each session starts from scratch.
- **Concurrency** — Multiple features can progress simultaneously. The first officer handles dispatch, worktree isolation, and merge coordination. With raw superpowers, you manage one feature at a time in a single conversation.
- **Resumability** — If a session dies, the pipeline state is on disk. The first officer picks up where things left off. With superpowers, session death means starting over (or hoping the agent remembers context).
- **Audit trail** — Entity files accumulate design specs, plans, and validation results in their body. With superpowers, artifacts go to `docs/superpowers/specs/` and `docs/superpowers/plans/` — scattered and not tied to a single entity.

**What you lose:**

- **Interactivity** — Brainstorming's greatest strength is its interactive, conversational nature. One question at a time, visual companion, iterative refinement. Flattening this into a pipeline stage loses the collaborative feel. The captain has to interact with an ensign through the first officer relay, adding latency and reducing fluency.
- **Dynamic skill selection** — Superpowers' router (`using-superpowers`) picks the right skill based on context. A pipeline forces a fixed stage sequence. A bug fix doesn't need brainstorming; a config change doesn't need TDD. The pipeline either processes everything through all stages (wasteful) or needs conditional skip logic (not currently supported).
- **Skill updates** — Superpowers skills are maintained by the superpowers project. When they update, you get improvements automatically. A compiled pipeline is a snapshot — it doesn't update when the source skills evolve.
- **Simplicity** — Invoking `/superpowers brainstorming` is simple and direct. Running a pipeline involves the first officer, ensigns, worktrees, merge coordination, approval gates — significantly more machinery for what may be the same outcome.

**The honest assessment:**

The superpowers workflow is fundamentally interactive and adaptive. It selects skills based on runtime context (what's the task? what went wrong? what's the right next step?). PTP is fundamentally sequential and state-based — entities move through fixed stages.

These are different execution models solving different problems:
- **Superpowers** = adaptive, interactive, context-sensitive skill selection for a single agent working with a human
- **PTP** = state machine for tracking work items through defined stages with dispatch, concurrency, and resumability

The overlap is real (both process features through a lifecycle) but the fit is poor at the edges. The interactive stages (brainstorming) and adaptive routing (debugging as a side-loop) don't map well to PTP's fixed-stage model.

### Recommendation: Park

The superpowers-as-pipeline prototype is instructive for understanding the boundaries of PTP, but it's not a practical compilation target for v0. The core issues:

1. **Interactive stages** require sustained multi-turn dialogue that the current ensign model doesn't support well.
2. **Adaptive routing** (pick the right skill for the situation) requires conditional transitions that PTP doesn't have.
3. **The value proposition is marginal** — superpowers already works well as a skill invocation system. The pipeline adds visibility and concurrency, but at the cost of interactivity and adaptability.

A better near-term focus for pipeline export would be **domain-specific pipelines** (email triage, content review, test suites) where stages are non-interactive, entity processing is independent, and the fixed-stage model is a natural fit. These are the pipelines where PTP's strengths (state tracking, concurrency, resumability) matter most and its weaknesses (inflexible routing, non-interactive stages) matter least.

If we wanted to revisit superpowers-as-pipeline later, the prerequisite features would be:
- **Instruction files** — stage-specific instruction documents referenced from the README, so skill content doesn't bloat the README
- **Conditional transitions** — allow stage routing based on entity properties or runtime assessment
- **Interactive stages** — a stage mode where the ensign has a sustained conversation with the captain, not just fire-and-forget dispatch

These are all interesting PTP evolution directions, but they shouldn't be driven by the superpowers use case alone.
