---
title: Commission Speed — Reduce Time to Value
status: implementation
source: CL feedback
started: 2026-03-23T00:00:00Z
completed:
verdict:
score: 0.80
worktree: .worktrees/ensign-commission-speed
---

The interactive commission flow asks 7 questions one at a time. This is the main bottleneck for time-to-value — a new user waits through a lengthy Q&A before seeing any output.

## Problem

Each question requires a round-trip: agent asks, user answers, agent processes. With 7 questions (plus confirmation), that's 8+ turns before generation begins. For users who know what they want, this is friction.

## Analysis of Current Flow

### Question inventory (7 questions + confirmation)

| # | Question | Essential? | Can derive? | Notes |
|---|----------|-----------|-------------|-------|
| 1 | Mission | Yes — irreducible | No | The whole pipeline hangs on this |
| 2 | Entity | Yes — shapes schema | Partially — label derived from description (domain-terminology branch) | Could combine with mission |
| 3 | Stages | Yes — structural | Yes — defaults from mission work well | Already suggests defaults |
| 4 | Approval gates | Nice-to-have | Yes — sensible default: gate before terminal stage | Most users accept suggestions |
| 5 | Seed entities | Yes — needed for pilot | No — user-specific content | Could defer: generate empty pipeline, seed via refit |
| 6 | Location | Low value | Yes — `docs/{slug}/` works for nearly all cases | Almost always accepted as-is |
| 7 | Captain title | Cosmetic | Yes — default "captain" | Almost never changed |

**Conclusion:** Questions 1, 2, and 5 require genuine user input. Questions 3 and 4 are confirm-or-modify (defaults are usually accepted). Questions 6 and 7 are almost always accepted as-is.

### Round-trip cost

Each question costs: agent output (question text) + user reading + user typing + agent processing. With Claude Code's turn latency, the 8 round-trips take 2-5 minutes depending on how fast the user types. The actual information content of most answers is low — "yes", "looks good", "go with the default".

## Direction Evaluation

### 1. Fewer questions — combine or drop

**Drop Q7 (captain title):** Default to "captain", mention it in the confirmation summary with "change if you want." Saves one round-trip that almost never produces a non-default answer.

**Drop Q6 (location):** Derive from mission slug. Mention derived location in confirmation. Only ask if it can't be derived.

**Combine Q3+Q4 (stages + gates):** Present stages with suggested gates inline: `ideation → [gate] implementation → validation → done`. User confirms or modifies the whole flow at once.

**Result:** 7 questions → 4 questions (mission, entity, stages+gates, seeds) + confirmation = 5 round-trips. Saves 3 turns.

**Verdict:** Good incremental improvement. Not transformative.

### 2. Freeform intake — single description

Parse a sentence like "track blog posts through draft → review → published" to extract mission, entity type, and stages. Feed remaining unknowns through smart defaults.

**Problem:** Unreliable extraction. "I want to manage feature requests" — what are the stages? The LLM infers, but the user has no control point until confirmation. If the inference is wrong, the user corrects at confirmation time, which is the same number of turns (just shuffled around). Worse: the user doesn't know what they need to specify, so they under-specify, then over-correct.

**Verdict:** Attractive but fragile. Better as an enhancement to batch mode (see #4) than as the primary flow.

### 3. Express mode — 2-3 essential questions + defaults

Ask only: (1) mission, (2) entity description, (3) seed entities. Derive everything else:
- Stages from mission (already done in Q3's suggestion — just auto-accept)
- Approval gates: default to gating before terminal stage
- Location: `docs/{mission-slug}/`
- Captain: "captain"

Present a full design summary for confirmation. User can modify anything at the confirmation step.

**Result:** 3 questions + 1 confirmation = 4 round-trips. Saves 4 turns.

**Verdict:** Best balance of speed and control. The confirmation step is the safety net for bad defaults.

### 4. Better batch mode UX

Batch mode already exists but requires knowing the exact field names. Making it more forgiving (accept freeform descriptions, partial inputs) is the freeform intake idea applied to batch mode.

**Verdict:** Batch mode is already the fast path for power users. Improving its parser is useful but orthogonal — it doesn't help interactive users.

### 5. Progressive disclosure — generate with minimal input, refine via refit

Ask mission + entity only, generate with all defaults, let user refit to customize stages/gates/etc.

**Problem:** The pilot run executes against the defaults. If the default stages are wrong, the pilot run is wasted. Refit exists but costs another session. Net time-to-value could be worse if defaults miss.

**Verdict:** Interesting for a "just show me something" mode but risky as the primary flow. The pilot run is the proof of value — if it runs against bad defaults, the user's first experience is broken.

## Recommended Approach: Express Mode with Confirm-to-Modify

Combine directions #1 (fewer questions) and #3 (express mode). The key insight: the confirmation step already exists and already allows modifications. Shift information from dedicated questions into derived defaults shown at confirmation.

### Proposed question flow

**Question 1 — Mission + Entity (combined)**

> What's this pipeline for, and what does each work item represent?
>
> Example: "Track design ideas through review stages" — the pipeline is for tracking, each item is a design idea.

Store `{mission}` and `{entity_description}`. Derive `{entity_label}`, `{entity_label_plural}`, `{entity_type}` per the domain-terminology derivation logic.

If the user's answer is clear enough to extract both mission and entity, proceed. If only mission is clear, ask a follow-up for entity description (still saves turns vs. always asking both separately).

**Question 2 — Seed Entities**

> Give me 2-3 starting items to seed the pipeline. For each, provide:
> - **Title** — short name
> - **Description** — a sentence or two
> - **Score** (optional) — priority from 0.0 to 1.0

(Drop the `source` field from the interactive prompt — it can be specified in batch mode or defaults to "commission seed".)

**Confirm Design (with derived defaults)**

Derive everything else from mission context:
- `{stages}` — suggest from mission (same logic as current Q3, but auto-applied)
- `{approval_gates}` — default: gate before terminal stage
- `{dir}` — `docs/{mission-slug}/`
- `{captain}` — "captain"

Present the full summary:

> **Pipeline Design Summary**
>
> - **Mission:** {mission}
> - **Entity:** {entity_description} (label: {entity_label})
> - **Stages:** {stages joined with " → "} (derived from mission)
> - **Approval gates:** {approval_gates}
> - **Seed entities:** {count} items
> - **Location:** `{dir}`
> - **Address:** captain
>
> Modify anything above, or confirm to generate. (y/n/changes)

**Total: 2 questions + 1 confirmation = 3 round-trips.** Down from 8.

The confirmation step becomes the single point where the user can override any derived default. This is better than dedicated questions because most users accept defaults — they scan the summary and say "yes."

### What stays the same

- Batch mode: unchanged. Already the fastest path; accepts all inputs in one message.
- Phase 2 (generation): unchanged.
- Phase 3 (pilot run): unchanged.
- Greeting: updated to say "I'll ask a couple questions" instead of "six questions."

### Interaction with precompiled-dist

With dist artifacts, Phase 2 (generation) becomes fast copy-and-substitute. The time-to-value bottleneck shifts entirely to Phase 1 (Q&A). This makes commission-speed more important, not less — when generation is instant, every Q&A round-trip is a larger fraction of total time.

The two changes are complementary:
- **commission-speed** reduces Phase 1 from 8 turns to 3 turns
- **precompiled-dist** reduces Phase 2 from LLM-generation to copy-substitute

Combined, commission goes from "several minutes of Q&A + slow generation" to "quick conversation + instant scaffolding."

No design conflicts: commission-speed changes SKILL.md Phase 1 only; precompiled-dist changes Phase 2 only. They don't overlap.

## Acceptance Criteria

1. **Interactive mode asks at most 2 questions** before presenting the design summary for confirmation (mission+entity combined, then seeds)
2. **Derived defaults are reasonable:** stages, gates, location, and captain title are inferred from mission context without dedicated questions
3. **Confirmation step shows all derived values** and allows modification of any field before proceeding
4. **Batch mode is unaffected:** providing all inputs in one message still skips to confirmation
5. **Greeting text updated** to reflect the shorter flow ("a couple questions" not "six questions")
6. **Label derivation preserved:** the domain-terminology entity_label logic (from Q2) works with the combined Q1 (mission+entity)
7. **Test harness passes:** both interactive and batch commission paths produce valid pipelines
8. **Time-to-value measurably reduced:** 3 round-trips (2 questions + confirm) vs. 8 round-trips (7 questions + confirm)

## Open Questions

None — the design is straightforward. Implementation is a SKILL.md rewrite of Phase 1 only.
