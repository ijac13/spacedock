---
id: 087
title: Codex direct skill dispatch - remove packaged agent wrapper dependency
status: implementation
source: CL - 085 gap review
started: 2026-04-03T16:54:38Z
completed:
verdict:
score: 0.72
worktree: .worktrees/ensign-codex-direct-skill-dispatch
issue:
pr:
---

The Claude-side boot problem is now solved by 085: thin agents preload skills, and skills load references through `${CLAUDE_SKILL_DIR}`. But the Codex runtime still treats logical ids like `spacedock:first-officer` and `spacedock:ensign` as packaged agent assets that resolve through `agents/{name}.md`.

That leaves an unnecessary wrapper layer in the Codex path:

- `resolve_codex_worker()` maps `spacedock:ensign` to `agents/ensign.md`
- worker bootstrap prompts tell Codex workers to read `~/.agents/skills/{namespace}/agents/{name}.md` first
- `codex_prepare_dispatch.py` emits `role_asset_kind: agent` for packaged workers

This means 085 fixed Claude boot mechanics but did not finish the architectural simplification. We still need `agents/` in Codex even though the real source of truth is already split across `skills/` and `references/`.

## Current regression on main

The current live Codex gate test on `main` shows a concrete helper/runtime bug that overlaps this task's scope:

- the first officer presents the correct gate review and says it is waiting for approval
- but `codex_prepare_dispatch.py` is still invoked for the entity and returns a payload for the terminal `done` stage
- that helper mutates main-branch frontmatter to `status: done` and writes a `done` worktree path before approval exists

This means the next implementation slice should address both problems together:

1. remove the remaining Codex dependency on packaged agent wrappers
2. stop Codex dispatch helpers from advancing gated entities past the gate before approval

The combined fix belongs in the same surface area (`scripts/codex_prepare_dispatch.py`, `scripts/test_lib.py`, Codex runtime prompts, and helper tests), so it should be handled as one change rather than two unrelated patches.

## Goal

Make Codex dispatch packaged logical ids directly through skills and references, without requiring packaged agent wrapper files as a runtime dependency.

## Proposed approach

1. Treat names like `spacedock:first-officer` and `spacedock:ensign` as skill identities first, not agent-file identities.
2. Update Codex bootstrap prompts to load `spacedock:{name}` via the skill system instead of telling workers to read `agents/{name}.md`.
3. Change `resolve_codex_worker()` and `codex_prepare_dispatch.py` so the packaged path produces skill-oriented payloads rather than `role_asset_kind: agent`.
4. Keep `references/` as the only source of operational contract text. Skills remain the stable bootstrap surface that read those references.
5. Decide whether `agents/` remains only for Claude/plugin packaging compatibility or can become optional for Codex tests and runtime docs.

## Constraints

- Do not regress Claude plugin behavior from 085.
- Do not duplicate reference content into skills or test prompts.
- Preserve logical ids (`spacedock:first-officer`, `spacedock:ensign`) as the public names used in tests and docs.
- Keep the live Codex E2E suite green, especially gate, rejection, merge-hook, and packaged-agent/plugin-discovery coverage.

## Open questions

1. Should Codex packaged worker payloads still carry a role asset name for observability, or is the logical skill id enough?
2. Can `tests/test_codex_packaged_agent_e2e.py` be renamed once the path is no longer agent-based, or is the "packaged agent" name still acceptable as historical shorthand?
3. After this change, is `agents/` needed only for Claude, or should we keep thin wrappers there as a cross-runtime compatibility surface anyway?

## Acceptance criteria

1. Codex packaged dispatch no longer instructs workers to read `~/.agents/skills/{namespace}/agents/{name}.md`.
2. Codex packaged logical ids resolve through skills/references instead of `agents/{name}.md`.
3. `scripts/codex_prepare_dispatch.py` and `scripts/test_lib.py` use the new skill-oriented payload shape consistently.
4. Codex helper tests are updated to assert the new bootstrap contract.
5. Live Codex tests for gate, rejection, merge-hook, and packaged dispatch still pass.
6. Claude-side runtime behavior and 085's skill-preload design remain intact.
7. The live Codex gate test no longer writes `status: done` for a gated entity before approval.

## Test plan

- Update unit/helper tests for `resolve_codex_worker()`, Codex bootstrap prompts, and dispatch payload generation.
- Rerun:
  - `uv run tests/test_gate_guardrail.py --runtime codex`
  - `uv run tests/test_rejection_flow.py --runtime codex`
  - `uv run tests/test_merge_hook_guardrail.py --runtime codex`
  - `uv run tests/test_codex_packaged_agent_e2e.py`
- Spot-check that Claude-facing agent/skill files still match 085 expectations.
