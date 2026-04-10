---
id: 119
title: FO dispatch Phase 1 band-aids — membership verification, required-field header, upstream issue
status: backlog
source: anthropics/claude-code (local) issue #63 — fuzzy prose dispatch template causes silent sidechain downgrade
score: 0.75
---

Protect the FO dispatch path against the silent sidechain downgrade failure mode described in issue #63 (the Agent tool accepts `team_name` without `name` and produces a sidechain subagent instead of a team member) by adding cheap, immediate band-aid protections to the runtime adapter and the FO's procedural core. This is Phase 1 of the issue #63 proposal; the Phase 2 `build_dispatch` helper is tracked separately as task 120.

## Why now

During the 2026-04-10 session, the FO initially misdiagnosed `isSidechain:true` in subagent jsonls as a bug marker and nearly raised a false alarm. The actual bug marker is "new member name missing from `~/.claude/teams/{team}/config.json` members array immediately after dispatch". The session's own dispatches were clean — the FO passed `name=` to every `Agent()` call by virtue of manually substituting `{worker_key}-{slug}-{stage}` per the template — but the detection path for the bug was fragile and the template was one distracted copy-paste away from silent downgrade. Stronger guardrails on both the dispatch side and the verification side are warranted.

## Scope

Three band-aids, all from issue #63:

1. **Post-dispatch team-membership verification** in the Claude first-officer runtime adapter. After any `Agent()` call with `team_name=`, the FO reads `~/.claude/teams/{team_name}/config.json` and asserts the new `name` appears in the members array. If absent, the FO alerts the captain and pauses (or redispatches after captain direction). Add as an explicit numbered step in the Dispatch section.

2. **Required-field-list header** preceding the `Agent()` template in the runtime adapter. An explicit markdown table separating fields by category:
   - **required for every dispatch**: `subagent_type`, `prompt`
   - **required in team mode**: `name`, `team_name`
   - **optional**: `description`, `model`

   Makes the team-mode `name` requirement visually separable from the template code block so it cannot fall through as "just another variable substitution".

3. **Upstream issue filing** against anthropics/claude-code requesting that `Agent()` error (or at minimum warn loudly) when `team_name` is passed without `name`. Silent downgrade is the worst possible failure mode. **Requires captain approval per FO rules** and will be documented in the implementation stage report as "pending captain green light" rather than filed by the worker.

## Out of scope

- The `build_dispatch` helper (Phase 2) — tracked as task 120.
- Codex runtime adapter parity for band-aid 2 — can land in a follow-up task or as part of 120 depending on which ships first.
- Any changes to commission, skills/commission/bin, or the plugin surface.
- Filing the upstream issue without explicit captain approval.

## Acceptance Criteria

1. `skills/first-officer/references/claude-first-officer-runtime.md` has a "Required fields" table preceding the `## Dispatch Adapter` Agent() template, clearly marking `name` and `team_name` as required-in-team-mode and `subagent_type`/`prompt` as required-always.
   - Test: `grep -n 'Required fields' skills/first-officer/references/claude-first-officer-runtime.md` returns one match, and the following lines contain a markdown table with a "team mode" qualifier for `name`.
2. `skills/first-officer/references/first-officer-shared-core.md` has a post-dispatch verification step in the Dispatch section (after step 9 or similar), instructing the FO to read the team config and confirm the new member name before proceeding.
   - Test: a grep assertion for a phrase like "post-dispatch verification" or "confirm the new member name" returns one match in the shared core file; the step is procedural.
3. `tests/test_agent_content.py` has a new assertion that the assembled Claude FO content contains both the required-fields header and the post-dispatch verification step.
   - Test: the new test passes on the fix commit and fails on the parent commit.
4. The upstream GitHub issue filing is NOT performed by the worker. The stage report documents a "pending captain approval" note describing what the issue would say (title, body, target repo).
5. Existing suites stay green.
   - Test: `unset CLAUDECODE && uv run --with pytest python tests/test_agent_content.py -q`, `unset CLAUDECODE && uv run tests/test_rejection_flow.py`, `unset CLAUDECODE && uv run tests/test_merge_hook_guardrail.py`.

## Test Plan

- Static assertion via `tests/test_agent_content.py` — low cost, required.
- Adjacent E2E suites re-run to confirm no regression in dispatch flow.
- No new E2E test: the band-aids are documentation-level; the behavior assertion (FO verifies membership) is covered by the runtime adapter read path and manual captain confirmation during validation.

## Related

- anthropics/claude-code local issue #63 — umbrella issue; Phase 1 is this task, Phase 2 is task 120.
- Task 107 — team-agent skill loading bug (adjacent upstream quirk).
- Task 115 — first fuzzy-template patch, landed in PR #62.
- Task 118 — PR body template (related fuzzy-template anti-pattern).
