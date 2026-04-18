---
id: 192
title: "Limit FO-built checklists to 3 items by default; allow workflow README override"
status: ideation
source: "captain directive — FO dispatch checklists currently drift toward 8-14 items (observed throughout 2026-04-17/18 session). That enumerates mechanical steps instead of forcing the FO to name the 3 things that matter. Cognitive load on both ensign (reading) and FO (tracking) increases with length; prioritization erodes. A 3-item ceiling by default, overridable per workflow, forces the FO to compress."
started: 2026-04-18T04:40:02Z
completed:
verdict:
score: 0.6
worktree:
issue:
pr:
mod-block:
---

## Why this matters

The FO (per `skills/first-officer/references/first-officer-shared-core.md` line 60) builds a numbered checklist from (a) stage outputs in the workflow README and (b) entity acceptance criteria. In practice during this session, checklists consistently ended up 8-14 items long:

- Enumerated mechanical steps ("read entity body", "inspect commit X", "commit before signaling complete")
- Mixed stage-wide expectations with dispatch-specific flagging
- Mixed "do this" with "verify that"

Long checklists have real costs:

1. **Ensign attention dilution.** 14 items means the ensign reads each one less carefully; the load-bearing items get lost in the mechanical ones.
2. **Stage report bloat.** Every item must be addressed as DONE/SKIPPED/FAILED. Reports become ceremonial.
3. **FO cognitive load.** Reviewing a 14-item report against a 14-item checklist is slow; the FO often rubber-stamps.
4. **Scope drift risk.** More items = more places to smuggle scope.

Three items forces the FO to ask: "what are the 3 things this dispatch must produce?" Everything else becomes narrative in `scope_notes` or folded into one compound item.

## Proposed rule

**Default:** FO-built checklists MUST be ≤ 3 items (not counting the Summary block). Items are numbered; each item can be one compound sentence with its own evidence expectation.

**Override:** workflow `README.md` frontmatter may declare:

```yaml
dispatch:
  checklist:
    max-items: 5   # or whatever the workflow needs
```

When present, the FO honors the workflow-specific limit. Default remains 3 when absent.

## Questions for ideation

1. **Enforcement surface:** where does the limit live?
   - (a) Prose guideline in `first-officer-shared-core.md` (FO discipline, no mechanism enforcement)
   - (b) Mechanism check in `skills/commission/bin/claude-team build` — rejects input JSON with `len(checklist) > N` (validated against workflow README frontmatter override)
   - (c) Both — prose + mechanism belt-and-suspenders
   Captain prefers mechanism over prose per post-#182 discipline. Lean (c) or (b).

2. **What counts as "one item"?** Options:
   - Compound sentence, one numbered line (most restrictive)
   - Numbered top-level item with optional sub-bullets (looser)
   - Hard character cap per item (harder to measure)
   Recommendation to ideation: top-level numbered item, no sub-bullets. Forces aggregation.

3. **Override shape:** is `dispatch.checklist.max-items: N` the right frontmatter path? Alternatives: `checklist: {max: N}` at top level, or a `fo.checklist.limit` nesting. Needs a decision.

4. **Boundary cases:**
   - What about explicit "read entity body" boilerplate? Is that ever item 1, or always implicit? (Recommend: always implicit; remove from checklists.)
   - What about "commit before signaling complete"? (Recommend: already covered by the Stage Report Protocol; remove.)
   - What about "write Stage Report"? (Recommend: already covered; remove.)
   The 3-item cap forces these to move out of the checklist into structural conventions.

5. **Dispatch-prompt preamble update:** `claude-team build` currently injects `'Every checklist item must appear in your report. Do not omit items.'` The 3-item rule might benefit from an additional line like `'Checklists are intentionally compact — the 3 things named here are the load-bearing outputs of this dispatch.'` to train ensign expectations.

6. **Effect on existing workflows:** `docs/plans/README.md` is a workflow whose stages naturally have 3-5 `Outputs:` bullets (ideation, validation). Would the cap break any existing flow? Probably not — most of what I wrote as checklist items were mechanical sub-steps, not Outputs-derived.

## Acceptance criteria (draft — ideation refines)

**AC-1** — FO dispatch rule documented in `first-officer-shared-core.md` with the 3-item default and the frontmatter override mechanism.

**AC-2** — `claude-team build` validates `len(checklist)` against the workflow README's override value (default 3). Rejects with a clear error naming the limit and suggesting either reducing items or adding the frontmatter override. Covered by a new unit test in `tests/test_claude_team.py` or similar.

**AC-3** — `docs/plans/README.md` either (a) adopts the default (no frontmatter change) and we refactor existing checklist expectations, or (b) sets an override if > 3 Outputs bullets per stage warrant it. Captain decides at gate.

**AC-4** — Commission skill (`skills/commission/SKILL.md`) documents the override in the new-workflow-generation flow so newly commissioned workflows know they can adjust.

**AC-5** — Static suite green. Any existing dispatches-in-flight at merge time don't break — the cap applies to NEW dispatches only.

## Out of scope

- Rewriting existing stage reports or historical entity bodies.
- A new "stage-wide default outputs" syntax — if stage outputs are enumerated in the README, ideation decides whether those count toward the cap or are separate.
- Enforcing the format of individual checklist items (length, grammar).
- Runtime metrics (e.g., "average checklist length by stage") — not needed.

## Test plan (draft — ideation refines)

- **Static:** unit test that `claude-team build` rejects a 4-item input when no override; accepts a 4-item input when override is 5.
- **Static:** verify default behavior when workflow README has no `dispatch.checklist` frontmatter.
- **Behavioral:** one live dispatch on an existing workflow (this project) with a 3-item checklist — confirm ensign produces a usable stage report.
- **Cost estimate:** ~$2-3 (one live sanity-check dispatch).

## Cross-references

- `skills/first-officer/references/first-officer-shared-core.md` — dispatch contract
- `skills/commission/bin/claude-team` — dispatch-assembly helper (current preamble at lines 264-274)
- `skills/commission/SKILL.md` — workflow-generation skill
- `skills/ensign/references/ensign-shared-core.md` — Stage Report Protocol (consumer side)
- `docs/plans/README.md` — the first workflow the new rule applies to
