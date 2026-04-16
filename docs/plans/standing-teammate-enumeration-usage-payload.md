---
id: 166
title: "Standing-teammate auto-enumeration payload: inline per-teammate usage spec into dispatch prompts"
status: ideation
source: "CL observation during 2026-04-16 session after comm-officer mod gained two new modes (polish-and-write, polish-and-edit) — dispatched ensigns can't discover mode trigger phrases from the current AC-13 section wording"
started: 2026-04-16T16:00:50Z
completed:
verdict:
score: 0.55
worktree:
issue:
pr:
---

## Problem Statement

#162 cycle 2 AC-13 ships `claude-team build` auto-enumeration: every dispatch prompt gains a `### Standing teammates available in your team` section listing alive standing teammates. The current section payload per teammate is:

```
**{name}** ({description}): SendMessage with the relevant input shape; reply format per the mod.
```

"SendMessage with the relevant input shape" is hand-waving. It tells the dispatched ensign a standing teammate exists but not how to address it. A caller who doesn't already know the mod's trigger phrases (like `polish and write to {path}:` or the exact `polish this file` gate) cannot invoke non-trivial modes from that line. They have to go read the mod file itself, which defeats the point of auto-enumeration — the whole mechanism exists to remove the FO's discipline burden of surfacing teammate availability to workers.

## Context

This gap surfaced on 2026-04-16 after the comm-officer mod was updated mid-session to add two new caller patterns: `polish-and-write` (mirrors the Write tool shape) and `polish-and-edit` (mirrors Edit). Both have precise trigger headers. A dispatched ensign reading the current auto-enumeration section could not reconstruct those headers from "the relevant input shape." The FO (who loaded the mod at session boot + authored the updates) knows the patterns, but that knowledge doesn't propagate to freshly-dispatched workers through the AC-13 mechanism as currently implemented.

## Approach tradeoffs

Three options, not mutually exclusive:

**(a) Pull the mod's existing `## Routing guidance` section into the dispatch payload.** Helper extracts the whole section verbatim from each alive teammate's mod and drops it below that teammate's header line in the enumerated section. No mod schema change — the current `## Routing guidance` text becomes caller-facing as written. Costs: the `## Routing guidance` section mixes WHEN-to-use prose with HOW-to-use prose; dropping it all in bloats every dispatch prompt with scope-discipline paragraphs dispatched workers don't need. Also couples the helper to section conventions.

**(b) Introduce a dedicated `## Routing Usage` section (or equivalent) to the mod schema.** Helper pulls this named section per teammate. Mod authors write concise caller-facing trigger-phrase + reply-shape documentation there; general scope discipline stays in `## Routing guidance`. Costs: mod schema gets another required-ish section; existing mods (pr-merge, comm-officer) need to be updated to add it; schema versioning story emerges.

**(c) Encode caller-facing trigger shape in mod frontmatter.** Instead of a free-form markdown section, standardize a `usage:` structured block in frontmatter listing each pattern's trigger, input shape, and reply format. Helper renders it. Costs: frontmatter becomes non-trivial (multi-line structured); loses the "mod file is readable markdown" property; schema evolution is harder than text.

All three address the same asymmetry: the mod file owns the caller-facing usage spec, but today's AC-13 helper doesn't lift enough of it into dispatch prompts for ensigns to use. Option (a) is cheapest to ship but potentially noisy; option (b) adds one schema bit for cleaner separation; option (c) is structured but more invasive.

## Open questions for ideation

- Which of the three options (or a hybrid)?
- Do we include routing usage for non-standing mods too (e.g., pr-merge), or only for standing teammates?
- How verbose should the inlined usage be per teammate? A line, a paragraph, or a full section? Trade-off: dispatch-prompt token cost vs caller autonomy.
- Does the mod's `## Routing guidance` section need a backward-compat strategy if we introduce a new section? Refit?
- Does this mechanism generalize to Codex, or is it Claude-only for v1?

## Out of Scope

- **Whole mod-schema overhaul.** Ideation should not redesign how mods are structured beyond what's needed for this payload.
- **Cross-workflow mod aggregation.** Same single-workflow scope as #162 v1.
- **Codex runtime equivalents.** Codex's dispatch-prompt assembly has its own path; ideation may scope Codex in or out based on cost.

## Decision

**Option (b) with a single refinement: require the section, keep it short, fall back gracefully when absent.**

Chosen section name: `## Routing Usage`. The helper looks for this heading in each alive standing-teammate's mod; if found, it splices that section's body (heading excluded) beneath the teammate's header line in the enumerated block. If absent, the helper falls back to today's single-line `"SendMessage with the relevant input shape; reply format per the mod."` wording.

Rejected alternatives:

- **(a) Pull `## Routing guidance` verbatim.** The pilot comm-officer's `## Routing guidance` section is ~90 lines mixing scope discipline ("what comm-officer polishes / does NOT polish"), four usage patterns, and hard rules about blocking. Pasting all of that into every dispatched ensign's prompt wastes tokens on text the ensign will never act on (the scope discipline is an FO-routing concern, not a caller-invocation concern). It also overloads one section with two audiences.
- **(c) Structured `usage:` frontmatter.** Overbuilt for one producer (mod author) and one consumer (the helper). A multi-line structured YAML block carries no benefit over a tight markdown section: the helper doesn't need to rerender, and mod authors already write markdown fluently. Costs markdown readability and schema stability for a non-existent consumer.

Option (b) wins on all three axes from the brief:
- **Dispatch-prompt token cost:** bounded — mods must keep `## Routing Usage` terse (≤ 25 lines soft-capped by convention, enforced by spot-check). The comm-officer rewrite is ~18 lines covering all four patterns. A hundred-character line budget × 25 lines ≈ 2.5 KB per teammate; with today's one teammate this is negligible relative to the existing 15-KB dispatch prompt.
- **Mod-author burden:** one new section, written once per mod, mirroring shape already-familiar from `## Hook: startup`. No required-field ceremony, no schema versioning.
- **Caller autonomy:** the dispatched ensign sees trigger phrases, header shape, and reply-format summary inline without opening the mod file.

**Non-standing mods (pr-merge) are out of scope.** `pr-merge.md` has no `standing: true` and never appears in the `### Standing teammates available in your team` section. The brief's question about pr-merge is answered by "the helper already ignores it"; no change needed.

## Proposed mod-file contract

Add a new top-level `## Routing Usage` section to standing-teammate mods. Placement: after `## Routing guidance` (when present), before `## Agent Prompt` (the mandatory-last section enforced by `parse_mod_metadata`).

**Convention (not mechanically enforced for v1):**

- Header: exactly `## Routing Usage`.
- Body: markdown prose or a short bulleted list naming each caller pattern, its exact trigger phrase (if any), the input shape the caller sends, and the reply shape the teammate returns.
- Audience: dispatched callers (ensigns + FO) who already know WHY to route to the teammate. This section answers HOW.
- Soft cap: ≤ 25 lines. If longer, move scope-discipline paragraphs back to `## Routing guidance`.

**Helper behaviour (`claude-team build` — `enumerate_alive_standing_teammates` + the build-time payload assembly at claude-team:278-299):**

1. For each alive standing teammate, read its mod file.
2. If a `## Routing Usage` section exists, extract its body (everything from the line after the heading up to — but not including — the next `## ` heading or EOF, stopping at `## Agent Prompt` regardless of intervening sections).
3. In the dispatch payload, render per-teammate as:
   - `- **{name}** ({description})` on its own line
   - the `## Routing Usage` body, reindented one level (existing bullets stay as bullets under the teammate line) when present
   - fallback one-liner (`SendMessage with the relevant input shape; reply format per the mod.`) indented under the teammate when the section is missing

**Backward compatibility:** mods without `## Routing Usage` still work — they get the fallback one-liner (today's behaviour verbatim). No refit required to ship; comm-officer adds the section in the same change (pilot mod lives in `docs/plans/_mods/` so the update is a pilot edit, not a production refit). pr-merge is untouched because it is not a standing teammate.

**Schema versioning:** no bump needed. The addition is a new optional convention, not a breaking change. `parse_mod_metadata` is unchanged — the new section sits between `## Routing guidance` and `## Agent Prompt`, both positions already permitted.

## Before/after payload examples

### Today — `### Standing teammates available in your team` section as rendered by claude-team:278-299

```
### Standing teammates available in your team

The FO has spawned these standing teammates; you MAY route to them via SendMessage. Best-effort, non-blocking, 2-minute timeout; proceed with un-polished/un-reviewed content if no reply.

- **comm-officer** (Standing prose-polishing teammate for this workflow): SendMessage with the relevant input shape; reply format per the mod.

Full routing contract: see `skills/first-officer/references/first-officer-shared-core.md` `## Standing Teammates`.
```

pr-merge does not appear — it is not a standing teammate.

### After — with `## Routing Usage` populated in the pilot comm-officer mod

```
### Standing teammates available in your team

The FO has spawned these standing teammates; you MAY route to them via SendMessage. Best-effort, non-blocking, 2-minute timeout; proceed with un-polished/un-reviewed content if no reply.

- **comm-officer** (Standing prose-polishing teammate for this workflow)
  Four caller patterns (mirror Claude's Read/Edit/Write tool shapes):
  1. **Text passthrough** — send prose as the message body; reply is polished prose + notes block. Caller places the result.
  2. **File-in-place** — send the exact phrase `polish this file` with an absolute path; teammate Edits/Writes the file in place; reply is confirmation + notes.
  3. **Polish-and-write** — send header `polish and write to {absolute_path}:` followed by raw prose; teammate Writes the polished prose to that path; reply is confirmation + notes.
  4. **Polish-and-edit** — send header `polish and edit {absolute_path}:` followed by labeled blocks `old_string:` and `new_string:`; teammate polishes new_string and Edits the file; reply is confirmation + notes.
  Reply format for patterns 2–4: one-line receipt then `---` + **Polish notes** block (Mode, Guide applied, Changes, Flagged). Text-passthrough reply leads with polished text then the same notes block.

Full routing contract: see `skills/first-officer/references/first-officer-shared-core.md` `## Standing Teammates`.
```

pr-merge still does not appear. If a second standing teammate (e.g., a science-officer) were alive and its mod omitted `## Routing Usage`, the fallback would render:

```
- **science-officer** (Standing literature-review teammate)
  SendMessage with the relevant input shape; reply format per the mod.
```

## Acceptance criteria

Each criterion below includes how it will be verified.

1. **AC-1: `claude-team build` emits `## Routing Usage` body under the teammate's header when the section is present.** Test: unit test with a fixture workflow containing a standing-teammate mod whose `## Routing Usage` section reads `- pattern X: trigger Y`. Assert that the string `- pattern X: trigger Y` appears in the generated prompt, and that the `**{name}**` header line immediately precedes the indented body. (Unit test against the build command's stdout, mirroring `test_claude_team_spawn_standing.py` setup.)
2. **AC-2: Helper extracts only the body, not the heading.** Test: same fixture as AC-1; assert the literal string `## Routing Usage` does NOT appear in the generated prompt.
3. **AC-3: Section body terminates correctly at the next `## ` heading.** Test: fixture mod whose `## Routing Usage` is followed by `## Agent Prompt`. Assert the Agent Prompt body does not leak into the rendered enumeration block. (Unit test.)
4. **AC-4: Fallback wording when `## Routing Usage` is absent.** Test: fixture mod with `standing: true` but no `## Routing Usage` section. Assert the exact fallback line `SendMessage with the relevant input shape; reply format per the mod.` appears beneath the teammate header, and no extra text leaks from elsewhere in the mod. (Unit test.)
5. **AC-5: pr-merge and other non-standing mods remain invisible.** Test: fixture with both a `standing: true` mod and a non-standing mod. Assert only the standing mod's name appears in the enumeration block. (Unit test — likely already covered by existing `test_claude_team_spawn_standing.py`; extend if not.)
6. **AC-6: comm-officer pilot mod is updated with a `## Routing Usage` section that mirrors its current four-pattern guidance, ≤ 25 lines, with no scope-discipline prose.** Test: static grep against `docs/plans/_mods/comm-officer.md` asserting the heading exists, line count within cap, and that the four trigger phrases (`polish this file`, `polish and write to`, `polish and edit`, plus the implicit text-passthrough default) appear. (Static grep test like `test_standing_teammate_prose.py`.)
7. **AC-7: `## Routing guidance` section retains scope discipline.** Test: grep the same pilot mod asserting that scope text ("does NOT polish", "captain-chat", "operational statuses") stays in `## Routing guidance` and is not duplicated in `## Routing Usage`. (Static grep, prevents redundant bloat.)
8. **AC-8: Existing enumeration tests still pass.** Test: rerun `tests/test_claude_team_spawn_standing.py` and `tests/test_standing_teammate_prose.py` unchanged. (Regression guard.)

## Test plan

Total cost: low. No E2E / live dispatch required — the helper is pure input-to-stdout and already has a unit-test harness.

- **Unit tests** (AC-1, AC-2, AC-3, AC-4, AC-5): extend `tests/test_claude_team_spawn_standing.py` with a new class `TestRoutingUsagePayload`. Reuse the existing team-config + mod-fixture setup pattern. Four new cases: (i) mod with Routing Usage present, (ii) Routing Usage absent → fallback, (iii) Routing Usage followed by another `##` heading, (iv) standing and non-standing mods coexisting.
- **Static grep tests** (AC-6, AC-7): extend `tests/test_standing_teammate_prose.py` with a new class `TestCommOfficerRoutingUsage` asserting heading presence, line count, trigger-phrase coverage, and scope-discipline non-duplication.
- **Regression** (AC-8): rerun existing suites; no expected changes in their outputs.
- **Captain spot-check** (manual): run `claude-team build` against a live fixture workflow once, paste the rendered `### Standing teammates available` section into the gate review for confirmation that it reads cleanly at the dispatch point. Not automated — one-shot after implementation lands.

E2E / live dispatch is **explicitly scoped out** for v1. The helper output drives dispatch prompts; if the unit tests assert the exact text, a live ensign will see that exact text. No new behavioural surface needs live validation.

## Risks

- **Scope-discipline drift.** Nothing mechanically prevents mod authors from duplicating WHEN-to-use prose into `## Routing Usage`. Mitigation: AC-7 static test against the pilot, plus a sentence in the shared-core section describing the two sections' different audiences. Follow-up: if drift appears across mods in the wild, add a lint rule to the helper that flags suspected scope-prose keywords in the routing-usage body.
- **Line-cap enforcement is soft.** The 25-line cap is a convention, not a helper-enforced limit. First violation triggers a hard cap discussion (warning-with-line-count in `claude-team build` stderr) — defer that debate until we see a second standing-teammate mod written in the wild.
- **Backward-compat with mods authored before this change.** Handled: fallback wording keeps the old behaviour for mods without the section. No forced refit.
- **Second standing teammate reveals framing errors.** The pilot comm-officer is the only standing mod today, so the contract is validated against N=1. A science-officer-style teammate (read-heavy, not write-heavy) may want a different rendering shape. Mitigation: document the format as advisory in the shared-core; revisit after the second standing mod ships.
- **Codex runtime parity.** `claude-team build` is Claude-specific. Codex has its own dispatch-prompt assembly path. Scoped OUT for v1 per the brief; when Codex gains auto-enumeration, the contract here should transfer directly because the `## Routing Usage` section lives in the mod file, not in runtime-specific helper code. Flagged as follow-up, not blocking.
- **Schema versioning.** No version bump this round. If a future change demands structured fields (option c resurrected), that would warrant a `schema_version` in mod frontmatter. For v1, free-form markdown keeps the door open without paying the cost yet.

## Stage Report

1. Read the full entity body — DONE. Read problem statement, context, three approach tradeoffs, open questions, and out-of-scope sections.
2. Decide between options (a) / (b) / (c) / hybrid — DONE. Picked (b) with graceful fallback; rationale justifies against dispatch-prompt token cost (bounded ≤ 25 lines per teammate), mod-author burden (one optional section), and caller autonomy (trigger phrases inline).
3. Concrete before/after payload examples — DONE. Showed today's single-line enumeration and the post-change multi-line form, both for comm-officer. Clarified pr-merge never appears because it is not a standing teammate, so no before/after pair applies to it.
4. Exact mod-file contract change — DONE. Specified new optional `## Routing Usage` section, placement between `## Routing guidance` and `## Agent Prompt`, body extraction rule (heading-exclusive, terminates at next `## `), fallback behaviour when absent, no schema bump, no forced refit for existing mods (only the pilot comm-officer is authored today and gets the section in the same change).
5. Test plan proportional to risk — DONE. Unit tests for helper output, static grep tests for the pilot mod, regression rerun of existing suites. E2E scoped out with rationale.
6. Risks — DONE. Flagged scope-discipline drift, soft line cap, single-mod N=1 sample, Codex parity deferred, schema versioning unchanged.
7. Entity body updated in place with ideation outputs — DONE. Added `## Decision`, `## Proposed mod-file contract`, `## Before/after payload examples`, `## Acceptance criteria`, `## Test plan`, `## Risks`, and this `## Stage Report`.
8. Acceptance criteria include test strategy per item — DONE. Each AC names its verification mode (unit test / static grep / regression / captain spot-check).
9. Stage Report summary — DONE (this section).

### Summary

Chose option (b): add an optional `## Routing Usage` section per standing-teammate mod, have `claude-team build` splice its body into the `### Standing teammates available in your team` enumeration, fall back to today's one-liner when the section is absent. No schema bump, no forced refit (pilot comm-officer gets the section in the same change; pr-merge is not a standing teammate and stays untouched). Test plan is unit + static-grep only; E2E and Codex parity are explicitly deferred.

Ready for ideation gate review.
