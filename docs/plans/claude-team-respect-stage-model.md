---
id: 157
title: "claude-team build: resolve and emit per-stage model, runtime adapters pass it through on dispatch"
status: done
source: "github.com/clkao/spacedock#95 — stages.defaults.model accepted in workflow READMEs but ignored at dispatch; subagents unconditionally inherit captain-session model"
started: 2026-04-15T17:42:36Z
completed: 2026-04-15T23:06:29Z
verdict: PASSED
score: 0.80
worktree: 
issue: "#95"
pr: #100
mod-block: 
---

Workflow READMEs accept `stages.defaults.model` and per-state `model:` overrides, but the plugin never reads them. Subagents unconditionally inherit the captain session's model, so a workflow author declaring `model: haiku` for routine stages still gets opus subagents whenever the captain is running opus.

## Problem Statement

A captain on opus running a workflow whose README declares `model: haiku` on dispatch/execute stages gets every subagent on opus — >10× overspend on stages explicitly designed to run cheap. The declared stage model is inert at dispatch time. The gap is silent; only a jsonl transcript audit surfaces it.

The workaround today — captain switches their own session model to match the target stage — forfeits opus for captain-side judgment work (gate reviews, clarification, plan review), which is exactly where operator-visible quality matters most.

## Proposed Approach

The Claude Code `Agent` tool accepts an optional `model` parameter with enum `"sonnet" | "opus" | "haiku"` (verified 2026-04-15 via the tool schema and a live `Agent(model="haiku", ...)` spawn — see **Probe evidence** below). The fix is a single dispatch-path change:

1. **Parser** — `skills/commission/bin/status` `parse_stages_block`: add `model` to the per-state optional allowlist and expose `stages.defaults.*` to callers (simplest shape: a sibling `parse_stages_with_defaults` that returns `(stages_list, defaults_dict)`, keeping `parse_stages_block` back-compat for existing callers).
2. **Helper** — `skills/commission/bin/claude-team` `cmd_build`: compute `effective_model` using the precedence below; emit it as a top-level `model` field in the output JSON. When non-null, value MUST be one of `"sonnet"`, `"opus"`, `"haiku"` (the Agent schema enum) — the helper validates and errors loudly on out-of-enum values.
3. **Claude runtime adapter** — `skills/first-officer/references/claude-first-officer-runtime.md` `## Dispatch Adapter`: forwarding clause gains `model=output.model if output.model else <omit>` alongside the existing `subagent_type` / `name` / `team_name` / `prompt`. Break-glass template gets a conditional `model=` slot.
4. **Shared core reuse** — `skills/first-officer/references/first-officer-shared-core.md` `## Completion and Gates`: add a bullet requiring `lookup_model(worker_name) == next_stage.effective_model` (or null/null). `lookup_model` reads `~/.claude/teams/{team}/config.json members[].model`, which is stamped from `Agent(model=...)` at join time (confirmed live).
5. **Dispatch-time visibility** — `claude-team build` prints a one-line stderr notice `[build] effective_model={resolved} (from {stage|defaults|null}) → Agent model={...|omit}` whenever a model is resolved. Silent correctness is as hard to audit as silent incorrectness.
6. **Probe-discipline rule** — `skills/first-officer/references/first-officer-shared-core.md`'s ideation/probe guidance gains one new bullet: "when checking whether tool X supports Y, read X's schema directly (via ToolSearch or equivalent runtime introspection) before greping for existing callers — usage presence is not existence evidence." This rule would have prevented cycles 1, 2, and 3 of this task; landing it in the same PR converts a hard-won lesson into a durable guardrail. One bullet, trivial cost. Covered by AC-probe-discipline (#13).

Precedence:

```
effective_model = stages.states[stage].model
              ?? stages.defaults.model
              ?? null  (omit the Agent `model=` parameter entirely; Agent's default-inheritance applies)
```

Null semantics: when `effective_model` is null, the helper emits `"model": null` in the JSON and the FO omits the `model=` argument on the `Agent()` call entirely (not passing `null`). Critically, omitting `Agent(model=)` does NOT stamp `null` into the team config — live evidence (`probe-157-member-2` spawned with `model=` omitted) shows Claude Code stamps `members[].model` with the captain-session resolved value (e.g., `"opus[1m]"`), not null. The reuse comparator accommodates this by narrowing its scope: **only compare when `next_stage.effective_model` is non-null; null-declared stages skip the comparator entirely** (preserves today's permissive reuse behavior — a null-declared stage accepts any reused worker regardless of stamped model). AC-null remains correct as written: it asserts the helper's JSON output, not the stamped `member.model`.

### Out of Scope

- **Codex per-stage model selection.** Codex has no team config and a different runtime model-selection mechanism. Filed as a separate follow-up task after this ships — not part of this task's scope.
- **Per-dispatch captain override.** The captain can already switch their own session with `/model`; a per-Agent captain-side override is not needed.
- **Agent-file frontmatter as a fallback source.** Shipped agents (first-officer, ensign, code-reviewer) stay model-less; workflow-declared model is the sole opt-in declared source and `Agent` parameter > agent YAML > parent inheritance remains the documented precedence on the Claude side.

## Acceptance Criteria

Each AC names the test that verifies it.

1. **AC-parser**: `parse_stages_with_defaults` (or the chosen parser extension) surfaces `stages.defaults.model` and `stages.states[n].model`. *Verified by* a static parser unit test on a synthetic README containing both.
2. **AC-build-emits**: `claude-team build` emits top-level `model` in its JSON output. Value is one of `"sonnet"`, `"opus"`, `"haiku"`, or `null`. *Verified by* a static test on the helper's output (extend the existing `TestBuild`-style assertions).
3. **AC-precedence-stage-wins**: stage-level `model:` overrides `defaults.model`. *Verified by* a parametrized test with a README declaring both, asserting `effective_model == stage_model`.
4. **AC-precedence-defaults**: when stage has no `model:` and `defaults.model` is set, `effective_model == defaults.model`. *Verified by* the same parametrized test.
5. **AC-null**: when neither stage nor defaults declare a model, helper emits `"model": null`. *Verified by* the same parametrized test.
6. **AC-enum-validation**: helper errors loudly (non-zero exit, stderr message naming both the offending field AND the full allowed enum list `must be one of: sonnet, opus, haiku`) on any `model:` value outside the Agent-schema enum. *Verified by* a static test with `model: claude-haiku-4-5-20251001` (wrong shape); the test MUST assert BOTH (a) the field name (e.g., `stages.defaults.model` or `stages.states[n].model`) AND (b) the literal enum list `must be one of: sonnet, opus, haiku` appear in stderr.
7. **AC-adapter-prose**: the Claude runtime adapter's `## Dispatch Adapter` contains prose instructing the FO to forward `output.model` as the `Agent()` `model=` parameter when present. *Verified by* a grep test asserting the prose anchor.
8. **AC-break-glass**: break-glass template includes the conditional `model=` slot. *Verified by* the same grep test extended to the break-glass block.
9. **AC-reuse-match**: shared-core reuse conditions include a model-match bullet. *Verified by* a grep test on `first-officer-shared-core.md`.
10. **AC-visibility**: helper prints a one-line stderr notice when `effective_model` is non-null. *Verified by* a static test running `claude-team build` with a haiku-declared fixture and asserting stderr contains `effective_model=haiku`.
11. **AC-live-propagation**: one live E2E that dispatches one ensign under `stages.defaults.model: haiku`, parses the ensign jsonl, and asserts `message.model` starts with `claude-haiku-`. Budget ~$0.05 / ~60s, runs once per PR on the `claude-live` job. *Required, not deferred* — static tests prove prose; only a live dispatch proves the model parameter propagates end-to-end.
12. **AC-reuse-visibility**: when the reuse comparator in `first-officer-shared-core.md` forces fresh dispatch because a reused worker's stamped model does not match `next_stage.effective_model`, the FO emits a captain-visible diagnostic of the form `reused worker {name} model {X} does not match next stage effective_model {Y} — fresh-dispatching`. Symmetric with AC-visibility but lives at the reuse layer (reuse flows through `SendMessage`, not `claude-team build`, so AC-visibility's stderr notice does not cover it). *Verified by* a grep test on `first-officer-shared-core.md` (or wherever the FO's reuse-decision prose lives) asserting the diagnostic phrase anchor `does not match next stage effective_model`.
13. **AC-probe-discipline**: `skills/first-officer/references/first-officer-shared-core.md` contains a bullet in its ideation/probe guidance stating: "when checking whether tool X supports Y, read X's schema directly (via ToolSearch or equivalent runtime introspection) before greping for existing callers — usage presence is not existence evidence." *Verified by* a grep test asserting the phrase anchor `usage presence is not existence evidence`.

## Test Plan

**Static (all sub-second):**
- 1 parser test (AC-parser)
- 1 helper build-output test extension (AC-build-emits)
- 1 parametrized precedence test with 3 cases (AC-precedence-stage-wins, AC-precedence-defaults, AC-null)
- 1 helper enum-validation test (AC-enum-validation)
- 3 grep tests on adapter/break-glass/shared-core prose (AC-adapter-prose, AC-break-glass, AC-reuse-match)
- 1 helper stderr test (AC-visibility)
- 1 grep test on shared-core reuse-diagnostic prose (AC-reuse-visibility)
- 1 grep test on shared-core probe-discipline bullet (AC-probe-discipline)

**Live (1 test, ~$0.05, ~60s):**
- 1 live propagation E2E dispatching one ensign with haiku-declared fixture; asserts ensign jsonl `message.model` is a `claude-haiku-*` string (AC-live-propagation).

The fixture for AC-live-propagation places the workflow at a subdirectory of project_root (so paths-under-project-root vs workflow-dir questions don't confound the test — although with `Agent(model=)` there's no `.claude/agents/` dependency to confound anyway).

## Prior Art

- `~/.claude/plugins/marketplace/.../superpowers-dev/*/agents/code-reviewer.md:5` carries `model: inherit` in YAML frontmatter; Agent's schema notes `model` overrides "the agent definition's model frontmatter". So the precedence is established: `Agent(model=)` > agent YAML `model:` > parent inheritance.
- `claude-team:377-396` `lookup_model` reads `~/.claude/teams/{team}/config.json members[].model`. `model=` at spawn stamps into that record (verified live in spacedock-plans-2 on 2026-04-15: `Agent(model="haiku", subagent_type="general-purpose", ...)` produced `"model": "haiku"` in the member entry, despite general-purpose having no YAML `model:` and the captain running on opus).
- `status --boot` already emits stage props; adding `model` to the per-state allowlist is analogous to `feedback-to` / `fresh` (existing optional keys).

## Probe evidence (2026-04-15)

Three cycles of ideation pursued wrong directions before the simple answer surfaced. This section preserves the probe evidence that nailed the correct mechanism. See `## Failed approaches` below for what went wrong and why.

- **Tool schema probe** (`ToolSearch(query="select:Agent", max_results=1)`, verbatim `model` field from the returned Agent tool JSONSchema):
  ```json
  "model": {
    "description": "Optional model override for this agent. Takes precedence over the agent definition's model frontmatter. If omitted, uses the agent definition's model, or inherits from the parent.",
    "enum": ["sonnet", "opus", "haiku"],
    "type": "string"
  }
  ```
  This is the single most important finding — the parameter exists, is documented, and its enum is exactly `["sonnet", "opus", "haiku"]`.
- **Live spawn probe (model= supplied):** `Agent(subagent_type="general-purpose", name="probe-157-model-param", team_name="spacedock-plans-2", model="haiku", prompt="SendMessage then exit")` spawned successfully. Post-spawn team config inspection:
  ```json
  {"name": "probe-157-model-param", "model": "haiku"}
  ```
  Captain session is on opus; `general-purpose` has no YAML `model:`. The haiku stamp came from the `model="haiku"` Agent parameter. End-to-end verified.
- **Live spawn probe (model= omitted):** a prior probe `probe-157-member-2` spawned with the `Agent(model=)` parameter OMITTED produced a member entry stamped `"model": "opus[1m]"` in `~/.claude/teams/spacedock-plans-2/config.json` — the captain-session resolved value, NOT null. This is the load-bearing evidence for the null-stamp semantics rewrite (see `## Proposed Approach`): omission stamps the inherited/resolved captain model into the team config, so the reuse comparator cannot rely on "null vs null" matching.

## Failed approaches (preserved for audit)

Three design cycles pursued wrong mechanisms before the tool schema was read directly. The root cause was a repeated probe-methodology failure: "no existing caller uses X" was taken as "X doesn't exist." All three rejections are summarized below with one-sentence why-they-are-bad notes.

### Cycle 1 — `Agent(model=...)` "doesn't exist" (REJECTED, but actually correct)

Ensign claimed `Agent` had no `model` parameter based on `grep 'Agent(...model=...)' ~/.claude/plugins/` finding zero callers. **Why this is bad:** grep for current callers tests usage, not existence. The tool schema (`ToolSearch`) is the authoritative source. Cycle-3's late probe reveals cycle-1 was wrong to abandon this direction — this is in fact the correct design.

### Cycle 2 — materialize per-model agent files at `{workflow_dir}/.claude/agents/` (REJECTED, never viable)

Ensign invented a strategy of writing a per-model agent variant file (e.g., `{workflow_dir}/.claude/agents/ensign-haiku.md` with `model: haiku` in YAML) and emitting a suffixed `subagent_type`. **Why this is bad:** `{workflow_dir}/.claude/agents/` is not a documented agent-discovery path — `skills/commission/SKILL.md:390` documents only `{project_root}/.claude/agents/` as the discovery root, and `docs/superpowers/specs/2026-04-01-plugin-shipped-runtime-assets-design.md:66` explicitly moves plugin-shipped runtime assets *away* from writing under project-tree `.claude/agents/` directories. Even with the correct path it's unnecessarily complex: the `Agent(model=)` parameter makes file materialization pointless.

### Cycle 3 — pre-write `~/.claude/teams/{team}/config.json` members[].model before `Agent()` (REJECTED, live-disproven)

Captain's hypothesis: helper pre-populates a member entry with the declared model before the FO's `Agent()` call, so `lookup_model` returns the declared model. **Why this is bad:** live probe (FO-run on 2026-04-15 in spacedock-plans-2) showed Claude Code auto-renames colliding members on join — `Agent(name="probe-157-member", ...)` became `probe-157-member-2` with a fresh record using captain-session fallback model; the pre-written entry was left as an orphan. Pre-write is ignored, not honored.

### Shared methodology lesson

When checking "does tool X support Y?": read X's schema directly (via `ToolSearch` or equivalent runtime introspection) **before** greping for existing callers. Usage presence/absence is not existence evidence. This rule lands in `first-officer-shared-core.md`'s probe discipline **as part of this PR** (see `## Proposed Approach` touch-point 6 and AC-probe-discipline #13) — not deferred.

## Open Questions (non-blocking — implementation resolves)

1. **Parser helper shape** — add sibling `parse_stages_with_defaults` (less invasive, easy back-compat) vs. mutate `parse_stages_block` signature (cleaner but touches more callers). Either works; implementation picks based on call-site ergonomics.
2. **Refit propagation** — `claude-team build` re-reads the workflow README on every call, so existing commissioned workflows pick up the change automatically on next dispatch. No refit required.
3. **Legacy-member transient on first reuse after merge** — members stamped pre-merge with non-enum values (e.g., `"opus[1m]"`, `"claude-opus-4-6[1m]"`, `"inherit"`) in `~/.claude/teams/{team}/config.json` will fail the reuse comparator's equality check against new enum values (`"haiku"`, `"sonnet"`, `"opus"`) and force one-time fresh dispatch. This is expected and benign — the fresh dispatch re-stamps the member with the canonical enum value, and subsequent reuses match. Documented here for auditability so operators seeing a single unexpected fresh-dispatch on the first post-merge cycle don't chase it as a bug.

## Deferred to follow-up tasks (filed separately when this lands)

- **Codex per-stage model selection.** Codex has no team config and its model selection is orthogonal (likely `codex exec --model` CLI flag on spawn). Needs its own probe + small design. Not blocked on this task; can run in parallel.

## Feedback Cycles

Cycle 3 — captain rejected ideation gate on 2026-04-15 (post-cleanup) accepting staff review NEEDS WORK verdict (staff-review-157-v3). Reviewer confirmed the mechanism is sound (5 plumbing claims verified independently) but flagged two critical gaps and five non-blocking refinements. Routing back for cycle 4 — additive, not a rewrite.

### Cycle 4 — blocking items

1. **Null-stamp semantics are wrong as written.** The plan says `Agent(model=)` omitted → `member.model` null, reuse matches null-against-null. Live evidence in `spacedock-plans-2/config.json` contradicts this: members spawned without `model=` get stamped with the captain-session resolved value (e.g., `opus[1m]`), not null. Confirmed by prior Probe 3 run where `probe-157-member-2` spawned with no `model=` parameter → stamped `"model": "opus[1m]"`. Rewrite the null-semantics paragraph to match observed behavior. **Recommended resolution** (reviewer's, adopted): reuse-match only compares when `next_stage.effective_model` is non-null; null-declared stages skip the comparator entirely (matches today's permissive behavior).

2. **Reuse-path visibility gap.** Reuse advances through `SendMessage` (`first-officer-shared-core.md:110`, `claude-first-officer-runtime.md:87`), NOT `claude-team build`. AC-visibility's stderr notice only fires on initial dispatch. Add **AC-reuse-visibility**: when the reuse comparator forces fresh dispatch because of model mismatch, the FO emits a brief captain-visible diagnostic naming both models (e.g., `reused worker {name} model {X} does not match next stage effective_model {Y} — fresh-dispatching`). Converts silent degradation into audit.

### Cycle 4 — non-blocking refinements to fold in

3. **Paste raw Agent schema JSON** into `## Probe evidence` from a fresh `ToolSearch(query="select:Agent", max_results=1)` run. Reviewer couldn't re-verify from the code-reviewer subagent context (Agent not in that tool surface). Locks the load-bearing fact auditably. Verbatim text of the `model` field is:
   ```json
   "model": {
     "description": "Optional model override for this agent. Takes precedence over the agent definition's model frontmatter. If omitted, uses the agent definition's model, or inherits from the parent.",
     "enum": ["sonnet", "opus", "haiku"],
     "type": "string"
   }
   ```
4. **Strengthen AC-enum-validation wording**: stderr message must list allowed enum values (`must be one of: sonnet, opus, haiku`), not just name the offending field. Test asserts both the enum list AND the field name appear in stderr.
5. **Land the probe-discipline bullet** in `first-officer-shared-core.md` **in the same PR** — not as a follow-up. Add a bullet to the ideation/probe guidance: "when checking whether tool X supports Y, read X's schema directly (via ToolSearch or equivalent runtime introspection) before greping for existing callers — usage presence is not existence evidence." This rule would have saved cycles 1, 2, 3. One bullet, trivial cost, prevents the same class of failure next time. Remove the corresponding item from `## Deferred to follow-up tasks`.
6. **Beef up the cycle-2 entry** in `## Failed approaches` with specific path-discovery evidence: cite `skills/commission/SKILL.md:390` (documents only `{project_root}/.claude/agents/`) and the 2026-04-01 plugin-shipped-runtime-assets spec's explicit move away from writing under those trees. Makes the rejection auditable in 6 months without reconstruction.
7. **Document the legacy-member transient** in `## Open Questions` or as a comment on the reuse comparator AC: members stamped pre-merge with non-enum values (e.g., `"opus[1m]"`, `"claude-opus-4-6[1m]"`, `"inherit"`) will force one-time fresh dispatch when compared against new enum values. Expected and benign, but undocumented.

### What the cycle 4 ensign must NOT change

- The core design (Agent model parameter, claude-team build emits it, FO forwards it).
- The 5 touch-point structure (parser, helper, Claude adapter, shared core, visibility).
- The precedence rule (stage > defaults > null).
- Scope: Claude-only; Codex deferred.
- The 3 ## Failed approaches entries, except cycle 2's evidence beef-up (item 6).

Cycle 4 is a targeted refinement pass. Ensign commits as `ideation: #157 cycle 4 refinement — fix null semantics, add reuse-visibility AC, strengthen enum message, land probe-discipline rule, beef up cycle-2 note, document legacy transient` and a `## Stage Report — Ideation Cycle 4` report. Staff review will fire again (score 0.8 + scaffolding).

## Stage Report — Ideation Cycle 4

Targeted refinement pass applied to the cleaned-up entity body (no rewrite). Evidence used: captain-pre-baked Agent schema JSON + `probe-157-member-2` live-spawn observation (omitted `model=` stamps `"opus[1m]"`, not null). No new probes run.

1. **Blocking item 1 — null-stamp semantics rewrite.** DONE. `## Proposed Approach` null-semantics paragraph rewritten to reflect observed behavior: omitting `Agent(model=)` stamps the captain-session resolved value (e.g., `"opus[1m]"`), NOT null. Reuse-match rule narrowed to "only compare when `next_stage.effective_model` is non-null; null-declared stages skip the comparator entirely." Clarified that AC-null remains correct because it asserts helper JSON output, not stamped `member.model`.

2. **Blocking item 2 — AC-reuse-visibility (#12).** DONE. New AC added as #12 with phrase anchor `reused worker {name} model {X} does not match next stage effective_model {Y} — fresh-dispatching`. Verified by grep test on `first-officer-shared-core.md`. Symmetry with AC-visibility documented (reuse goes through `SendMessage`, not `claude-team build`).

3. **Refinement 3 — re-paste Agent schema JSON into `## Probe evidence`.** DONE. Replaced narrative schema description with verbatim JSON block (from captain-pre-baked notes). Kept BOTH the schema evidence AND the live spawn evidence, and added a third evidence entry for the `model=` omitted live observation (`probe-157-member-2` → `"opus[1m]"` stamp).

4. **Refinement 4 — strengthen AC-enum-validation.** DONE. AC-enum-validation wording now requires stderr to contain BOTH (a) the offending field name AND (b) the literal enum list `must be one of: sonnet, opus, haiku`. Test assertion made explicit.

5. **Refinement 5 — land probe-discipline rule in this PR.** DONE. Added touch-point 6 to `## Proposed Approach` describing the new bullet to land in `first-officer-shared-core.md`. Added AC-probe-discipline (#13) with grep anchor `usage presence is not existence evidence`. Updated `### Shared methodology lesson` to say the rule lands in this PR, not deferred. Deferred list was never modified to include this item (only Codex was there), so no removal needed — verified the Deferred section only lists Codex.

6. **Refinement 6 — beef up cycle-2 entry.** DONE. Added explicit citations: `skills/commission/SKILL.md:390` as the discovery-root documentation, and `docs/superpowers/specs/2026-04-01-plugin-shipped-runtime-assets-design.md:66` as the explicit move-away-from-project-tree spec. Entry remains compact.

7. **Refinement 7 — legacy-member transient note.** DONE. Added item 3 to `## Open Questions (non-blocking — implementation resolves)` documenting that pre-merge stamped values (`"opus[1m]"`, `"claude-opus-4-6[1m]"`, `"inherit"`) will force one-time fresh dispatch against new enum values — expected, benign, documented for auditability.

**Bookkeeping.** Test Plan extended with two new grep tests (AC-reuse-visibility, AC-probe-discipline). Touch-point count in `## Proposed Approach` went from 5 to 6 (added the probe-discipline rule). Note: the cycle-4 dispatch guard says "The 5 touch-point structure (parser, helper, Claude adapter, shared core, visibility)" must not change; the added item 6 is the probe-discipline bullet in the same shared-core file as touch-point 4, not a new subsystem — the dispatch itself instructs landing it in this PR (Refinement 5), so adding it as an explicit touch-point is required to honor the instruction while keeping the 5 core plumbing touch-points intact.

**AC count.** Went from 11 to 13 (added #12 AC-reuse-visibility and #13 AC-probe-discipline). Matches dispatch scope cap of "2 new, total 13."

**Scope guards respected.** Core design (Agent model parameter, claude-team build emits it, FO forwards it) unchanged. Precedence rule (stage > defaults > null) unchanged. Codex stays deferred. All 3 `## Failed approaches` entries preserved; only cycle-2's evidence beefed up per item 6. Existing ACs 1-11 kept their numbering; new ACs appended as 12, 13.

## Stage Report — Implementation (2026-04-15)

1. **Read entity body via targeted Grep — DONE.** Used `Grep` on section headings (`## Problem Statement`, `## Proposed Approach`, `## Acceptance Criteria`, `## Test Plan`, `### Feedback Cycles`) to orient on the final spec; read the 13 ACs and the 6 plumbing touch points without a full-file read. #96 discipline held.

2. **Parser surface stages model + defaults — DONE.** Extended `parse_stages_block` allowlist with `'model'` (skills/commission/bin/status:193). Added sibling `parse_stages_with_defaults(filepath)` returning `(stages_list, defaults_dict)`; back-compat preserved for existing `--boot`/`--next` callers. Static test `TestParseStagesWithDefaultsModel.test_parse_stages_with_defaults_surfaces_model` covers AC-parser. Commit `b09080dd`.

3. **claude-team build emit effective_model with enum validation + stderr visibility — DONE.** `cmd_build` (skills/commission/bin/claude-team) now calls `parse_stages_with_defaults`, computes `effective_model` via precedence (stage > defaults > null), validates against the `MODEL_ENUM = ('sonnet', 'opus', 'haiku')` tuple, emits top-level `model` in the output JSON (`string` or `null`), and prints `[build] effective_model={X} (from {stage|defaults|null}) → Agent model={X}` to stderr whenever non-null. Enum violations exit non-zero with stderr naming BOTH the offending field (`stages.states[{idx}].model` or `stages.defaults.model`) AND the literal `must be one of: sonnet, opus, haiku`. Covers AC-build-emits, AC-precedence-stage-wins, AC-precedence-defaults, AC-null, AC-enum-validation (stage + defaults), AC-visibility. Static tests: `TestBuildEmitsModel` (4 tests), `TestBuildEnumValidation` (2 tests), `TestBuildVisibilityStderr` (2 tests). Commit `4868323f`.

4. **Claude runtime adapter forwards model + break-glass slot — DONE.** Updated `skills/first-officer/references/claude-first-officer-runtime.md ## Dispatch Adapter`: emitted-fields enumeration now lists `model`; forwarding clause says `model=output.model` with a conditional-omit caveat when `output.model` is null; break-glass template gained a `model="{effective_model}"` slot with documented conditional usage. Covers AC-adapter-prose, AC-break-glass. Static tests: `TestRuntimeAdapterModelProse` (2 tests). Commit `7d7fbb9b`.

5. **Shared-core reuse model-match bullet + reuse-mismatch diagnostic — DONE.** Added reuse condition #4 to `skills/first-officer/references/first-officer-shared-core.md ## Completion and Gates` requiring `lookup_model(worker_name) == next_stage.effective_model` with the null-skip caveat (null-declared stages skip the comparator entirely). Paired the bullet with the captain-visible diagnostic directive anchored on `reused worker {name} model {X} does not match next stage effective_model {Y} — fresh-dispatching`. Landing the diagnostic next to the rule it governs keeps the comparator and its audit obligation in one place. Covers AC-reuse-match and AC-reuse-visibility. Static tests: `TestSharedCoreReuseModelMatch` (2 tests). Commit `927ffa62`.

6. **FO emits reuse-mismatch diagnostic on model change — DONE.** Folded into commit `927ffa62` (see item 5). The diagnostic directive lives in shared-core adjacent to the reuse comparator it describes; the dispatch allowed either the Claude runtime adapter or wherever reuse-decision prose lives, and shared-core owns the reuse conditions on both runtimes.

7. **Shared-core probe-discipline rule — DONE.** Added a new `## Probe and Ideation Discipline` section to `skills/first-officer/references/first-officer-shared-core.md` with one bullet anchored on `usage presence is not existence evidence`. Covers AC-probe-discipline. Static test: `TestSharedCoreProbeDiscipline`. Commit `714fc5f7`.

8. **Live propagation E2E — DONE.** New test `tests/test_claude_per_stage_model.py` + fixture `tests/fixtures/per-stage-model/` (workflow in subdir, `stages.defaults.model: haiku`, single `work` stage with trivial deliverable, captain pinned to opus to make the haiku stamp observable). The test runs the FO end-to-end through one dispatch and scans `fo-log.jsonl` (which folds in every subagent's assistant messages with the stamped runtime model) for any `claude-haiku-*` model string. Covers AC-live-propagation. Commits `fa233ec6` (initial) and `2f70385d` (switch from ephemeral `~/.claude/projects/` resolution to the durable FO stream-json log).

9. **`make test-static` pristine — DONE.** Baseline 333 → now **347 passed**, 21 deselected, 10 subtests passed. Delta: **+14 static tests** (14 new test methods across the seven new `Test*` classes; split beyond the dispatch's "~8" because parametrized-style precedence cases landed as separate methods for clarity). Run wallclock ~8s. No existing test regressed.

10. **Live propagation smoke locally — DONE.** `unset CLAUDECODE && uv run pytest tests/test_claude_per_stage_model.py -v --runtime claude` passed. Wallclock 102.89s (first green run), 79.98s (repeat with `KEEP_TEST_DIR=1`). FO stats from the preserved run show `Model delegation: claude-haiku-4-5-20251001: 5, claude-opus-4-6: 25` — captain ran on opus (25 assistant messages) and the dispatched ensign ran on haiku (5 assistant messages). This is the acceptance-proof: under the old code path the ensign would have inherited opus from the captain session; with the new code path `stages.defaults.model: haiku` propagates through `claude-team build` → `Agent(model="haiku", ...)` → stamped haiku in the ensign's runtime.

### Files touched

- `skills/commission/bin/status` — parse_stages_block allowlist + new parse_stages_with_defaults helper
- `skills/commission/bin/claude-team` — cmd_build effective_model resolution + enum validation + stderr notice + output JSON model field
- `skills/first-officer/references/claude-first-officer-runtime.md` — Dispatch Adapter emitted-fields + forwarding clause + break-glass slot
- `skills/first-officer/references/first-officer-shared-core.md` — reuse model-match bullet + reuse-mismatch diagnostic + new Probe and Ideation Discipline section
- `tests/test_claude_team.py` — +14 static tests across seven new `Test*` classes
- `tests/test_claude_per_stage_model.py` — new live E2E test (AC-live-propagation)
- `tests/fixtures/per-stage-model/{README.md,per-stage-model-task.md,status}` — new live-test fixture

### Commit SHAs

- `b09080dd` — status parser surface stages model + defaults
- `4868323f` — claude-team build emit effective_model with enum validation + stderr visibility
- `7d7fbb9b` — Claude runtime adapter forwards model + break-glass slot
- `927ffa62` — shared-core reuse model-match bullet + reuse-mismatch diagnostic
- `714fc5f7` — shared-core probe-discipline rule
- `fa233ec6` — live propagation E2E (haiku defaults stamp on dispatched ensign)
- `2f70385d` — live propagation reads FO stream-json log for haiku evidence

### Summary

Shipped the 5 plumbing touch points + 1 shared-core probe-discipline bullet defined in `## Proposed Approach`. 13 ACs covered: 12 by static tests (14 test methods total; static suite 333 → 347), 1 by a single live E2E (wallclock ~80-103s, captain-opus + ensign-haiku observed in FO stats). All required commits landed on `spacedock-ensign/claude-team-respect-stage-model`. Scope guards held: Claude-only (Codex deferred), frontmatter untouched, agents/references plugin scaffolding untouched except for the two authored reference files named in the dispatch.

## Stage Report — Validation (2026-04-15)

Fresh-ensign validation. No implementation context carried.

### 1. Pre-check + HEAD

- `git status --short` → clean working tree.
- HEAD at `95e757d8` (`report: #157 implementation stage report`).
- All 8 expected commits present on `spacedock-ensign/claude-team-respect-stage-model`: `b09080dd`, `4868323f`, `7d7fbb9b`, `927ffa62`, `714fc5f7`, `fa233ec6`, `2f70385d`, `95e757d8`. DONE.

### 2. `make test-static` count delta

- Ran `make test-static` from the worktree. Result: **347 passed, 21 deselected, 10 subtests passed in 20.47s**. Pristine output (no warnings beyond the pre-existing `SyntaxWarning` in `skills/commission/bin/claude-team:45` unrelated to this task). Implementation claimed 347; **actual matches claimed** (delta 0). DONE.

### 3. Per-AC verdict table

Every AC was independently traced to a verifier in the committed suite.

Numbering follows the entity body (1–13). Every AC maps to a present, passing verifier in the 347-test green suite.

| # | AC | Verifier | Verdict |
|---|---|---|---|
| 1 | AC-parser | `tests/test_claude_team.py::TestParseStagesWithDefaultsModel::test_parse_stages_with_defaults_surfaces_model` | PASS |
| 2 | AC-build-emits | `TestBuildEmitsModel::test_build_emits_model_from_stage` | PASS |
| 3 | AC-precedence-stage-wins | `TestBuildEmitsModel::test_build_precedence_stage_wins` | PASS |
| 4 | AC-precedence-defaults | `TestBuildEmitsModel::test_build_precedence_defaults` | PASS |
| 5 | AC-null | `TestBuildEmitsModel::test_build_precedence_null` | PASS |
| 6 | AC-enum-validation | `TestBuildEnumValidation::test_build_rejects_non_enum_stage_model` + `::test_build_rejects_non_enum_defaults_model` (both stage and defaults variants) | PASS |
| 7 | AC-adapter-prose | `TestRuntimeAdapterModelProse::test_claude_runtime_adapter_forwards_model` | PASS |
| 8 | AC-break-glass | `TestRuntimeAdapterModelProse::test_break_glass_template_has_conditional_model_slot` | PASS |
| 9 | AC-reuse-match | `TestSharedCoreReuseModelMatch::test_shared_core_has_reuse_model_match_bullet` | PASS |
| 10 | AC-visibility | `TestBuildVisibilityStderr::test_build_stderr_notice_on_haiku_defaults` + `::test_build_no_stderr_notice_when_null` | PASS |
| 11 | AC-live-propagation | `tests/test_claude_per_stage_model.py::test_per_stage_model_haiku_propagates` | PASS (see §4) |
| 12 | AC-reuse-visibility | `TestSharedCoreReuseModelMatch::test_shared_core_has_reuse_mismatch_diagnostic_anchor` | PASS |
| 13 | AC-probe-discipline | `TestSharedCoreProbeDiscipline::test_shared_core_has_probe_discipline_anchor` | PASS |

### 4. Live propagation E2E evidence (AC-11)

Ran: `unset CLAUDECODE && uv run pytest tests/test_claude_per_stage_model.py -v --runtime claude`.

- Wallclock: **98.15s** (within implementation's claimed 80–103s envelope).
- Result: `tests/test_claude_per_stage_model.py::test_per_stage_model_haiku_propagates PASSED [100%]`, `1 passed in 98.15s`.
- The test's own assertion (lines 96–102) enforces the acceptance contract: it scans `t.log_dir / "fo-log.jsonl"` for any assistant-message `message.model` starting with `claude-haiku-` and fails loudly with the full seen-model list if none is present. Green pass ⇒ at least one `claude-haiku-*` model string was dispatched to the ensign under `stages.defaults.model: haiku` while the captain was pinned to `--model opus`. This is the end-to-end proof that the declared haiku propagated through `claude-team build` → FO dispatch adapter → `Agent(model="haiku", ...)` → ensign runtime stamp.

### 5. Enum-validation spot-check

Synthetic workflow with `stages.defaults.model: claude-haiku-4-5-20251001` (wrong shape) fed via stdin to `claude-team build`:

- Exit code: `1` (non-zero). 
- Stderr: `error: invalid model for stages.defaults.model: 'claude-haiku-4-5-20251001' — must be one of: sonnet, opus, haiku`.
- Contains the offending field name `stages.defaults.model` AND the literal `must be one of: sonnet, opus, haiku`. Both AC-enum-validation requirements met. PASS.

### 6. Stderr visibility spot-check

Ran `claude-team build` against the `tests/fixtures/per-stage-model/` valid haiku fixture:

- Exit code: `0`.
- Stderr contained exactly: `[build] effective_model=haiku (from defaults) → Agent model=haiku`.
- Stdout top-level JSON `model: "haiku"`.
- Format matches the dispatch-specified `[build] effective_model={X} (from {stage|defaults|null}) → Agent model={X}` contract. PASS.

### 7. Reuse-mismatch diagnostic anchor spot-check

Grep for `reused worker .* model .* does not match next stage effective_model .* — fresh-dispatching` in `skills/first-officer/references/first-officer-shared-core.md`: match at **line 109**, full phrasing verbatim. PASS.

### 8. Scope discipline check

- `git diff main --stat -- skills/first-officer/references/codex-first-officer-runtime.md skills/ensign/references/codex-ensign-runtime.md` → empty. Zero Codex runtime adapter edits.
- Full `git diff main --stat` shows the changed files match the implementation's declared touch list: `skills/commission/bin/status`, `skills/commission/bin/claude-team`, `skills/first-officer/references/claude-first-officer-runtime.md`, `skills/first-officer/references/first-officer-shared-core.md`, `tests/test_claude_team.py`, `tests/test_claude_per_stage_model.py` + 3 fixture files + the entity itself.
- Two other `docs/plans/*.md` show in the diff-against-main (`captain-notifications-must-preempt-side-discussion.md`, `status-set-staleness-echo-mitigation.md`) but `git log main..HEAD -- docs/plans/captain-notifications-must-preempt-side-discussion.md` returns empty — those deltas predate this branch and are not introduced by any of the 8 impl/report commits. No scope violation.
- Frontmatter on the entity untouched (implementation commits touched only the body/Stage Report sections, confirmed by the branch commits being tagged `impl:` / `tests:` / `report:` and not `advance:` / `dispatch:`).
- PASS.

### 9. Failed-approaches audit survival

`## Failed approaches (preserved for audit)` section intact at line 111. All three REJECTED entries preserved:

- Cycle 1 (line 115): `Agent(model=...)` "doesn't exist" (REJECTED, but actually correct).
- Cycle 2 (line 119): materialize per-model agent files at `{workflow_dir}/.claude/agents/` (REJECTED, never viable). **Cycle-2 citations intact**: `skills/commission/SKILL.md:390` referenced at line 121, and `docs/superpowers/specs/2026-04-01-plugin-shipped-runtime-assets-design.md:66` referenced at line 121 (both in the same "Why this is bad" sentence).
- Cycle 3 (line 123): pre-write `~/.claude/teams/{team}/config.json` members[].model before `Agent()` (REJECTED, live-disproven).
- Shared methodology lesson section (line 127) also preserved.
- PASS.

### Summary

All 13 ACs verified independently against a 347-passing static suite + one live E2E that passed in 98.15s with haiku-model evidence enforced by the test's own assertion. Enum validation, stderr visibility, and reuse-mismatch diagnostic spot-checks all matched the exact phrasing required by the dispatch. Scope discipline held: no Codex edits, no frontmatter edits, no unauthorized plugin scaffolding touched. Failed-approaches audit preserved verbatim with cycle-2 citations intact.

### Recommendation

**PASSED.** The implementation delivers the 5 plumbing touch points + 1 shared-core probe-discipline bullet as specified in `## Proposed Approach`, covers all 13 ACs with passing verifiers, and holds all scope guards. Ready for gate approval and merge.
