---
id: 124
title: "Best practices — batch advancement + serial gate (mod-based loops)"
status: backlog
source: "External FO feedback (GTM outreach pipeline) during 2026-04-10 session"
score: 0.55
worktree:
started:
completed:
verdict:
issue:
pr:
---

When a mod hook advances many entities at once (e.g., a silence-watcher firing on idle and promoting 8 entities from `watching` to `followup-draft`), downstream stages that require per-entity human approval create a serial review queue proportional to the batch size. The tool makes batch creation cheap; the captain pays the serialization cost. Document this as a design best practice and codify the mod-based loop pattern as the blessed approach for cyclic workflows — the captain has explicitly ruled that a dedicated loop primitive is not needed right now.

## Why now

External FO (GTM outreach pipeline) hit this during a 2026-04-10 session: the silence-watcher mod advanced 8 entities in a single idle run from `watching` → `followup-draft`. The `followup-review` stage explicitly requires "present one at a time, never batch", producing an 8-deep serial gate queue for the captain. The mismatch between batch-friendly automation (mods) and serial-only human gates is baked into the model. Workflow authors need to know this and design around it.

Separately, the same session confirmed that cyclic workflows (send → watch → reply-or-timeout → draft → review → send-again) can be modeled cleanly with mod-driven loops — a terminal-ish stage sets frontmatter state, an idle hook scans for that state and advances back into the pipeline. Captain's judgment: this pattern is sufficient for current needs; do NOT build a `repeatable: true` stage primitive.

## Scope

Write a best-practices doc that covers **both** the mod-based loop pattern and the batch-vs-serial pitfall, with concrete mitigation options. The doc is user-facing (workflow authors), not runtime contract.

Suggested location: `docs/best-practices/batch-and-gates.md` (new), or a section in the commission SKILL template, or an appendix to `docs/plans/README.md`'s pipeline documentation. Ideation should pick the canonical home.

### Content outline

1. **Pattern — mod-based loops for cyclic workflows.**
   - When to reach for it: your workflow has a natural cycle (send → watch → respond → send-again, observe → analyze → act → observe-again) that doesn't fit a linear DAG.
   - How to structure it:
     - One terminal-ish stage per loop body that parks entities in a `waiting` / `watching` / `queued` state via `status --set`.
     - An idle mod hook (`_mods/{name}.md` with `## Hook: idle`) that scans for parked entities matching the loop-continue predicate and advances them back into the pipeline.
     - Explicit loop-exit criteria in frontmatter or an outcome field.
   - Worked example: the silence-watcher mod in the discovery-outreach workflow (referenced with a link if the workflow is open-sourced, or paraphrased).

2. **Pitfall — batch advancement + serial-approval gates.**
   - Problem statement: cheap batch automation upstream of expensive serial human review downstream.
   - Example: silence-watcher advances 8 entities, captain faces 8 serial review turns. One idle hook fires; the captain spends 20 minutes reviewing the consequences.
   - Why the tool can't fix this: batch ≠ approval. Some decisions need per-entity scrutiny. A `batch-ok: true` gate mode is possible but dangerous (silent mass-approval is a foot-gun).

3. **Mitigations to consider when designing a cyclic workflow.**
   - **Throttle at the hook.** Cap the number of entities the idle hook advances per run. The remainder waits for the next idle tick. Document the cap in the mod file itself.
   - **Pipeline shaping.** Put the cheap-per-entity automated-review step before the expensive human approval step, so obvious rejects (too old, wrong category, mismatched profile) get filtered before the serial queue forms. Reserve the serial gate for the actual judgment calls.
   - **Batch-tolerant gates when the domain allows.** If a batch of entities shares enough context that the captain can meaningfully review N at once (e.g., "approve all three outreach drafts for the same customer"), design the gate stage to present the batch as a single unit. Not always possible; domain-specific.
   - **Approval-mode documentation per stage.** State the expected review mode in the stage definition (`"review mode: one-at-a-time"` vs. `"review mode: batch ok"`). No code change — just author discipline that the FO can surface at gate presentation time.
   - **Off-hour / async triggers.** Have the mod hook fire on a schedule the captain chooses (e.g., mornings only), so batches don't arrive at inconvenient moments.

4. **Explicit non-mitigations.**
   - Do not file a `repeatable: true` stage primitive as a TODO in the workflow — captain has ruled that mod-based loops are sufficient for the foreseeable future.
   - Do not add a "silent mass-approval" mode to gates. The captain's approval is the load-bearing safety check; bypassing it defeats the workflow.

## Acceptance Criteria

1. A best-practices doc exists at the chosen location with sections covering: the mod-based loop pattern, the batch-vs-serial pitfall, concrete mitigations, and explicit non-mitigations.
   - Test: manual inspection; structural grep for section headings.
2. At least one concrete worked example (the silence-watcher pattern from discovery-outreach OR an invented-but-realistic loop workflow) is included.
   - Test: manual inspection; grep for the worked-example section.
3. The commission SKILL template (if applicable) mentions the batch-vs-serial pitfall and links to the doc, so workflow authors see it at commission time.
   - Test: grep in `skills/commission/SKILL.md`.
4. The workflow README template (if applicable) has a short pointer to the doc for any workflow that uses idle hooks.
   - Test: grep in the emitted workflow README template.
5. No code changes outside the new doc + light edits to SKILL/README templates.
   - Test: `git diff --stat` on the implementation commit.

## Test Plan

- Manual inspection of the new doc against the acceptance criteria.
- Optional: dispatch a fresh-reader subagent for a 60-second scan of the doc to confirm the pattern and pitfall land.
- No code tests; this is a docs-only task.
- No E2E.

## Out of scope

- Building a `repeatable: true` stage primitive (captain-ruled).
- Adding batch-approval tooling to gates.
- Changing existing workflows to adopt the patterns (workflow-author choice).
- Rewriting existing mod examples beyond the minimum needed to illustrate the pattern.

## Related

- **External FO feedback (2026-04-10)** — GTM FO surfaced the batch-vs-serial pain point and the working mod-based loop pattern in their silence-watcher implementation.
- **Task 115** `fo-dispatch-template-completion-signal` — the existing pr-merge mod (a `## Hook: merge`) is a different class of mod from idle-driven loops, but the docs should cover both shapes to give workflow authors a complete picture of what mods can do.
- **Task 116** `readme-and-architecture-refresh` — the README refresh already added a brief "mods / hooks" mention per the external reviewer feedback; this task goes deeper for workflow authors who need to design cyclic workflows.
- **NEW-B1 (from external FO feedback)** — the "loops in stage graph" architectural concern. **Explicitly deferred per captain.** This task documents the mod-based workaround as the blessed pattern; the loop primitive question stays on the shelf.
