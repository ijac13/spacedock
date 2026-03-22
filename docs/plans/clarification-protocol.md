---
title: Clarification Protocol
status: ideation
source: CL feedback
started: 2026-03-22T21:17:00Z
completed:
verdict:
score:
worktree:
---

When a backlog entity's description is unclear or ambiguous, there's no defined protocol for how the first officer or a pilot should request clarification before proceeding. This can lead to wasted work on misunderstood requirements, or agents making assumptions that diverge from intent. Define how and when agents should stop and ask for clarification.

## Problem

Agents in the pipeline (first officer and pilots) currently have no defined behavior for handling ambiguous or incomplete entity descriptions. The existing protocol has two interaction points with CL — approval gates and completion messages — but neither addresses the case where an agent *doesn't understand what to do*.

Concrete failure modes:

1. **Pilot guesses wrong.** A backlog entity says "improve status script output" — the pilot interprets this as adding color codes when CL meant adding a column for `worktree`. The pilot completes ideation with a well-structured but wrong proposal. CL catches it at the approval gate, but the ideation work is wasted.

2. **Pilot scope-creeps to fill gaps.** An entity says "add error handling." The pilot doesn't know which errors CL cares about, so it designs handling for every conceivable failure mode. The result is over-engineered and CL has to pare it back.

3. **First officer dispatches prematurely.** The first officer picks up an entity with a one-line seed description that's genuinely ambiguous (e.g., "fix the merge issue" — which merge issue?). It dispatches a pilot who wastes time investigating the wrong thing.

4. **No way to ask mid-stage.** A pilot is mid-ideation and discovers the entity depends on an architectural decision CL hasn't made yet. There's no protocol for pausing to ask — the pilot either guesses or produces a conditional design with branches CL has to sort through.

The approval gate between ideation and implementation catches *some* of these, but only after the ideation work is done. Clarification should happen *before* or *early in* the work, not after.

## Proposed Approach

### When clarification happens

Clarification is relevant at two points:

1. **Before dispatch (first officer)** — The first officer reads the entity description as part of dispatch. If the description is too ambiguous to write a useful pilot prompt, the first officer should ask CL before creating a worktree and dispatching.

2. **Early in stage work (pilot)** — The pilot reads the entity and context, and may realize the requirements are unclear or depend on decisions outside its scope. The pilot should ask CL rather than guessing.

Both cases use the same mechanism: message CL via `SendMessage` and wait for a response before continuing.

### What triggers clarification

Agents should request clarification when:

- The entity description is ambiguous enough that two reasonable interpretations would lead to materially different work products
- The entity depends on an architectural or design decision that hasn't been documented
- The entity references something that doesn't exist or can't be found in the codebase
- The scope is unclear enough that the agent can't define concrete acceptance criteria

Agents should NOT request clarification for:

- Minor ambiguities they can resolve by reading surrounding code or other entities
- Implementation details they can decide themselves within the stated scope
- Questions already answered in the pipeline README, entity body, or other pipeline entities

### The protocol

**First officer clarification (pre-dispatch):**

1. First officer identifies an entity ready for dispatch
2. First officer reads the entity and determines the description is too ambiguous to write a meaningful pilot prompt
3. First officer sends a message to CL:
   ```
   SendMessage(to="user", message="Clarification needed for {entity title} before I dispatch a pilot.\n\n{specific questions}\n\nThe entity currently says: {quote seed description}")
   ```
4. First officer moves on to other dispatchable entities (does not block the pipeline)
5. When CL responds, first officer updates the entity body with the clarification and proceeds with dispatch

**Pilot clarification (mid-stage):**

1. Pilot reads the entity and supporting context
2. Pilot identifies something that requires CL's input to proceed
3. Pilot sends a message to the team lead (first officer), which surfaces to CL:
   ```
   SendMessage(to="team-lead", message="Clarification needed on {entity title} during {stage}.\n\n{specific questions}\n\nContext: {what the pilot has understood so far}")
   ```
4. Pilot waits for a response before continuing the ambiguous part of the work (it can continue on unambiguous parts if any)
5. When CL responds (relayed by first officer), pilot incorporates the answer and continues

### What a clarification message contains

Every clarification request must include:

- **Entity name** — which entity this is about
- **Specific questions** — numbered list of concrete questions, not vague "what should I do?"
- **Context** — what the agent understands so far, so CL can see where the confusion is
- **Impact** — what the agent would do if it had to guess (so CL can say "yes, that's fine" or redirect)

This structure prevents agents from asking low-quality questions ("what do you want?") and gives CL enough context to answer quickly.

### Where this lives in the generated artifacts

The clarification protocol belongs in two places:

1. **First-officer template (SKILL.md section 2d)** — Add a "Clarification" section to the generated first-officer agent prompt, between Dispatching and Event Loop. This instructs the first officer to evaluate entity clarity before dispatch and message CL when needed.

2. **Pilot prompt template (SKILL.md section 2d, dispatch step 6)** — Add a line to the pilot prompt instructing the pilot to ask for clarification via SendMessage rather than guessing when requirements are unclear.

No changes to the pipeline README schema are needed — clarification is an agent behavior protocol, not an entity state.

### What this does NOT include

- No new entity status (like "blocked" or "needs-clarification"). Clarification is a transient interaction, not a pipeline state. The entity stays in its current status while the agent waits.
- No automated ambiguity detection. The agent uses judgment, same as a human would.
- No clarification history tracking in entity frontmatter. The clarification and its resolution are captured in the entity body as part of the normal stage work.

## Acceptance Criteria

- [ ] First-officer template in SKILL.md includes instructions to evaluate entity clarity before dispatch and message CL when the description is too ambiguous
- [ ] Pilot prompt template in SKILL.md includes instructions to ask for clarification via SendMessage rather than guessing on unclear requirements
- [ ] Clarification message format is specified (entity name, specific questions, context, what-I'd-guess)
- [ ] First-officer reference doc (`agents/first-officer.md`) updated with clarification protocol
- [ ] Protocol does not introduce new entity statuses or frontmatter fields
- [ ] Protocol does not block the pipeline — first officer can dispatch other entities while waiting for clarification
