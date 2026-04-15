---
id: 157
title: "claude-team build: resolve and emit per-stage model, runtime adapters pass it through on dispatch"
status: backlog
source: "github.com/clkao/spacedock#95 — stages.defaults.model accepted in workflow READMEs but ignored at dispatch; subagents unconditionally inherit captain-session model"
started:
completed:
verdict:
score: 0.80
worktree:
issue: "#95"
pr:
---

Workflow READMEs accept `stages.defaults.model` and presumably per-state overrides (the `parse_stages_block` helper in `skills/commission/bin/status` already collects arbitrary keys under `defaults:` and under each `states:` entry, returning them in the dict it emits). Nothing in the plugin reads them. Subagents inherit the captain session's model unconditionally, so a workflow author declaring `model: haiku` for routine stages gets Opus subagents anyway when the captain is running Opus.

```
$ grep -rn '\bmodel\b' skills/commission/ skills/first-officer/
(no dispatch-side matches — only runtime parsing helpers)
```

## Problem Statement

A captain on Opus running a workflow whose README declares `model: haiku` on dispatch/execute stages gets every subagent on Opus — >10× overspend on stages explicitly designed to run cheap. The declared stage model is inert. The gap is silent; only a jsonl transcript audit surfaces it.

The workaround today — captain switches their own session model to match the target stage — forfeits Opus for captain-side judgment work (gate reviews, clarification, plan review), which is exactly where operator-visible quality matters most.

## Proposed Approach

Resolve in dispatch with this precedence at the `claude-team build` helper level:

```
effective_model = stages.states[stage].model
              ?? stages.defaults.model
              ?? null  (omit — let agent frontmatter / session default apply)
```

Touch points, minimum viable landing:

1. **`skills/commission/bin/claude-team build`** — read `stages.defaults.model` and `stages.states[stage].model` from the parsed README; resolve with the precedence above; emit a `model` field in the output JSON (null when no override declared). The existing `parse_stages_block` already exposes the raw values; just consume them.

2. **`skills/first-officer/references/claude-first-officer-runtime.md`** — document that the FO reads `output.model` and includes `model=output.model` in the `Agent()` call when non-null; otherwise omits the parameter (inherit applies). Update the verbatim-forwarding clause to include the `model` field alongside `subagent_type`, `name`, `team_name`, `prompt`.

3. **`skills/first-officer/references/codex-first-officer-runtime.md`** — same pass-through note for fresh dispatches (`spawn_agent` with explicit model) and for `send_input` reuse cycles (model is fixed at spawn time; document that the FO shuts down and fresh-dispatches if a reused worker's model no longer matches the target stage's declared model). Codex's `spawn_agent` shape accepts `model`; wire it.

4. **Break-glass manual dispatch template** (in the Claude runtime adapter) — include `model="{effective_model}"` parameter when non-null.

5. **`agents/first-officer.md` / `agents/ensign.md`** — no changes required; they stay model-less and inherit. Workflow config remains the source of truth when set.

## Out of Scope

- No per-dispatch runtime model override (captain doesn't get to override the workflow's declared stage model at dispatch time — if they want a different model they edit the README).
- No mid-cycle model switching inside a reused agent (Codex fresh-dispatches on model mismatch; Claude's team members are spawn-time-fixed).
- No auto-upgrade/downgrade logic based on budget or failure rate — stays a static resolution.

## Acceptance Criteria (provisional — finalize in ideation)

- `claude-team build` output JSON includes a `model` field; non-null when the stage declares one via per-state override or defaults.model; null otherwise.
- Precedence correctness: per-state override wins over defaults.model; both win over no-declaration (null).
- Runtime adapter prose instructs the FO to pass `model=output.model` to `Agent()` when non-null.
- Codex runtime adapter prose documents the spawn-time `model` parameter and the re-dispatch-on-mismatch rule for reused workers.
- Static test asserts the `claude-team build` resolution for three fixtures: (a) per-state override present; (b) defaults.model only; (c) neither.
- Optional live E2E: a workflow with `model: haiku` declared, captain runs on opus, dispatches observed via jsonl — model transcribed for subagents matches the declared haiku. Expensive; maybe folded into #154/#155's eventual fix pass.

## Prior Art

- Issue source: github.com/clkao/spacedock#95 filed 2026-04-15 after CL observed an Opus session dispatching Opus subagents despite workflow declaring Haiku.
- `parse_stages_block` in `skills/commission/bin/status` already collects arbitrary keys under `defaults` and each state — no parser change needed.
- Existing helpers `lookup_model()`, `extract_runtime_models()`, `context_limit_for_model()` in `claude-team` show the team config surfaces a model per member today; workflow-declared stage model is the missing upstream input.

## Test Plan (seed)

- **Static** — extend `tests/test_claude_team.py` with three parametrized cases around the precedence (per-state override, defaults-only, neither).
- **Static — runtime adapter prose** — assert the claude runtime adapter mentions the `model` field in the dispatch-assembly sequence.
- **Live (optional)** — a workflow fixture with explicit `model: haiku` declared, captain on opus (or explicit captain model via `--model opus`), dispatch an ensign, parse the subagent jsonl, assert the subagent's model string matches haiku. ~$0.05, ~60s. Add to `test-live-claude` serial tier.
