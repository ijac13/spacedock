---
id: 201
title: "FO bootstrap discipline — skipped TeamCreate in teams-mode sessions (multi-layer ergonomics)"
status: backlog
source: "session 2026-04-18 — three observations. (1) PR #132 CI haiku-teams job FO invoked `spawn-standing --team none` + `build` with `team_name: null, bare_mode: true`. (2) Separate captain-documented case: commissioned session FO skipped the team probe entirely at boot, defaulted to bare. (3) Research-pipeline session FO dispatched 10 parallel Agent() calls without ever invoking TeamCreate, paying a real entity-file collision cost. All three defaulted to bare by omission, not by design."
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

## Observed skipping behaviors (session 2026-04-18 captain-documented)

Beyond the PR #132 CI evidence, the captain documented two additional observed cases of FOs defaulting to bare mode by omission this week, with self-diagnosed root causes. Both were fresh-commissioned sessions (opus-4-7 operating as first-officer at session start, not inheriting team state from a prior chair).

### Case A — commissioned session, single-entity pilot

FO self-report (edited for brevity):

> I skipped the team probe entirely at session start, then drifted into bare mode by default. The commission skill's Phase 3 ("Pilot Run") says "execute the first-officer startup procedure directly." I half-did that — followed entity discovery, but never ran `ToolSearch(query="select:TeamCreate")`. I'd read the runtime adapter once at boot and it didn't reactivate when I shifted from commission to dispatch.
>
> When I built the first dispatch via `claude-team build`, I just set `bare_mode: true, team_name: null` without thinking. Bare is functionally adequate for one entity, so no failure forced me to course-correct.
>
> **Root causes (mine):**
> - Commission-to-FO handoff is a context switch I underweighted.
> - Cost asymmetry favored skipping. TeamCreate is one tool call. Shortest path to "ensign is running" was bare.
> - The team probe is buried prose, not a forcing function. It's in the FO runtime adapter, but there's no checklist that surfaces it as the very first thing before Agent().

### Case B — research-pipeline session, multi-worker dispatch

FO dispatched 10 parallel `Agent(background)` calls across a session (literature triage + VIX1D experiment cycles) without invoking TeamCreate once. Paid a real collision cost: two ensigns edited `docs/research/experiments/vix1d-regime-filter.md` concurrently, producing duplicated `## Smoke Verdict` / `## Lessons` / `## Stage Report` sections that required post-hoc deduplication.

FO self-report (edited):

> Three reinforcing reasons, by blame:
>
> **1. Tool loading friction (biggest factor).** `SendMessage`, `TeamCreate`, `TeamDelete` were DEFERRED tools — not in my active tool set at session boot. Schemas had to be loaded via `ToolSearch` before invocation. Agent was always loaded. The path of least resistance for dispatch was `Agent(background)`. Team setup required two extra tool loads plus schema digestion.
>
> **2. No forcing function in the Spacedock first-officer skill.** Explains team concepts, ships TeamCreate, but no decision rule like "for N≥2 coordinated workers, create a team first." The pre-Spacedock `.claude/agents/orchestrator.md` had "Create team" as Step 3 of its startup sequence, unconditional. The new Spacedock first-officer lost that forcing function.
>
> **3. My own habit.** Agent(background) worked for earlier batches; I carried the habit into workflows where coordination mattered.
>
> **What we actually paid: the VIX1D Cycle 1 / Cycle 2 collision.** Two ensigns edited the same entity file concurrently. Process paid real reconciliation cost; verdict happened to agree on REJECTED so the outcome wasn't worse, but the pattern is dangerous.

### Shared pattern

All three cases (PR #132 CI haiku-teams, Case A commissioned single-entity, Case B research pipeline multi-worker) share:

- FO started without an explicit team state.
- No forcing function at dispatch time asked "did you set up a team?"
- Bare mode was functional for the immediate task, so no feedback signal corrected the omission.
- The skip compounded: once bare, downstream team-dependent primitives (`spawn-standing`, `SendMessage` coordination) were silently unavailable or malformed.

This isn't a prose-only problem. It's a multi-layer ergonomics gap: FO prose + harness tool-loading defaults + helper binary behavior + commission skill Phase 3 prose.

## Proposed approach

**Diagnosis candidates:**

1. **FO prose gap** — `skills/first-officer/SKILL.md` or `references/claude-first-officer-runtime.md` may not say strongly enough "in teams mode, call TeamCreate FIRST, before ANY other team-mode tool invocation (including spawn-standing)." Check whether the current prose has an imperative "MUST call TeamCreate before X" for each team-mode operation.
2. **Sequencing ambiguity** — the FO reads the workflow's _mods at boot, sees `standing-teammate` entries, and may race to `spawn-standing` before completing `TeamCreate`. The runtime adapter may allow either order.
3. **Model-specific rendering** — haiku may parse a conditional "if in teams mode, TeamCreate first" less reliably than opus; unconditional language would be more robust.
4. **Upstream coverage gap** — no existing test asserts "FO always calls TeamCreate before spawn-standing in teams mode." A new test predicate could catch this pre-prose-fix.

**Fix shape — multi-layer (ranked by leverage):**

### L1 — `status --boot` surfaces team state (highest leverage)

Currently returns `MODS / NEXT_ID / ORPHANS / PR_STATE / DISPATCHABLE`. Add a `TEAM_STATE` section:

```
TEAM_STATE
present: false
hint: run TeamCreate before first dispatch (claude runtime supports it)
```

Every session boot surfaces the team question explicitly, regardless of how the FO entered (commission pilot, fresh start, resume). Converts a silent skip into an active decision. Works for all three observed cases simultaneously.

### L2 — `claude-team build` warns or refuses on first bare dispatch without prior TeamCreate evidence

When called with `bare_mode: true` AND no prior TeamCreate attempt has been recorded for this session (e.g., via a session-state file under `~/.claude/teams/` or a new `claude-team session-state` check), either:
- Emit stderr warning: `WARN: dispatching bare with no recorded TeamCreate attempt; this is unusual on Claude runtime — run ToolSearch select:TeamCreate first or pass --intentional-bare to suppress`
- OR refuse to build, requiring `--intentional-bare` flag

Converts silent skip into deliberate choice. Needs helper to track session state (small change).

### L3 — FO prose tightening (original task scope)

- `references/claude-first-officer-runtime.md`: an unconditional "TeamCreate MUST be the first team-mode tool call before any spawn-standing / Agent / SendMessage invocation." Present it as Step 1 of the startup sequence, not buried prose.
- Mirror the imperative in `skills/first-officer/SKILL.md` at the visibility level where haiku reliably reads it.

### L4 — Commission skill Phase 3 explicit team-probe step

`skills/commission/SKILL.md` Phase 3 Step 2 currently says "execute the first-officer startup procedure directly." Replace with an explicit numbered step:

```
Step 2 — Team Probe
Before any dispatch:
- Run ToolSearch(query="select:TeamCreate", max_results=1)
- If found, run TeamCreate(...) and record team_name
- Forward team_name into the pilot dispatch
```

This targets Case A directly (commission-to-FO handoff) without requiring the FO to inherit discipline from the runtime adapter alone.

### L5 — `claude-team spawn-standing` rejects empty/none team name (mechanism guard)

The narrow boundary guard from the original filing. Refuses `--team none` / `--team ""`, emits `requires a real team name; call TeamCreate first`. Catches the PR #132 CI evidence shape at the helper boundary.

### L6 — Static test locking in prose

`tests/test_runtime_prose_teamcreate_first` (name suggestive): grep the skill-preloaded FO contract for the "TeamCreate first" imperative. Locks L3 against regression.

### Out-of-scope — platform / harness layer

Pre-loading team primitives (`TeamCreate`, `SendMessage`, `TeamDelete`) on the first-officer agent type is a Claude Code platform concern, not a Spacedock code change. File upstream if warranted. Similarly, `TeamAdopt` (promote a running bare Agent into a team) is a platform feature request. Note both in "out of scope" and optionally cross-reference a platform issue.

## Acceptance criteria

**AC-1 — `status --boot` reports a `TEAM_STATE` section.**
Verified by: `status --boot --workflow-dir <wd>` output includes a `TEAM_STATE` block with at minimum a `present: true|false` line. The block's format is structured/greppable (not free prose). When absent, the hint line names TeamCreate.

**AC-2 — `claude-team build` warns or refuses first bare dispatch without prior TeamCreate evidence.**
Verified by: `claude-team build` called with `bare_mode: true` AND no recorded session TeamCreate either (a) emits a stderr warning naming the omission and suggesting the flag, or (b) exits non-zero unless `--intentional-bare` is passed. Captain chooses warn-vs-refuse during implementation.

**AC-3 — FO runtime adapter names TeamCreate-first unconditionally.**
Verified by: `grep -n 'TeamCreate' skills/first-officer/references/claude-first-officer-runtime.md` returns a match where TeamCreate is named as the FIRST team-mode tool call, presented as Step 1 of an explicit startup sequence (not buried prose, not conditional).

**AC-4 — Commission Phase 3 has an explicit Team Probe step.**
Verified by: `grep -n 'Team Probe\|ToolSearch.*TeamCreate' skills/commission/SKILL.md` returns a match inside Phase 3 (pilot-run) prose. The step names `ToolSearch(query="select:TeamCreate")` as the probe verb and gives a conditional action (if found, call TeamCreate; forward team_name).

**AC-5 — `claude-team spawn-standing` rejects empty/none team name.**
Verified by: `claude-team spawn-standing --mod path --team none` exits non-zero with stderr containing "requires a real team name" or equivalent. `--team ""` same behavior.

**AC-6 — Static test locks in the TeamCreate-first prose.**
Verified by: a new static test (name suggestive, e.g., `test_runtime_prose_names_teamcreate_first` in `tests/test_claude_team.py` or similar) greps the skill-preloaded FO contract for the imperative and fails if the prose weakens.

**AC-7 — Static suite green post-merge.**
Verified by: `make test-static` passes on main after the implementation.

**AC-8 — Behavioral spot-check (optional).**
Verified by: one live haiku-teams dispatch of `test_standing_teammate_spawn` reaches Phase 2 Agent dispatch without hitting the "team_name null" failure mode. ~$1, deferrable.

## Out of scope

- Fixing opus-4-7-specific ECHO roundtrip flakiness — #194 owns that.
- Fixing haiku-bare guardrail weaknesses — #200 owns those.
- Fixing `claude-team build` template emission — not broken.
- Rewriting the FO contract end-to-end — this task is targeted at TeamCreate-bootstrap ergonomics, not full FO redesign.
- **Claude Code platform changes** — pre-loading team primitives (TeamCreate, SendMessage, TeamDelete) on the `first-officer` agent type so they aren't deferred tools; `TeamAdopt` primitive to promote a running bare Agent into a team; symmetric dispatch cost for team-mode vs bare Agent. These require upstream Claude Code changes, not Spacedock-side code. File as upstream issues separately if the in-scope L1-L6 layers prove insufficient.
- **FO decision matrix in the skill** ("1 worker → bare; 2+ coordinated workers → team"). Broader skill redesign; may belong to a future skill-polish task. L1-L4 address the "is team state established" question without requiring an explicit decision matrix.

## Cross-references

- **#194** — opus-4-7 standing-teammate roundtrip flakiness. Adjacent failure class; distinct scope.
- **#200** — haiku-bare FO behavioral weaknesses on guardrail suite. Different tests, different failure modes.
- **#190** (archived) — PR #132's claude-live failure is the concrete motivating evidence for this task.
- CI artifact: run `24612094887`, claude-live job. Test dir `spacedock-test-co13e139`. Key lines in fo-log.jsonl show `spawn-standing --team none` and `build` with null `team_name`.
- `skills/commission/bin/claude-team` lines 276-308 (standing section emission), 311 (completion signal guard), 526-527 (enumerate early-return on falsy team_name).
