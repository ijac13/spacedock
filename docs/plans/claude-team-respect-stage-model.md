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

Precedence:

```
effective_model = stages.states[stage].model
              ?? stages.defaults.model
              ?? null  (omit the Agent `model=` parameter entirely; Agent's default-inheritance applies)
```

Null semantics: when `effective_model` is null, the helper emits `"model": null` in the JSON and the FO omits the `model=` argument on the `Agent()` call entirely (not passing `null`). Reuse matches null against null — a stage that doesn't declare a model is reuse-compatible with any reused worker that also joined without a model override.

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
6. **AC-enum-validation**: helper errors loudly (non-zero exit, stderr message naming the offending field) on any `model:` value outside the Agent-schema enum. *Verified by* a static test with `model: claude-haiku-4-5-20251001` (wrong shape — should reject and tell the user "use one of: sonnet, opus, haiku").
7. **AC-adapter-prose**: the Claude runtime adapter's `## Dispatch Adapter` contains prose instructing the FO to forward `output.model` as the `Agent()` `model=` parameter when present. *Verified by* a grep test asserting the prose anchor.
8. **AC-break-glass**: break-glass template includes the conditional `model=` slot. *Verified by* the same grep test extended to the break-glass block.
9. **AC-reuse-match**: shared-core reuse conditions include a model-match bullet. *Verified by* a grep test on `first-officer-shared-core.md`.
10. **AC-visibility**: helper prints a one-line stderr notice when `effective_model` is non-null. *Verified by* a static test running `claude-team build` with a haiku-declared fixture and asserting stderr contains `effective_model=haiku`.
11. **AC-live-propagation**: one live E2E that dispatches one ensign under `stages.defaults.model: haiku`, parses the ensign jsonl, and asserts `message.model` starts with `claude-haiku-`. Budget ~$0.05 / ~60s, runs once per PR on the `claude-live` job. *Required, not deferred* — static tests prove prose; only a live dispatch proves the model parameter propagates end-to-end.

## Test Plan

**Static (all sub-second):**
- 1 parser test (AC-parser)
- 1 helper build-output test extension (AC-build-emits)
- 1 parametrized precedence test with 3 cases (AC-precedence-stage-wins, AC-precedence-defaults, AC-null)
- 1 helper enum-validation test (AC-enum-validation)
- 3 grep tests on adapter/break-glass/shared-core prose (AC-adapter-prose, AC-break-glass, AC-reuse-match)
- 1 helper stderr test (AC-visibility)

**Live (1 test, ~$0.05, ~60s):**
- 1 live propagation E2E dispatching one ensign with haiku-declared fixture; asserts ensign jsonl `message.model` is a `claude-haiku-*` string (AC-live-propagation).

The fixture for AC-live-propagation places the workflow at a subdirectory of project_root (so paths-under-project-root vs workflow-dir questions don't confound the test — although with `Agent(model=)` there's no `.claude/agents/` dependency to confound anyway).

## Prior Art

- `~/.claude/plugins/marketplace/.../superpowers-dev/*/agents/code-reviewer.md:5` carries `model: inherit` in YAML frontmatter; Agent's schema notes `model` overrides "the agent definition's model frontmatter". So the precedence is established: `Agent(model=)` > agent YAML `model:` > parent inheritance.
- `claude-team:377-396` `lookup_model` reads `~/.claude/teams/{team}/config.json members[].model`. `model=` at spawn stamps into that record (verified live in spacedock-plans-2 on 2026-04-15: `Agent(model="haiku", subagent_type="general-purpose", ...)` produced `"model": "haiku"` in the member entry, despite general-purpose having no YAML `model:` and the captain running on opus).
- `status --boot` already emits stage props; adding `model` to the per-state allowlist is analogous to `feedback-to` / `fresh` (existing optional keys).

## Probe evidence (2026-04-15)

Three cycles of ideation pursued wrong directions before the simple answer surfaced. This section preserves the probe evidence that nailed the correct mechanism. See `## Failed approaches` below for what went wrong and why.

- **Tool schema probe:** `ToolSearch(query="select:Agent", max_results=1)` returned the Agent tool definition with `"model": {"enum": ["sonnet", "opus", "haiku"], "description": "Optional model override for this agent. Takes precedence over the agent definition's model frontmatter. If omitted, uses the agent definition's model, or inherits from the parent."}`. This is the single most important finding — the parameter exists and is documented.
- **Live spawn probe:** `Agent(subagent_type="general-purpose", name="probe-157-model-param", team_name="spacedock-plans-2", model="haiku", prompt="SendMessage then exit")` spawned successfully. Post-spawn team config inspection:
  ```json
  {"name": "probe-157-model-param", "model": "haiku"}
  ```
  Captain session is on opus; `general-purpose` has no YAML `model:`. The haiku stamp came from the `model="haiku"` Agent parameter. End-to-end verified.

## Failed approaches (preserved for audit)

Three design cycles pursued wrong mechanisms before the tool schema was read directly. The root cause was a repeated probe-methodology failure: "no existing caller uses X" was taken as "X doesn't exist." All three rejections are summarized below with one-sentence why-they-are-bad notes.

### Cycle 1 — `Agent(model=...)` "doesn't exist" (REJECTED, but actually correct)

Ensign claimed `Agent` had no `model` parameter based on `grep 'Agent(...model=...)' ~/.claude/plugins/` finding zero callers. **Why this is bad:** grep for current callers tests usage, not existence. The tool schema (`ToolSearch`) is the authoritative source. Cycle-3's late probe reveals cycle-1 was wrong to abandon this direction — this is in fact the correct design.

### Cycle 2 — materialize per-model agent files at `{workflow_dir}/.claude/agents/` (REJECTED, never viable)

Ensign invented a strategy of writing a per-model agent variant file (e.g., `{workflow_dir}/.claude/agents/ensign-haiku.md` with `model: haiku` in YAML) and emitting a suffixed `subagent_type`. **Why this is bad:** `{workflow_dir}/.claude/agents/` is not a documented agent-discovery path; `skills/commission/SKILL.md:390` documents only `{project_root}/.claude/agents/`, and the 2026-04-01 plugin-shipped-runtime-assets spec deliberately moved *away* from writing under those trees. Even with the correct path it's unnecessarily complex: the `Agent(model=)` parameter makes file materialization pointless.

### Cycle 3 — pre-write `~/.claude/teams/{team}/config.json` members[].model before `Agent()` (REJECTED, live-disproven)

Captain's hypothesis: helper pre-populates a member entry with the declared model before the FO's `Agent()` call, so `lookup_model` returns the declared model. **Why this is bad:** live probe (FO-run on 2026-04-15 in spacedock-plans-2) showed Claude Code auto-renames colliding members on join — `Agent(name="probe-157-member", ...)` became `probe-157-member-2` with a fresh record using captain-session fallback model; the pre-written entry was left as an orphan. Pre-write is ignored, not honored.

### Shared methodology lesson

When checking "does tool X support Y?": read X's schema directly (via `ToolSearch` or equivalent runtime introspection) **before** greping for existing callers. Usage presence/absence is not existence evidence. This rule should land in `first-officer-shared-core.md`'s probe discipline — a likely follow-up task.

## Open Questions (non-blocking — implementation resolves)

1. **Parser helper shape** — add sibling `parse_stages_with_defaults` (less invasive, easy back-compat) vs. mutate `parse_stages_block` signature (cleaner but touches more callers). Either works; implementation picks based on call-site ergonomics.
2. **Refit propagation** — `claude-team build` re-reads the workflow README on every call, so existing commissioned workflows pick up the change automatically on next dispatch. No refit required.

## Deferred to follow-up tasks (filed separately when this lands)

- **Codex per-stage model selection.** Codex has no team config and its model selection is orthogonal (likely `codex exec --model` CLI flag on spawn). Needs its own probe + small design. Not blocked on this task; can run in parallel.
- **Shared-core probe-methodology rule.** Capture the "read schema before greping callers" lesson in `first-officer-shared-core.md`'s ideation / probe guidance so future cycles don't repeat the failure.
