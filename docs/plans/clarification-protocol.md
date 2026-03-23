---
title: Clarification Protocol
status: implementation
source: CL feedback
started: 2026-03-22T21:17:00Z
completed:
verdict:
score:
worktree: .worktrees/pilot-clarification-protocol
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

## Design (refined via brainstorming with CL)

### Core principle

Agents must never guess when uncertain. The protocol gives agents permission and instruction to stop and ask CL rather than proceeding with assumptions. No rigid message format — agents ask naturally, like a colleague would.

### When clarification happens

Clarification is relevant at two points:

1. **Before dispatch (first officer)** — The first officer reads the entity description as part of dispatch. If the description is too ambiguous to write a useful pilot prompt, the first officer should ask CL before creating a worktree and dispatching.

2. **Early in stage work (pilot)** — The pilot reads the entity and context, and may realize the requirements are unclear or depend on decisions outside its scope. The pilot should ask rather than guessing.

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

### Communication flow

**Default path: pilot → first officer → CL.** When a pilot hits ambiguity, it reports to team-lead (the first officer) via SendMessage. The first officer relays to CL and passes the answer back.

**Direct path: CL → pilot.** Since pilots are team members (dispatched via TeamCreate), CL can talk to any pilot directly at any time. The first officer includes the pilot's name when relaying a clarification request so CL knows who to address if they want to skip the relay.

**First officer's own questions.** When the first officer identifies ambiguity before dispatch, it asks CL directly and moves on to other dispatchable entities (does not block the pipeline).

Examples of good clarification:

> "The entity says 'fix the merge issue' but I see two open merge problems — the worktree merge conflict in the status script (#12) and the branch naming collision when two pilots target the same entity. Which one is this about?"

> "This entity asks for 'error handling' but doesn't specify scope. The status script has three failure points: missing files, malformed YAML, and permission errors. Should I cover all three or is there a specific one you care about?"

The key qualities: specific, shows what the agent already understands, and frames the ambiguity concretely so CL can answer quickly.

### Follow-up clarification and inconsistencies

Clarification is not capped at one round. If CL's answer raises new ambiguity, the agent must ask again rather than guessing. Agents should never skip clarification to avoid bothering CL — getting it right matters more than speed.

If CL's clarification contradicts something in the README, another entity, or the codebase, the agent must flag the inconsistency explicitly. Example:

> "Your answer says to use associative arrays, but the README constraints say bash 3.2+ only (no bash 4 features). Which takes precedence?"

CL's response resolves the conflict. If the resolution means the README or another entity needs updating, the agent notes this in its work output.

### Where this lives in the generated artifacts

The clarification protocol belongs in two places:

1. **First-officer template (SKILL.md section 2d)** — Add a "Clarification" section to the generated first-officer agent prompt, between Dispatching and Event Loop. This instructs the first officer to evaluate entity clarity before dispatch and to relay pilot clarification requests to CL.

2. **Pilot prompt template (SKILL.md section 2d, dispatch step 6)** — Add a line to the pilot prompt instructing the pilot to ask for clarification via SendMessage to team-lead rather than guessing when requirements are unclear.

No changes to the pipeline README schema are needed — clarification is an agent behavior protocol, not an entity state.

### What this does NOT include

- No new entity status (like "blocked" or "needs-clarification"). Clarification is a transient interaction, not a pipeline state. The entity stays in its current status while the agent waits.
- No automated ambiguity detection. The agent uses judgment, same as a human would.
- No clarification history tracking in entity frontmatter. The clarification and its resolution are captured in the entity body as part of the normal stage work.
- No structured message format. Agents ask naturally with enough context for CL to answer quickly.

## Implementation Summary

Three changes made:

1. **`skills/commission/SKILL.md` — first-officer template**: Added a "Clarification" section between Dispatching and Event Loop. Covers when the first officer should ask CL directly (ambiguous descriptions before dispatch), how to relay pilot clarification requests (include pilot name), and follow-up/inconsistency handling. Includes explicit instruction not to block the pipeline while waiting.

2. **`skills/commission/SKILL.md` — pilot prompt template**: Added a line in dispatch step 6's pilot prompt instructing pilots to ask for clarification via `SendMessage(to="team-lead")` rather than guessing, with guidance to describe what they understand and what's ambiguous.

3. **`agents/first-officer.md`**: Added a "Clarification Protocol" section covering the first officer's own questions, relaying pilot questions, and follow-up/inconsistency handling.

No new entity statuses, frontmatter fields, or structured message formats were introduced.

## Acceptance Criteria

- [ ] First-officer template in SKILL.md includes instructions to evaluate entity clarity before dispatch and message CL when the description is too ambiguous
- [ ] First-officer template includes instructions to relay pilot clarification requests to CL, including the pilot's name so CL can respond directly
- [ ] Pilot prompt template in SKILL.md includes instructions to ask for clarification via SendMessage to team-lead rather than guessing on unclear requirements
- [ ] First-officer reference doc (`agents/first-officer.md`) updated with clarification protocol
- [ ] Agents are instructed to ask follow-up questions if CL's answer creates new ambiguity (no cap on rounds)
- [ ] Agents are instructed to flag inconsistencies between CL's clarification and existing docs/code
- [ ] Protocol does not introduce new entity statuses or frontmatter fields
- [ ] Protocol does not block the pipeline — first officer can dispatch other entities while waiting for clarification

## Validation Report

**Recommendation: PASSED**

All 8 acceptance criteria verified against the implementation.

### Criterion 1 — First-officer template: evaluate clarity before dispatch
**PASS.** `skills/commission/SKILL.md` lines 407-420: "Clarification" section placed between Dispatching and Event Loop. Lists four triggers (ambiguous scope, undocumented decisions, nonexistent references, unclear scope) and instructs the first officer to ask CL directly.

### Criterion 2 — First-officer template: relay pilot clarification with pilot name
**PASS.** `skills/commission/SKILL.md` lines 424-427: "Relay the question to CL, including the pilot's name so CL can respond directly if they prefer. Pass CL's answer back to the pilot."

### Criterion 3 — Pilot prompt template: ask via SendMessage rather than guessing
**PASS.** `skills/commission/SKILL.md` line 377, in the pilot prompt string: "If requirements are unclear or ambiguous, ask for clarification via SendMessage(to=\"team-lead\") rather than guessing. Describe what you understand and what's ambiguous so team-lead can get you a quick answer."

### Criterion 4 — First-officer reference doc updated
**PASS.** `agents/first-officer.md` lines 55-75: "Clarification Protocol" section with three subsections covering first officer questions, relaying pilot questions, and follow-up/inconsistencies.

### Criterion 5 — Follow-up clarification not capped
**PASS.** Both `skills/commission/SKILL.md` line 429 and `agents/first-officer.md` line 73 state: "Clarification is not capped at one round."

### Criterion 6 — Flag inconsistencies
**PASS.** Both `skills/commission/SKILL.md` lines 429-431 and `agents/first-officer.md` lines 73-75 instruct agents to flag contradictions between CL's clarification and existing README, entities, or codebase.

### Criterion 7 — No new entity statuses or frontmatter fields
**PASS.** No schema changes in any file. Clarification is purely behavioral.

### Criterion 8 — Pipeline not blocked
**PASS.** `skills/commission/SKILL.md` line 420: "Do NOT block the pipeline — if one entity needs clarification, move on to other dispatchable entities while waiting." Also `agents/first-officer.md` line 64: "Do not block the pipeline — dispatch other ready entities while waiting."
