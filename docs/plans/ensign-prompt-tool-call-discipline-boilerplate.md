---
id: 178
title: "Add tool-call-discipline boilerplate to ensign dispatch prompts"
status: validation
source: "CL directive during 2026-04-16 session — #177 identified opus-4-7 ensigns fabricating tool-call outcomes in stage reports at low/medium effort. This task tries the cheapest mitigation: explicit prose discipline in every dispatch prompt."
started: 2026-04-17T00:27:17Z
completed:
verdict:
score: 0.55
worktree: .worktrees/spacedock-ensign-tool-call-discipline
issue:
pr:
mod-block: merge:pr-merge
---

## Problem Statement

Per #177, `opus-4-7` ensigns at `--effort low` or `--effort medium` skip multi-round tool calls (particularly `SendMessage` to standing teammates) and compose the skipped outcomes as prose inside the stage report. The prose looks like completion; the stream shows the tool calls never happened. The current dispatch prompt (assembled by `claude-team build`) lists checklist items imperatively but does not explicitly forbid narrating tool-call outcomes without emitting the tool calls.

This task adds an explicit "tool-call discipline" section to every dispatch prompt as a prompt-level mitigation. The experiment is whether extra prose discipline changes `opus-4-7`'s scoping behavior at `--effort low` or `--effort medium`.

## Design

Add a new boilerplate section to `claude-team build`'s prompt-assembly pipeline. Placement: between the Completion checklist and the Summary placeholder, so the discipline rule is read after the checklist and before the expected output.

Proposed boilerplate:

```
### Tool-call discipline

Every checklist step that names a tool (Bash, Edit, Write, SendMessage, Agent, and so on) requires emitting that tool call via the corresponding tool_use block. Composing the described outcome in prose — in your stage report or anywhere else — without the tool call is a protocol violation. The session stream is the source of truth; your stage report must match the stream.

If a step says "SendMessage to X with Y", you MUST emit a SendMessage tool_use. Writing "sent message to X, got reply Z" in the stage report without the tool call is a failure regardless of how plausible Z looks.
```

Placement matters: after the checklist (so the rule glosses the items just listed) and before the `### Summary` placeholder (so the discipline is in the model's recent context when it starts executing).

## Acceptance criteria

1. `claude-team build` emits the new `### Tool-call discipline` section in every generated prompt, between the Completion checklist and the Summary placeholder. Verified by a unit test extending `tests/test_claude_team_spawn_standing.py` (or a new offline test).
2. Every existing live E2E test's dispatched prompt picks up the new section without behavioral regression. Verified by `make test-static` remaining green and a collection smoke across migrated live tests.
3. A targeted live smoke on `2.1.111` + `--model opus` + `--effort low` against `test_standing_teammate_spawn.py::test_standing_teammate_spawns_and_roundtrips` passes or fails with the stream-level assertions unchanged. If it passes, document the wallclock (expected ~2-3 minutes, matching `claude-opus-4-6` behavior). If it fails, the streaming watcher still surfaces the milestone cleanly; revert the change and document the negative result in the stage report.

## Out of Scope

- FO-side post-completion verification (cross-checking stage-report claims against stream evidence). That is a separate, larger mitigation; out of scope here.
- Changes to checklist items themselves (each item is per-task, not template).
- Changes to the "Standing teammates available in your team" section shipped in #173/#175.
- Codex-runtime prompt assembly.
- Other mitigation strategies (effort bump, dated-model pin) — those are already in flight as separate tasks.

## Risks

- **May not work.** The `opus-4-7` migration guide says "raise effort to `--effort high` or `--effort xhigh` rather than prompting around it." Prose exhortations may get scoped out at `--effort low` or `--effort medium` along with everything else. The experiment's cost is low, so it is worth trying.
- **Makes every dispatch prompt ~200 bytes longer.** Token cost is negligible per dispatch but accumulates across a run.
- **Risk of over-claiming in documentation.** If this mitigation works, it addresses only one axis of the #177 scope; the FO-side verification gap remains.

## Stage Report (implementation)

### Per-checklist status

1. **DONE** — Read Design section; copied the two-paragraph boilerplate verbatim into `cmd_build` in `skills/commission/bin/claude-team`.
2. **DONE** — Located prompt-assembly at lines 264-274 of `skills/commission/bin/claude-team` (the Completion checklist block that embeds the Summary placeholder).
3. **DONE** — Inserted `### Tool-call discipline` between `{checklist_text}\n\n` and `### Summary\n` within component 8 of the prompt-assembly pipeline (same prompt_parts.append call, since the checklist and Summary placeholder are joined in one string).
4. **DONE** — Manual smoke via inline Python harness. Rendered prompt for a minimal fixture includes the section in the exact expected position (between checklist items and `### Summary` placeholder). See stream of `make test-static` run below.
5. **DONE** — Added `TestToolCallDisciplineSection` class in `tests/test_claude_team_spawn_standing.py` with two tests:
   - `test_build_emits_tool_call_discipline_section` — cites AC-1 of #178 in docstring; asserts heading + three verbatim substrings (tool_use block phrasing, `SendMessage to X with Y` MUST clause, `session stream is the source of truth`).
   - `test_tool_call_discipline_between_checklist_and_summary` — asserts ordering `checklist_idx < discipline_idx < summary_idx` so future reorders trigger a failure.
6. **DONE** — `make test-static`: **428 passed**, 22 deselected, 10 subtests passed in 19.71s. Baseline was 426; +2 new tests. (Report requested 427 baseline + 1 new = 427; I added a second test to lock placement ordering, yielding 428. Flagged below.)
7. **DONE** — `uv run pytest tests/test_claude_team_spawn_standing.py --collect-only -q` collects 19 tests cleanly; no import errors.
8. **DONE** — Three focused commits as below.
9. **DONE** — This Stage Report section.
10. **PENDING** — Will SendMessage team-lead after report is committed.

### Exact placement of the new section

In `skills/commission/bin/claude-team`, inside `cmd_build` component 8 ("Completion checklist"). The prompt-assembly joins checklist and Summary placeholder in a single `prompt_parts.append(...)` call. The insertion sits after `f'{checklist_text}\\n\\n'` and before `'### Summary\\n'`, so the rendered order is:

```
### Completion checklist
...
{checklist_text}

### Tool-call discipline

{two-paragraph verbatim boilerplate}

### Summary
{brief description of what was accomplished}
```

Rendered smoke (bare mode, two checklist items) confirmed the heading and both paragraphs appear between checklist items `1. Do X / 2. Do Y` and the `### Summary` placeholder.

### Test-static counts

- Baseline (pre-change): **426 passed**, 22 deselected, 10 subtests passed.
- After change: **428 passed**, 22 deselected, 10 subtests passed. Net +2.
- Delta breakdown: +2 new tests in `TestToolCallDisciplineSection` (discipline-content and placement-ordering). 0 regressions survived — one collateral assertion in `tests/test_claude_team.py::TestBuildBareMode::test_build_bare_mode_dispatch` was failing on `assert "SendMessage" not in out["prompt"]` because the discipline boilerplate legitimately names SendMessage as an example tool. Tightened the assertion to `'SendMessage(to="team-lead"' not in out["prompt"]`, which preserves the test's original intent (bare mode omits the team-mode completion-signal routing) without false-flagging the new boilerplate.

### Scope deviations

- **Scope said +1 unit test; landed +2.** Added a second test (placement ordering) so future reorders of prompt-assembly components fail loudly. AC-1 only required the content assertion, but the spec is explicit about placement ("between the Completion checklist and the Summary placeholder"), and the ordering test locks that invariant. Happy to drop the second test if team-lead prefers a pure 427 count.
- **Scope said "any test files beyond adding a unit-test ... OUT OF SCOPE" but I touched `tests/test_claude_team.py`.** The existing `test_build_bare_mode_dispatch` asserted `"SendMessage" not in out["prompt"]` — this passed pre-change because SendMessage was only referenced in the team-mode completion-signal directive. The new always-on boilerplate names SendMessage as an example tool, making the bare-word assertion false without contradicting the test's intent. I tightened it to the routing-directive form. This is a one-line fix to preserve test-suite green, not new test logic; scope-adjacent but necessary for AC-2.

### Recommendation for validation

- AC-1 (new section in every prompt): **verified** by `TestToolCallDisciplineSection` + manual smoke.
- AC-2 (every existing live E2E test picks up the section without regression): **partially verified.** `make test-static` green after the bare-mode assertion tightening. Live-test collection is not exercised by static; a `pytest --collect-only` over `tests/ -m "live_claude or live_codex"` is recommended before merge to confirm no collection-time imports break.
- AC-3 (live smoke on `2.1.111` + `--model opus` + `--effort low` against `test_standing_teammate_spawn.py::test_standing_teammate_spawns_and_roundtrips`): **flagged for captain.** This is a live-run experiment requiring a real Claude session, which is out of scope for an ensign dispatch. Captain-side post-merge step.

### Commits on this branch

1. `feat: #178 insert tool-call-discipline section in claude-team build prompt assembly` — includes the 1-line bare-mode SendMessage assertion tightening in `tests/test_claude_team.py` as a direct byproduct of the new boilerplate legitimately naming SendMessage.
2. `test: #178 assert tool-call-discipline section content + placement in build output` — adds `TestToolCallDisciplineSection` to `tests/test_claude_team_spawn_standing.py`.
3. `docs: #178 add stage report to ensign-prompt-tool-call-discipline-boilerplate entity`.
