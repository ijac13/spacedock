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

Resolve in dispatch with this precedence at the `claude-team build` helper level:

```
effective_model = stages.states[stage].model
              ?? stages.defaults.model
              ?? null  (omit — let agent frontmatter / session default apply)
```

### Touch points

1. **`skills/commission/bin/status` — `parse_stages_block`.** Today this helper collects only a fixed allowlist of optional per-state keys (`feedback-to`, `agent`, `fresh`) into the returned stage dict, and consumes `defaults:` only to compute `default_worktree` / `default_concurrency` before discarding the rest. To surface `model`, extend `parse_stages_block` to:
   - add `model` to the per-state optional-field allowlist, so `stages.states[stage].model` is preserved on each returned stage dict;
   - expose the parsed `defaults` dict to callers. Simplest shape: return `(stages_list, defaults_dict)` from a new sibling helper (e.g., `parse_stages_with_defaults`) and keep `parse_stages_block` as-is for back-compat with existing callers (`status --boot`, `--next`, etc.). `claude-team build` switches to the new helper.

2. **`skills/commission/bin/claude-team` — `cmd_build`.** Call the defaults-aware helper, compute `effective_model` using the precedence above, and emit `model` as a top-level key in the output JSON. Value is the resolved string or `null`. This is additive and does not require a schema bump (SCHEMA_VERSION stays 1).

3. **`skills/first-officer/references/claude-first-officer-runtime.md` — `## Dispatch Adapter`.** Update the verbatim-forwarding clause so the FO includes `model=output.model` in the `Agent()` call when non-null, and omits the parameter when null. Update the example `Agent(...)` block to show the conditional `model` line. Update the Break-Glass Manual Dispatch template to include `model="{effective_model}"` when non-null.

4. **`skills/first-officer/references/codex-first-officer-runtime.md` — `## Dispatch Adapter`.** Document how the resolved model is threaded through `spawn_agent` on fresh dispatch. Because `send_input` reuse keeps the worker's spawn-time model, document the reuse-invalidation rule: if the next stage's `effective_model` differs from the reused worker's spawn-time model, reuse is disallowed — shut down and fresh-dispatch. Because the current `spawn_agent` example in this file uses `agent_type="worker"` without a model parameter, the exact parameter name to use for model pass-through is an open question flagged below.

5. **Shared core — `skills/first-officer/references/first-officer-shared-core.md`.** Add one bullet to `## Dispatch`: reuse conditions must include "next stage's effective_model matches the reused worker's spawn-time model." This keeps the reuse-invalidation rule runtime-agnostic.

6. **`agents/first-officer.md` / `agents/ensign.md`.** No changes required; they stay model-less and inherit. Workflow config remains the source of truth when set, captain/session default applies otherwise.

### Precedence decision

The precedence list in the issue is final: per-state override beats defaults beats null. No fourth tier (agent frontmatter, session default) is introduced by this task — those remain implicit inheritance when the helper emits `null`.

### Reuse and Refit

- **Reuse:** a Claude team member's model is set at `Agent()` spawn time and cannot be changed through `SendMessage`. A Codex worker's model is set at `spawn_agent` and cannot be changed through `send_input`. Therefore the reuse path in the FO must treat "effective_model changed between stages" as a reuse-blocker — shut down and fresh-dispatch. This is the minimum guardrail; anything smarter (e.g., migrating state) is out of scope.
- **Refit propagation:** existing commissioned workflows that add or change `stages.defaults.model` after the fact take effect on the next dispatch because `claude-team build` re-reads the README each call. No `refit` update is required unless the refit skill itself duplicates dispatch logic (it does not).

## Out of Scope

- **Per-dispatch captain override.** Captain does not get a `--model` flag at dispatch time; if they want a different model they edit the workflow README. Keeps `claude-team build` deterministic from its declared inputs.
- **Mid-cycle model switching inside a reused agent.** Not supported by either runtime; reuse is blocked on model change and the FO fresh-dispatches.
- **Auto-upgrade/downgrade.** No budget-driven or failure-rate-driven model selection. Static resolution only.
- **Agent frontmatter model defaults.** `agents/ensign.md` / `agents/first-officer.md` stay model-less. Adding a fallback there is deferred; it would silently mask missing workflow declarations, which is the opposite of what this task wants.
- **Model name validation.** `claude-team build` passes the string through verbatim. Typos produce a runtime error from Agent/spawn_agent, not a helper-side error. Matches current behavior for other frontmatter strings.

## Acceptance Criteria

Each AC below states what must be true after implementation AND how it is verified.

1. **Parser surfaces stage `model`.** `parse_stages_block` (or a new sibling helper) preserves per-state `model:` on the returned stage dict, and the parsed `defaults` dict is reachable from `claude-team build`.
   - *Verified by:* unit test in `tests/test_claude_team.py` that constructs a README with `stages.defaults.model: haiku` and `stages.states[0].model: opus`, invokes the parser, asserts both values are present in the returned structure.

2. **`claude-team build` emits `model` in output JSON.** The output object always contains a `model` key; value is the resolved string or JSON `null`.
   - *Verified by:* extend an existing `TestBuild*` case to assert `"model" in output` in both present and null branches.

3. **Precedence: per-state override wins.** When both `stages.defaults.model` and `stages.states[stage].model` are declared, `output.model` equals the per-state value.
   - *Verified by:* new `TestBuildModelPrecedence::test_per_state_override_wins`.

4. **Precedence: defaults apply when per-state is absent.** When only `stages.defaults.model` is declared, `output.model` equals the defaults value.
   - *Verified by:* new `TestBuildModelPrecedence::test_defaults_only`.

5. **Precedence: null when neither is declared.** When neither is declared, `output.model` is JSON `null`.
   - *Verified by:* new `TestBuildModelPrecedence::test_neither_declared_is_null`.

6. **Default inheritance is preserved.** A workflow with no `model` declaration anywhere produces a dispatch that Agent/spawn_agent receives without a `model=` parameter — preserving today's captain-session inheritance behavior.
   - *Verified by:* the null-case test above (AC 5), plus a prose assertion in `tests/test_runtime_adapters.py` (or similar) that the Claude runtime adapter explicitly instructs "omit `model=` when `output.model` is null."

7. **Claude runtime adapter prose passes the field through.** `claude-first-officer-runtime.md`'s Dispatch Adapter section names `model` in the verbatim-forwarding list and shows a conditional `model=output.model` in the `Agent()` example. The Break-Glass template includes `model=` guidance.
   - *Verified by:* static test that greps the adapter file for `output.model` in the forwarding instruction.

8. **Codex runtime adapter prose documents spawn-time model and reuse invalidation.** `codex-first-officer-runtime.md`'s Dispatch Adapter section documents that the resolved model is passed through `spawn_agent` on fresh dispatch and that reuse is blocked when the next stage's effective_model differs from the reused worker's spawn-time model.
   - *Verified by:* static test that greps for both the spawn-time pass-through and the reuse-invalidation clause.

9. **Shared core reuse conditions include model match.** `first-officer-shared-core.md`'s Dispatch section reuse conditions list contains a bullet asserting "next stage's effective_model matches the reused worker's spawn-time model."
   - *Verified by:* static test greps shared-core for the reuse-invalidation bullet.

## Prior Art

- **Issue source:** github.com/clkao/spacedock#95 filed 2026-04-15 after CL observed an Opus captain session dispatching Opus subagents despite the workflow declaring Haiku for those stages.
- **Parser reality check:** `parse_stages_block` in `skills/commission/bin/status` does NOT today surface `model` — the per-state allowlist is `('feedback-to', 'agent', 'fresh')` and `defaults` is consumed for `worktree`/`concurrency` only. Earlier provisional framing claimed "just consume them" — that was wrong. Parser extension is required.
- **Team-config precedent:** `claude-team` already reads `model` per team member in the generated team config (`lookup_model`, `extract_runtime_models`, `context_limit_for_model`) for the context-budget flow. This task adds the upstream input that should have been driving those values.
- **Single chokepoint:** both `claude-first-officer-runtime.md` and `codex-first-officer-runtime.md` already route dispatch assembly through `claude-team build`. That makes the helper the right place to resolve `effective_model` exactly once.
- **Related local tasks:** #154 / #155 touch live-dispatch cost observability; this task is their prerequisite insofar as cost controls are meaningless while declared model is inert.

## Test Plan

### Static (required)

1. **Parser tests** — extend `tests/test_claude_team.py` with a parser-focused class asserting the per-state `model` key survives and the defaults dict is reachable. Covers AC 1.
2. **Build output presence** — augment an existing `TestBuildNormalDispatch` case to assert `"model"` is a key in the emitted JSON. Covers AC 2.
3. **Precedence parametrized** — new `TestBuildModelPrecedence` with three cases (per-state, defaults-only, neither). Covers AC 3-5. Null case simultaneously covers AC 6's positive-side verification.
4. **Runtime adapter prose** — one static test per adapter file (Claude, Codex, shared-core) grepping for the required phrasing. Covers AC 7, 8, 9, and AC 6's prose side. Format mirrors existing adapter-prose tests if any; otherwise adds a minimal `tests/test_runtime_adapter_prose.py` with three targeted assertions.

Estimated cost: negligible (pure-Python fixture tests, sub-second each). No new fixture directories required — the existing `tmp_path`-based workflow-README synthesis pattern used by `TestBuild*` is sufficient.

### Live (deferred / optional)

- **E2E model propagation** — a workflow fixture with `stages.defaults.model: claude-haiku-...` declared, captain invoked with `--model claude-opus-...`, dispatch one ensign, parse the ensign's jsonl, assert the subagent's model string matches the declared haiku. ~$0.05, ~60s, new entry under `test-live-claude` serial tier.
- **Reuse-invalidation E2E** — two-stage workflow where stage A declares haiku and stage B declares opus; assert the FO fresh-dispatches between stages rather than reusing. Expensive and touches FO decision logic. Defer unless the static prose tests prove insufficient to catch regressions.

Both live tests are deferred to implementation stage; they are not required to land the core behavior. Decision deferred to the implementation gate.

## Open Questions (for captain at ideation gate)

1. **Codex `spawn_agent` model parameter name.** The current codex adapter example uses `spawn_agent(agent_type="worker", fork_context=false, message=...)` with no `model` parameter shown. Is the parameter `model=`, `agent_model=`, or does Codex require a different pass-through mechanism? If unknown, implementation stage should probe Codex's actual API before wiring AC 8.
2. **Parser helper shape.** Preferred: keep `parse_stages_block` unchanged (back-compat) and add `parse_stages_with_defaults` returning a tuple, OR change `parse_stages_block` to return a richer dict and migrate callers. First option is less invasive; second is cleaner. Captain call.
3. **Null representation in JSON.** Emit `"model": null` explicitly, or omit the key entirely when unset? Explicit null is clearer for the adapter-prose "omit the parameter when null" instruction. Recommend explicit null; captain may prefer omission to match other optional fields.
