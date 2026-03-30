---
id: 075
title: Restore ensign reuse across stages (fresh field support)
status: ideation
source: user report during 0.3.0 → 0.8.2 upgrade
started: 2026-03-29T00:00:00Z
completed:
verdict:
score: 0.75
worktree:
---

The `fresh` field in stage definitions is effectively dead in the 0.8.2 FO template. The template always dispatches a new agent per stage (`name="{agent}-{slug}-{stage}"`). The old FO (0.3.0) had explicit reuse logic: advance ensigns via SendMessage by default, `fresh: true` opted into a new agent.

## User report

> Old FO (0.3.0) had explicit reuse logic:
> - Reuse if: next stage has the same worktree mode AND next stage does NOT have `fresh: true`
> - Fresh dispatch if: worktree mode changes, or `fresh: true` is set on the stage
>
> New FO (0.8.2) always dispatches fresh — every stage gets a new agent. There's no `fresh` field support. The only cases where an agent stays alive are feedback-to loops and gate redo.

## Impact

- `fresh: true` in stage definitions is a no-op — misleading for users who set it
- Ensigns lose ambient context between stages (they re-read entity files from scratch)
- Extra file reads and lost context vs. the old reuse behavior
- For many workflows this is fine (entity file carries context), but for workflows with rich ambient state between stages it's a regression

## What the current template does

- Dispatch section step 7: always `Agent(name="{agent}-{slug}-{stage}", ...)` — new agent per stage
- Completion: "If no gate, shut down the agent" (with 068's keep-alive exception for feedback-to)
- No code path checks the `fresh` property on the next stage

## What needs to change

The FO template's completion/dispatch flow should check the next stage's `fresh` property:
- If `fresh: true` on next stage: shut down current agent, dispatch new one (current behavior)
- If `fresh: false` or unset, AND same worktree mode: advance the existing agent to the next stage via SendMessage instead of dispatching fresh
- If worktree mode changes between stages: always dispatch fresh (can't reuse across worktree boundaries)

This interacts with 068 (keep-alive for feedback-to) — the keep-alive logic is a special case of the general reuse pattern.

## Open question: reuse without teams (bare mode)

With teams, reuse is straightforward — the ensign stays alive and the FO sends new instructions via SendMessage. Without teams (bare mode from 074), each `Agent()` call creates a new subprocess that's gone when it returns. The question is whether `Agent()` with the same `name` parameter can reconnect to an existing agent, or if each invocation is always fresh regardless of name.

If bare-mode reuse is impossible, `fresh` would only be meaningful in team mode. Need to investigate the Agent() tool's behavior with named agents before designing the reuse flow.

## Problem Statement

The `fresh` field in README frontmatter stage definitions (e.g., `fresh: true` on a validation stage) is dead code in the 0.8.3 FO template. The template's dispatch step 7 says "Always dispatch fresh" and creates a new `Agent(name="{agent}-{slug}-{stage}")` for every stage transition. The old FO (0.3.0, task 028) had reuse logic: after completing a stage, the FO sent the next stage's instructions to the existing ensign via SendMessage instead of spawning a new one. The `fresh: true` property opted out of this reuse, forcing a new agent (useful for validation stages that should assess without prior context bias).

The regression means:
1. **`fresh: true` is misleading** — users can set it in README frontmatter (and the commission template suggests it for validation stages), but the FO ignores it.
2. **Ensigns lose ambient context** — each stage starts cold, re-reading entity files from scratch. For workflows where consecutive stages build on each other (e.g., ideation -> implementation), the ensign that did ideation already understands the entity deeply, and restarting discards that understanding.
3. **Extra overhead** — file re-reads, context re-parsing, and agent startup cost per stage.

The entity file carries most persistent state, so this is tolerable for many workflows, but for workflows with rich ambient context between stages it's a real regression from 0.3.0 behavior.

## Investigation: Bare-mode (no teams) Reuse

**Finding: bare-mode reuse is not possible.** In bare mode (074), `Agent()` calls are blocking — the FO dispatches a subagent, blocks until it completes and returns, and then the agent process is gone. There is no live agent to send a follow-up message to. Each `Agent()` invocation creates an independent subprocess.

Evidence from the bare-mode investigation (task 074 / fo-startup-improvements):
- "FO cannot keep agents alive across dispatches (subagents are blocking)" — from the bare-mode feedback flow analysis
- "Dispatch is naturally sequential anyway when using Agent() without teams — the FO blocks until the subagent completes"
- The `name` parameter on `Agent()` is for identification/routing, not reconnection — a completed subagent cannot be addressed again

**Conclusion:** Reuse via SendMessage only works in team mode. In bare mode, `fresh` is inherently always true (every dispatch is fresh). The FO template should implement reuse logic with a team-mode guard — in bare mode, always dispatch fresh (which is the only option), making `fresh` a no-op. This matches the physical constraint rather than being a design choice.

## Proposed Approach

### Change 1: Modify the "If no gate" completion path (line 94)

Current behavior:
```
If no gate: If terminal, proceed to merge. Otherwise, check whether the next
stage has feedback-to pointing at this stage. If yes, keep the agent alive —
do not shut it down. Run status --next and dispatch the next stage.
```

The `feedback-to` keep-alive (task 068) is already a special case of reuse — the FO keeps the completed agent alive so the feedback stage's reviewer can message it later. The general reuse pattern subsumes this: the FO keeps the completed agent alive whenever the next stage allows reuse.

Proposed "If no gate" path:
```
If no gate: If terminal, proceed to merge. Otherwise, determine whether to
reuse or dispatch fresh for the next stage:

**Reuse conditions (all must be true):**
1. Not in bare mode (teams available — subagents can't be kept alive otherwise)
2. Next stage does NOT have `fresh: true`
3. Next stage has the same `worktree` mode as the completed stage
   (both worktree or both non-worktree)

**If reuse:** Keep the agent alive. Update frontmatter on main (set status
to next stage, commit). Send the next stage's work to the existing agent via
SendMessage with the stage definition, checklist, and continuation
instructions.

**If fresh dispatch (or bare mode):** If the next stage has `feedback-to`
pointing at the completed stage, keep the completed agent alive (for the
feedback loop). Otherwise shut down the agent. Run status --next and
dispatch the next stage.
```

This preserves 068's feedback-to keep-alive as the specific case it was: even when reuse conditions aren't met (e.g., `fresh: true` on the feedback stage), the feedback-to target agent stays alive for the reviewer to message.

### Change 2: Modify the gate approval paths (line 124-128)

Current "Approve + next stage is NOT terminal" path:
```
Shut down the agent. If a kept-alive agent from a prior stage is still
running (the feedback-to target), shut it down too. Dispatch a fresh agent
for the next stage.
```

Apply the same reuse logic: if reuse conditions are met, send the next stage's instructions to the current agent via SendMessage instead of shutting down and dispatching fresh. If not reusable, shut down as before.

### Change 3: Define the reuse SendMessage format

When reusing an ensign, the FO sends:
```
SendMessage(to="{agent}-{slug}-{stage}", message="
Advancing to next stage: {next_stage_name}

### Stage definition:

[STAGE_DEFINITION — copy the full ### stage subsection from the README]

### Completion checklist

[CHECKLIST — same as dispatch step 2]

Continue working on {entity title}. The entity file is at {entity_file_path}.
Do the work described in the stage definition. Update the entity file body
with your findings or outputs. Commit before sending your completion message.
")
```

This mirrors the dispatch prompt but omits setup context (working directory, worktree path, branch info) that the agent already has from its prior stage.

### Change 4: Dispatch step 7 — remove "Always dispatch fresh"

Change the opening of dispatch step 7 from:
```
7. **Dispatch agent** — Always dispatch fresh.
```
to:
```
7. **Dispatch agent** — Dispatch a new agent for the stage.
```

The "always fresh" language is no longer accurate since the completion path now supports reuse. Initial dispatch (from the event loop) is always fresh — reuse only happens within the completion flow when advancing to the next stage.

### Interaction with feedback-to keep-alive (068)

The 068 keep-alive and the reuse pattern serve different purposes:
- **Reuse** (this task): advance the same agent to the next stage, sending it new instructions. The agent continues working on the same entity.
- **068 keep-alive**: keep the prior-stage agent alive so the feedback-stage reviewer can message it with findings. The agent waits for feedback rather than doing new stage work.

These are complementary, not conflicting:
- If the next stage has `feedback-to` pointing at the completed stage AND `fresh: true` (the typical validation pattern): **do not reuse** (fresh overrides), but **do keep alive** (068 — the reviewer needs to reach the implementer).
- If the next stage has `feedback-to` AND no `fresh: true`: **reuse** — send the agent the feedback stage instructions. This means the same agent both implemented and reviews, which defeats the purpose of feedback, so this combination is unlikely in practice.
- If the next stage has no `feedback-to` and no `fresh: true`: **reuse** — straightforward advancement.

### Interaction with worktree boundary transitions

When `worktree` mode changes between stages (one is `worktree: true`, the other is `worktree: false`), reuse is blocked by condition 3. This is correct:
- A worktree->main transition means the agent's working directory context is wrong (it's been working in `.worktrees/{agent}-{slug}`, but the next stage works on main).
- A main->worktree transition means a worktree needs to be created and the agent needs to be told about it.

In both cases, a fresh dispatch with the correct path context is required.

### Interaction with gate stages

Gate stages already have their own completion flow (the gate approval path in "Completion and Gates"). The reuse change applies at the point after gate approval where the FO decides how to advance to the next stage:
- "Approve + next stage is terminal": no reuse (merge path).
- "Approve + next stage is NOT terminal": apply reuse logic (Change 2).
- "Reject + redo": unchanged — the same agent retries.
- "Reject + discard": unchanged — agent shuts down.

## Acceptance Criteria

### AC1: Reuse when consecutive non-worktree stages share context
When an entity completes a non-gate, non-terminal stage and the next stage has `fresh: false` (or unset), `worktree: false` (same as current), and the FO is in team mode: the FO sends the next stage instructions to the existing agent via SendMessage instead of dispatching a new one.

**Test plan:** Static template inspection — verify the "If no gate" path has the three reuse conditions and the SendMessage format. No E2E test needed for the reuse path itself (would require multi-stage team-mode run), but the template text can be grep-checked.

### AC2: Fresh dispatch when `fresh: true`
When the next stage has `fresh: true`, the FO always dispatches a new agent regardless of worktree mode match.

**Test plan:** Static template inspection — verify the reuse conditions include `fresh: true` as a disqualifier. The existing rejection-flow fixture (`tests/fixtures/rejection-flow/README.md`) has `fresh: true` on the validation stage — if an E2E test is added for that fixture, it would validate this path.

### AC3: Fresh dispatch on worktree boundary change
When the completed stage and next stage have different `worktree` modes, the FO dispatches fresh.

**Test plan:** Static template inspection — verify condition 3 (same worktree mode). The rejection-flow fixture has `backlog` (worktree: false) -> `implementation` (worktree: true), which is a boundary change that should force fresh dispatch.

### AC4: Bare mode always dispatches fresh
When the FO is in bare mode (no teams), reuse is impossible and the FO always dispatches fresh. The `fresh` field is effectively a no-op in bare mode.

**Test plan:** Static template inspection — verify the reuse conditions include "not in bare mode" as the first check. Document in the template that bare mode cannot reuse (subagents are blocking).

### AC5: feedback-to keep-alive preserved
When the next stage has `feedback-to` pointing at the completed stage but reuse conditions are NOT met (e.g., `fresh: true`), the completed agent is kept alive (not shut down) so the feedback reviewer can reach it.

**Test plan:** Static template inspection — verify the "If fresh dispatch" path retains the 068 keep-alive check. The existing `test_rejection_flow.py` fixture exercises the feedback-to path and can serve as a regression check.

### AC6: Gate approval path uses reuse logic
After gate approval when the next stage is not terminal, the FO applies the same reuse-vs-fresh logic as the "If no gate" path.

**Test plan:** Static template inspection — verify the "Approve + next stage is NOT terminal" path references the reuse conditions. Before/after wording specified below.

### AC7: Dispatch step 7 no longer says "Always dispatch fresh"
The dispatch step 7 wording changes from "Always dispatch fresh" to neutral language, since reuse now happens in the completion flow.

**Test plan:** Grep for "Always dispatch fresh" in `templates/first-officer.md` — should not be found.

## Before/After Template Wording

### Dispatch step 7 (line 64)

**Before:**
```
7. **Dispatch agent** — Always dispatch fresh. **You MUST use the Agent tool** ...
```

**After:**
```
7. **Dispatch agent** — Dispatch a new agent for the stage. **You MUST use the Agent tool** ...
```

### "If no gate" path (line 94)

**Before:**
```
**If no gate:** If terminal, proceed to merge. Otherwise, check whether the next stage has `feedback-to` pointing at this stage. If yes, keep the agent alive — do not shut it down. Run `status --next` and dispatch the next stage.
```

**After:**
```
**If no gate:** If terminal, proceed to merge. Otherwise, determine whether to reuse the current agent or dispatch fresh for the next stage.

**Reuse conditions** (all must hold — if any fails, dispatch fresh):
1. Not in bare mode (teams available)
2. Next stage does NOT have `fresh: true`
3. Next stage has the same `worktree` mode as the completed stage

**If reuse:** Keep the agent alive. Update frontmatter on main (set `status` to next stage, commit: `advance: {slug} entering {next_stage}`). Send the agent its next assignment:

SendMessage(to="{agent}-{slug}-{completed_stage}", message="Advancing to next stage: {next_stage_name}\n\n### Stage definition:\n\n[STAGE_DEFINITION — copy the full ### stage subsection from the README verbatim]\n\n### Completion checklist\n\n[CHECKLIST — assemble from step 2]\n\nContinue working on {entity title}. The entity file is at {entity_file_path}. Do the work described in the stage definition. Update the entity file body with your findings or outputs. Commit before sending your completion message.")

**If fresh dispatch:** Check whether the next stage has `feedback-to` pointing at the completed stage. If yes, keep the completed agent alive (the feedback reviewer will need to message it). Otherwise, shut down the agent. Run `status --next` and dispatch the next stage.
```

### Gate approval — "Approve + next stage is NOT terminal" (line 128)

**Before:**
```
- **Approve + next stage is NOT terminal:** Shut down the agent. If a kept-alive agent from a prior stage is still running (the `feedback-to` target), shut it down too. Dispatch a fresh agent for the next stage.
```

**After:**
```
- **Approve + next stage is NOT terminal:** Apply the reuse conditions from the "If no gate" path. If reuse: keep the agent, send the next stage via SendMessage. If fresh dispatch: shut down the agent. In either case, if a kept-alive agent from a prior stage is still running (the `feedback-to` target) and the next stage does not need it, shut it down. Dispatch a fresh agent for the next stage if not reusing.
```

## Stage Report: ideation

- [x] Problem statement clarifying the fresh-field regression and its impact on ensign context continuity
  See "Problem Statement" section — documents the regression from 0.3.0, the three impacts (misleading field, lost context, extra overhead), and why it matters
- [x] Proposed approach for restoring fresh field support in the FO template completion/dispatch flow
  Four changes: "If no gate" reuse path, gate approval reuse, SendMessage format, dispatch step 7 wording fix — with exact before/after template text
- [x] Investigation of bare-mode (no teams) reuse — does Agent() with the same name reconnect, or is each call always fresh?
  Finding: bare-mode reuse is impossible. Agent() subagents are blocking — once they return, the process is gone. name parameter is for identification, not reconnection. Reuse requires team mode with live agents and SendMessage.
- [x] Acceptance criteria with test plan (including specific before/after template wording for the FO changes)
  7 acceptance criteria (AC1-AC7), each with test plan. Before/after wording for all three template sections that change.
- [x] Edge case analysis: interaction with feedback-to keep-alive (068), worktree boundary transitions, gate stages
  Three subsections analyzing: feedback-to + fresh interaction (complementary, not conflicting), worktree boundary forces fresh (correct — path context mismatch), gate stages (reuse applies only at "approve + not terminal" decision point)

### Summary

Investigated the `fresh` field regression introduced in the 0.8.2 FO simplification. The field exists in README frontmatter but the FO template ignores it, always dispatching fresh. Proposed a three-condition reuse check (team mode, no `fresh: true`, same worktree mode) applied at both the "no gate" and "gate approval" completion paths. Confirmed that bare-mode reuse is physically impossible (blocking subagents), so the feature is team-mode only. The existing feedback-to keep-alive (068) is preserved as a separate concern — it keeps agents alive for the feedback loop even when reuse conditions aren't met.
