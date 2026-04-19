---
id: 201
title: "FO bootstrap discipline — skipped TeamCreate in teams-mode jobs (multi-model)"
status: backlog
source: "session 2026-04-18 investigation of PR #132 re-run — haiku claude-live job FO invoked `claude-team spawn-standing --team none` and `build` with `team_name: null, bare_mode: true` inside what should have been a teams-mode job. Same bootstrap-skip failure class as #194 but cross-model: haiku-teams exhibits it, not just opus-4-7."
started:
completed:
verdict:
score: 0.6
worktree:
issue:
pr:
mod-block:
---

## Why this matters

PR #132 (entity #190) re-run's `claude-live` job (haiku teams mode) failed `test_standing_teammate_spawns_and_roundtrips` with:

```
AssertionError: Ensign dispatch prompt missing the standing-teammates section.
```

The initial read was "regression in `claude-team build`'s standing-teammates prompt emission." Investigation (2026-04-18 session, cited below) showed otherwise: `claude-team build` correctly skipped the section because the FO passed `team_name: null, bare_mode: true` in its input JSON. The FO **never established a team** in a job that was supposed to run in teams mode.

Evidence from CI artifact `spacedock-test-co13e139/fo-log.jsonl`:
- FO invoked `claude-team spawn-standing --mod … --team none` — literal string `none` as team name.
- FO piped `dispatch_spec.json` into `claude-team build` with `"team_name": null, "bare_mode": true`.
- `enumerate_declared_standing_teammates()` in `skills/commission/bin/claude-team` returns empty when `team_name` is falsy; the standing-teammates prompt section is correctly skipped.
- Completion-signal guard `not bare_mode and team_name` at line 311 is also not satisfied; completion-signal section absent.

This is a **FO bootstrap-discipline failure on the standing-teammate pipeline** — the FO should have called `TeamCreate` and captured a real team name before `spawn-standing`, but didn't. The test fixture's mod (`_mods/echo-agent.md`) is valid; `list-standing` would find it. The pipeline is correct; the FO skipped the first step.

## Relationship to #194

#194 tracks "opus-4-7 standing-teammate spawn flakiness" — documented failure modes include "FO stalled before ensign Agent dispatch" and "zero TeamCreate observed." That description is model-agnostic in shape but the task's framing and title are opus-4-7-specific. PR #132 evidence shows the same failure mode on haiku-teams (claude-live job).

**Decision:** file this as #201 separately rather than absorbing into #194, because:
- #194 was widened this session to "multi-model FO-side ECHO-roundtrip flake" — its scope is already about roundtrip behavior, not TeamCreate omission.
- This task's scope is specifically "FO bootstrap discipline: TeamCreate must precede spawn-standing / ensign dispatch in teams-mode jobs." A focused task with a bounded fix surface.

Cross-reference #194 but keep scope distinct.

## Proposed approach

**Diagnosis candidates:**

1. **FO prose gap** — `skills/first-officer/SKILL.md` or `references/claude-first-officer-runtime.md` may not say strongly enough "in teams mode, call TeamCreate FIRST, before ANY other team-mode tool invocation (including spawn-standing)." Check whether the current prose has an imperative "MUST call TeamCreate before X" for each team-mode operation.
2. **Sequencing ambiguity** — the FO reads the workflow's _mods at boot, sees `standing-teammate` entries, and may race to `spawn-standing` before completing `TeamCreate`. The runtime adapter may allow either order.
3. **Model-specific rendering** — haiku may parse a conditional "if in teams mode, TeamCreate first" less reliably than opus; unconditional language would be more robust.
4. **Upstream coverage gap** — no existing test asserts "FO always calls TeamCreate before spawn-standing in teams mode." A new test predicate could catch this pre-prose-fix.

**Fix shape (hypothesis):**

- Tighten FO prose with an unconditional "TeamCreate MUST be the first tool call in teams mode before any spawn-standing / Agent / SendMessage invocation."
- Optionally add a mechanism guard in `claude-team spawn-standing` that refuses `--team none` / empty string, emitting a clear error like "spawn-standing requires a real team name; call TeamCreate first."
- Add a static test that asserts the FO's skill preload output, when run in teams mode, contains the "TeamCreate first" imperative in a grep-able form.

## Acceptance criteria

**AC-1 — FO prose makes TeamCreate-first unconditional.**
Verified by: `grep -n 'TeamCreate' skills/first-officer/references/claude-first-officer-runtime.md` includes a sentence naming TeamCreate as the FIRST team-mode tool call (unconditional, not qualified with "when possible" or similar). The imperative appears before any spawn-standing / Agent dispatch prose.

**AC-2 — `claude-team spawn-standing` rejects empty/none team name.**
Verified by: `claude-team spawn-standing --mod path --team none` exits non-zero with stderr containing "requires a real team name" or equivalent. `claude-team spawn-standing --mod path --team ""` same behavior.

**AC-3 — New static test locks in the TeamCreate-first prose.**
Verified by: `tests/test_claude_team.py` (or similar location per tests/README.md) has a test like `test_runtime_prose_names_teamcreate_first` that greps the skill-preloaded FO contract for the "TeamCreate first" imperative.

**AC-4 — Static suite green post-merge.**
Verified by: `make test-static` passes on main after the implementation.

**AC-5 — Behavioral spot-check (optional).**
Verified by: one live haiku-teams dispatch of test_standing_teammate_spawn reaches Phase 2 Agent dispatch without hitting the "team_name null" failure mode. ~$1, deferrable to follow-up if the prose change is structurally sufficient.

## Out of scope

- Fixing opus-4-7-specific ECHO roundtrip flakiness — #194 owns that.
- Fixing haiku-bare guardrail weaknesses — #200 owns those.
- Fixing `claude-team build` template emission — not broken.
- Rewriting the FO contract end-to-end — this task is a targeted prose tightening on TeamCreate-first.

## Cross-references

- **#194** — opus-4-7 standing-teammate roundtrip flakiness. Adjacent failure class; distinct scope.
- **#200** — haiku-bare FO behavioral weaknesses on guardrail suite. Different tests, different failure modes.
- **#190** (archived) — PR #132's claude-live failure is the concrete motivating evidence for this task.
- CI artifact: run `24612094887`, claude-live job. Test dir `spacedock-test-co13e139`. Key lines in fo-log.jsonl show `spawn-standing --team none` and `build` with null `team_name`.
- `skills/commission/bin/claude-team` lines 276-308 (standing section emission), 311 (completion signal guard), 526-527 (enumerate early-return on falsy team_name).
