---
id: 120
title: build_dispatch helper — structured dispatch assembly (Phase 2 of issue #63)
status: ideation
source: anthropics/claude-code (local) issue #63 — fuzzy prose dispatch template causes silent failures
score: 0.70
started: 2026-04-13T21:19:53Z
---

Replace the prose-wearing-code `Agent()` dispatch template in the Claude first-officer runtime adapter with a structured helper. The helper owns deterministic scaffolding (name derivation, team_name wiring, stage definition extraction, guardrail paragraphs, completion rubric); the FO supplies judgment fragments (checklist, feedback context, scope notes) as JSON on stdin; the helper emits a validated dispatch JSON object that the FO forwards to `Agent()` verbatim. This is Phase 2 of local issue #63.

## Packaging — `claude-team build` subcommand (2026-04-13 decision)

The helper ships as a new subcommand on the existing `skills/commission/bin/claude-team` script, not as a standalone `build_dispatch` binary. Rationale:

- Every other planned team-dispatch helper already lives under `claude-team` (`context-budget` today; `verify-member` from #119; `health` from #143). A single `claude-team --help` surface for all dispatch-adjacent helpers.
- Plugin install paths reference `skills/commission/bin/` as-is; adding one new sibling binary requires a scaffolding-reference update, adding a subcommand does not.
- Future codex equivalents (e.g., a `codex-team build` or `codex-agent build` sibling) get the same shape for free.

### Code sharing with `status` via `importlib`

The helper needs workflow-file parsing primitives that already exist in `skills/commission/bin/status`:

- `parse_frontmatter(filepath)` — status:73
- `parse_stages_block(filepath)` — status:97
- `load_active_entity_fields(path, git_root)` — status:229 (worktree-aware reads)
- `find_git_root(start_dir)` — status:904

Do NOT extract these into a new `skills/commission/lib/` package — the project relies on the current skills/bin layout for reference/install stability, and fewer directories is the stated preference. Instead, `claude-team` should import them sideways from `status` using `importlib.util.spec_from_file_location`. This works because `status` has an `if __name__ == '__main__': main()` guard at line 1207 — importing as a module skips the CLI path.

Reference shape (ideation to finalize):

```python
import importlib.util
from pathlib import Path

_here = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_status_lib", _here / "status")
_status = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_status)
# _status.parse_frontmatter(...) etc.
```

Caveats the ideation must resolve:

1. The import contract between `claude-team` and `status` becomes a runtime-only API. A small pytest should exercise each borrowed function via the sibling-import path so signature drift fails a static test, not a live dispatch.
2. Document the borrowed surface (which `status` functions are "public" for `claude-team`) in a comment at the top of `claude-team` or in a short section of the script's own help text. Otherwise a future edit to `status` may break `claude-team` silently.
3. The same `importlib` pattern is fine for future consumers (e.g., codex-side helpers) but past 2–3 consumers the argument for a proper library module gets stronger; revisit if that happens.

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

1. New `build` subcommand on `skills/commission/bin/claude-team` (Python, follows the pattern of the existing `context-budget` subcommand). No new sibling binary, no `lib/` directory.
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
