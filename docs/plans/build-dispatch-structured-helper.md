---
id: 120
title: build_dispatch helper — structured dispatch assembly (Phase 2 of issue #63)
status: backlog
source: anthropics/claude-code (local) issue #63 — fuzzy prose dispatch template causes silent failures
score: 0.70
---

Replace the prose-wearing-code `Agent()` dispatch template in the Claude first-officer runtime adapter with a structured helper at `skills/commission/bin/build_dispatch`. The helper owns deterministic scaffolding (name derivation, team_name wiring, stage definition extraction, guardrail paragraphs, completion rubric), the FO supplies judgment fragments (checklist, feedback context, scope notes) as JSON on stdin, and the helper emits a validated dispatch JSON object that the FO forwards to `Agent()` verbatim. This is Phase 2 of local issue #63.

## Why

Any LLM-facing instruction that mixes "data to substitute" with "logic to execute" is a fuzzy template in disguise, and fuzzy templates fail silently in proportion to their complexity. The current runtime adapter template mixes four notations (`{curly_braces}`, `[BRACKETS imperative]`, `{if condition: '...'}`, surrounding prose) in one code block. The LLM parses, resolves conditionals, distinguishes variable slots from imperative instructions, and assembles the final call in one shot. Every assembly step is a place a field can get dropped — the `name`-missing sidechain bug (issue #63) is one example; the 115 completion-signal missing bug was another.

Task 115 patched one symptom; task 118 is patching another (PR body template). A structured helper is the deeper treatment that subsumes the patch-a-symptom pattern.

## Design sketch (from issue #63)

The helper reads:
- The entity file (extracts title, worktree, entity file path)
- The workflow README (extracts the `### {stage}` subsection verbatim)
- The stage metadata (derives `subagent_type` from `agent:` field, `worker_key`, `name`, `branch`)
- LLM-supplied JSON on stdin (`checklist`, `feedback_context`, `scope_notes`)

The helper validates:
- If `--team` set, `name` must be derivable
- If the stage is a worktree stage, worktree path must exist
- If the stage has `feedback-to`, feedback context must be present
- etc.

The helper emits final dispatch JSON to stdout:

```json
{
  "subagent_type": "spacedock:ensign",
  "name": "spacedock-ensign-{slug}-{stage}",
  "team_name": "{team}",
  "description": "...",
  "prompt": "<fully assembled prompt>"
}
```

The FO calls `Agent()` with those exact fields. No interpretation, no assembly, no conditional branches to forget.

## Open questions for ideation

The ideation stage must resolve these before implementation:

1. **Helper failure mode.** The helper becomes a single point of failure. Bug in the helper = all dispatches fail. Mitigation: unit tests + a break-glass manual-dispatch procedure documented in the runtime adapter.
2. **Helper scope discipline.** The helper must NOT grow into a general-purpose orchestrator. It emits a single validated dispatch object and stops. It does NOT run `TeamCreate`, `status --set`, or commit state — those stay with the FO. This line must be explicit in the design.
3. **Schema versioning.** The LLM's input JSON schema will evolve. The helper should version its input schema and the runtime adapter should assert the version it expects. Plan the versioning mechanism.
4. **Bootstrap.** The helper lives at `skills/commission/bin/build_dispatch`, plugin-shipped. First-time workflows should have access to it (same path as the existing `skills/commission/bin/status`). Verify commission's install path includes both.
5. **Multi-runtime strategy.** Initially Claude Code only. Codex and Gemini adapters will eventually use the same helper. Decide whether the helper is runtime-agnostic or runtime-specific; if runtime-agnostic, how does it learn which runtime to emit dispatch JSON for?

## Acceptance Criteria (placeholder — ideation to refine)

1. New helper at `skills/commission/bin/build_dispatch` (Python, follows the pattern of `skills/commission/bin/status`).
2. Helper reads entity file, workflow README, LLM JSON from stdin; emits validated dispatch JSON to stdout; exit code 0 on success, non-zero on validation failure.
3. Unit tests covering: normal dispatch, team-mode dispatch, worktree-stage dispatch, feedback-stage dispatch, each validation failure mode.
4. Runtime adapter `skills/first-officer/references/claude-first-officer-runtime.md` updated to instruct the FO to pipe judgment fragments into the helper and forward the emitted fields to `Agent()`.
5. E2E regression test that dispatches via the new path — the FO in a nested `claude -p` session uses the helper end-to-end, a worker is dispatched, and the entity advances without captain intervention.
6. All existing suites green — `test_agent_content.py`, `test_rejection_flow.py`, `test_merge_hook_guardrail.py`, `test_dispatch_completion_signal.py`, `test_checklist_e2e.py` (if present).
7. The runtime adapter contains a documented break-glass manual-dispatch procedure for use when the helper is unavailable or broken.

## Test Plan

Ideation-determined; likely:
- Static: unit tests for the helper (low cost, required)
- Static: the existing assertions in `tests/test_agent_content.py` updated to check that the runtime adapter references the helper invocation
- E2E: a new `tests/test_structured_dispatch.py` that drives the full path via `claude -p`
- Integration: ensure `test_rejection_flow.py`, `test_dispatch_completion_signal.py`, and `test_merge_hook_guardrail.py` still pass with the new helper in place

## Out of scope

- Codex and Gemini runtime adapter updates (separate tasks after this lands).
- Generalizing the pattern to other fuzzy-template sites (feedback rejection flow, gate presentation, event loop) — Phase 4 of issue #63.
- Mod files (`pr-merge.md`) — separate concern (task 118).

## Related

- anthropics/claude-code local issue #63 — umbrella, this is Phase 2.
- Task 119 — Phase 1 band-aids (should land first).
- Task 115 — first completion-signal patch (precedent for the patch-a-symptom pattern that this task replaces).
- Task 118 — PR body template (adjacent fuzzy-template anti-pattern).
