---
id: 119
title: FO dispatch Phase 1 band-aids — verify-member subcommand, required-field header, upstream issue
status: ideation
source: anthropics/claude-code (local) issue #63 — fuzzy prose dispatch template causes silent sidechain downgrade
score: 0.75
started: 2026-04-15T05:18:01Z
---

Protect the FO dispatch path against the silent sidechain downgrade failure mode described in issue #63 (the Agent tool accepts `team_name` without `name` and produces a sidechain subagent instead of a team member) by adding cheap, immediate band-aid protections in two places: a new `claude-team verify-member` subcommand (extending the helper that task 121 introduced), and documentation improvements in the runtime adapter.

## Why now

During the 2026-04-10 session, the FO initially misdiagnosed `isSidechain:true` in subagent jsonls as a bug marker and nearly raised a false alarm. The actual bug marker is "new member name missing from `~/.claude/teams/{team}/config.json` members array immediately after dispatch". The session's own dispatches were clean — the FO passed `name=` to every `Agent()` call by virtue of manually substituting `{worker_key}-{slug}-{stage}` per the template — but the detection path was fragile and the template was one distracted copy-paste away from silent downgrade. This session's FO ran the check as a manual shell one-liner after every dispatch; the rule needs to be codified so future FOs do it reliably.

Task 121 landed `skills/commission/bin/claude-team` with a `context-budget` subcommand. That script is now the canonical home for mechanical team-operation work, and `verify-member` is a natural sibling to `context-budget`. This task reuses that foundation.

## Scope

Three band-aids:

1. **`claude-team verify-member` subcommand.** Add to `skills/commission/bin/claude-team` (same script as `context-budget` from task 121). Interface:

   ```bash
   skills/commission/bin/claude-team verify-member --name spacedock-ensign-foo-impl
   ```

   Output (JSON):
   ```json
   {
     "name": "spacedock-ensign-foo-impl",
     "team_name": "moonlit-giggling-pillow",
     "present": true
   }
   ```

   Exit 0 on success (even when `present: false` — that's data, not an error). Non-zero on lookup failure (e.g., team config missing).

   Internal logic: discover the team config via the same helper used by `context-budget` (scan `~/.claude/teams/*/config.json` for a member matching `--name`), assert the name appears in the members array. Return JSON. This replaces the manual `python3 -c "import json..."` one-liner the FO has been running all session.

   Add a post-dispatch verification step to the shared core Dispatch section: "After every `Agent()` call with `team_name`, run `claude-team verify-member --name {name}`. If `present: false`, the dispatch silently downgraded to a sidechain — alert the captain and do not proceed with work routing."

   **Note on zombies (from task 121):** a dead ensign still passes `verify-member` because it's still listed in the team config. This check only catches the "never added" case (the sidechain downgrade bug). Combining `verify-member` with session-memory dead-ensign tracking (task 121's dead-ensign handling) gives full coverage.

2. **Required-field-list header** preceding the `Agent()` template in `skills/first-officer/references/claude-first-officer-runtime.md`. An explicit markdown table separating fields by category:
   - **required for every dispatch**: `subagent_type`, `prompt`
   - **required in team mode**: `name`, `team_name`
   - **optional**: `description`, `model`

   Makes the team-mode `name` requirement visually separable from the template code block so it cannot fall through as "just another variable substitution".

3. **Upstream issue filing** against anthropics/claude-code requesting that `Agent()` error (or at minimum warn loudly) when `team_name` is passed without `name`. Silent downgrade is the worst possible failure mode. **Requires captain approval per FO rules** and will be documented in the implementation stage report as "pending captain green light" rather than filed by the worker.

## Out of scope

- The `build_dispatch` helper (Phase 2) — tracked as task 120. Will live as another `claude-team` subcommand.
- Codex runtime adapter parity for band-aid 2 — can land in a follow-up task.
- Any changes to commission or the plugin surface outside `skills/commission/bin/claude-team`.
- Filing the upstream issue without explicit captain approval.

## Acceptance Criteria

1. `skills/commission/bin/claude-team verify-member --name {name}` exists as a subcommand. Returns JSON with `name`, `team_name`, `present`. Exit 0 on success (even when `present: false`).
   - Test: unit tests in `tests/test_claude_team.py` covering present-member, missing-member, and missing-team-config cases.
2. `skills/first-officer/references/claude-first-officer-runtime.md` has a "Required fields" table preceding the `## Dispatch Adapter` Agent() template.
   - Test: grep for "Required fields" returns one match in the runtime adapter; the following lines contain a markdown table with a "team mode" qualifier for `name`.
3. `skills/first-officer/references/first-officer-shared-core.md` has a post-dispatch verification step in the Dispatch section instructing the FO to run `claude-team verify-member` after every team-mode dispatch.
   - Test: grep for "verify-member" returns one match in the shared core Dispatch section.
4. `tests/test_agent_content.py` has new assertions covering the required-fields header (AC-2) and the post-dispatch verification rule (AC-3).
   - Test: the new tests pass on the fix commit and fail on the parent commit.
5. The upstream GitHub issue filing is NOT performed by the worker. The stage report documents a "pending captain approval" note describing what the issue would say (title, body, target repo).
6. Existing suites stay green.
   - Test: `unset CLAUDECODE && uv run --with pytest python tests/test_claude_team.py -v`, `tests/test_agent_content.py`, `tests/test_rejection_flow.py`, `tests/test_merge_hook_guardrail.py`.

## Test Plan

- **Unit tests** for the new `verify-member` subcommand in `tests/test_claude_team.py`: present-member (returns `present: true`), missing-member (returns `present: false`), missing-team-config (exit non-zero), wrong-team-config (name belongs to a different team — decide whether that's a lookup failure or `present: false` in ideation).
- **Static assertions** in `tests/test_agent_content.py` for the required-fields header and the post-dispatch verification rule.
- **Regression**: existing suites re-run to confirm no breakage.
- **No new E2E test**: behavior is verified by unit tests on the script + static assertions on the runtime contract.

## Related

- **Task 121** `fo-context-aware-reuse` — landed. Introduced `skills/commission/bin/claude-team` with the `context-budget` subcommand. This task reuses that helper for `verify-member`.
- **Task 120** `build-dispatch-structured-helper` — Phase 2 of issue #63. Will be a third `claude-team` subcommand. May depend on `verify-member` as a post-dispatch check.
- **Task 126** `claude-team-context-budget-peak-token-bug` — in flight. Fixes a dead-ensign detection bug in the same script.
- **anthropics/claude-code local issue #63** — umbrella issue; Phase 1 is this task, Phase 2 is task 120.
- **Task 107** — team-agent skill loading bug (adjacent upstream quirk).
- **Task 115** — first fuzzy-template patch, landed in PR #62.
- **Task 118** — PR body template (related fuzzy-template anti-pattern).
