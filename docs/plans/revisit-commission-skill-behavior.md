---
id: 191
title: "Revisit commission skill behavior for first-time vs experienced users"
status: backlog
source: "captain observation — the current interactive commission flow treats all users the same, which underserves both ends: first-time users don't get enough scaffolding to discover what 'good' looks like for their mission, and experienced users have to sit through questions whose answers they already know."
started:
completed:
verdict:
score: 0.5
worktree:
issue:
pr:
mod-block:
---

## Why this matters

The commission skill (`skills/commission/SKILL.md`) owns the first-touch experience for anyone creating a new spacedock workflow. Today's interactive flow walks every user through the same sequence of questions (mission, entity label, stages, gates, etc.) without adapting to what the user already knows.

Two personas are underserved:

### Persona 1 — First-time user

They want to build a workflow but don't yet have a mental model for what "good" looks like. Questions like "what should your stages be?" or "what's your entity label?" land cold — they don't know enough to answer well.

**What they need (candidate):** the skill could help them reason about their mission BEFORE asking mechanical questions. Something like:
- "Describe what you're trying to accomplish — what's the outcome if this workflow succeeds?"
- "Tell me about one concrete example of a thing this workflow will handle. I'll help you generalize it into an entity shape."
- "Here are 3 example workflows from existing projects that roughly match what you described. Pick the closest, and I'll adapt."

Or: let them say "I don't know yet" and have the skill generate a reasonable default structure they can refine later.

### Persona 2 — Experienced user

They already have a rough shape in mind — "this is an approval-gated editorial pipeline with three review rounds" — and just want to get to a running workflow.

**What they need (candidate):** the skill could ask early for a one-sentence description of the intended workflow shape and let the user confirm/correct generated defaults rather than answering 10 individual questions. Something like:
- "Describe the workflow in one sentence and I'll propose a structure. You'll tell me what to tweak."
- Skip per-stage questions if the user already named the stages.

The current flow's question order is mechanical (mission → entities → stages → gates), which means experienced users can't short-circuit by supplying structure upfront.

## Out of scope for this entity

- A full rewrite of commission.
- Changing the output format (entity files, README, frontmatter shape).
- New stage types or workflow features.
- AI-assisted generation of domain-specific stage catalogs (could be a follow-up).

## Proposed approach (to be refined in ideation)

Ideation should:

1. **Audit current flow end-to-end.** Walk `skills/commission/SKILL.md` as written. Identify each question, what it depends on, what follow-ups it triggers.
2. **Identify branch points.** Where could the flow branch between first-time and experienced modes? Is it a single "do you already have a shape in mind?" question upfront, or subtler adaptive prompting throughout?
3. **Decide on persona detection.** Self-declared ("which describes you?"), inferred (e.g., "if you answered the first question in under 5 words, you're experienced"), or structural (e.g., "experienced mode is opt-in via flag")?
4. **Sketch concrete flow alternatives.** At least one for each persona. Include the first 3 questions verbatim.
5. **Consider escape hatches.** Both personas should be able to bail to "give me a reasonable default and let me edit the markdown after."
6. **Preserve the output contract.** Whatever the flow looks like, the generated workflow structure (entity files, README, frontmatter) must match today's shape so existing `status` / FO / mod infrastructure keeps working.

## Acceptance criteria (draft — ideation to refine)

**AC-1 — Clear persona branching documented in the skill.** The new flow explicitly acknowledges the two personas and routes them differently.

**AC-2 — First-time user gets scaffolding, not a blank prompt.** A first-time invocation offers either concrete examples to start from OR a guided "describe your mission" prompt that does NOT require stage knowledge upfront.

**AC-3 — Experienced user gets early-exit.** An invocation with an upfront workflow shape ("approval-gated editorial pipeline, 3 rounds, no concurrency") produces a reasonable first draft in one turn.

**AC-4 — Both paths converge on the same output shape.** Existing `status --boot`, FO dispatch, merge hooks continue to work against the generated output.

**AC-5 — Escape hatch.** Any user can say "just give me defaults" and get a working minimal workflow.

**AC-6 — Regression: existing commission test harness still passes.** `scripts/test-harness.md` generated output remains valid.

## Test plan (draft — ideation to refine)

- **Manual walk-throughs:** run the new flow as each persona on a test mission. Record friction points.
- **Harness:** re-run `scripts/test-harness.md` against the new flow. Generated files must still validate.
- **No live-e2e changes expected** — commission is a skill, not a runtime behavior; existing commission tests stay the source of truth.

## Open questions (for ideation)

- Is this the right time to also add AI-assisted stage suggestion? (Probably out of scope — separate entity.)
- Should the skill ask the user for a sample entity title/description before even discussing stages? The entity is the concrete artifact; stages are abstract.
- How does this interact with the "two-phase" commission flow (if one exists — check current SKILL.md)?

## Cross-references

- `skills/commission/SKILL.md` — the current skill to revisit
- `scripts/test-harness.md` — existing test infrastructure that must keep working
- Prior commission-adjacent entities in `docs/plans/_archive/` (e.g., workflow-adopt-sync, commission-template refinements) — check for relevant context
