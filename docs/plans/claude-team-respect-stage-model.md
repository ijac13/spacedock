---
id: 157
title: "claude-team build: resolve and emit per-stage model, runtime adapters pass it through on dispatch"
status: ideation
source: "github.com/clkao/spacedock#95 — stages.defaults.model accepted in workflow READMEs but ignored at dispatch; subagents unconditionally inherit captain-session model"
started: 2026-04-15T17:42:36Z
completed:
verdict:
score: 0.80
worktree:
issue: "#95"
pr:
---

Workflow READMEs accept `stages.defaults.model` and per-state `model:` overrides, but the plugin never reads them. Subagents unconditionally inherit the captain session's model, so a workflow author declaring `model: haiku` for routine stages still gets Opus subagents whenever the captain is running Opus.

```
$ grep -rn '\bmodel\b' skills/commission/ skills/first-officer/
(no dispatch-side matches — only runtime parsing helpers in claude-team)
```

## Problem Statement

A captain on Opus running a workflow whose README declares `model: haiku` on dispatch/execute stages gets every subagent on Opus — >10× overspend on stages explicitly designed to run cheap. The declared stage model is inert at dispatch time. The gap is silent; only a jsonl transcript audit surfaces it.

The workaround today — captain switches their own session model to match the target stage — forfeits Opus for captain-side judgment work (gate reviews, clarification, plan review), which is exactly where operator-visible quality matters most.

The fix must resolve the declared model at `claude-team build` time (the single chokepoint through which both Claude and Codex FO runtimes are already required to pipe dispatch assembly) and thread it through both dispatch paths without regressing the default-inherit behavior.

## Proposed Approach

**⚠ Architectural shift flagged in cycle 2:** the cycle-1 design assumed Claude Code's `Agent()` tool accepted a per-dispatch `model=` parameter. Probing the upstream plugin docs (see Prior Art below) shows that is false: Claude Code agent-level model selection is declared in `agents/*.md` YAML frontmatter (e.g., `model: inherit` in superpowers' `code-reviewer.md`), not as a runtime Agent-call argument. The cycle-2 design therefore routes per-stage model through **agent-file materialization at `claude-team build` time**, not through a forwarded `Agent(model=...)` parameter. Codex's `spawn_agent` also has no documented `model` parameter in any runtime reference shipped today; the Codex path uses the same materialization strategy (a prefabricated per-model agent definition the packaged worker can load).

Resolve at `claude-team build` with this precedence:

```
effective_model = stages.states[stage].model
              ?? stages.defaults.model
              ?? null  (omit — let agent frontmatter / session default apply)
```

### Touch points (revised for cycle 2)

1. **`skills/commission/bin/status` — `parse_stages_block`.** Today this helper collects only a fixed allowlist of optional per-state keys (`feedback-to`, `agent`, `fresh`) into the returned stage dict, and consumes `defaults:` only to compute `default_worktree` / `default_concurrency` before discarding the rest. To surface `model`, extend `parse_stages_block` to:
   - add `model` to the per-state optional-field allowlist, so `stages.states[stage].model` is preserved on each returned stage dict;
   - expose the parsed `defaults` dict to callers. Simplest shape: return `(stages_list, defaults_dict)` from a new sibling helper (e.g., `parse_stages_with_defaults`) and keep `parse_stages_block` as-is for back-compat with existing callers (`status --boot`, `--next`, etc.). `claude-team build` switches to the new helper.

2. **`skills/commission/bin/claude-team` — `cmd_build`.** Call the defaults-aware helper, compute `effective_model` using the precedence above, and:
   - **Materialize a per-stage agent file** when `effective_model` is non-null. Path: `{workflow_dir}/.claude/agents/{base_agent_name}-{model_slug}.md` where `base_agent_name` is derived from the stage's `agent:` (e.g., `spacedock:ensign` → `ensign`) and `model_slug` is a filesystem-safe derivation of the model string (e.g., `claude-haiku-4-5` → `claude-haiku-4-5`). The materialized file copies the base agent's body and sets `model: {effective_model}` in the YAML frontmatter. Skip materialization if the file already exists with a matching model field (idempotent).
   - **Emit `subagent_type: {namespace}:{base_agent_name}-{model_slug}`** in the build output JSON so the FO's `Agent(subagent_type=...)` call targets the materialized variant.
   - **Emit `model: {effective_model}` as a top-level output field** for visibility, tests, and the stderr observability requirement (see item 7 below). Value is the resolved string or `null`.
   - **On null `effective_model`:** emit the vanilla `subagent_type` unchanged (no materialization), preserving today's captain-session inheritance.

3. **`skills/first-officer/references/claude-first-officer-runtime.md` — `## Dispatch Adapter`.** The forwarding clause stays as-is (`subagent_type`, `name`, `team_name`, `prompt`) — the model is baked into the subagent_type rather than passed as a separate parameter. Add prose explaining that the helper may emit a materialized `subagent_type` (e.g., `spacedock:ensign-haiku`), which the FO forwards verbatim. Update the Break-Glass Manual Dispatch template with a note: "if the workflow declares `stages.defaults.model` or a per-state `model`, the break-glass path must also materialize a per-stage agent file or the declared model will be silently ignored." Keep break-glass minimal — the primary path is the helper.

4. **`skills/first-officer/references/codex-first-officer-runtime.md` — `## Dispatch Adapter`.** Codex packaged workers resolve their role from the skill asset path (`~/.agents/skills/{namespace}/{name}/SKILL.md`). Document that a materialized per-model variant results in a new logical id (e.g., `spacedock:ensign-haiku`) whose skill asset resolution points to the same shared body. Codex's `fork_context=false` spawn already carries the assignment self-contained, so the per-model variant's role-definition preload is the mechanism that biases the worker toward the declared model. Document the reuse-invalidation rule: if the next stage's `effective_model` differs from the reused worker's spawn-time model, reuse is disallowed — shut down and fresh-dispatch. Do NOT claim `spawn_agent` accepts `model=` — it does not in current documentation.

5. **Shared core — `skills/first-officer/references/first-officer-shared-core.md`.** Add one bullet to the reuse conditions in `## Completion and Gates`: reuse requires "next stage's effective_model matches the reused worker's spawn-time model, inferred from the worker's `subagent_type` suffix (or null-null match when neither stage declares a model)." This keeps the rule runtime-agnostic.

6. **`agents/first-officer.md` / `agents/ensign.md`.** No changes required; they stay model-less (inherit). They remain the template body used for materialization. Materialized variants live under the workflow directory's `.claude/agents/`, not under the plugin's `agents/`.

7. **Dispatch-time visibility (cycle 2 new).** `claude-team build` prints a one-line stderr notice like `[build] effective_model=claude-haiku-4-5 (from defaults) → subagent_type=spacedock:ensign-claude-haiku-4-5` whenever a materialized variant is used. The FO's dispatch commit message (`dispatch: {slug} entering {next_stage}`) should optionally include the effective model as a trailer. Silent correctness is as hard to audit as silent incorrectness — this makes per-dispatch model visible at a glance.

### Precedence and null semantics

The precedence list is final: per-state override > defaults > null. The cycle-2 design pins the following semantics for the null case:

- **Null JSON representation (Open Question 3, resolved):** emit `"model": null` explicitly in the build output. Explicit null is clearer for adapter-prose assertions, makes the "is anything declared?" check trivial, and mirrors the default YAML behavior (`null` vs absent key).
- **Null reuse semantics (staff gap 7, resolved):** null is a distinct value in reuse comparisons. If the completed worker was spawned from the vanilla `subagent_type` (no model materialization) and the next stage declares a model, effective_model differs and reuse is blocked. Conversely, if both the completed stage and the next stage declare the SAME non-null model, the same materialized subagent_type was used and reuse is valid. "Null matches null" and "model-X matches model-X" are both valid reuses; every other pairing invalidates reuse. Captain session model is NOT part of this comparison — only declared workflow model is.

### Reuse and Refit

- **Reuse identity:** the reused worker's spawn-time model is inferred from its `subagent_type` — vanilla `spacedock:ensign` means inherited/null, materialized `spacedock:ensign-haiku` means `haiku`. This avoids needing to read `~/.claude/teams/{team}/config.json` at reuse time (though `lookup_model` remains available as a cross-check and is the suggested AC verification).
- **Refit propagation:** existing commissioned workflows that add or change `stages.defaults.model` after the fact automatically pick up the change because `claude-team build` re-reads the README every call and materializes on-demand. No `refit` update is strictly required for the runtime behavior. BUT: `refit` should be taught to regenerate the materialized `.claude/agents/*.md` files when the plugin's base `ensign.md` or `first-officer.md` body changes, so stale per-model variants don't fall behind. Treat as a follow-up refit task if complexity exceeds this task's scope; flag in Open Questions.

## Out of Scope

- **Per-dispatch captain override.** Captain does not get a `--model` flag at dispatch time; if they want a different model they edit the workflow README. Keeps `claude-team build` deterministic from its declared inputs.
- **Mid-cycle model switching inside a reused agent.** Not supported by either runtime; reuse is blocked on model change and the FO fresh-dispatches.
- **Auto-upgrade/downgrade.** No budget-driven or failure-rate-driven model selection. Static resolution only.
- **Agent frontmatter model defaults.** `agents/ensign.md` / `agents/first-officer.md` stay model-less. Adding a fallback there is deferred; it would silently mask missing workflow declarations, which is the opposite of what this task wants.
- **Model name validation.** `claude-team build` passes the string through verbatim. Typos produce a runtime error from Agent/spawn_agent, not a helper-side error. Matches current behavior for other frontmatter strings.

## Acceptance Criteria (revised in cycle 2)

Each AC below states what must be true after implementation AND how it is verified.

1. **Parser surfaces stage `model`.** `parse_stages_block` (or a new sibling helper) preserves per-state `model:` on the returned stage dict, and the parsed `defaults` dict is reachable from `claude-team build`.
   - *Verified by:* unit test in `tests/test_claude_team.py` that constructs a README with `stages.defaults.model: haiku` and `stages.states[0].model: opus`, invokes the parser, asserts both values are present in the returned structure.

2. **`claude-team build` emits `model` in output JSON.** The output object always contains a `"model"` key; value is the resolved string when declared or JSON `null` otherwise. Null representation is explicit (`"model": null`), not key omission.
   - *Verified by:* extend an existing `TestBuild*` case to assert `"model" in output` in both present and null branches, and assert `output["model"] is None` in the null branch.

3. **Precedence: per-state override wins.** When both `stages.defaults.model` and `stages.states[stage].model` are declared, `output.model` equals the per-state value.
   - *Verified by:* new `TestBuildModelPrecedence::test_per_state_override_wins`.

4. **Precedence: defaults apply when per-state is absent.** When only `stages.defaults.model` is declared, `output.model` equals the defaults value.
   - *Verified by:* new `TestBuildModelPrecedence::test_defaults_only`.

5. **Precedence: null when neither is declared.** When neither is declared, `output.model` is JSON `null`.
   - *Verified by:* new `TestBuildModelPrecedence::test_neither_declared_is_null`.

6. **Default inheritance is preserved.** A workflow with no `model` declaration anywhere produces a dispatch that Agent/spawn_agent receives without any materialized variant or agent-level model override — preserving today's captain-session inheritance behavior.
   - *Verified by:* the null-case test (AC 5) PLUS an assertion in the same test that `output["subagent_type"]` equals the vanilla stage agent (no model suffix).

7. **`claude-team build` materializes a per-model agent variant and emits the materialized `subagent_type` when `effective_model` is non-null.** The materialized file lives under `{workflow_dir}/.claude/agents/{base}-{model_slug}.md`, inherits the base agent body, and sets `model: {effective_model}` in YAML frontmatter. The build output's `subagent_type` names the materialized variant (e.g., `spacedock:ensign-claude-haiku-4-5`). When `effective_model` is null, `subagent_type` equals the vanilla stage agent and no file is written. Materialization is idempotent — re-running build with the same inputs does not rewrite an existing matching file.
   - *Verified by:* `TestBuildMaterialization::test_non_null_model_materializes_variant` (asserts file exists, body matches base, YAML contains `model:`, output's `subagent_type` names the variant), `TestBuildMaterialization::test_null_model_no_materialization` (asserts no file written, output `subagent_type` is vanilla), `TestBuildMaterialization::test_idempotent` (mtime unchanged on second invocation with same model).

8. **Claude runtime adapter prose reflects materialization semantics.** `claude-first-officer-runtime.md`'s `## Dispatch Adapter` documents: (a) the helper may emit a materialized `subagent_type` like `spacedock:ensign-{model_slug}`; (b) the FO forwards it verbatim — no per-call `model=` parameter; (c) the Break-Glass Manual Dispatch template (lines 91–96 today) includes a note that bypassing the helper silently ignores any declared stage model unless the caller also materializes the variant manually.
   - *Verified by:* static grep test asserting (a) the prose mentions "materialized subagent_type" or equivalent phrasing near the dispatch example, AND (b) the break-glass section contains a warning clause about stage-model bypass.

9. **Codex runtime adapter prose reflects the same materialization model.** `codex-first-officer-runtime.md`'s `## Dispatch Adapter` documents: (a) the materialized `subagent_type` is passed to Codex's logical-id resolution unchanged; (b) the prose does NOT claim `spawn_agent` accepts a `model=` parameter (this was wrong in cycle 1's draft design); (c) reuse is blocked when the next stage's effective_model differs from the reused worker's spawn-time model.
   - *Verified by:* static grep test asserting (a) the prose contains the materialized-subagent-type clause, AND (b) no occurrence of `spawn_agent(model=` in the dispatch example, AND (c) a reuse-invalidation clause mentioning "effective_model" or "spawn-time model."

10. **Shared core reuse conditions include model match.** `first-officer-shared-core.md`'s reuse conditions (in the `## Completion and Gates` section) contain a bullet asserting "next stage's effective_model matches the reused worker's spawn-time model" (inferable from the worker's subagent_type suffix or, as a backstop, from `lookup_model(name)` on the team config).
   - *Verified by:* static grep test on shared-core for the reuse-invalidation bullet.

11. **Dispatch-time visibility on stderr.** When `effective_model` is non-null, `claude-team build` writes exactly one stderr line of the form `[build] effective_model={model} (from {defaults|state}) → subagent_type={materialized}` before exiting 0. When `effective_model` is null, no such line is written.
   - *Verified by:* extend `TestBuildModelPrecedence::test_per_state_override_wins` and `test_defaults_only` to capture stderr and assert the notice appears with the correct source tag. `test_neither_declared_is_null` asserts stderr is silent of this notice.

12. **Reuse-invalidation model-identity check uses the team config as backstop.** The Claude FO's reuse path, when comparing next-stage effective_model against a reused worker's spawn-time model, uses `lookup_model(name)` from `claude-team` (reads `~/.claude/teams/{team}/config.json` `members[].model`) as the authoritative spawn-time model. The `subagent_type` suffix is advisory; the config is authoritative.
   - *Verified by:* static grep test on the Claude runtime adapter's reuse prose for a reference to `lookup_model` or `config.json` as the authoritative comparator. No runtime behavior change beyond the prose assertion — actual reuse enforcement is FO-judgement at dispatch time.

13. **Live propagation E2E (required, not deferred).** A workflow fixture declaring `stages.defaults.model: claude-haiku-4-5` dispatches one ensign under a captain started with `--model claude-opus-4-6`; the ensign's jsonl transcript at `~/.claude/projects/.../` contains at least one `message.model` field whose value equals the declared haiku identifier (not opus). Exit on first assistant turn to bound cost.
   - *Verified by:* new live test `tests/test_live_stage_model.py::test_stage_model_propagates` under the `test-live-claude` serial tier. Budget: ~$0.05, ~60s wallclock. Uses the existing `InteractiveSession` harness pattern. Fixture: minimal one-stage workflow with no gate, ensign writes a trivial stage report and exits.

## Prior Art

- **Issue source:** github.com/clkao/spacedock#95 filed 2026-04-15 after CL observed an Opus captain session dispatching Opus subagents despite the workflow declaring Haiku for those stages.
- **Parser reality check:** `parse_stages_block` in `skills/commission/bin/status` does NOT today surface `model` — the per-state allowlist is `('feedback-to', 'agent', 'fresh')` and `defaults` is consumed for `worktree`/`concurrency` only. Earlier provisional framing claimed "just consume them" — that was wrong. Parser extension is required.
- **Team-config precedent:** `claude-team` already reads `model` per team member in the generated team config (`lookup_model`, `extract_runtime_models`, `context_limit_for_model`) for the context-budget flow. This task adds the upstream input that should have been driving those values.
- **Cycle-2 Agent() probe (BLOCKING R1 resolved).** Probed upstream evidence for per-dispatch `Agent(model=)` support:
  - `grep -rn "Agent(.*model=" ~/.claude/plugins/cache` → no hits; the only `model=` occurrences in plugin code are (i) `InteractiveSession(model=...)` for captain CLI sessions, (ii) skill-creator Anthropic-SDK code using `client.messages.create(model=...)`, (iii) context-budget comparison strings. None is a per-`Agent()` parameter.
  - `head -12` on six cached plugin `agents/*.md` files (`superpowers:code-reviewer`, `noteplan:productivity-assistant`, `plugin-dev:plugin-validator`, others). Result: `superpowers-dev/5.0.6/agents/code-reviewer.md` declares `model: inherit` in YAML frontmatter. Confirmed agent-level model selection is YAML, not runtime.
  - Upstream `docs/plans/_archive/plugin-shipped-agents.md` (cached spacedock 0.9.1, line 94): "Agent file format: standard YAML frontmatter with `name`, `description`, and optionally `model` fields."
  - Live team config evidence: `~/.claude/teams/test-project-rejection-pipeline/config.json` members entries contain `"model": "claude-opus-4-6"` stamped per member at join time (observed in two separate real runs). The model is captured from the agent file (or inheritance) when the member joins the team.
  - **Conclusion:** Claude Code's `Agent()` tool does not accept `model=`. Model selection propagates via the agent file's YAML frontmatter at dispatch resolution. Cycle-2 design routes per-stage model through materialized agent file variants; AC 7 rewritten to match.
- **Cycle-2 spawn_agent probe (BLOCKING R2 resolved).** Probed Codex `spawn_agent`:
  - `skills/first-officer/references/codex-first-officer-runtime.md` lines 85 and 143: `spawn_agent(agent_type="worker", fork_context=false, message=...)`. No `model=` parameter anywhere in the adapter.
  - `references/codex-tools.md` (repo) and the cached `codex-tools.md` describe `spawn_agent` as an experimental multi-agent primitive: "the model can call spawn_agent to create sub-agents in separate threads. Sub-agents run in their own sandbox context." No documented model parameter.
  - `grep -rn "spawn_agent(" ~/.claude/plugins/cache` → only the spacedock adapter references; no external precedent for a `model=` keyword.
  - **Conclusion:** `spawn_agent` does not accept a `model=` parameter in any documented form. Codex must rely on the packaged worker's skill asset to bias toward the declared model (same materialization pattern as the Claude side — the logical id names the variant, Codex's role-preload loads the variant's skill/agent body). AC 9 rewritten to match and to explicitly prohibit the cycle-1 `spawn_agent(model=...)` wording.
- **Superpowers `model: inherit` precedent.** Confirms the exact YAML field name (`model:`) and a sample value (`inherit`) that agent-file materialization must use. This removes guesswork from implementation.
- **Single chokepoint:** both `claude-first-officer-runtime.md` and `codex-first-officer-runtime.md` already route dispatch assembly through `claude-team build`. That makes the helper the right place to resolve `effective_model` exactly once.
- **Related local tasks:** #154 / #155 touch live-dispatch cost observability; this task is their prerequisite insofar as cost controls are meaningless while declared model is inert.

## Test Plan (revised for cycle 2)

### Static (required)

1. **Parser tests** — extend `tests/test_claude_team.py` with a parser-focused class asserting the per-state `model` key survives on returned stage dicts and the defaults dict is reachable from `claude-team build` callers. Covers AC 1.
2. **Build output presence + explicit null** — augment an existing `TestBuildNormalDispatch` case (or add one) to assert both `"model"` is always a key in the emitted JSON AND `output["model"] is None` in the null branch. Covers AC 2.
3. **Precedence parametrized** — new `TestBuildModelPrecedence` with three cases: per-state-override, defaults-only, neither. Covers AC 3, AC 4, AC 5, and the positive-side of AC 6 (null → vanilla subagent_type).
4. **Materialization** — new `TestBuildMaterialization` with three cases: non-null materializes a variant file with correct YAML frontmatter and returns a suffixed subagent_type; null writes no file and returns vanilla subagent_type; re-running with matching model is idempotent (mtime preserved). Covers AC 7.
5. **Runtime adapter prose — Claude** — static grep on `claude-first-officer-runtime.md` for (a) materialized-subagent-type clause, (b) break-glass stage-model-bypass warning, (c) reference to `lookup_model`/`config.json` as reuse comparator. Covers AC 8 and AC 12.
6. **Runtime adapter prose — Codex** — static grep on `codex-first-officer-runtime.md` for (a) materialized-subagent-type clause, (b) absence of `spawn_agent(model=` pattern, (c) reuse-invalidation clause naming `effective_model`. Covers AC 9.
7. **Runtime adapter prose — shared core** — static grep on `first-officer-shared-core.md`'s reuse conditions for the model-match bullet. Covers AC 10.
8. **Stderr visibility** — extend the `TestBuildModelPrecedence` cases to capture stderr: per-state and defaults cases must emit the `[build] effective_model=...` notice with the correct source tag; null case must not emit it. Covers AC 11.

Estimated cost: negligible (all pure-Python, `tmp_path`-based, sub-second each). No new fixture directories — existing README-synthesis pattern covers everything. Adapter-prose tests 5–7 land in an existing or new `tests/test_runtime_adapter_prose.py`.

### Live (required — promoted from cycle 1)

9. **Stage-model propagation E2E** — new `tests/test_live_stage_model.py::test_stage_model_propagates` under `test-live-claude` serial tier. Fixture: one-stage workflow with no gate, `stages.defaults.model: claude-haiku-4-5` in README, one trivial entity. Captain session started via `InteractiveSession(model="claude-opus-4-6", max_budget_usd=0.20)`; FO dispatches the ensign; test waits for completion and then parses the ensign's jsonl transcript. Assertion: at least one assistant-role entry's `message.model` string contains `haiku` (and none contain `opus`). Budget: ~$0.05, ~60s wallclock. Covers AC 13.

### Live (still deferred)

10. **Reuse-invalidation E2E** — two-stage workflow where stage A declares haiku and stage B declares opus; assert the FO fresh-dispatches between stages rather than reusing. Touches FO reuse decision logic, doubles the live-test cost, and is adequately covered by static AC 10 + AC 12 prose for this task's scope. Revisit if regressions appear.

## Open Questions (remaining for captain at ideation gate)

1. **Parser helper shape.** Preferred: keep `parse_stages_block` unchanged (back-compat with `status --boot`, `--next`, etc.) and add `parse_stages_with_defaults` returning a tuple, OR change `parse_stages_block` signature to return a richer dict and migrate all callers. First option is less invasive; second is cleaner. Implementation will pick based on call-site ergonomics; captain may override.

2. **Refit regeneration of materialized variants.** When the plugin's base `ensign.md` or `first-officer.md` body is updated (e.g., via `refit`), pre-existing materialized variants in `{workflow_dir}/.claude/agents/` will have stale bodies. Should this task add a refit hook to re-materialize variants on the next `refit` run? The cycle-2 design treats it as a follow-up task; landing this cycle's work without refit integration is safe because `claude-team build` re-materializes on demand and the cycle's idempotency check only compares the YAML `model:` field, not the body. BUT — that means if a variant already exists with the right `model:` but a stale body, the stale body is used. Two options for the captain to pick: (a) file as a separate follow-up task (recommended — keeps this task small), (b) expand idempotency check to compare body hashes and regenerate on mismatch (adds ~20 lines but closes the staleness window).

### Questions resolved in cycle 2

- **Cycle 1 OQ-1 (Codex `spawn_agent` model parameter name) — RESOLVED.** `spawn_agent` does not accept `model=`. Cycle-2 design routes through agent-file materialization, same as Claude. See Prior Art probe.
- **Cycle 1 OQ-3 (null representation) — RESOLVED.** Explicit `"model": null`. See AC 2 and "Precedence and null semantics" subsection.
- **Staff-review gap 7 (null-next-stage reuse semantics) — RESOLVED.** Null is a distinct value; null-null matches, model-model matches, any cross is reuse-invalid. See "Precedence and null semantics" subsection.

## Stage Report

**1. Read full task body via section-heading Grep — DONE.** Pulled `## Problem Statement`, `## Proposed Approach`, `## Out of Scope`, `## Acceptance Criteria`, `## Prior Art`, `## Test Plan` headings then read the full body once (65-line pre-edit state is well under the #159/#96 staleness concern since the provisional body was already concise — the larger echo risk is post-edit, which is unavoidable for ideation).

**2. Read upstream issue body — DONE.** Via `gh api repos/clkao/spacedock/issues/95 --jq .body`. Confirms the proposed precedence (`stages.states[stage].model ?? stages.defaults.model ?? omit`), confirms no existing dispatch-side consumer, confirms the Opus-captain / Haiku-workflow footgun framing.

**3. Inspect plumbing — DONE.** Inspected without editing:
   - `skills/commission/bin/claude-team` (`cmd_build`, lines 73-271): single JSON-stdin chokepoint, emits `subagent_type`/`name`/`team_name`/`prompt`. SCHEMA_VERSION=1. No model handling today.
   - `skills/commission/bin/status` (`parse_stages_block`, lines 97-198): per-state optional allowlist is `('feedback-to', 'agent', 'fresh')` — model is NOT surfaced. `defaults` is used only for `worktree`/`concurrency` and discarded. This contradicts the provisional body's "just consume them" claim; parser update is required.
   - `skills/first-officer/references/first-officer-shared-core.md` `## Dispatch` (line 53+): dispatch instructions reference worker assignment fields generically; no model logic today. Reuse conditions (in `## Completion and Gates`, lines 102-106) need a new bullet for model-match.
   - `skills/first-officer/references/claude-first-officer-runtime.md` `## Dispatch Adapter` (line 38+): the forwarding clause names `subagent_type`, `name`, `team_name`, `prompt` — `model` must be added. Break-glass template needs conditional `model=`.
   - `skills/first-officer/references/codex-first-officer-runtime.md` `## Dispatch Adapter` (line 61+): `spawn_agent(agent_type="worker", fork_context=false, message=...)` — no `model` parameter shown. Open question logged.
   - `agents/first-officer.md`, `agents/ensign.md`: no `model:` frontmatter. Confirmed they stay model-less per scope decision.

**4. Resolve three open questions — DONE (partially; one flagged for captain).**
   - (a) JSON schema field emitted by `claude-team build`: top-level `model` key, value is string or JSON `null`, additive (no SCHEMA_VERSION bump).
   - (b) Codex runtime pass-through: documented design is `spawn_agent(..., model=effective_model, ...)` on fresh dispatch and reuse-invalidation on model change, BUT the exact Codex parameter name is unverified. Flagged as Open Question 1.
   - (c) Agent frontmatter fallback: stays empty. Workflow config is the sole declared source; captain-session inheritance remains the implicit fallback. No silent-default layer added.

**5. Sharpen AC — DONE.** Nine concrete, testable ACs. Covers per-dispatch-path scenarios (initial Claude dispatch via AC 2/7, initial Codex dispatch via AC 8, reuse invalidation via AC 8/9), preserved default inheritance (AC 6), and precedence order (AC 3/4/5).

**6. Test plan — DONE.** Static-only for required behavior: parser test, build-output-presence test, 3-case precedence test, 3 adapter-prose grep tests. Live tests deferred with explicit costs ($0.05/60s) and decision point at implementation gate.

**7. Scaffolding impact call-out — DONE.** Changes touch: `skills/commission/bin/status` (parser), `skills/commission/bin/claude-team` (build output), and three adapter reference files. `refit` propagation NOT required — `claude-team build` re-reads README each call so existing commissioned workflows pick up the change on next dispatch. Break-glass template gains a conditional `model=` slot.

**8. Update entity body — DONE.** Committed as `63f2eb48` with message `ideation: #157 claude-team-respect-stage-model flesh out problem, approach, AC, test plan`.

**9. Stage report written — DONE** (this section).

**10. Report completion via SendMessage — pending** (final action after this commit).

### Summary

Ideation complete. Fleshed-out problem framing, five-touchpoint approach (parser, helper, Claude adapter, Codex adapter, shared core), nine testable ACs, static-first test plan (~4 test additions, negligible cost), three open questions logged for captain. One provisional-body error corrected: `parse_stages_block` does not today surface `model` — parser extension is required. No scope creep beyond the issue's proposed precedence; no silent agent-frontmatter fallback added; per-dispatch captain override left out of scope.

### Final AC List

1. Parser surfaces stage `model` and defaults.
2. `claude-team build` emits `model` in output JSON.
3. Precedence: per-state override wins.
4. Precedence: defaults apply when per-state absent.
5. Precedence: null when neither declared.
6. Default inheritance preserved (null → omit).
7. Claude runtime adapter prose passes field through.
8. Codex runtime adapter documents spawn-time model and reuse invalidation.
9. Shared core reuse conditions include model match.

### Final Test Plan

Static, required: (a) parser test; (b) build-output presence in existing TestBuild case; (c) TestBuildModelPrecedence with 3 parametrized cases; (d) three adapter-prose grep tests (Claude, Codex, shared-core). All sub-second. Live E2E deferred to implementation gate.

### Remaining Open Questions for Captain

1. Codex `spawn_agent` model parameter name (probe in implementation stage if unknown now).
2. Parser helper shape: add sibling `parse_stages_with_defaults` (less invasive) or mutate `parse_stages_block` signature (cleaner).
3. Null representation: explicit `"model": null` vs. key-omission.

### Feedback Cycles

Cycle 1 — captain rejected ideation gate on 2026-04-15 accepting staff review NEEDS WORK verdict. Routing findings back to ideation ensign for another cycle (no stage transition; ideation has no `feedback-to` so the target is itself).

Staff reviewer (staff-review-157) findings — blocking:

1. **Un-flagged Claude runtime assumption** (staff R1): plan prescribes `Agent(model=output.model)` but `claude-first-officer-runtime.md:76-81` lists only `subagent_type`/`name`/`team_name`/`prompt`. Per-member model on the Claude path today is set via `~/.claude/teams/{team}/config.json` members (see `claude-team:377-396` `lookup_model`), NOT a runtime `Agent()` parameter. AC 7's grep test would pass while behavior silently doesn't change. Resolve by probing whether `Agent()` accepts per-dispatch `model=`, or whether the plumbing must instead write per-member model into the team config at TeamCreate time.
2. **Codex runtime assumption** (staff R2): Open Question 1 is blocking, not deferrable. `spawn_agent(agent_type="worker", fork_context=false, message=...)` has no documented `model` parameter. Probe before entering implementation or AC 8 is a speculative prose write-up.
3. **Live propagation test required, not deferred** (staff R3): a single live E2E dispatching one ensign under `stages.defaults.model: haiku` and asserting the ensign jsonl contains `message.model=haiku` (~$0.05, ~60s). Static tests prove prose exists; they do not prove dispatch works. Defer only reuse-invalidation E2E.

Non-blocking gaps to fold into the revision:

4. **Break-glass template AC**: AC 7 only greps the forwarding clause. Add an AC (or extend AC 7) asserting the manual break-glass template at `claude-first-officer-runtime.md:91-96` contains a conditional `model=` slot.
5. **Dispatch-time visibility AC**: `claude-team build` should emit the resolved `effective_model` to stderr or in a commit-message suggestion so the captain can see one-glance what model a dispatched worker is running. Silent correctness is as hard to validate as silent incorrectness.
6. **Captain-session model identity for reuse**: specify how the FO compares "next stage's effective_model" against "reused worker's spawn-time model" on the Claude path (probably `lookup_model` equivalent). Make it an AC, don't leave to implementation discovery.
7. **Null next-stage semantics**: pin explicitly — does "null next stage model" match any reused worker (inherit → no invalidation) or is null a distinct value (invalidates reuse)? Pick one and add an AC.
8. **Null JSON representation** (Open Question 3): pin at this gate, not at implementation. Adapter-prose grep targets depend on it.

Still safe to defer:

- Parser helper shape (Open Question 2) — implementation picks based on call-site ergonomics.

Captain direction: resolve blocking items 1–3 before re-presenting at the ideation gate. Open Questions 3 must also be pinned; Open Question 1 becomes blocking item 2 above; Open Question 2 stays deferred.

Cycle 2 — captain rejected ideation gate on 2026-04-15 accepting staff review UNSOUND verdict. Cycle-2 pivot correctly avoided cycle-1's mistake (unverified `Agent(model=)` / `spawn_agent(model=)`) but committed the same class of error: materialization-strategy claims rest on two unprobed runtime mechanisms.

Staff reviewer (staff-review-157-v2) findings — blocking:

1. **Agent discovery path almost certainly wrong**: plan targets `{workflow_dir}/.claude/agents/{base}-{model_slug}.md`. But `skills/commission/SKILL.md:390` documents discovery at `{project_root}/.claude/agents/`, and the `2026-04-01-plugin-shipped-runtime-assets-design.md:66` spec deliberately stopped commission from writing into that tree. In this repo `workflow_dir` != `project_root`. No evidence Claude Code probes under workflow_dir at dispatch. If discovery doesn't happen there, every static test passes and AC-13 fails → same silent-no-op shape as cycle 1 relocated.
2. **Codex mechanism speculative**: `spawn_agent` has no `model=` (cycle-2 confirmed negative). Cycle-2's positive replacement claim — that materializing a skill asset "biases the worker toward the declared model" — is unprobed. Codex spawns generic `agent_type="worker"` and the worker reads a logical id's skill body; a `model:` field on a SKILL body is not documented anywhere as changing Codex's runtime model. AC 9 is speculative prose with different wording than cycle 1.

Staff reviewer medium items:

3. `lookup_model` → materialized variant model is un-probed. AC 12 assumes team-config member model gets stamped from the materialized variant's frontmatter at member-join time rather than captain-session-inherited — never verified.
4. Refit staleness landmine (OQ-2): plan's idempotency check only compares the YAML `model:` field, so refit-updated base agent bodies leave materialized variants stale. Defer-to-follow-up is the wrong call.

Staff reviewer non-blocking clean-up:

5. AC-13 fixture must place the workflow at a subdirectory (not project root) so discovery-path behavior is actually exercised.
6. No Codex live test — add one or explicitly accept Codex coverage as deferred with a named follow-up task.
7. Trim redundant AC 5 + AC 6 + AC 2 null-branch into a single null-case AC.
8. Concurrency: materialize as write-if-missing with atomic rename, or explicitly accept the same-content race as benign.

Staff reviewer strengths (keep as-is):

- Cycle-2's negative probes held under spot-check (zero `Agent(...model=...)`, zero `spawn_agent(...model=...)`, superpowers `code-reviewer.md` does carry `model: inherit`).
- Null semantics + `"model": null` JSON pinning unambiguous and well-reasoned.
- AC 13 (live propagation) is the right shape of test — just needs fixture pinning.

Captain direction (cycle-3 design pivot, not yet dispatched): investigate whether `claude-team build` can emit the effective model AND write it into `~/.claude/teams/{team}/config.json` members[] before returning, so that when the FO's subsequent `Agent()` call joins the member, `lookup_model` returns the declared model. This uses documented existing plumbing (`claude-team:377-396` proves team config members carry model per member) instead of the speculative workflow-dir agent-file materialization mechanism. Codex needs a separately verified mechanism since it has no team config — most likely via `codex exec --model {effective_model}` CLI flag (cheap probe). Cycle 3 dispatch pending captain resolution of the team-config-write approach.

## Stage Report — Ideation Cycle 2

### Probe evidence for blocking items

**Blocking R1 — Claude `Agent(model=)` probe:**

- `grep -rn "Agent(.*model=" ~/.claude/plugins/cache` → no hits. The only `model=` hits in plugin code are `InteractiveSession(model=...)` (captain CLI), Anthropic SDK `client.messages.create(model=...)`, and context-budget comparison strings. No Agent-tool call site with a `model=` argument.
- Inspected six cached plugin `agents/*.md` frontmatter blocks (`superpowers:code-reviewer`, `noteplan:productivity-assistant`, `plugin-dev:plugin-validator`, `plugin-dev:skill-reviewer`, `plugin-dev:agent-creator`, `hookify:conversation-analyzer`). Found `model: inherit` in `superpowers-marketplace/superpowers-dev/5.0.6/agents/code-reviewer.md`. Documented convention confirmed by `spacedock 0.9.1/docs/plans/_archive/plugin-shipped-agents.md:94`: "Agent file format: standard YAML frontmatter with `name`, `description`, and optionally `model` fields."
- Live evidence: `~/.claude/teams/test-project-rejection-pipeline/config.json` and `~/.claude/teams/sparkling-rolling-adleman/config.json` show member entries with `"model": "claude-opus-4-6"` stamped per member. The model gets captured at join time from the agent-file's declared model (falling back to session inheritance if absent).
- **Finding:** Claude Code `Agent()` does NOT accept `model=`. Architectural shift forced: per-stage model must propagate via agent-file YAML frontmatter, not via a runtime Agent-call argument.

**Blocking R2 — Codex `spawn_agent(model=)` probe:**

- `skills/first-officer/references/codex-first-officer-runtime.md` lines 85 and 143 both show `spawn_agent(agent_type="worker", fork_context=false, message=...)` with no `model=` parameter.
- Repo `references/codex-tools.md:150-156` describes `spawn_agent` as experimental, with sub-agents running in their own sandbox contexts and coordinating via collab events. No model parameter mentioned.
- `grep -rn "spawn_agent(" ~/.claude/plugins/cache` returns only spacedock's adapter references; no external precedent for a `model=` parameter.
- **Finding:** `spawn_agent` has no documented `model=` parameter. Codex must use the same agent-file-materialization strategy as Claude — a per-model logical id (`spacedock:ensign-haiku`) whose packaged skill/agent asset declares the model in YAML.

**Blocking R3 — Live propagation test:** promoted to REQUIRED. Written as AC 13 and Test Plan item 9. Budget ~$0.05, ~60s, fixture one-stage workflow, assertion on `message.model` in ensign jsonl.

### Design decisions made this cycle

1. **Architectural shift:** per-stage model propagates via materialized agent-file variants, not through a per-dispatch tool-call parameter. `claude-team build` writes `{workflow_dir}/.claude/agents/{base}-{model_slug}.md` and emits the suffixed `subagent_type`. Cycle-1 AC 7 (Agent forwarding) and AC 8 (Codex `spawn_agent(model=)`) were both wrong; rewritten as AC 7 (materialization), AC 8 (Claude prose for materialization), AC 9 (Codex prose for materialization with explicit prohibition on the cycle-1 wording).
2. **Null reuse semantics pinned:** null is a distinct value. Null-null matches, X-X matches, every other pairing invalidates reuse. Added to "Precedence and null semantics" subsection and implied by AC 10.
3. **Null JSON representation pinned:** explicit `"model": null`. AC 2 updated.
4. **Visibility AC added:** AC 11 requires `[build] effective_model=... (from defaults|state) → subagent_type=...` stderr notice on non-null resolution. Covers staff gap 5.
5. **Break-glass AC folded in:** AC 8 (b) asserts the break-glass section contains a warning about stage-model bypass. Covers staff gap 4.
6. **Reuse model-identity AC added:** AC 12 requires the Claude runtime prose to point at `lookup_model`/`config.json` as the authoritative comparator. Covers staff gap 6.

### Open questions that remain for captain

1. Parser helper shape — sibling vs. signature change (low-stakes, implementation call).
2. Refit regeneration of materialized variants — separate follow-up task, or add body-hash idempotency check to this task? Recommend the former to keep scope tight.

### Final AC list (cycle 2)

1. Parser surfaces stage `model` and defaults.
2. `claude-team build` emits `"model"` in output JSON (explicit null when unset).
3. Precedence: per-state override wins.
4. Precedence: defaults apply when per-state absent.
5. Precedence: null when neither declared.
6. Default inheritance preserved (null → vanilla subagent_type).
7. Build materializes per-model agent variant and emits suffixed `subagent_type` when non-null; no file and vanilla subagent_type when null; idempotent.
8. Claude runtime adapter prose reflects materialization semantics and break-glass bypass warning.
9. Codex runtime adapter prose reflects materialization semantics and explicitly does NOT claim `spawn_agent(model=)`.
10. Shared core reuse conditions include model match.
11. Stderr visibility on non-null resolution.
12. Reuse comparator points at `lookup_model`/`config.json`.
13. Live propagation E2E (required): ensign jsonl `message.model` matches declared haiku, not captain's opus.

### Final test plan (cycle 2)

Static required: parser test, build output + null, precedence (3 cases), materialization (3 cases), three adapter-prose grep tests, stderr-visibility assertions. Live required: one propagation E2E (~$0.05, ~60s). Live deferred: reuse-invalidation E2E.

### Summary

Resolved both blocking runtime assumptions via direct evidence probes. The cycle-1 design's Agent(model=) and spawn_agent(model=) forwarding was both wrong — corrected to agent-file materialization under `{workflow_dir}/.claude/agents/`. Added four new ACs covering staff-review gaps 4–7. Promoted propagation E2E to required. Two low-stakes open questions remain (parser helper shape, refit regeneration); neither blocks the ideation gate re-presentation.
