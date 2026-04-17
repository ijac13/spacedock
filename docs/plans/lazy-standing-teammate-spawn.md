---
id: 172
title: "Lazy-spawn standing teammates on first routing, not at boot"
status: validation
source: "CL directive during 2026-04-16 session — eager comm-officer spawn adds a sonnet Agent() cold-start to every boot even when no polish is requested"
started: 2026-04-16T20:27:03Z
completed:
verdict:
score: 0.65
worktree: .worktrees/spacedock-ensign-lazy-standing-teammate-spawn
issue:
pr: #107
mod-block: merge:pr-merge
---

## Problem Statement

The Claude FO runtime adapter (`claude-first-officer-runtime.md` lines 34-43) mandates that standing teammates be spawned eagerly — after `TeamCreate` succeeds and before the normal dispatch event loop begins. Every FO session therefore pays one `Agent()` cold-start per standing teammate at boot, regardless of whether any dispatched ensign or the FO itself ever routes work to that teammate.

In the current workflow, the only standing teammate is `comm-officer` (sonnet). Its cold-start adds wallclock time and token cost to every session boot. In sessions where no polish is requested — a quick task-filing session, a pure gate-review session, or a session that dispatches only bare-mode entities — this cost is pure waste.

## Observed cost (2026-04-16 session)

The comm-officer was spawned at boot. Its first actual polish request arrived roughly 20 minutes later (when #167's task body was routed for polish-and-write). In the intervening time it sat idle, having consumed one `Agent()` spawn round-trip plus its ToolSearch probe and online notification — all before the FO had dispatched its first ensign.

## Current design rationale (from the runtime adapter)

The eager-spawn design exists for three reasons documented in the adapter:

1. **first-boot-wins lifecycle** — early name-binding so the teammate's slot is claimed before a second workflow in the same captain session might spawn its own instance.
2. **Message queueing** — Claude Code queues `SendMessage` to an agent that exists but has not completed its first turn yet. If the teammate does not exist at all, the message fails.
3. **Amortized cost** — spawn cost is paid once and amortized across all polish requests in the session.

Reasons (1) and (3) remain valid for long sessions with heavy polish traffic. Reason (2) is the hard constraint: if we defer spawn until first routing, the first `SendMessage` will fail because the teammate does not exist yet.

## Proposed direction

Lazy spawn by default: defer `Agent()` for each standing teammate until the first `SendMessage` is about to be sent to it. The FO (or the ensign) checks whether the teammate exists before routing; if absent, spawns it, waits for the name to register, then sends the message. Subsequent routes to the same teammate hit the live member with no extra cost.

## Open questions for ideation

- How does the FO or ensign detect "teammate doesn't exist yet"? Options: (a) check team config members list, (b) try `SendMessage` and catch the failure, (c) maintain a session-memory set of spawned names.
- Does `SendMessage` to a non-existent teammate fail gracefully (returnable error) or hard-fail (tool error the model must recover from)? If (b), is the recovery path reliable enough for production?
- First-boot-wins under lazy spawn: if two workflows share a team and both try to lazy-spawn the same teammate on their first route, one will race. The eager design avoids this because boot is sequential. Does lazy spawn need a mutex, or is the race benign (first spawn wins, second detects `already-alive`)?
- Should lazy spawn be the default for all standing teammates, or configurable per mod (e.g., `eager: true` in `_mods/` frontmatter for teammates that benefit from warm-start)?
- What changes in the runtime adapter prose? The "Standing teammate spawn pass" section would become a "Standing teammate lazy-spawn protocol" section. `claude-team list-standing` still runs at boot to discover available teammates, but `claude-team spawn-standing` defers to first use.
- Does this interact with the dispatch-prompt `### Standing teammates available in your team` section (#166)? Today that section is populated from `enumerate_alive_standing_teammates`, which checks `member_exists`. Under lazy spawn, the teammate will not be alive at dispatch time. The section would need to enumerate *declared* teammates (from `list-standing`), not *alive* ones.

## Out of Scope

- Changing the standing-teammate mod schema.
- Removing the eager-spawn option entirely — some teammates may benefit from warm-start.
- Codex runtime equivalents.

## Decision

**Lazy spawn by default. Spawn inline on first routing attempt, gated by `member_exists`.**

### Detection mechanism: option (a) — `member_exists` check

Option (b) try-and-catch is rejected. `SendMessage` to a non-existent teammate produces a hard tool error (observed in testflight-005: "SendMessage instead of Agent: first officer sends messages to non-existent teammates"). Recovery from tool errors is model-dependent and unreliable. Option (c) session-memory set is viable but redundant — `member_exists` already reads `~/.claude/teams/{team}/config.json` and is the authoritative aliveness signal. No new mechanism needed; just call `member_exists` before each `SendMessage` routing and spawn-if-absent.

### First-boot-wins under lazy spawn: race is benign

Two concurrent lazy-spawners (e.g., FO and an ensign both route to `comm-officer` for the first time simultaneously) would both find `member_exists` returns false, both call `spawn-standing`, and both attempt `Agent()`. The first `Agent()` to complete registers the name in team config. The second `Agent()` will fail with a name collision. The caller treats this the same as `already-alive`: skip the spawn, proceed with `SendMessage`. The `spawn-standing` helper already handles the `already-alive` case at exit 0 — the lazy-spawn protocol adds a second recovery path for the name-collision error from `Agent()`.

In practice, this race is unlikely. The FO is the only actor that calls `spawn-standing` directly. Ensigns route via `SendMessage` and rely on the `### Standing teammates available in your team` prompt section to know teammates exist — they never spawn directly. The FO is single-threaded in its dispatch loop, so two concurrent FO-initiated spawns of the same teammate cannot occur.

### `eager: true` opt-in

Not needed in v1. The only standing teammate today is `comm-officer` (sonnet), which is a pure request-response polish service with no warm-up benefit. If a future teammate needs preloading (e.g., a science officer that reads a large corpus at startup), `eager: true` in mod frontmatter can be added as a follow-up. Out of scope here — YAGNI.

### Dispatch-prompt interaction (#166)

Today `enumerate_alive_standing_teammates` filters by `member_exists`, so the `### Standing teammates available in your team` section in `claude-team build` output only includes alive teammates. Under lazy spawn, teammates are not alive at dispatch time. The section must enumerate *declared* teammates (from mod metadata), not *alive* ones. Rename and rewrite `enumerate_alive_standing_teammates` to `enumerate_declared_standing_teammates` — drop the `member_exists` filter. The payload (name, description, mod_path, routing usage) stays identical; only the aliveness gate is removed.

This is correct because the ensign's routing contract is already best-effort non-blocking with a 2-minute timeout. Whether the teammate is alive or merely declared, the ensign's behavior is the same: send a `SendMessage`, proceed if no reply. The only difference is that under lazy spawn, the FO must intercept the first routing attempt and spawn the teammate before the message is delivered. Since ensigns cannot spawn teammates themselves (they don't have access to `spawn-standing`), the FO's lazy-spawn intercept is the only spawn path.

**Wait — ensigns route directly via `SendMessage`.** If the teammate is declared-but-not-alive and an ensign sends a `SendMessage`, it will fail (hard tool error). The ensign cannot spawn the teammate. This is the critical gap.

**Resolution:** Two options:

1. **FO spawns on first `build` call** — when `claude-team build` assembles the dispatch prompt and finds declared-but-not-alive teammates, it spawns them before emitting the prompt. This front-loads the spawn to ensign dispatch time rather than session boot time. Still lazy (deferred from boot to first dispatch that might need the teammate), but the teammate is alive before the ensign runs.
2. **Ensigns never route; only the FO routes** — change the routing contract so ensigns produce un-polished content and the FO polishes after receiving the stage report. This is a bigger change.

Option 1 is the right call. The spawn moves from "FO boot" to "first `build` invocation that emits a standing-teammate prompt section." This is lazier than eager (skips sessions with zero dispatches or bare-mode dispatches) but ensures the teammate is alive before any ensign tries to route to it. The FO calls `spawn-standing` inline, between the `build` output and the `Agent()` dispatch, on the first dispatch only.

Actually, option 1 is still eager relative to the ensign's actual need — it spawns the teammate when the *first ensign is dispatched*, not when the *first polish request is sent*. But it's the minimum viable lazy: it avoids the boot-time cost for sessions that never dispatch (task-filing, gate-review), and it avoids spawning for bare-mode dispatches. The teammate is spawned at most once and only when team-mode dispatch actually happens.

**Revised decision:** Lazy spawn triggers at **first team-mode `Agent()` dispatch**, not at boot and not at first `SendMessage`. The FO checks `member_exists` before dispatching the first ensign. If the teammate is absent, the FO runs `spawn-standing` inline, then dispatches the ensign. Subsequent dispatches skip the check (the teammate is alive). The `### Standing teammates available in your team` section in the dispatch prompt continues to enumerate declared teammates, so ensigns always know the teammate exists and can route to it.

## Protocol

### Boot phase (changed)

1. `claude-team list-standing --workflow-dir {wd}` still runs at boot. The FO records the list of declared standing-teammate mod paths in session memory. **No `spawn-standing` calls at boot.**
2. The standing-teammate spawn pass section in the runtime adapter becomes a "Standing teammate discovery pass" — enumerate, record, defer.

### First team-mode dispatch (new)

Before the first `Agent()` call that uses a `team_name` (i.e., the first non-bare dispatch):

1. For each declared standing-teammate mod path recorded at boot:
   a. Run `claude-team spawn-standing --mod {mod_path} --team {team_name}`.
   b. If `status: "already-alive"` — skip (another workflow in this captain session already spawned it).
   c. Otherwise, forward the Agent() spec verbatim. Fire-and-forget, same as the current eager pass.
2. After all standing teammates are spawned (or skipped), proceed with the ensign `Agent()` dispatch.

This is a one-time cost at first dispatch. Subsequent dispatches skip the spawn pass entirely — the FO tracks "standing teammates spawned for this team" in session memory.

### `claude-team build` change

`enumerate_alive_standing_teammates` becomes `enumerate_declared_standing_teammates`:

- Drop the `member_exists` call inside the loop.
- Return all declared standing teammates from mod metadata, regardless of team membership.
- The output shape `[(name, description, mod_path)]` is unchanged.
- The `### Standing teammates available in your team` section preamble changes from "The FO has spawned these standing teammates" to "These standing teammates are available in your team" (reflecting that they may or may not be alive yet, but will be by the time the ensign runs).

### FO routing (unchanged)

The FO's own routing (shared-core Dispatch section, line 82) already gates on `member_exists` before routing. Under lazy spawn, this check is still correct: by the time the FO routes, the teammate was spawned at first dispatch. If the teammate died mid-session, `member_exists` returns false and the FO proceeds with un-polished text (existing contract).

### Ensign routing (unchanged)

Ensigns route via `SendMessage` to named teammates listed in their dispatch prompt. The teammate is guaranteed alive because the FO spawned it before dispatching the ensign. The best-effort non-blocking contract is unchanged.

## Changes Required

### 1. Runtime adapter prose (`claude-first-officer-runtime.md`)

- Rename `### Standing teammate spawn pass` to `### Standing teammate discovery pass`.
- Replace the 6-step eager-spawn protocol with a 2-step discovery protocol: (1) run `list-standing`, (2) record mod paths in session memory.
- Add a new subsection `### Standing teammate lazy-spawn` after the discovery pass, describing the first-dispatch spawn trigger.
- Update the single-entity/bare-mode/Degraded-Mode skip note: discovery still runs (it's cheap — just `list-standing`), but lazy-spawn is skipped in those modes (no team to spawn into).

### 2. Shared-core prose (`first-officer-shared-core.md`)

- Update the `## Standing Teammates` section's first-boot-wins bullet to note that spawn is deferred to first dispatch, not boot.
- Update the FO routing paragraph (line 82) to note that `member_exists` check now also serves as the post-lazy-spawn aliveness confirmation.

### 3. `claude-team` helper code (`skills/commission/bin/claude-team`)

- Rename `enumerate_alive_standing_teammates` to `enumerate_declared_standing_teammates`.
- Remove the `member_exists` call inside the enumeration loop.
- Update the docstring to reflect the new semantics.
- Update `cmd_build` call site (line 277) to use the new function name.

### 4. Tests

- Update `test_standing_teammate_prose.py` — the heading grep test changes from `Standing teammate spawn pass` to `Standing teammate discovery pass`.
- Update any tests that assert on `enumerate_alive_standing_teammates` by name.
- Add a unit test for `enumerate_declared_standing_teammates` confirming it returns entries without checking `member_exists`.

## Acceptance Criteria

### AC-1: Boot no longer calls `spawn-standing`

The runtime adapter prose must not invoke `claude-team spawn-standing` in the boot/discovery pass. The heading changes from `### Standing teammate spawn pass` to `### Standing teammate discovery pass`. Only `list-standing` runs at boot.

**Test:** Static grep test — assert `spawn-standing` does not appear in the discovery-pass section. Assert the new heading exists.

### AC-2: Lazy-spawn triggers at first team-mode dispatch

The runtime adapter prose describes a `### Standing teammate lazy-spawn` subsection that runs `spawn-standing` for each declared teammate before the first `Agent()` call with a `team_name`.

**Test:** Static grep test — assert the new subsection heading exists, assert it mentions `spawn-standing` and `member_exists`.

### AC-3: `enumerate_declared_standing_teammates` replaces `enumerate_alive_standing_teammates`

The function is renamed and the `member_exists` filter is removed. The return shape is unchanged.

**Test:** Unit test — create a mock workflow with a `standing: true` mod, call `enumerate_declared_standing_teammates` without any team config on disk, assert the mod is returned. This would have returned empty under the old function.

### AC-4: Dispatch prompt enumerates declared teammates

`cmd_build` calls `enumerate_declared_standing_teammates`. The `### Standing teammates available in your team` section preamble reads "These standing teammates are available" (not "The FO has spawned these").

**Test:** Unit test — run `cmd_build` with a standing mod but no team config member, assert the section appears in the output prompt. Static grep test for the preamble wording.

### AC-5: Shared-core prose updated

The `## Standing Teammates` section mentions deferred spawn. The FO routing paragraph still references `member_exists`.

**Test:** Static grep test — assert "deferred" or "lazy" appears in the Standing Teammates section. Assert `member_exists` still appears in the Dispatch section.

### AC-6: Single-entity, bare-mode, and Degraded Mode skip lazy-spawn

The runtime adapter prose states that lazy-spawn is skipped in these modes (same as the current eager-spawn skip).

**Test:** Static grep test — assert the skip conditions are documented in or near the lazy-spawn subsection.

### AC-7: Existing tests pass after rename

All tests in `test_standing_teammate_prose.py`, `test_claude_team_spawn_standing.py`, `test_claude_team_list_standing.py`, and `test_standing_teammate_spawn.py` pass (with updates for the heading rename and function rename).

**Test:** Run the full test suite.

## Test Plan

| AC | Test type | Cost | Notes |
|----|-----------|------|-------|
| AC-1 | Static grep (prose) | Low | Existing pattern from `test_standing_teammate_prose.py` |
| AC-2 | Static grep (prose) | Low | New test class |
| AC-3 | Unit test (Python) | Low | Mock filesystem, no live team |
| AC-4 | Unit test (Python) | Medium | Existing `test_claude_team_spawn_standing.py` patterns, needs fixture without team config |
| AC-5 | Static grep (prose) | Low | Extension of existing shared-core tests |
| AC-6 | Static grep (prose) | Low | Check skip-condition prose |
| AC-7 | Test suite run | Low | `pytest tests/` |

No E2E tests needed. All changes are prose (runtime adapter, shared-core) and a single function rename with filter removal in the helper. The behavioral change (spawn timing) is enforced by prose instructions to the FO model, not by code — static grep tests verify the prose says what we intend.

## Stage Report

1. Read the full entity body — DONE. Read problem statement, observed cost, current design rationale, proposed direction, open questions, out of scope.
2. Read the runtime adapter's standing-teammate spawn pass (lines 32-43) and shared-core Standing Teammates section — DONE. Understood the 6-step eager protocol, fire-and-forget discipline, already-alive handling, and the four concept areas (first-boot-wins, team-scope lifecycle, routing contract, declaration format).
3. Read `claude-team` helper's `enumerate_alive_standing_teammates` and `spawn-standing` — DONE. Understood `member_exists` checks team config.json on disk, enumeration filters by aliveness, `spawn-standing` returns `already-alive` JSON or Agent() spec.
4. Investigate SendMessage to non-existent teammate — DONE. Confirmed it is a hard tool error, not a graceful returnable error. Evidence from testflight-005 observation and the entity file's own analysis. Option (b) try-and-catch is not viable for production.
5. Design the lazy-spawn protocol — DONE. Addressed all open questions: (a) detection via `member_exists`, (b) race is benign but practically impossible since only FO spawns, (c) dispatch prompt enumerates declared not alive teammates, (d) `eager: true` deferred as YAGNI. Key design decision: spawn at first team-mode dispatch, not at first `SendMessage`, to avoid the ensign-cannot-spawn gap.
6. Specify changes — DONE. Four change areas: runtime adapter prose, shared-core prose, `claude-team` helper code (function rename + filter removal), tests.
7. Acceptance criteria with test strategy — DONE. Seven ACs, all testable with static grep or unit tests. No E2E needed.
8. Updated entity body — DONE. Added Decision, Protocol, Changes Required, Acceptance Criteria, Test Plan, and Stage Report sections.
9. Stage Report — DONE (this section).

**Recommendation:** Ready for ideation gate review. The design is minimal (prose changes + one function rename), addresses all open questions, and avoids the ensign-cannot-spawn pitfall that a naive "spawn on first SendMessage" approach would hit.

## Stage Report (implementation)

1. Read the entity ideation output (Decision, Protocol, Changes Required, AC-1 through AC-7, Test Plan) — DONE. All sections read and understood as the implementation spec.
2. Rename `enumerate_alive_standing_teammates` to `enumerate_declared_standing_teammates` — DONE. Removed `member_exists` call inside the loop. Updated docstring to reflect declared-not-alive semantics. Updated `cmd_build` call site. Updated `cmd_list_standing` docstring cross-reference. Return shape `[(name, description, mod_path)]` preserved.
3. Update preamble in `cmd_build` — DONE. Changed from "The FO has spawned these standing teammates" to "These standing teammates are available in your team".
4. Update `claude-first-officer-runtime.md` — DONE. (a) Renamed heading to `### Standing teammate discovery pass`, replaced 6-step eager protocol with 2-step discovery (list-standing + record mod paths, no spawn at boot). (b) Added `### Standing teammate lazy-spawn` subsection describing first-dispatch trigger with `spawn-standing`, `already-alive` handling, fire-and-forget discipline. (c) Updated bare-mode/single-entity/Degraded Mode skip notes: discovery still runs, lazy-spawn skipped.
5. Update `first-officer-shared-core.md` — DONE. (a) Updated Standing Teammates intro and first-boot-wins bullet to note spawn is deferred to first dispatch. (b) Confirmed FO routing paragraph at line 82 still references `member_exists`.
6. Update `test_standing_teammate_prose.py` — DONE. Changed heading grep from `Standing teammate spawn pass` to `Standing teammate discovery pass`. Added assertion that old heading is absent. Added `test_lazy_spawn_heading_present`. Added `test_discovery_does_not_call_spawn_standing` (AC-1). Added `test_lazy_spawn_mentions_spawn_standing` (AC-2). Added `TestSharedCoreLazySpawn` class with AC-5 grep for 'deferred'/'lazy'. Added `TestLazySpawnSkipConditions` class with AC-6 grep for skip conditions.
7. Update `test_claude_team_spawn_standing.py` — DONE. Added `_load_claude_team_module` helper for direct import. Added `TestEnumerateDeclaredStandingTeammates` class with unit test: standing mod with no team config on disk, `enumerate_declared_standing_teammates` returns the mod (would have been empty under old function). Added bare-mode test returning empty list.
8. Update `test_claude_team_spawn_standing.py` with AC-4 test — DONE. Added `TestBuildDeclaredTeammatesSection` class: run `cmd_build` with standing mod but no team config member, assert `### Standing teammates available in your team` section appears and preamble reads "These standing teammates are available". Also updated `test_claude_team.py`: renamed `test_build_omits_standing_section_when_absent` to `test_build_emits_standing_section_for_declared_but_not_alive` (expectation flipped — section now appears for declared-but-not-alive teammates).
9. Run `make test-static` — DONE. 422 passed, 22 deselected, 10 subtests passed. Zero failures.
10. Commits — DONE. Four focused commits: (i) helper code rename + filter removal + preamble, (ii) runtime adapter prose, (iii) shared-core prose, (iv) tests. Entity stage report commit follows.
11. Stage Report — DONE (this section).

**Summary:** Implemented lazy-spawn for standing teammates. Boot no longer calls `spawn-standing`; it only runs `list-standing` (discovery). Spawn is deferred to the first team-mode `Agent()` dispatch. The dispatch prompt now enumerates declared (not alive) teammates, so ensigns see standing teammates before they are spawned. All 7 ACs are covered by the test suite.

**Recommendation:** Ready for validation.

## Stage Report (validation)

1. Read the entity's full body (ideation Decision, Protocol, Changes Required, ACs 1-7, Test Plan) and implementation Stage Report — DONE. All sections read and cross-referenced with the implementation output.

2. Inspect the implementation branch commits — DONE. Five commits on the branch (excluding the stage-report commit):
   - `e3e2338d` — `skills/commission/bin/claude-team` only (rename + filter removal + preamble). Scope: correct.
   - `c51f4603` — `skills/first-officer/references/claude-first-officer-runtime.md` only (adapter prose). Scope: correct.
   - `1fea3a32` — `skills/first-officer/references/first-officer-shared-core.md` only (shared-core prose). Scope: correct.
   - `f358adb5` — `tests/test_claude_team.py`, `tests/test_claude_team_spawn_standing.py`, `tests/test_standing_teammate_prose.py` only (tests). Scope: correct.
   - `58d51ae6` — `docs/plans/lazy-standing-teammate-spawn.md` only (stage report). Scope: correct.
   No out-of-scope edits detected.

3. Run `make test-static` — DONE. **422 passed, 22 deselected, 10 subtests passed** in 7.64s. Zero failures.

4. **AC-1: Boot no longer calls spawn-standing** — PASSED.
   - The heading `### Standing teammate discovery pass` exists at line 32 of `claude-first-officer-runtime.md`.
   - The old heading `### Standing teammate spawn pass` does not exist (grep confirms absent).
   - The discovery-pass section body (lines 34-39) does not contain `spawn-standing`. It only references `list-standing` and "Record the returned mod paths in session memory. **No spawn calls at boot.**"
   - Test `test_discovery_does_not_call_spawn_standing` extracts the section and asserts `spawn-standing` not in body.

5. **AC-2: Lazy-spawn triggers at first team-mode dispatch** — PASSED.
   - `### Standing teammate lazy-spawn` subsection exists at line 41 of `claude-first-officer-runtime.md`.
   - The subsection body describes: "Before the first `Agent()` call that uses a `team_name`" trigger, `spawn-standing` invocation (line 46), `member_exists` aliveness check via `already-alive` status handling (line 47), fire-and-forget discipline (line 49).
   - Tests `test_lazy_spawn_heading_present` and `test_lazy_spawn_mentions_spawn_standing` confirm heading and content.

6. **AC-3: Function rename** — PASSED.
   - `enumerate_declared_standing_teammates` exists at line 452 of `claude-team`.
   - `enumerate_alive_standing_teammates` does not appear anywhere in `claude-team` (grep returns zero matches in the script; only appears in archived plan docs).
   - `member_exists` is NOT called inside `enumerate_declared_standing_teammates` (lines 452-494). The function scans `_mods/*.md` for `standing: true` and returns entries directly. `member_exists` is only used in `cmd_spawn_standing` (line 693).
   - Return shape `[(name, description, mod_path)]` preserved (line 452 type hint, line 493 `.append((declared_name, description, mod_path))`).
   - Test `TestEnumerateDeclaredStandingTeammates::test_returns_declared_mod_without_team_config` confirms a standing mod is returned even with no team config on disk.

7. **AC-4: Dispatch prompt enumerates declared teammates** — PASSED.
   - `cmd_build` calls `enumerate_declared_standing_teammates(workflow_dir, team_name)` at line 277.
   - Preamble reads "These standing teammates are available in your team" (line 282), not "The FO has spawned these".
   - Test `TestBuildDeclaredTeammatesSection::test_section_appears_without_team_config_member` runs `cmd_build` with a standing mod but no team config member and asserts the section appears with correct preamble.
   - `test_claude_team.py::test_build_emits_standing_section_for_declared_but_not_alive` (renamed from `test_build_omits_standing_section_when_absent`) confirms the section now appears for declared-but-not-alive teammates.

8. **AC-5: Shared-core prose updated** — PASSED.
   - `## Standing Teammates` section (line 217 of `first-officer-shared-core.md`) contains: "defers spawn to the first team-mode dispatch" (line 219) and "Spawn is deferred to first dispatch, not boot" (line 221).
   - `member_exists` still appears in the Dispatch section at line 82: "Check team-config membership via `member_exists` before routing."
   - Test `TestSharedCoreLazySpawn::test_deferred_or_lazy_in_standing_teammates_section` greps the section for 'deferred' or 'lazy'.
   - Test `TestFORoutingProse::test_member_exists_check_mentioned` asserts `member_exists` present.

9. **AC-6: Skip conditions documented** — PASSED.
   - The lazy-spawn subsection closing paragraph (line 53): "In single-entity (bare) mode and in Degraded Mode, skip lazy-spawn (same as the discovery-pass skip note above)."
   - The discovery-pass section (line 39): "In single-entity (bare) mode and in Degraded Mode, discovery still runs (it is cheap — just `list-standing`), but lazy-spawn is skipped in those modes (no team to spawn into)."
   - All three conditions (bare-mode, single-entity, Degraded Mode) are documented.
   - Test `TestLazySpawnSkipConditions::test_skip_conditions_documented` greps the lazy-spawn section for 'bare', 'single-entity', or 'degraded'.

10. **AC-7: Existing tests pass after rename** — PASSED.
    - `make test-static` returned 422 passed, 22 deselected, 10 subtests passed, zero failures.
    - All pre-existing test classes pass: `test_standing_teammate_prose.py` (updated heading greps), `test_claude_team_spawn_standing.py` (all original classes pass plus new ones), `test_claude_team_list_standing.py` (unchanged, still passes), `test_claude_team.py` (renamed test expectation flipped correctly).
    - The 22 deselected are live/codex-marked tests, consistent with `test-static` exclusion. No regressions.

**Overall recommendation: PASSED.** All 7 ACs verified with evidence. Test suite green at 422/422. No out-of-scope edits. Implementation is minimal and well-scoped.

## Fold-In: SyntaxWarning fix (claude-team line 46)

(a) **Why folded in:** Captain-directed fold-in. The bug lives in the same file (`skills/commission/bin/claude-team`) that #172 already touches, so amending the diff here avoids a separate single-line PR and a second round-trip through validation. Not a 172 regression — pre-existing bug surfaced during the 172 work.

(b) **Origin:** Introduced by commit `36ed45fb` on 2026-04-14 ("feat: harden dispatch helper + runtime adapter for verbatim-prompt discipline"). That commit added the `extract_stage_subsection` docstring with backslash-escaped backticks (`\``) inside a non-raw triple-quoted string, which Python 3.12+ flags as `SyntaxWarning: invalid escape sequence '\`'` on every import/run. Separate task from #172.

(c) **Fix:** One-character change — converted the docstring at `skills/commission/bin/claude-team:44` from `"""..."""` to `r"""..."""`. The raw-string prefix tells Python to treat backslashes literally, so `\`` no longer triggers the warning. Smallest possible semantic-preserving change. Body of the docstring is byte-for-byte identical.

(d) **Verification:**

```
$ python3 -W default -c "import py_compile; py_compile.compile('skills/commission/bin/claude-team', doraise=True)"
(zero stderr, zero stdout, exit 0)

$ python3 -W default skills/commission/bin/claude-team list-standing --workflow-dir /Users/clkao/git/spacedock/docs/plans
/Users/clkao/git/spacedock/docs/plans/_mods/comm-officer.md
(no SyntaxWarning prefix)

$ unset CLAUDECODE && make test-static
422 passed, 22 deselected, 10 subtests passed in 11.52s
```

## Stage Report (fold-in)

1. Read entity to ground in original 172 scope — DONE. Confirmed 172 implementation and validation already complete; this is a captain-directed fold-in, not a validator rejection.
2. Identify the bug — DONE. `skills/commission/bin/claude-team:44-48` docstring contained `\`` escape sequences inside a non-raw triple-quoted string, triggering `SyntaxWarning: invalid escape sequence '\`'` on every invocation.
3. Apply minimal fix — DONE. Converted the docstring at line 44 to a raw string (`r"""..."""`). One-character change. No other edits to claude-team. Did not touch any other file.
4. Verify warning is gone via `python3 -W default -c "import py_compile..."` — DONE. Zero stderr, zero stdout, exit 0.
5. Sanity-check script runs via `python3 -W default skills/commission/bin/claude-team list-standing` — DONE. Output: `/Users/clkao/git/spacedock/docs/plans/_mods/comm-officer.md`. No SyntaxWarning prefix. (Note: the dispatch's `bash skills/commission/bin/claude-team list-standing` invocation from the worktree root failed because the file's shebang is `#!/usr/bin/env python3` and `bash` interprets it as shell. Re-ran via `python3` directly per the shebang's intent. Result confirms the fix.)
6. Run `unset CLAUDECODE && make test-static` from worktree root — DONE. **422 passed, 22 deselected, 10 subtests passed** in 11.52s. Zero failures. Same green baseline as the original 172 validation.
7. Append `## Fold-In` section to entity with rationale, origin commit, fix, and verification — DONE (above).
8. Commit with message `fix: claude-team line 46 docstring escape (folded into #172)` — DONE (next step).
9. Stage Report — DONE (this section).

### Summary

Folded a one-character docstring fix (raw-string prefix on `extract_stage_subsection`) into the 172 worktree to silence the `SyntaxWarning: invalid escape sequence '\`'` that fired on every `claude-team` invocation since commit `36ed45fb` on 2026-04-14. Verified via `py_compile`, direct `list-standing` run, and `make test-static` (422/422 green). One file changed: `skills/commission/bin/claude-team` (line 44, `"""` → `r"""`). New commit on top of the existing 172 commits — no amend, no reorder, no other files touched.
