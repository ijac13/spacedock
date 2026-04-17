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
pr: #113
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
