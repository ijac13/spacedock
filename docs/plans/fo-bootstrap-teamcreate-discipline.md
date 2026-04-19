---
id: 201
title: "FO bootstrap discipline — skipped TeamCreate in teams-mode sessions (multi-layer ergonomics)"
status: ideation
source: "session 2026-04-18 — three observations. (1) PR #132 CI haiku-teams job FO invoked `spawn-standing --team none` + `build` with `team_name: null, bare_mode: true`. (2) Separate captain-documented case: commissioned session FO skipped the team probe entirely at boot, defaulted to bare. (3) Research-pipeline session FO dispatched 10 parallel Agent() calls without ever invoking TeamCreate, paying a real entity-file collision cost. All three defaulted to bare by omission, not by design."
started: 2026-04-19T01:33:07Z
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

## Observed skipping behaviors

Three independent fresh-commissioned sessions defaulted to bare by omission (not design):

1. **PR #132 CI haiku-teams** — FO invoked `spawn-standing --team none` and `build` with `team_name: null, bare_mode: true`. Failed `test_standing_teammate_spawn` with a missing standing-teammates prompt section.
2. **Commissioned single-entity pilot** — FO skipped the team probe at boot; built first dispatch with `bare_mode: true, team_name: null`. Single-entity path, so no failure forced course-correction.
3. **Multi-worker research-pipeline session** — FO dispatched ~10 parallel `Agent(background)` calls without invoking `TeamCreate` once. Paid a real cost: two ensigns edited the same entity file concurrently and produced duplicated sections requiring post-hoc deduplication.

**Shared pattern:**

- FO started without an explicit team state.
- No forcing function at dispatch time asked "did you set up a team?"
- Bare mode was functional for the immediate task; no feedback signal corrected the omission.
- The skip compounded: once bare, downstream team-dependent primitives (`spawn-standing`, `SendMessage` coordination) were silently unavailable or malformed.

This isn't a prose-only problem. It's a multi-layer ergonomics gap: FO prose + harness tool-loading defaults + helper binary behavior + commission skill Phase 3 prose.

## Feedback Cycles

### Cycle 1 — 2026-04-19 light-verify rejected as insufficient

Cycle 1 ideation did anchor verification + sanity-checked L1-L6 layers + confirmed AC↔layer 1:1 mapping. Useful but incomplete.

**Captain rejection rationale:** ideation must do an actual spike (reproduce the targeted TeamCreate-skip failure) AND incorporate the failure mode into tests **before** contemplating fixes. The cycle-1 output jumped straight to describing fix layers without a deterministic reproducer or a failing-test-first discipline. Fixes without failing tests risk shipping prose/code that reads sensible but doesn't demonstrably close the observed behavior.

**Cycle 2 scope:** execute the `## Spike and test-first plan` section — reproduce the skip, land failing tests for L1-L5, then the fix surface becomes well-grounded (tests are the gate).

## Spike and test-first plan (pre-fix)

Before contemplating fixes, ideation must (a) reproduce the FO TeamCreate-skip pattern deterministically in a local or CI-reachable setup, and (b) capture the failure modes as tests that fail against current code. Only after failing tests are in place should fix surfaces be finalized.

**Spike — reproduce the skip pattern:**

- Smallest reproducer: invoke the FO (via `make test-live-claude` selector or a standalone harness) against a fixture that contains a standing-teammate mod, with `--runtime claude --model claude-haiku-4-5 --team-mode=teams`. Observe fo-log.jsonl for the TeamCreate sequence.
- Secondary target: confirm the `claude-team spawn-standing --team none` shape exits successfully today (silent empty). The PR #132 CI artifact is evidence of the failure; a local invocation deterministically reproduces the boundary behavior.
- Acceptable evidence: one fresh-session fo-log dump showing Agent dispatch without preceding TeamCreate, OR a direct `claude-team spawn-standing --team none` invocation returning with code 0.

**Failing tests to land with this PR (before fixes):**

Each test must FAIL against `main` at the cycle-2 branch base, and PASS after the corresponding fix ships. This is the AC bar.

1. **L1 test — `status --boot` TEAM_STATE section.** Test parses `status --boot` output and asserts a `TEAM_STATE` header line exists. Today: no such line → test fails.
2. **L2 test — `claude-team build` signals on bare-without-evidence.** Test pipes a `bare_mode: true, team_name: null` input into `claude-team build` and asserts either (a) non-zero exit + specific stderr OR (b) stderr warning + zero exit. Today: silent zero → test fails.
3. **L3 test — runtime adapter prose asserts TeamCreate-first.** Grep test for the stronger imperative + `spawn-standing` named in the sequencing rule. Today's prose at `claude-first-officer-runtime.md:10-12` presents TeamCreate as step 2-3 and doesn't name spawn-standing → test fails (verifies the delta cycle-1 worker found).
4. **L4 test — commission Phase 3 has explicit Team Probe step.** Grep `skills/commission/SKILL.md` for `Team Probe` or `ToolSearch.*TeamCreate` inside Phase 3. Today: absent → test fails.
5. **L5 test — `spawn-standing` rejects empty/none team.** CLI-level test: invoke with `--team none` and `--team ""`; assert non-zero exit + specific stderr. Today: exits 0 with empty output → test fails.

**Behavioral spike test (optional but recommended):** one live haiku-teams invocation asserting fo-log shows `TeamCreate` tool_use before any `claude-team spawn-standing` invocation. Covers the end-to-end FO discipline, not just helper boundaries.

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

## Stage Report

Ideation light-verify (score 0.6, no staff review). Checklist items below.

### 1. Anchor file + edit-site verification — DONE

All six anchors exist and edit sites resolve:

- **L1 `status --boot`** — output shape confirmed at `skills/commission/bin/status:659-702` (`print_boot`). Current sections: `MODS`, `NEXT_ID`, `ORPHANS`, `PR_STATE`, `DISPATCHABLE`. Each section is printed as a header line with structured rows below. A new `TEAM_STATE` sibling section fits cleanly — insert after `DISPATCHABLE` (or before, per style preference). The header `--boot` option is wired in `status:1215` and downstream. No structural obstacle.
- **L2 `claude-team build` bare_mode handling** — `cmd_build` is at `skills/commission/bin/claude-team:77`, with `bare_mode = inp.get('bare_mode', False)` at line 111 and existing `not bare_mode and not team_name` guard at line 206. Injection point for a "first bare dispatch without TeamCreate evidence" check sits naturally between line 111 (bare_mode read) and line 206 (existing team_name guard). See item 2 below for the cost concern.
- **L3 FO runtime TeamCreate-first prose** — `skills/first-officer/references/claude-first-officer-runtime.md:10-12` already presents TeamCreate as step 2-3 of the startup sequence ("Probe for team support: `ToolSearch(query="select:TeamCreate", max_results=1)`" then "If the result contains a TeamCreate definition, run `TeamCreate(...)`"). Also covered by line 20+ recovery ladder and line 26 "Block all Agent dispatch until team setup resolves." **Finding:** the prose is NOT buried — it is already step 2. L3's useful delta is (a) promoting the probe/TeamCreate to **Step 1** of the sequence explicitly, (b) strengthening the "MUST call TeamCreate before any `spawn-standing` invocation" — `spawn-standing` is not currently named by the sequencing rule at line 69. The fix surface is narrower than "unconditional imperative where none exists" — it is "promote to Step 1 + name spawn-standing in the sequencing rule." AC-3's grep verifier is still satisfiable with this tightening.
- **L4 Commission Phase 3 Team Probe** — `skills/commission/SKILL.md:398` begins Phase 3. Step 2 "Assume First-Officer Role" is at line 424-431 with the "Execute the first-officer startup procedure directly" sentence at line 431. Insertion point for an explicit "Team Probe" step between "Assume First-Officer Role" and "Monitor and Report" (line 433), OR as an inline bullet inside Step 2 after line 429. Either shape satisfies AC-4.
- **L5 `spawn-standing` boundary guard** — `cmd_spawn_standing` at `skills/commission/bin/claude-team:676`. `team_name = args.team` at line 694. Guard goes immediately after line 694: reject when `not team_name` OR `team_name in ('none', 'None', '')`. The PR #132 evidence was literal string `none`; that case is a two-line check.
- **L6 Static test location** — `tests/test_claude_team.py` (1712 lines) exists as sibling. Pattern for prose-greps already established (per `test_status_sibling_import_*` references in `claude-team:19`). New test fits naturally.

### 2. L2 session-state sanity-check — DONE with concern

**Finding:** `claude-team` is stateless. It does not maintain a session-state file across invocations. The binary reads input JSON, writes output JSON, exits. No persistent state mutation in `cmd_build`.

**Existing state that could serve as "TeamCreate evidence":**
- `~/.claude/teams/*/config.json` exists and contains `leadSessionId` (referenced in `claude-team:422`). A team directory under `~/.claude/teams/` with a non-empty `config.json` is evidence that `TeamCreate` was called at some point.
- BUT — `claude-team build` has no knowledge of the **current Claude Code session ID**. Claude Code does not pass a session-id env var to helper binaries (verified: no `CLAUDE_SESSION_ID`, `CLAUDE_TEAM`, or similar sentinel used in `claude-team`). So `claude-team build` cannot distinguish "TeamCreate was called in THIS session" from "a team exists from some prior session."

**Cheapest plausible shapes, ranked:**

a. **Ambient-presence check (cheapest, works, slight false-negative risk):** If `~/.claude/teams/` contains at least one directory whose `config.json` has `leadSessionId` set AND was modified within the last N minutes (e.g., 30m), treat as "recent TeamCreate evidence." Warn otherwise. **Cost: ~15 lines.** Weakness: a fresh session that starts immediately after a prior team-enabled session passes silently; a long-running session whose TeamCreate was hours ago triggers the warning spuriously. Acceptable for a warn-only signal.

b. **Env-var sentinel (simplest, needs FO cooperation):** FO sets `CLAUDETEAM_INTENTIONAL_BARE=1` (or `CLAUDETEAM_TEAM_NAME=<name>`) before invoking `claude-team build`. Helper reads the env var. **Cost: ~5 lines.** Weakness: the FO omitting TeamCreate is also likely to omit setting the sentinel — does not catch the observed skip cases.

c. **Marker file under workflow-dir (new infrastructure):** Track session state in `workflow_dir/.claude-team-session` or under `/tmp`. **Cost: ~30 lines + tests + cleanup policy.** New infrastructure, rejected per checklist guidance.

**Recommendation:** Adopt shape (a) — ambient-presence check via `~/.claude/teams/*/config.json` mtime. It is cheap, reuses existing state, and the false-negative risk is acceptable for a **warn-only** L2 (not refuse). If the captain insists on refuse-semantics, shape (a) is too fuzzy and L2 should either drop the session-state check entirely (refuse ALL bare dispatch unless `--intentional-bare` is passed) or be deferred.

**Alternative (if captain prefers not to touch helper state semantics at all):** drop L2, rely on L1 (boot surfaces team state), L3 (prose names spawn-standing sequencing), L4 (commission Phase 3 explicit probe). This is a defensible simplification — L1 alone converts silent skip into an actively visible boot-time fact, which addresses the root cause (no forcing function at session boot).

**Concrete suggestion for captain:** reframe AC-2 as "warn-only with ambient-presence check" OR drop L2/AC-2 and rely on L1+L3+L4. The refuse-semantics path materially inflates implementation.

### 3. AC ↔ L layer mapping — DONE

1:1 mapping verified, no orphans:

| AC | L layer | Maps cleanly? |
|---|---|---|
| AC-1 `status --boot` TEAM_STATE | L1 | yes |
| AC-2 `claude-team build` warn/refuse | L2 | yes — but see item 2 concern re: refuse-semantics cost |
| AC-3 runtime adapter TeamCreate-first | L3 | yes — with the caveat that prose tightening is narrower than "add imperative where absent" (see item 1 L3 finding) |
| AC-4 Commission Phase 3 Team Probe | L4 | yes |
| AC-5 `spawn-standing` rejects empty/none | L5 | yes |
| AC-6 Static test locks prose | L6 | yes |
| AC-7 `make test-static` green | cross-cutting | meta-AC, not orphan |
| AC-8 optional haiku-teams spot-check | behavioral | meta-AC, deferrable |

No un-ACd layer, no orphan AC. Mapping is clean.

**Score calibration (item 3 addendum):** Current 0.6 assumes warn-only L2 with ambient-presence check (~$3-5 total: L1 ~$1, L2 ~$1 if warn-only, L3 ~$0.50, L4 ~$0.50, L5 ~$0.50, L6 ~$0.50, tests/verification ~$1). If captain chooses refuse-semantics L2 with a proper session-state primitive, cost rises to ~$8-12 and score should lift to 0.7-0.8. If L2 is dropped entirely, cost drops to ~$3 and score stays at 0.6 or drops to 0.5. Current 0.6 is appropriate for the warn-only interpretation; flag for captain to confirm the L2 shape at exit.

### Summary

All L1-L6 anchor files and edit sites exist and are resolvable. L1, L3, L4, L5, L6 have clean, bounded fix surfaces. **L2 has a material cost concern** — `claude-team build` is stateless and Claude Code does not pass a session ID to helper binaries, so "recorded TeamCreate attempt this session" requires either (a) an ambient-mtime heuristic on `~/.claude/teams/*/config.json` (cheap, warn-only, slight false-negative risk — recommended), (b) an env-var sentinel (cheap but doesn't catch the observed skip pattern), or (c) new marker-file infrastructure (rejected as new infrastructure). Also noted: L3's runtime adapter already presents TeamCreate as step 2 of startup — L3's useful delta is promoting it to Step 1 and naming `spawn-standing` in the existing sequencing rule at line 69, rather than adding a net-new imperative. AC↔L mapping is 1:1 with no orphans. Score 0.6 is appropriate if L2 lands warn-only; captain should confirm L2 shape before implementation.
