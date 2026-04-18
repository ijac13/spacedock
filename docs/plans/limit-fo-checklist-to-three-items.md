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

## Ideation (2026-04-17)

### Audit of recent FO-built checklists

Sampled `### Checklist` sections under `## Stage Report` across recent entity bodies in `docs/plans/`:

| Entity (stage)                                          | Items |
|---------------------------------------------------------|------:|
| #188 streaming-watcher (ideation)                       | 11    |
| #177 opus-4-7 hallucination scope (ideation)            | 10    |
| #177 opus-4-7 hallucination scope (staff review)        | 10    |
| #177 opus-4-7 hallucination scope (ideation revision)   | 10    |
| #192 this dispatch (ideation, captain-packaged)         | 3     |

Most other recent entities use narrative stage reports and don't echo a numbered checklist, so sample is small but consistent where present. Median 10, max 11. The captain-packaged #192 at 3 items demonstrates the target is achievable. The data validates the 3-item ceiling — what FO dispatches routinely emit is 3x the useful density. The bloat items in the 10-11-item examples are mechanical boilerplate ("Read entity body", "Commit on main", "Append Stage Report") and sub-steps of a single compound output ("Surgical Fix #1", "Surgical Fix #2", "Gap #1", "Gap #2", "Gap #3" → could compress to one item: "Fold all five staff-review findings").

### Resolved questions

**Q1 — Enforcement surface.** Recommendation: **(c) mechanism + prose**, leaning mechanism-primary. Post-#182 discipline is clear: prose alone does not change FO behavior reliably. `claude-team build` already assembles the dispatch prompt from structured input and is the chokepoint. Reject input JSON with `len(checklist) > limit` with a clear error. Prose in `first-officer-shared-core.md` explains the *why* so the FO compresses before submitting, rather than submitting-and-failing.

**Q2 — What counts as one item.** Recommendation: **top-level numbered item, no sub-bullets**. Measured as count of `^\s*\d+\.` lines in the `checklist` array entries at top level. Sub-bullets rendered under a top-level item are fine (they're one semantic item). Hard character caps rejected — too brittle, hard to measure.

**Q3 — Override shape.** Recommendation: **`dispatch.checklist.max-items` nested under a `dispatch` key** in workflow README frontmatter:

```yaml
dispatch:
  checklist:
    max-items: 5
```

Rationale: groups future dispatch-related knobs (e.g., `max-items`, possibly `preamble-extra`) under a single namespace. `dispatch` at top level leaves room for non-checklist dispatch tuning without re-nesting later. Absent key → default 3. Non-int or ≤0 → reject with clear error at `claude-team build` time.

**Q4 — Boundary cases.** Recommendation: all three boilerplate items MUST be omitted from the FO-built checklist:
- "Read entity body" — already stated structurally ("Read the entity file at {path} for the current spec") in the preamble. Redundant.
- "Commit before signaling complete" — covered by `ensign-shared-core.md` Stage Report Protocol and the completion-signal block already injected.
- "Write Stage Report" — covered by preamble "Write a ## Stage Report section into the entity file when done." Redundant.

The FO's checklist focuses purely on load-bearing outputs specific to this dispatch. Boilerplate stays out.

**Q5 — Dispatch-prompt preamble update.** Add a line to the existing preamble in `claude-team build` after "Every checklist item must appear in your report. Do not omit items.":

> Checklists are intentionally compact — the items named here are the load-bearing outputs of this dispatch. Boilerplate (reading the entity, committing, writing the stage report) is assumed and not re-listed.

This trains the ensign to expect the compact shape and not pattern-match "only 3 items? something must be missing".

**Q6 — Effect on existing workflows.** `docs/plans/README.md` stages have 2-3 Outputs bullets each (ideation lists a single bullet plus three nested clarifiers; validation lists 3). No breakage expected. If at gate review a specific workflow genuinely needs more, it sets the override. This entity does NOT pre-emptively set an override on `docs/plans/README.md`; adoption of default is the test.

### Refined Acceptance Criteria

**AC-1 — Mechanism enforcement.** `skills/commission/bin/claude-team build` rejects dispatch JSON where `len(checklist) > max_items` (resolved limit) with error naming the configured limit, the override path, and the current count. Reads `dispatch.checklist.max-items` from the workflow README's YAML frontmatter; defaults to 3 when absent.
- **Test:** unit test in `tests/` (locate existing `claude-team build` test or add adjacent). Three cases: (a) 4-item input with no override → error; (b) 4-item input with `dispatch.checklist.max-items: 5` → accepted; (c) 3-item input with no override → accepted.

**AC-2 — Prose update.** `skills/first-officer/references/first-officer-shared-core.md` adds one short paragraph near line 60 (inside the dispatch contract, after step 2 "Build a numbered checklist …") describing the 3-item default, the override path, and explicitly listing the excluded boilerplate (read-entity, commit, write-report).
- **Test:** `tests/test_static_guardrails.py` or equivalent grep-based static test asserts the prose is present and names both `max-items` and the three excluded boilerplate phrases. Added alongside AC-1 test.

**AC-3 — Preamble line added.** `claude-team build` dispatch preamble (current text at `skills/commission/bin/claude-team:264-274`) gains the "Checklists are intentionally compact …" line immediately after "Every checklist item must appear in your report. Do not omit items."
- **Test:** unit test asserts the new line is present in assembled prompt output for a sample dispatch.

**AC-4 — Commission skill doc update.** `skills/commission/SKILL.md` documents the override (field, YAML shape, default, purpose) in whatever section currently covers workflow-README schema or stage configuration. One paragraph.
- **Test:** grep-based static assertion for `dispatch.checklist.max-items` appearing in `SKILL.md`. Piggybacks on AC-2 static test.

**AC-5 — Behavioral sanity check.** One live FO-driven dispatch on `docs/plans/` (any small task; a follow-up typo-fix or a standing trivial task works) produces a 3-item checklist without the FO hitting the rejection error. Evidence: dispatch prompt captured from `fo-log.jsonl` or equivalent shows 3 items; stage report on the target entity shows 3 `^\d+\.` items.
- **Test:** manual, captured in validation stage report. E2E not gated by CI — one sanity run is sufficient since AC-1/AC-3 cover mechanism correctness.

**AC-6 — Static suite green.** `make test-static` passes after all changes. No behavioral E2E regression because existing workflow's README has no override and the default applies prospectively; any in-flight dispatch at merge time that exceeds 3 items would have been assembled before the limit landed and is unaffected.
- **Test:** `make test-static`.

### Test plan (refined)

- Static unit test covering AC-1 (three input cases), AC-2 (grep prose), AC-3 (grep preamble line), AC-4 (grep SKILL.md). Single new test file or additions to existing `tests/test_claude_team*.py`. ~60 lines, cheap.
- Live dispatch for AC-5: ~$1-2, ~5 min wallclock. Use an existing trivial task in `docs/plans/` or a docs-only correction; no new E2E fixture needed.
- **Cost estimate total:** $1-2 + static test time. Low risk; no framework or scaffolding changes to the FO agent itself — purely dispatch-assembly helper plus prose.
- **E2E not required** beyond the single sanity dispatch — the mechanism path is deterministic JSON validation.

### Override frontmatter path (final)

```yaml
# In workflow README frontmatter (e.g., docs/plans/README.md)
dispatch:
  checklist:
    max-items: 5    # integer ≥ 1; default 3 when absent
```

Precedence: per-workflow override (if present and valid) > default 3. Invalid values (non-integer, ≤0) rejected at `claude-team build` with clear error naming the file and key path.

## Stage Report (ideation)

### Summary
Audited recent FO-built checklists (median 10, max 11 items) against the 3-item target; data validates the cap. Resolved all six seed questions with concrete answers. Specified override frontmatter path `dispatch.checklist.max-items` and refined ACs into 6 testable criteria with a cheap test plan (~$1-2, mostly static). Captain-preferred mechanism-primary enforcement at `claude-team build`, with a short prose companion in shared-core and a one-line preamble addition.

### Checklist

1. **Resolve the six seed questions with rationale — DONE.** Each question answered under `### Resolved questions`: (Q1) mechanism + prose, mechanism-primary at `claude-team build`; (Q2) top-level numbered items, sub-bullets allowed under an item; (Q3) `dispatch.checklist.max-items` nested path, default 3; (Q4) boilerplate items (read-entity, commit, write-report) excluded from the checklist; (Q5) preamble gets one added training line; (Q6) `docs/plans/README.md` adopts the default without pre-emptive override.

2. **Audit recent FO dispatch checklists — DONE.** Counted numbered items in `### Checklist` sections under `## Stage Report` across recent entity bodies. Sampled 15 files; useful signal from 4 entities where the ensign echoed the FO's checklist into the stage report: #188 ideation (11), #177 ideation (10), #177 staff review (10), #177 ideation revision (10). Most other recent entities use narrative stage reports so don't echo. Captain-packaged #192 (this dispatch) at 3 items demonstrates the target is achievable by design rather than prose exhortation. Median 10, max 11; data validates the 3-item target and surfaces the compression pattern (boilerplate + sub-step enumeration → single compound items).

3. **Write refined ACs + test plan + concrete override path — DONE.** ACs restructured to AC-1 (mechanism enforcement with three-case unit test), AC-2 (shared-core prose with static-grep test), AC-3 (preamble line with unit test), AC-4 (commission SKILL.md doc with static-grep test), AC-5 (one live sanity dispatch), AC-6 (`make test-static` green). Test plan: ~$1-2 total, mostly static tests; single live dispatch for AC-5. Override path finalized as `dispatch.checklist.max-items` nested under `dispatch` in workflow README frontmatter; precedence and invalid-value handling specified.


