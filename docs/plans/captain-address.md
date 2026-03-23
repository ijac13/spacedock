---
title: Address Human Partner as Captain by Default
status: ideation
source: commission seed
started:
completed:
verdict:
score: 0.68
---

## Problem Statement

The commission skill (`SKILL.md`) hardcodes "CL" as the term of address for the human partner throughout the generated first-officer agent template and the interactive design flow. "CL" is a personal preference from one user's CLAUDE.md — it is not portable. Any pipeline commissioned by a different user will contain a name that means nothing to them.

The generated first-officer agent at `.claude/agents/first-officer.md` inherits this because the template in SKILL.md bakes "CL" into the prompt text. The local instance for this project (`.claude/agents/first-officer.md`) correctly uses "CL" because it matches the project owner's CLAUDE.md, but this is accidental — the template itself is not parameterized.

## Where "CL" Appears in SKILL.md

### Phase 1 — Interactive Design (the commission skill itself addressing the human)

These references are the skill agent talking to the human during commission:

| Line | Context |
|------|---------|
| 13 | "You will walk CL through interactive design..." |
| 32 | "Before asking Question 1, greet CL with the following..." |
| 43 | "Ask CL these six questions..." |
| 129 | "Wait for CL to confirm..." / "If CL wants changes..." |
| 173 | "If CL explicitly asks for a multi-dimension rubric..." |
| 202 | "{any domain-specific fields from CL's answers}" |
| 237 | "{ONLY include this section if CL explicitly requests...}" |
| 308 | "{Description/thesis from CL's seed input.}" |
| 468 | "Tell CL what was generated..." |
| 495 | "report the results to CL..." |
| 507 | "let CL decide next steps" |

### Phase 2d — Generated First-Officer Template (baked into the agent the user will run later)

These are the critical ones — they end up in the generated `.claude/agents/first-officer.md`:

| Line | Context |
|------|---------|
| 348 | "The following transitions require CL's approval:" |
| 350 | "ask CL before dispatching" |
| 383-387 | "the evidence CL reviews" / "Report...to CL" / "Wait for CL's decision" / "ask CL whether to discard..." |
| 400 | "Report the conflict to CL" |
| 412 | "hold the worktree and ask CL" |
| 418 | "report the current state to CL and wait for instructions" / "CL will respond when ready" |
| 437 | "Report to CL for a decision" |

### Reference doc (`agents/first-officer.md`)

| Line | Context |
|------|---------|
| 20 | "CL will respond when ready" |
| 41, 44 | "report to CL, wait for approval" / "CL approved: merge to main" |

## Two Distinct Scopes

The occurrences fall into two categories with different replacement strategies:

1. **Skill-time references** (Phase 1, Phase 3): The commission skill itself addressing the human during the interactive session. These could be replaced with `{captain}`, but since the skill runs inside Claude Code which already has a CLAUDE.md-configured term of address, this may be unnecessary — the LLM will naturally use whatever name the user's CLAUDE.md specifies. However, for portability, these should still use the variable so the skill works without a CLAUDE.md.

2. **Template-time references** (Phase 2d): The generated first-officer prompt. These are the most important — they persist in the generated agent file and are used in every future session. These MUST use a `{captain}` variable that gets substituted during generation.

## Proposed Approach

### Add a commission variable: `{captain}`

Default value: `"captain"`.

### Collect during commission (optional question)

After Question 6 (Location) and before Confirm Design, add a lightweight note rather than a full question:

> The first officer will address you as **captain** (fitting the nautical theme). If you'd prefer a different title, just say so — otherwise we'll go with "captain".

This avoids adding friction to the commission flow. Most users will accept the default. Store the response (or default) as `{captain}`.

### Substitute throughout

- In the generated first-officer template (Phase 2d): replace all hardcoded "CL" with `{captain}`.
- In the skill's own Phase 1/Phase 3 text: replace all hardcoded "CL" with `{captain}`. Since `{captain}` defaults to "captain", this also makes the skill itself portable without relying on the user's CLAUDE.md.

### Display in Confirm Design

Add the captain title to the design summary:

> - **Address:** {captain}

## Edge Cases

### User's CLAUDE.md specifies a term of address

If the user's CLAUDE.md says "address me as Dave", the LLM running the commission skill will already see that instruction. Two scenarios:

- **Commission-time:** The LLM may naturally use "Dave" in conversation regardless of what the skill says. This is fine — the skill's `{captain}` references are instructions to the agent, not literal dialogue. The agent will follow whichever instruction is strongest. No conflict.
- **Generated agent:** The first-officer prompt will say "captain" (or whatever the user chose during commission). Since the first-officer runs in the same project, the user's CLAUDE.md still applies and may override. This is acceptable — the user's CLAUDE.md is their preference, and if it overrides "captain" with "Dave", that's intentional. The important thing is that the generated template has a sensible default rather than a leaked personal name.

### No CLAUDE.md exists

This is the primary use case. The generated agent will use "captain" naturally, giving the pipeline a consistent personality.

### User wants no term of address

If the user says "just say 'you'", store `{captain}` as "you" and substitute normally. The templates read fine with "you" in place of "CL".

## Acceptance Criteria

1. SKILL.md contains no hardcoded "CL" — all references use `{captain}` variable
2. `{captain}` defaults to "captain" if the user does not specify a preference
3. Commission flow includes a lightweight opt-out/customize step for the captain title
4. The Confirm Design summary displays the chosen captain title
5. The generated first-officer template uses `{captain}` throughout — no "CL" in generated output
6. The reference doc `agents/first-officer.md` uses "the captain" instead of "CL"
7. Existing pipelines are not affected (this only changes future commissions)
