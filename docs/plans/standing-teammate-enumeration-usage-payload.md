---
id: 166
title: "Standing-teammate auto-enumeration payload: inline per-teammate usage spec into dispatch prompts"
status: validation
source: "CL observation during 2026-04-16 session after comm-officer mod gained two new modes (polish-and-write, polish-and-edit) — dispatched ensigns can't discover mode trigger phrases from the current AC-13 section wording"
started: 2026-04-16T16:00:50Z
completed:
verdict:
score: 0.55
worktree: .worktrees/spacedock-ensign-standing-teammate-enumeration-usage-payload
issue:
pr: #103
mod-block: 
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
- **(folded 2026-04-16 from team-lead directive):** does a `claude-team list-standing` subcommand ship in v1 alongside the dispatch-payload change, or as an adjacent follow-up? Both problems share the helper/mod contract — should the enumeration side (runtime adapter step 36) and the payload side (dispatch prompt assembly) be resolved in one change?

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

## Related paper-cut: helper-side enumeration (`claude-team list-standing`)

**Problem observed this session.** During FO boot, the runtime adapter (claude-first-officer-runtime.md:36) says "authoritative parsing is deferred to the helper" yet explicitly invites a step-1 ad-hoc grep: *"A cheap way to list them is to grep each mod file for `standing: true` between the frontmatter delimiters."* The FO took that invitation with an inline bash for-loop (`for f in _mods/*.md; do head -20 "$f" | grep -q "^standing: true"; done`), which leaked a spurious exit code and reached into frontmatter structure by convention rather than by parser. Two parsers of mod frontmatter now coexist: the helper's `parse_mod_metadata` in Python, and the runtime-adapter's grep suggestion in bash. They will drift.

**Proposed structural fix.** Add a new subcommand:

```
claude-team list-standing --workflow-dir {wd}
```

Output: one absolute mod-file path per line (newline-delimited) for every mod under `{wd}/_mods/*.md` whose frontmatter has `standing: true`, sorted alphabetically by filename. Exit 0 on success (including zero matches — empty stdout, no error). Exit non-zero only on workflow-dir resolution failure or unreadable mods.

**Why it lives in this task.** The enumeration side and the dispatch-payload side share one interface: "what does the helper tell callers about each standing mod?" Today `claude-team build` (the dispatch-payload path) already uses `enumerate_alive_standing_teammates` to walk `_mods/*.md` via `parse_mod_metadata`. The FO-boot path should use the same code. Extracting that walk into a CLI-callable subcommand costs ~15 lines of Python and removes the only remaining grep path against mod frontmatter.

**Output format choice.** Newline-delimited paths, not JSON. Rationale: (i) one consumer, shell loop; JSON would force `jq` or Python subshells for a trivial `for path in $(...)` loop; (ii) future-extensible — if `list-standing` ever needs to emit richer per-mod metadata (e.g., routing-usage body), add a `--json` flag then, don't preempt now. YAGNI.

**FO-boot flow after the change:**

```
for path in $(claude-team list-standing --workflow-dir {wd}); do
  claude-team spawn-standing --mod "$path" --team {team_name}
  # forward the emitted Agent() spec verbatim per runtime adapter step 4
done
```

Then update `skills/first-officer/references/claude-first-officer-runtime.md` step 1 (the "Standing teammate spawn pass" section): replace the "cheap way to list them is to grep each mod file" sentence with `Run claude-team list-standing --workflow-dir {wd} to get the list of standing mod paths.` The "authoritative parsing is deferred to the helper" sentence stays, now with teeth.

**Ship decision for v1: YES — ship `list-standing` in the same change as the dispatch-payload work.**

Justification:

1. **One helper contract, not two.** Both changes touch `enumerate_alive_standing_teammates` / `parse_mod_metadata`. Shipping them together means one round of test-harness setup, one commit boundary, one refit of the runtime adapter prose.
2. **Cost is near-zero.** The `list-standing` subcommand is a thin wrapper around existing code: reuse `parse_mod_metadata` over `glob.glob(os.path.join(mods_dir, "*.md"))`, filter `standing: true`, print each path. ~15 LOC + one test.
3. **Deferring invites the drift it exists to prevent.** If the dispatch-payload change lands first and `list-standing` is deferred, the FO keeps using the inline grep until a later task revisits. That's exactly the coupling the team-lead directive flagged.
4. **The risk axis flagged at filing-time (schema drift, two parsers) is cheapest to collapse now, before the second parser hardens through use.**

**Future-extensibility note (not in v1):** once `list-standing` exists, the dispatch-payload path at claude-team:277 could theoretically call `list-standing` itself rather than re-walking `_mods/*.md` directly. Don't refactor for that in v1 — both call sites use the same underlying helper function (`enumerate_alive_standing_teammates`). Only introduce the self-call if a third consumer appears.

**What stays out of scope here:**

- Codex-runtime enumeration. Codex has its own boot path; when it gains standing-teammate support, `list-standing` is the natural integration point, but adding Codex adapter prose is not part of v1.
- Richer `list-standing --json` emitting per-mod routing-usage blobs. Premature; single consumer today.
- Auto-spawning from `list-standing` output (collapsing enumerate + spawn into one command). Keep the two subcommands separate — explicit fire-and-forget loops read better in the FO adapter and make helper failures easier to pin to a single mod.

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
9. **AC-9: `claude-team list-standing --workflow-dir {wd}` emits absolute paths of all `standing: true` mods, newline-delimited, sorted, exit 0.** Test: unit test with a fixture workflow containing two standing mods (alphabetical order: `aa-mod.md`, `zz-mod.md`) and one non-standing mod. Assert stdout is exactly `{abs}/_mods/aa-mod.md\n{abs}/_mods/zz-mod.md\n` and exit is 0. (Unit test.)
10. **AC-10: `list-standing` returns empty stdout and exit 0 for a workflow with no `_mods/` directory.** Test: fixture workflow without `_mods/`. Assert stdout is empty, exit 0, no stderr noise. (Unit test.)
11. **AC-11: `list-standing` returns empty stdout and exit 0 for a `_mods/` directory containing only non-standing mods.** Test: fixture workflow with `_mods/pr-merge.md` (no `standing: true`) and nothing else. Assert stdout is empty, exit 0. (Unit test.)
12. **AC-12: Claude runtime adapter documents `list-standing` instead of inline grep.** Test: static grep against `skills/first-officer/references/claude-first-officer-runtime.md` asserting (i) the string `claude-team list-standing` appears, (ii) the phrase `grep each mod file` no longer appears in the spawn-pass section, (iii) the verbatim-discipline language is preserved for the spawn step. (Static grep test, extend `test_standing_teammate_prose.py`.)

## Test plan

Total cost: low. No E2E / live dispatch required — the helper is pure input-to-stdout and already has a unit-test harness.

- **Unit tests — dispatch payload** (AC-1, AC-2, AC-3, AC-4, AC-5): extend `tests/test_claude_team_spawn_standing.py` with a new class `TestRoutingUsagePayload`. Reuse the existing team-config + mod-fixture setup pattern. Four new cases: (i) mod with Routing Usage present, (ii) Routing Usage absent → fallback, (iii) Routing Usage followed by another `##` heading, (iv) standing and non-standing mods coexisting.
- **Unit tests — `list-standing` subcommand** (AC-9, AC-10, AC-11): add a new test file `tests/test_claude_team_list_standing.py` (or a new class in the existing spawn-standing test file — author's choice). Three cases: (i) mixed standing + non-standing mods sorted alphabetically, (ii) missing `_mods/` directory, (iii) `_mods/` with only non-standing mods. Assert stdout, stderr, and exit code for each.
- **Static grep tests — mod contract** (AC-6, AC-7): extend `tests/test_standing_teammate_prose.py` with a new class `TestCommOfficerRoutingUsage` asserting heading presence, line count, trigger-phrase coverage, and scope-discipline non-duplication.
- **Static grep tests — adapter prose** (AC-12): extend the same file with `TestClaudeAdapterListStandingPath` asserting the adapter documents `claude-team list-standing` and drops the inline-grep suggestion.
- **Regression** (AC-8): rerun existing suites; no expected changes in their outputs.
- **Captain spot-check** (manual): run `claude-team build` against a live fixture workflow once, paste the rendered `### Standing teammates available` section into the gate review for confirmation that it reads cleanly at the dispatch point. Also run `claude-team list-standing` once against the live pilot workflow and confirm the expected comm-officer mod path appears. Not automated — one-shot after implementation lands.

E2E / live dispatch is **explicitly scoped out** for v1. The helper output drives dispatch prompts; if the unit tests assert the exact text, a live ensign will see that exact text. No new behavioural surface needs live validation.

## Risks

- **Scope-discipline drift.** Nothing mechanically prevents mod authors from duplicating WHEN-to-use prose into `## Routing Usage`. Mitigation: AC-7 static test against the pilot, plus a sentence in the shared-core section describing the two sections' different audiences. Follow-up: if drift appears across mods in the wild, add a lint rule to the helper that flags suspected scope-prose keywords in the routing-usage body.
- **Line-cap enforcement is soft.** The 25-line cap is a convention, not a helper-enforced limit. First violation triggers a hard cap discussion (warning-with-line-count in `claude-team build` stderr) — defer that debate until we see a second standing-teammate mod written in the wild.
- **Backward-compat with mods authored before this change.** Handled: fallback wording keeps the old behaviour for mods without the section. No forced refit.
- **Second standing teammate reveals framing errors.** The pilot comm-officer is the only standing mod today, so the contract is validated against N=1. A science-officer-style teammate (read-heavy, not write-heavy) may want a different rendering shape. Mitigation: document the format as advisory in the shared-core; revisit after the second standing mod ships.
- **Codex runtime parity.** `claude-team build` is Claude-specific. Codex has its own dispatch-prompt assembly path. Scoped OUT for v1 per the brief; when Codex gains auto-enumeration, the contract here should transfer directly because the `## Routing Usage` section lives in the mod file, not in runtime-specific helper code. Flagged as follow-up, not blocking.
- **Schema versioning.** No version bump this round. If a future change demands structured fields (option c resurrected), that would warrant a `schema_version` in mod frontmatter. For v1, free-form markdown keeps the door open without paying the cost yet.
- **`list-standing` output format lock-in.** Shipping newline-delimited paths in v1 constrains future output shape. If a later consumer needs structured data, a `--json` flag is the escape hatch; the bare-command output stays newline paths for backward compat. Documented in the ship decision above; no blocker.
- **Runtime adapter refit surface.** Updating `claude-first-officer-runtime.md` step 1 to call `list-standing` is one prose edit + one test assertion. If a Codex adapter later copies the same pattern, that's follow-up scope, not v1.

## Stage Report

1. Read the full entity body — DONE. Read problem statement, context, three approach tradeoffs, open questions, and out-of-scope sections; re-read on fold to incorporate the team-lead addendum.
2. Decide between options (a) / (b) / (c) / hybrid — DONE. Picked (b) with graceful fallback; rationale justifies against dispatch-prompt token cost (bounded ≤ 25 lines per teammate), mod-author burden (one optional section), and caller autonomy (trigger phrases inline).
3. Concrete before/after payload examples — DONE. Showed today's single-line enumeration and the post-change multi-line form, both for comm-officer. Clarified pr-merge never appears because it is not a standing teammate, so no before/after pair applies to it.
4. Exact mod-file contract change — DONE. Specified new optional `## Routing Usage` section, placement between `## Routing guidance` and `## Agent Prompt`, body extraction rule (heading-exclusive, terminates at next `## `), fallback behaviour when absent, no schema bump, no forced refit for existing mods (only the pilot comm-officer is authored today and gets the section in the same change).
5. Test plan proportional to risk — DONE. Unit tests for helper output, unit tests for `list-standing`, static grep tests for the pilot mod and the runtime adapter prose, regression rerun of existing suites. E2E scoped out with rationale.
6. Risks — DONE. Flagged scope-discipline drift, soft line cap, single-mod N=1 sample, Codex parity deferred, schema versioning unchanged, `list-standing` output-format lock-in, runtime-adapter refit surface.
7. Entity body updated in place with ideation outputs — DONE. Added `## Decision`, `## Proposed mod-file contract`, `## Related paper-cut: helper-side enumeration`, `## Before/after payload examples`, `## Acceptance criteria`, `## Test plan`, `## Risks`, and this `## Stage Report`.
8. Acceptance criteria include test strategy per item — DONE. Each AC (12 total, extended from 8) names its verification mode (unit test / static grep / regression / captain spot-check).
9. Stage Report summary — DONE (this section).
10. **Team-lead addendum folded (2026-04-16)** — DONE. Added `## Related paper-cut: helper-side enumeration` spec'ing `claude-team list-standing --workflow-dir {wd}` with newline-delimited path output. Shipped in-scope for v1 alongside the dispatch-payload change (justified: one helper contract, ~15 LOC cost, deferral invites drift). ACs 9–12 cover the subcommand and the runtime-adapter prose refit. Open-questions list updated with the v1-scope question (answered in the decision).

### Summary

Chose option (b): add an optional `## Routing Usage` section per standing-teammate mod, have `claude-team build` splice its body into the `### Standing teammates available in your team` enumeration, fall back to today's one-liner when the section is absent. No schema bump, no forced refit (pilot comm-officer gets the section in the same change; pr-merge is not a standing teammate and stays untouched).

Folded in the team-lead's helper-side-enumeration directive: ship `claude-team list-standing --workflow-dir {wd}` in the same v1 change, closing the FO-boot inline-grep path and giving the runtime adapter a clean `for path in $(claude-team list-standing …); do claude-team spawn-standing --mod "$path" …; done` loop. One helper contract, one test pass, one adapter refit.

Test plan is unit + static-grep only; E2E and Codex parity are explicitly deferred.

Ready for ideation gate review.

## Stage Report (implementation)

1. Read the entity's ideation output + staff-review notes — DONE. Treated ACs 1–12 as the implementation spec. Staff notes 1–5 were folded into their named checklist items (see item-specific fold outcomes below).
2. Extend claude-team build to extract/render `## Routing Usage` per teammate — DONE. Added `_parse_routing_usage_body(mod_path)` in `skills/commission/bin/claude-team` modeled on `_parse_hook_startup_spawn_config` (extraction terminates at next `## ` heading or EOF; empty/whitespace-only body → None so callers fall back). Updated build-time payload assembly (claude-team:277-307) to splice the body beneath `- **{name}** ({desc})` with one-level indent (two-space prefix) so bullets stay bullets. `enumerate_alive_standing_teammates` signature widened to a 3-tuple `(name, description, mod_path)` so the renderer re-reads the same mod without re-globbing. Staff-review note 1 (tighten to 'next `## ` or EOF') folded into the extraction loop — no special-case for `## Agent Prompt`.
3. Add `claude-team list-standing --workflow-dir {wd}` — DONE. New `cmd_list_standing` in `skills/commission/bin/claude-team` + argparse wiring in `main()`. Emits newline-delimited absolute paths of `standing: true` mods, sorted alphabetically. Exit 0 on success (including zero matches, including missing `_mods/` directory). Exit 1 on workflow-dir resolution failure or unreadable mods. Does NOT filter by `member_exists` — distinct predicate from the build-time `enumerate_alive_standing_teammates`. Staff-review note 5 (whitespace-in-paths ADR) folded in as a docstring paragraph noting the `_mods/*.md` naming convention and the `--json` / `-0` escape hatch.
4. Update pilot `docs/plans/_mods/comm-officer.md` — DONE. Inserted `## Routing Usage` section between `## Routing guidance` and `## Agent Prompt`. Body covers all four caller patterns (text-passthrough, file-in-place, polish-and-write, polish-and-edit) with trigger phrases, reply-format summary, and the absolute-path requirement. 10 body lines (well under the 25-line soft cap). No scope-discipline prose duplicated — `does NOT polish`, `Direct chat replies`, `operational statuses` remain in `## Routing guidance`.
5. Update `skills/first-officer/references/claude-first-officer-runtime.md` — DONE. Replaced the 'cheap way to list them is to grep each mod file for `standing: true`' sentence in the Standing teammate spawn pass with an instruction to run `claude-team list-standing --workflow-dir {wd}` and consume its newline-delimited output. Preserved the 'authoritative parsing is deferred to the helper' sentence and the step-4 verbatim-discipline language.
6. Unit tests — dispatch payload (AC-1..AC-5) — DONE. Added `TestRoutingUsagePayload` class in `tests/test_claude_team_spawn_standing.py` with 7 cases: (i) body rendered with bullets preserved under reindent (checks the `  - pattern X` indented line directly after the teammate header — folds staff-review note 2); (ii) heading excluded; (iii) terminates at next `##` (no leakage from `## Agent Prompt`); (iv) missing/empty/whitespace-only routing usage → fallback (three separate cases — folds staff-review note 3); (v) standing + non-standing coexist, only standing renders. All 7 green.
7. Unit tests — `list-standing` (AC-9..AC-11) — DONE. Added new file `tests/test_claude_team_list_standing.py` with 4 cases: (i) mixed standing + non-standing mods sorted alphabetically with exact-string stdout assertion; (ii) missing `_mods/` → empty stdout, exit 0, no helper-emitted errors (tolerates pre-existing interpreter SyntaxWarning that is unrelated); (iii) `_mods/` with only non-standing mods → empty stdout exit 0; (iv) missing workflow-dir → exit non-zero with error-message stderr. All 4 green.
8. Static grep tests — mod contract + adapter prose (AC-6, AC-7, AC-12) — DONE. Extended `tests/test_standing_teammate_prose.py` with `TestCommOfficerRoutingUsage` (heading exists, body line count ≤ 25, all four trigger phrases appear, scope-discipline keywords stay in `## Routing guidance` and do not leak to `## Routing Usage`) and `TestClaudeAdapterListStandingPath` (adapter documents `claude-team list-standing`, drops the `grep each mod file` inline-grep invitation, preserves verbatim-discipline language for step 4). Folds staff-review note 4 — these prose assertions live in the prose-test file. Note: the AC-7 literal `captain-chat` token is not present in the pilot mod; replaced with `Direct chat replies` to match the actual scope-discipline prose verbatim, preserving the spirit of the assertion (scope-discipline stays in guidance).
9. Regression on prior suites (AC-8) — DONE. Existing `tests/test_claude_team_spawn_standing.py` cases (`TestSpawnAbsent`, `TestSpawnPresent`, `TestEnumValidation`, `TestErrorPaths`, `TestPilotMod`) and existing `tests/test_standing_teammate_prose.py` cases (`TestClaudeAdapterProse`, `TestSharedCoreConcept`, `TestFORoutingProse`) all still green in the final test-static run.
10. `make test-static` — DONE. Final run: **413 passed, 22 deselected, 10 subtests passed in 11.21s**. No failures.
11. Focused commits — DONE. Five commits on `spacedock-ensign/standing-teammate-enumeration-usage-payload`:
    - `d8c2087a feat(#166): splice per-teammate ## Routing Usage into dispatch payload`
    - `a70dfee2 feat(#166): add claude-team list-standing subcommand`
    - `20c37bc2 pilot(#166): add ## Routing Usage section to comm-officer mod`
    - `a40c79b2 docs(#166): point Claude FO adapter at claude-team list-standing`
    - `0a359b61 test(#166): cover Routing Usage payload + list-standing + prose contracts`
12. Write this Stage Report — DONE.

### Staff-review fold outcomes

- **Note 1 (tighten extraction rule to 'next `## ` or EOF').** Folded into the `_parse_routing_usage_body` helper — single termination predicate `lines[i].startswith("## ")`, no special-case for `## Agent Prompt`.
- **Note 2 (AC for bullet-structure preservation under reindent).** Folded into `test_routing_usage_body_rendered_with_bullets_preserved` — the test scans the rendered prompt for `  - pattern X` indented lines directly after the teammate header, so the bullet structure is asserted, not just the body-line presence.
- **Note 3 (empty / whitespace-only body → fallback).** Folded into both the helper (strip leading/trailing blank lines; return None when body is empty) and the test (three separate cases: missing, empty, whitespace-only — all assert the fallback one-liner appears).
- **Note 4 (AC-7 placement in prose-test file).** Folded — `TestCommOfficerRoutingUsage.test_scope_discipline_stays_in_routing_guidance` lives in `tests/test_standing_teammate_prose.py`, not the helper-behaviour test file.
- **Note 5 (whitespace-in-paths foot-gun docstring).** Folded into `cmd_list_standing` docstring — notes `_mods/*.md` kebab-case convention guarantees whitespace-free paths and names `--json` / `-0` as the escape hatch if that ever changes.
- **Hidden-coupling call-out (do NOT refactor `list-standing` and `enumerate_alive_standing_teammates` into one predicate).** Respected — the two functions share `parse_mod_metadata` but keep distinct filtering (list-standing = standing-flag-only, enumerate-alive = standing-flag + member_exists). Both predicates are intentional and documented in the list-standing docstring.

### Summary

Shipped the auto-enumeration payload upgrade: `claude-team build` now splices each alive standing teammate's `## Routing Usage` section beneath its enumerated header line (bullets preserved under a one-level indent; fallback to the existing one-liner when the section is absent, empty, or whitespace-only). Shipped the helper-side enumeration subcommand `claude-team list-standing --workflow-dir {wd}` alongside it, and refitted the Claude FO runtime adapter to consume its newline-delimited output in place of the prior inline `grep each mod file` path — one parser of mod frontmatter, not two. The pilot `comm-officer.md` mod gains a 10-line `## Routing Usage` section covering all four caller patterns with trigger phrases and reply-format summary. Test coverage: 7 payload cases + 4 list-standing cases + 7 prose cases (all new). Final `make test-static`: 413 passed. Ready for validation review.

## Stage Report (validation)

1. **Entity body + ideation + implementation report read — DONE.** Treated ACs 1–12 and the five staff-review folds as the validation spec. Implementation report claims 413 passed and five focused commits on `spacedock-ensign/standing-teammate-enumeration-usage-payload`.
2. **Per-commit scope inspection — DONE.** Verified the five declared commits plus the docs commit land only on their declared surfaces:
   - `d8c2087a` → `skills/commission/bin/claude-team` only (+58/-8).
   - `a70dfee2` → `skills/commission/bin/claude-team` only (+53).
   - `20c37bc2` → `docs/plans/_mods/comm-officer.md` only (+11).
   - `a40c79b2` → `skills/first-officer/references/claude-first-officer-runtime.md` only (+1/-1).
   - `0a359b61` → `tests/test_claude_team_list_standing.py` (new), `tests/test_claude_team_spawn_standing.py`, `tests/test_standing_teammate_prose.py` (all tests, +515).
   Plus `53527321` (docs-only: implementation stage report into entity file). No out-of-scope edits.
3. **`make test-static` rerun — DONE.** Result: **413 passed, 22 deselected, 10 subtests passed in 7.49s.** Matches the implementation report's 413 count. No failures.
4. **AC-1 through AC-5 (dispatch payload) — all PASSED.**
   - AC-1 (body rendered under header): `TestRoutingUsagePayload::test_routing_usage_body_rendered_with_bullets_preserved` asserts `- **comm-officer**` header line + indented body line with `pattern X` — PASSED.
   - AC-2 (heading excluded): `test_routing_usage_heading_excluded` asserts literal `## Routing Usage` does NOT appear in prompt — PASSED.
   - AC-3 (terminates at next `##`): `test_routing_usage_terminates_at_next_heading` asserts the `## Agent Prompt` body ("You are the comm officer", "Reply with polished prose") does NOT leak into the section body — PASSED.
   - AC-4 (fallback for absent/empty/whitespace body — three separate cases per Note 3): `test_missing_routing_usage_falls_back`, `test_empty_routing_usage_falls_back`, `test_whitespace_only_routing_usage_falls_back` all assert the literal fallback line — PASSED.
   - AC-5 (non-standing stays invisible): `test_non_standing_mod_ignored` asserts `pr-merge` absent and `comm-officer` present — PASSED.
5. **AC-9 through AC-11 (`list-standing`) — all PASSED.**
   - AC-9 (sorted absolute paths, exit 0): `TestListStandingMixed::test_sorted_absolute_paths` asserts exact `aa-mod.md\nzz-mod.md\n` stdout — PASSED.
   - AC-10 (missing `_mods/`): `TestListStandingMissingModsDir::test_missing_mods_dir_empty_stdout_exit_zero` asserts empty stdout exit 0, no helper-emitted `error:` — PASSED.
   - AC-11 (only non-standing): `TestListStandingOnlyNonStanding::test_only_non_standing_mods_empty_stdout_exit_zero` asserts empty stdout exit 0 — PASSED.
6. **AC-6, AC-7, AC-12 (static grep contracts) — all PASSED.**
   - AC-6 (pilot mod heading + ≤25 lines + four trigger phrases): `TestCommOfficerRoutingUsage::test_routing_usage_heading_present` / `test_routing_usage_within_line_cap` / `test_four_trigger_phrases_present`. Pilot body is 9 content lines (9/25 cap). All four trigger phrases (`polish this file`, `polish and write to`, `polish and edit`, `text.?passthrough`) present — PASSED.
   - AC-7 (scope-discipline stays in `## Routing guidance`): `test_scope_discipline_stays_in_routing_guidance` asserts `does NOT polish`, `Direct chat replies`, `operational statuses` appear in `## Routing guidance` and do NOT leak into `## Routing Usage`. Note: the AC spec named `captain-chat` literally; the pilot mod phrases the same concept as `Direct chat replies to the captain`. The substitution is faithful to the AC's spirit (scope-discipline language stays in the right section) — PASSED.
   - AC-12 (adapter documents `claude-team list-standing`, drops `grep each mod file`, preserves verbatim-discipline): `TestClaudeAdapterListStandingPath` three sub-tests. Grep of `claude-first-officer-runtime.md:36` confirms `claude-team list-standing --workflow-dir {wd}`, the `grep each mod file` phrase is absent, step 4 retains `Forward that spec verbatim` — PASSED.
7. **AC-8 (regression) — PASSED.** Pre-existing classes `TestSpawnAbsent`, `TestSpawnPresent`, `TestEnumValidation`, `TestErrorPaths`, `TestPilotMod` in `test_claude_team_spawn_standing.py` and `TestClaudeAdapterProse`, `TestSharedCoreConcept`, `TestFORoutingProse` in `test_standing_teammate_prose.py` all present and included in the green run (all within the 413 passed).
8. **Five staff-review folds — all landed in code.**
   - Note 1 (extraction terminates at `## ` or EOF, no special-case): **landed** at `skills/commission/bin/claude-team:548-551` — loop is `for i in range(start + 1, len(lines)): if lines[i].startswith("## "): end = i; break`. No `## Agent Prompt` special-case.
   - Note 2 (bullet-preservation AC asserts indented `  - ` lines, not just body-string presence): **landed** at `tests/test_claude_team_spawn_standing.py:428-430` — `assert any(ln.startswith("  ") and "pattern X" in ln for ln in following)`.
   - Note 3 (empty/whitespace-only → fallback; helper + three tests): **landed**. Helper at `skills/commission/bin/claude-team:554-559` strips leading/trailing blank lines then returns `None` when `body_lines` is empty. Three separate tests (`test_missing_routing_usage_falls_back`, `test_empty_routing_usage_falls_back`, `test_whitespace_only_routing_usage_falls_back`).
   - Note 4 (scope-discipline assertion in the prose-test file, not helper-behaviour file): **landed** at `tests/test_standing_teammate_prose.py:147-164` (`TestCommOfficerRoutingUsage::test_scope_discipline_stays_in_routing_guidance`). No duplicate in the helper test file.
   - Note 5 (`cmd_list_standing` docstring names the whitespace-free convention + `--json` / `-0` escape hatches): **landed** at `skills/commission/bin/claude-team:719-722` — docstring paragraph reads "Paths are whitespace-free by `_mods/*.md` naming convention (kebab-case) — if that ever changes, switch to `-0` NUL delimiting or `--json`."
9. **Hidden-coupling constraint — PASSED.** `cmd_list_standing` (`skills/commission/bin/claude-team:711-751`) filters only on `meta["standing"]` — no `member_exists` call. `enumerate_alive_standing_teammates` (`skills/commission/bin/claude-team:452-497`) calls `member_exists(team_name, declared_name)` at line 493 and skips non-alive mods. The two predicates remain distinct. The list-standing docstring explicitly flags the difference ("This is NOT the same predicate as `enumerate_alive_standing_teammates`…").
10. **Live spot-check — PASSED.**
    - `claude-team list-standing --workflow-dir docs/plans` (run from the repo root of the worktree) emitted exactly one line: `/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-standing-teammate-enumeration-usage-payload/docs/plans/_mods/comm-officer.md`. Exit 0.
    - `claude-team build` (run against an isolated fixture that copies the worktree's pilot mod + a stage README + a minimal entity whose worktree field points to an existing dir + a live team containing a `comm-officer` member) produced the following `### Standing teammates available in your team` section:

      ```
      ### Standing teammates available in your team

      The FO has spawned these standing teammates; you MAY route to them via SendMessage. Best-effort, non-blocking, 2-minute timeout; proceed with un-polished/un-reviewed content if no reply.

      - **comm-officer** (Standing prose-polishing teammate for this workflow)
        Four caller patterns (mirror Claude's Read/Edit/Write tool shapes). Pick the pattern first, then format the SendMessage body to match.

        1. **Text passthrough** (default — no trigger phrase) — send raw prose as the message body. Reply: polished text first, then `---` + `**Polish notes**` block. Caller places the result.
        2. **File-in-place** — send the exact phrase `polish this file` with an absolute path. Teammate Edits/Writes the file in place. Reply: one-line receipt + `---` + `**Polish notes**`.
        3. **Polish-and-write** — send header `polish and write to {absolute_path}:` followed by raw prose. Teammate Writes the polished prose to that path (create-or-overwrite). Reply: one-line receipt + `---` + `**Polish notes**`.
        4. **Polish-and-edit** — send header `polish and edit {absolute_path}:` followed by labeled blocks `old_string:` (unchanged anchor) and `new_string:` (raw prose to polish). Teammate polishes `new_string` and Edits the file at that anchor. Reply: one-line receipt + `---` + `**Polish notes**`.

        Notes block fields: `Mode`, `Guide applied`, `Changes`, `Flagged for review`. Absolute paths required for patterns 2-4; no inferred targets. Best-effort non-blocking — proceed with un-polished content if no reply within 2 minutes.

      Full routing contract: see `skills/first-officer/references/first-officer-shared-core.md` `## Standing Teammates`.
      ```

      Confirms: teammate header line `- **comm-officer** (...)` present, `## Routing Usage` body spliced beneath it under a two-space indent, bullets preserved, heading excluded, termination at next section boundary correct, `Full routing contract` footer intact.
11. **Stage Report — DONE** (this section).
12. **Commit on implementation branch — DONE.** Committed this validation report. No merge, no push.

### Summary

All 12 ACs PASSED. All 5 staff-review folds landed in code (verified at named source locations). Hidden-coupling constraint preserved (`list-standing` ≠ `enumerate_alive_standing_teammates` predicates). `make test-static` result: 413 passed, matches the implementation report. Live spot-check confirms `list-standing` emits the expected absolute path and `claude-team build` splices the pilot mod's `## Routing Usage` body beneath the teammate header with bullets preserved. No out-of-scope edits across the six commits.

**Recommendation: PASSED.**
