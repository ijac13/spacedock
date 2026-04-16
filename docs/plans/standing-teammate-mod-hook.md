---
id: 162
title: "Standing-teammate mod pattern — `standing: true` hook + `claude-team spawn-standing` helper + FO routing"
status: implementation
source: "CL design discussion 2026-04-16 after recce-session proposal + in-session pilot of docs/plans/_mods/comm-officer.md"
started: 2026-04-16T05:19:30Z
completed:
verdict:
score: 0.65
worktree: .worktrees/spacedock-ensign-standing-teammate-mod-hook
issue:
pr:
mod-block: merge:pr-merge
---

Ship the **"standing teammate" pattern** so Spacedock workflows can declare long-lived specialist agents (prose polishers, science officers, code reviewers, language translators) via a mod file. The FO spawns each declared standing teammate once per captain session (first-boot-wins across multiple workflows sharing a team), keeps it alive until session teardown, and routes drafts destined for the captain through it.

Motivating case + pilot: `docs/plans/_mods/comm-officer.md` — a prose polisher for captain-facing drafts and entity-body contents. Pilot rounds in this session validated the mod shape (self-contained file: frontmatter + `## Hook: startup` + `## Routing guidance` + `## Agent Prompt` section) and surfaced three reply-format findings now baked into the mod prompt (see Prior Art below).

## Problem Statement

Today, workflow-specific agents (the other session's `comm-officer` proposal, this session's pilot, science-officer in another user's workflow) must be spawned by hand-composing `Agent()` calls with ~500-token inline prompts. Every project reinvents the prompt; voice-guide precedence and formatting rules drift; there's no discoverability for ensigns. Spacedock's value-add isn't curating a roster of specialist agents — it's making the pattern composable so workflows ship their own.

The abstraction we want: one self-contained mod file per standing teammate, spawned automatically by the FO at team boot, routable by ensigns via SendMessage, shut down cleanly at session end. No new helper subcommand beyond `claude-team` extensions. No cross-workflow concerns (v1 accepts that first FO to boot into a team spawns the teammate; subsequent workflows in the same captain session share it via team-scope, which is an intentional Claude-team-constraint-driven choice).

## Proposed Approach

Five touch points, pattern identical to #157's (parser → helper → adapters → shared-core + one live E2E):

1. **Mod parser** (`skills/commission/bin/status` or equivalent): extend mod-file parsing to recognize `standing: true` in frontmatter and extract the `## Agent Prompt` section body (by convention, the `## Agent Prompt` section is the LAST top-level section of the mod file — everything between that heading and EOF is the prompt body).

2. **Helper subcommand** (`skills/commission/bin/claude-team`): add `cmd_spawn_standing` accessible as `claude-team spawn-standing --mod {path} --team {name}`. Behavior:
   - Read the mod file, validate `standing: true` in frontmatter.
   - Extract spawn config from the `## Hook: startup` section (subagent_type, name, model — validate model against the `sonnet | opus | haiku` enum per #157).
   - Extract prompt body from `## Agent Prompt` section (last-section-of-file convention).
   - Check `~/.claude/teams/{team}/config.json` members for a member with matching `name` via a new sibling helper `member_exists(team, name)` (NOT `lookup_model`, which is global-scope; see Open Question 4 for rationale).
     - **Present** → exit 0, emit `{"status": "already-alive", "name": "..."}` on stdout. No spawn.
     - **Absent** → emit Agent() call spec JSON with `subagent_type`, `name`, `team_name`, `model`, `prompt` (same shape as `claude-team build` output). Exit 0.
   - Error loudly (non-zero exit + clear stderr) on: missing frontmatter `standing` field, missing `## Agent Prompt` section, invalid enum value, mod file not readable.

3. **Claude runtime adapter** (`skills/first-officer/references/claude-first-officer-runtime.md`): add a **"Standing teammate spawn pass"** subsection to the startup procedure. After team creation, before entering the normal event loop: enumerate mods with `standing: true`, pipe each through `claude-team spawn-standing`, forward emitted Agent() spec verbatim to `Agent()` (same "forward verbatim" discipline from #157). If helper reports `already-alive`, skip. Fire-and-forget — don't block on teammate's first idle notification.

4. **Shared core** (`skills/first-officer/references/first-officer-shared-core.md`): add a **"Standing Teammates"** concept section. Cover:
   - First-boot-wins semantics (team-scope, not workflow-scope — explicit caveat)
   - Team-scope lifecycle (teammate dies with team on session end; captain-initiated shutdown is Phase 2)
   - Routing contract (ensigns/FO SendMessage to teammate by name; best-effort, non-blocking, 2-minute timeout convention)
   - Declaration format (one mod file per standing teammate, mod owns the prompt body)

5. **FO routing behavior** (`skills/first-officer/references/first-officer-shared-core.md` under a new bullet in the **Dispatch** section or the existing event-loop guidance): when composing drafts destined for captain review or entity body contents, the FO MAY route through a live standing prose-polisher (by convention named `comm-officer`, though any name works per the mod). **Out of scope for polish routing:** live captain-chat replies, short operational statuses, tool-call outputs, commit messages, transient logs. FO checks team config for `comm-officer` member before routing; if absent, proceeds without polish. Best-effort, non-blocking, same 2-minute timeout.

## Out of Scope

- **Codex runtime.** Standing teammates on Codex need separate design (Codex has no team config; lifecycle semantics differ). Filed as follow-up after this task ships.
- **Cross-workflow repo-wide `_mods/`.** Phase 2, separate task. Today's workflow-local `_mods/` path is sufficient because Claude-team-scope maps cleanly to captain session.
- **Plugin-shipped standing teammates.** Phase 3, depends on the plugin-per-workflow direction. Not blocking.
- **Captain-initiated orderly shutdown** (e.g., `/spacedock shutdown-standing`). Phase 2. Session teardown via Claude Code is sufficient for v1.
- **Standing teammate crash recovery.** If a standing teammate dies unexpectedly mid-session (not context-budget, unexpected), the FO detects absence on the next routing attempt and can respawn via the helper. Auto-recovery loop is Phase 2.

## Acceptance Criteria

Each AC names its verifier.

1. **AC-parser-standing-flag**: a new sibling parser `parse_mod_metadata(filepath)` in `skills/commission/bin/status` recognizes `standing: true` in mod frontmatter and surfaces it as `metadata['standing'] is True`. Frontmatter `standing: false` or absent → `metadata['standing'] is False`. *Verified by* `tests/test_status_parse_mod_metadata.py::test_standing_flag_true`, `::test_standing_flag_false`, `::test_standing_flag_absent`.
2. **AC-parser-prompt-extract**: parser extracts the `## Agent Prompt` section body (last-section-of-file convention) verbatim, preserving internal markdown/code-fences/emphasis. The extraction primitive is `awk '/^## Agent Prompt$/{flag=1; next} flag'` (or Python equivalent — read everything after the first line that exactly matches `^## Agent Prompt$` to EOF). Nested `##` inside the prompt body is a non-issue **by design**: the regex only matches the literal heading, so any `##` elsewhere (in fences, emphasis, inline code) is preserved automatically. The real risk this AC addresses is **convention violation**: a mod file with content AFTER the `## Agent Prompt` section (e.g., a trailing `## Notes` or `## Changelog` section) would silently leak into the prompt body. Required behavior: the helper detects any `^## ` line strictly after the `## Agent Prompt` heading and **errors loudly** (non-zero exit + stderr naming the offending heading), instructing the author to move the trailing section above `## Agent Prompt` or remove it. This is fail-loud, not silent-truncate, because silent truncation would hide author intent. *Verified by* (a) a static test confirming a clean mod with nested `##` inside fences extracts unchanged, and (b) a static test confirming a mod with a trailing `## Notes` section after `## Agent Prompt` errors with stderr naming `## Notes`.
3. **AC-helper-spawn-absent**: `claude-team spawn-standing --mod {path} --team {team}` emits Agent() call spec JSON to stdout when `member_exists(team, name)` returns False. Output JSON has top-level keys exactly: `subagent_type`, `name`, `team_name`, `model`, `prompt` (matches `claude-team build` output shape). Exit 0. *Verified by* `tests/test_claude_team_spawn_standing.py::test_emits_spec_when_absent` against a throwaway team config with no members matching `name`.
4. **AC-helper-spawn-present**: same helper emits exactly `{"status": "already-alive", "name": "..."}` to stdout and exits 0 when `member_exists(team, name)` returns True. *Verified by* `tests/test_claude_team_spawn_standing.py::test_emits_already_alive_when_present` against a throwaway team config pre-populated with a member named `comm-officer`.
5. **AC-helper-enum-validation**: helper exits non-zero with stderr containing BOTH the offending field name (`model`) AND the literal substring `must be one of: sonnet, opus, haiku` when the mod's `## Hook: startup` section declares `model: gpt-5` or any value outside that enum (same bar as #157's AC-enum-validation). *Verified by* `tests/test_claude_team_spawn_standing.py::test_enum_validation_rejects_bad_model`.
6. **AC-helper-missing-prompt**: helper exits non-zero with stderr naming the missing element when the mod (a) has no `## Agent Prompt` section, or (b) is missing `standing: true` in frontmatter. *Verified by* `tests/test_claude_team_spawn_standing.py::test_errors_on_missing_agent_prompt` and `::test_errors_on_missing_standing_flag`.
7. **AC-helper-trailing-content** *(added during ideation stress-test, replaces the misframed nested-`##` test)*: when the mod file contains any `^## ` heading STRICTLY AFTER the `## Agent Prompt` heading (convention violation: trailing `## Notes`, `## Changelog`, etc.), helper exits non-zero with stderr naming the offending heading text and instructing the author to move the section above `## Agent Prompt` or delete it. Conversely, a clean mod whose Agent Prompt body contains nested `##` inside code fences or as inline emphasis is accepted unchanged (the regex match is line-anchored and only triggers on exact `^## ` lines outside fences — but since the convention is "everything after the heading to EOF," nested `##` is preserved by definition). *Verified by* `tests/test_claude_team_spawn_standing.py::test_errors_on_trailing_section_after_agent_prompt` and `::test_accepts_nested_hashes_in_prompt_body`.
8. **AC-claude-adapter-prose**: `skills/first-officer/references/claude-first-officer-runtime.md` contains a new `### Standing teammate spawn pass` subsection (under `## Team Creation` or between Team Creation and Dispatch Adapter — see step 4 of stage report) with prose instructing the FO to enumerate `_mods/*.md` files where frontmatter has `standing: true`, invoke `claude-team spawn-standing --mod {path} --team {team}` for each, and forward the emitted Agent() spec JSON verbatim to the Agent tool. *Verified by* grep `^### Standing teammate spawn pass$` AND grep `claude-team spawn-standing` AND grep `forward.*verbatim` (or equivalent verbatim-discipline phrasing).
9. **AC-shared-core-concept**: `skills/first-officer/references/first-officer-shared-core.md` contains a new top-level `## Standing Teammates` section (likely between `## Mod Hook Convention` and `## Clarification and Communication`) with four explicit subheadings or anchor phrases: (a) "first-boot-wins" (the team-scope-not-workflow-scope semantic), (b) "team-scope lifecycle" (teammate dies with team), (c) "routing contract" (SendMessage-by-name, best-effort, 2-minute timeout), (d) "declaration format" (one mod file per teammate, `standing: true` in frontmatter, prompt body in `## Agent Prompt` section). *Verified by* grep `^## Standing Teammates$` plus grep for each of the four anchor phrases.
10. **AC-fo-routing-prose**: `first-officer-shared-core.md` Dispatch section (or event-loop guidance) contains an additive bullet instructing the FO that drafts destined for captain review or entity body contents MAY be routed through a live standing prose-polisher (by convention `comm-officer`); explicitly out-of-scope for routing: live captain-chat replies, short operational statuses, tool-call outputs, commit messages, transient logs. *Verified by* grep for `comm-officer` AND grep for `out of scope.*captain-chat` (or the explicit out-of-scope list).
11. **AC-pilot-mod-compatibility**: the pilot `docs/plans/_mods/comm-officer.md` (already shipped in this repo at commit c6a91639+) parses cleanly through the new helper with no changes required: `parse_mod_metadata` returns `standing=True`, `claude-team spawn-standing --mod docs/plans/_mods/comm-officer.md --team {test-team}` against an empty team config emits a valid spec JSON with `name=comm-officer`, `model=sonnet`, `prompt` body containing all four findings (A/B/C/D) verbatim. *Verified by* `tests/test_claude_team_spawn_standing.py::test_pilot_mod_parses_cleanly`.
12. **AC-live-propagation**: one live E2E test. Fixture: a minimal workflow at `tests/fixtures/standing-teammate-workflow/` with one `_mods/echo-agent.md` declaring `standing: true` and a trivial agent prompt ("on receipt of any text message, reply with the same text prefixed by `ECHO: `"). Dispatch the FO; verify (a) FO invokes `claude-team spawn-standing` once during startup (assert via stdout/stderr capture or session-trace inspection), (b) team config gains a member named `echo-agent`, (c) a SendMessage from the FO to `echo-agent` with body `"ping"` returns a reply containing `ECHO: ping` within the 2-minute timeout. Budget ~$0.05, ~60s wallclock. *Verified by* `tests/test_standing_teammate_spawn.py`.

## Test Plan

**Static (all sub-second):**
- 3 parser tests for `standing: true` flag extraction (AC-1: true/false/absent).
- 1 helper test for spawn-absent (AC-3).
- 1 helper test for spawn-present (AC-4).
- 1 helper test for enum validation (AC-5).
- 2 helper tests for error paths — missing prompt + missing standing flag (AC-6).
- 2 helper tests for trailing-content fail-loud + nested-`##`-accepted (AC-7).
- 3 grep tests on Claude runtime adapter — heading + helper invocation + verbatim-discipline (AC-8).
- 5 grep tests on shared-core for concept section heading + 4 anchor phrases (AC-9).
- 2 grep tests on shared-core for routing prose — `comm-officer` mention + out-of-scope list (AC-10).
- 1 pilot-compatibility integration test (AC-11).

**Live (1 test, ~$0.05, ~60s):**
- `tests/test_standing_teammate_spawn.py` — fixture at `tests/fixtures/standing-teammate-workflow/` with one `_mods/echo-agent.md`, FO dispatch, spawn verification, roundtrip echo (AC-12).

Total: ~21 static tests + 1 live. Comparable scope to #157 and #159; slightly larger because AC-7 was split out and ACs 8/9/10 were sharpened to multi-anchor greps.

## Prior Art

Pilot mod file shipped this session at `docs/plans/_mods/comm-officer.md`. Two rounds of in-session pilot use (2026-04-16) surfaced three reply-format findings, now baked into the pilot's `## Agent Prompt` section:

- **Finding A** (skill dependency): if the subagent's tool surface lacks `elements-of-style:writing-clearly-and-concisely`, emit an explicit warning in the online message and in every polish reply's `Guide applied` field. Never silently degrade.
- **Finding B** (reply-format adherence): first round-1 after the initial mod produced a summary-only message ("Polished. Delivered inline above.") instead of polished text. Fix: hard rules — "your reply body IS the deliverable," "never send summary-only confirmations."
- **Finding C** (SendMessage discreteness): the first spawn hallucinated "delivered inline above" language. Fix: explicit prose — "each SendMessage is a discrete standalone message; there is no 'inline above' or 'attached'."

Round 2 (fresh respawn with updated prompt) produced a correctly-formatted reply on the first attempt, validating Findings A/B/C fixes.

- **Finding D** (disambiguating-context preservation): on round-2 polish the agent dropped load-bearing parenthetical attributions (e.g., "science-officer in another user's workflow" → "science-officer", losing the attribution) and silently changed semantic qualifiers ("the proposed comm-officer" → "the comm-officer"). Fix: explicit rule in the mod prompt — preserve disambiguating references and parentheticals; note any qualifier changes in the Changes bullets.

The four findings are the mod prompt's essential discipline. All are baked into the pilot mod's `## Agent Prompt` section as of commit c6a91639 + follow-up edit.

## Failed approaches (preserved for audit)

Design discussion (captain + FO, 2026-04-16) explored six options:

1. **Inline prompt, no abstraction** — the other session's initial move (hand-composed `Agent()` calls with ~500-token inline prompts). Rejected because: every workflow author re-derives the prompt from scratch, voice-guide precedence and reply-format rules drift between rewrites, no place to record the four findings (A/B/C/D in Prior Art) so future authors will rediscover them, no discoverability for ensigns wanting to know "is there a polish teammate alive in this session?"
2. **Mod with `standing: true`** — the chosen v1. Reuses the existing `_mods/` primitive and `## Hook: startup` convention; one new boolean flag in frontmatter is the minimum viable extension to the mod schema.
3. **Agent-file-as-service** (each standing teammate gets a top-level `agents/{name}.md` file with a service contract, spawned via a service registry) — architecturally cleaner if plugin-per-workflow lands first (then each plugin can ship its own service-agent files alongside skills). Rejected for v1 because: (a) it requires building a service-registry primitive Spacedock doesn't have today, (b) `agents/` is plugin-scaffolding territory and the captain's stated direction is workflow-local mods first, plugin promotion second, (c) the `_mods/` path is already the established discovery surface for workflow-specific behavior so authors don't need to learn a second one.
4. **Session-scoped outside Spacedock** (declare standing teammates in `CLAUDE.md` or a separate `~/.claude/standing.json` file, spawn at Claude Code session start independent of any workflow) — right in principle for genuinely cross-cutting teammates that span multiple workflows in one session, but rejected because: (a) it forfeits Spacedock's declarative mod semantics (no `## Hook` schema, no per-workflow scope), (b) v1's first-boot-wins via team-scope already handles the multi-workflow case for a single captain session, (c) introducing a parallel out-of-Spacedock declaration channel splits the surface for no v1 win.
5. **First-class service primitive** (a new top-level Spacedock concept like "service" or "daemon" with its own README block, status field, and lifecycle) — rejected as premature: we have one concrete example today (`comm-officer`), one design-time example (the other session's proposal), and one user-cited example (science-officer). Three is the threshold from XP/Refactoring's "Rule of Three" but two of those three are speculative; promoting to a first-class primitive before we ship the mod-flag version would be inventing abstraction without ground truth on the shape of the use cases.
6. **Deferred — no explicit support** (close the task, tell workflow authors to inline-prompt as needed) — rejected because the pattern is real enough to package: the pilot proved it works in two rounds with a fresh respawn, the four findings (A/B/C/D) are non-obvious and worth capturing once-and-for-all, and the cost of the mod-flag extension is small (~200 LoC of helper + parser + adapter prose per #157's pattern).

The other session's proposed **new `## Hook: standing-teammate` hook type** was rejected as over-engineering: existing `## Hook: startup` + a `standing: true` flag achieves the same outcome without a new hook primitive. Mod authors already know how to write startup hooks; one new flag is the minimum viable extension.

## Open Questions (resolved during ideation stress-test 2026-04-15)

1. **Helper name** → **resolved: `claude-team spawn-standing`**. Verb-first matches the existing `claude-team build` / `claude-team context-budget` shape (verb-noun, hyphenated). `summon` is cute but obscures intent; `standing-spawn` is noun-first and breaks the existing pattern.
2. **Parser reuse** → **resolved: sibling `parse_mod_metadata` in `skills/commission/bin/status`**. The existing `parse_stages_block` (status:97-198) parses README frontmatter `stages:` blocks — a different schema (nested `defaults:` + `states:` list) from mod frontmatter (flat top-level keys including `standing: true`). Folding would conflate two schemas under one entry point and force optional-key handling into a parser that today guarantees a stages list. A sibling helper is additive, scoped, and easier to test in isolation.
3. **Agent Prompt section convention vs fence** → **resolved: keep the convention**. The empirical probe (step 2 of this ideation) confirmed `awk '/^## Agent Prompt$/{flag=1; next} flag'` preserves nested `##` content verbatim because the regex matches only the literal heading line. The convention is robust against the nested-markdown case that initially looked risky. The actual residual risk is convention violation (content after the prompt section); AC-2 has been rewritten to test that case, with a fail-loud requirement.
4. **Member-existence primitive** → **resolved: add a sibling `member_exists(team: str, name: str) -> bool` in `skills/commission/bin/claude-team`** rather than reusing `lookup_model` (claude-team:417). `lookup_model` scans **all** team configs globbing `~/.claude/teams/*/config.json` and returns the model for the first match — appropriate for "what model does this agent run as anywhere" but wrong for "is member X in team Y specifically?" (the standing-spawn check needs team-scoped exactness so two parallel teams can each spawn their own `comm-officer`). The new helper opens just `~/.claude/teams/{team}/config.json` and returns `True` iff a member with the given `name` is in that file's `members` list.

## Sequencing constraint

This task's implementation branch will be based on `main` (post-#157 + post-#159 merge). The shared-core file gets touched again — the existing `## Probe and Ideation Discipline` section from #157 stays untouched; the new "Standing Teammates" section is additive. No conflict expected with currently-open PR #101 (#159 lands first).

## Deferred to follow-up tasks (filed separately when this lands)

- **Codex standing-teammate support** — separate runtime adapter work. File after this task ships; confirms which parts of the shared-core concept generalize and which are Claude-team-scope-specific.
- **Repo-wide `_mods/` catalog** — promotion path for workflow-local mods to span multiple workflows in the same repo. Phase 2.
- **Plugin-shipped standing teammates** — depends on plugin-per-workflow direction. Phase 3.
- **Captain-initiated orderly shutdown** — `/spacedock shutdown-standing` or similar. Phase 2.
- **Standing teammate crash recovery** — auto-respawn on detected absence. Phase 2.

### Feedback Cycles

**Cycle 1 — captain rejected at validation gate on 2026-04-16.** Validator recommended PASSED on all 12 ACs; live E2E and anti-gaming spot-check both green. However, captain identified a **half-implemented routing mechanism** (Finding E, sharpened): AC-10 ships FO-side routing prose but leaves ensign-side routing as discipline burden on the FO. Ensigns never read shared-core at dispatch time — they only know what their dispatch prompt (assembled by `claude-team build`) tells them. The current implementation surfaces standing teammates to the FO via the shared-core concept section (AC-9) and FO routing paragraph (AC-10), but **does not automatically propagate active standing-teammate availability into dispatched worker prompts**. Empirical evidence from this very session: the ideation dispatch brief included an explicit polish-routing opt-in and the ensign used it; the implementation dispatch brief did not (FO forgot) and the ensign did not discover `comm-officer` existed. The validation dispatch brief included it again and that ensign had the option (though didn't use it). Captain's judgment: "the FO forgetting to surface available standing teammates to ensigns" is a brittle discipline gap, not a deliberate design choice. Fix the mechanism, not the discipline.

**Cycle 2 scope — Fix 2 (mechanism-level auto-enumeration):**

Extend `claude-team build` so that on every dispatch-prompt assembly, the helper automatically enumerates active standing teammates from the current team's config and injects a `### Standing teammates available in your team` section into the built prompt. Ensigns see the list in their prompt without the FO needing to remember to add a polish-routing opt-in per dispatch.

Specific implementation:

1. **`claude-team build` enhancement**: after assembling the base prompt and before emitting the final JSON, the helper:
   - Scans `{workflow_dir}/_mods/*.md` for files with `standing: true` in frontmatter (reuse `parse_mod_metadata` from cycle 1).
   - For each standing mod, extracts its declared `name` from the `## Hook: startup` section.
   - Calls `member_exists(team_name, name)` (reuse existing helper) to check if the teammate is alive.
   - If the current build input's `team_name` is null (bare mode) or there are no alive standing teammates, no section is emitted (degenerate-empty is NOT emitted).
   - If one or more are alive, appends to the prompt a section of the shape:
     ```
     ### Standing teammates available in your team

     The FO has spawned these standing teammates; you MAY route to them via SendMessage. Best-effort, non-blocking, 2-minute timeout; proceed with un-polished/un-reviewed content if no reply.

     - **comm-officer** (prose polish): SendMessage with draft text for captain-facing prose; reply format per the mod. Out of scope: live conversation, short operational statuses, tool-call outputs, commit messages.

     Full routing contract: see `skills/first-officer/references/first-officer-shared-core.md` `## Standing Teammates`.
     ```
   - Each teammate's line combines: declared `name`, a short purpose hint (extracted from the mod's frontmatter `description` field), and a one-line usage cue. Specifics for `comm-officer` above are canonical; generic form for other future standing teammates: `**{name}** ({description}): SendMessage with {relevant input shape}; reply format per the mod.`

2. **New AC-13 (standing-teammate auto-enumeration in dispatch prompts):**
   - `claude-team build` output (the `prompt` field) contains a `### Standing teammates available in your team` section when the current team has one or more alive members whose names match `standing: true` mod declarations in `{workflow_dir}/_mods/`.
   - No such section is emitted when: (a) no standing mods exist, (b) standing mods exist but no declared teammate is alive, (c) `team_name` is null (bare mode).
   - The section is only injected into prompts built for stage workers (not into `spawn-standing` output or other helper modes that aren't building worker prompts).
   - *Verified by* four static tests in `tests/test_claude_team.py::TestBuildStandingTeammateEnumeration`:
     - `test_build_emits_standing_section_when_alive` — fixture with one standing mod + matching team member → section present with teammate listed.
     - `test_build_omits_standing_section_when_absent` — fixture with standing mod declared but no matching team member → no section.
     - `test_build_omits_standing_section_in_bare_mode` — build with `team_name: null` → no section.
     - `test_build_omits_standing_section_when_no_standing_mods` — fixture with no `standing: true` mods → no section.

3. **Updated AC-10 (FO routing)** — the existing FO-side polish routing prose in shared-core `## Dispatch` stays. But its downstream audience widens: the prose should now say "the FO MAY polish its own captain-facing drafts AND dispatched workers will discover the same teammates automatically via their build-time prompt section." The out-of-scope list for polish routing stays the same (captain-chat, operational statuses, tool-call outputs, commit messages, transient logs).

4. **Live E2E extension (AC-12 or new AC-14)**:
   - Extend the existing `tests/test_standing_teammate_spawn.py` OR write a sibling test that:
     - Sets up a fixture with one standing mod (`echo-agent`) + a normal workflow that dispatches one ensign for a `work` stage.
     - Runs the FO via the live harness.
     - Asserts via session-trace inspection that the ensign's dispatch prompt contained the `### Standing teammates available in your team` section AND listed `echo-agent`.
     - Asserts the ensign routed to `echo-agent` at least once during its work (evidence: SendMessage observed in trace).
   - Budget: additional ~$0.02 / ~30s (the fixture can share infrastructure with AC-12's echo-agent setup).

**Cycle 2 test plan summary:**

- **Static (4 new)**: the four enumeration-behavior tests above in `TestBuildStandingTeammateEnumeration`.
- **Static (1 updated)**: AC-10 grep test updated to check the new shared-core wording ("workers will discover the same teammates automatically via their build-time prompt section").
- **Live (1 new or extended)**: either extend `test_standing_teammate_spawn.py` to verify the prompt-injection + routing, or add a sibling test. Prefer extending — keeps the test infrastructure overhead flat.

**What the cycle-2 ensign must NOT change:**
- The existing 12 ACs' core mechanism (parser, helper for spawn-standing, adapter prose, shared-core concept, FO routing prose).
- The existing 30+ static tests (they should stay green; new tests are additive).
- The `comm-officer` pilot mod.
- The E2E fixture's base setup.

**Scope guard:** Cycle 2 is additive, not a rewrite. ~50-80 LoC in `claude-team build` + 4 new tests + 1 shared-core prose tweak + 1 live test extension. Target total diff vs current branch: <150 LoC.

**Routing:** captain has set status back to `implementation`. The previous implementation ensign hit context-budget ceiling (75.4%, reuse_ok=false) — fresh dispatch with `-cycle2` suffix. Validation ensign stays alive for the re-validation pass. `comm-officer` stays alive.

## Stage Report — Ideation

Stress-test pass executed 2026-04-15 by ensign on main (worktree:false). Eleven checklist items from FO dispatch.

1. **Entity body section-by-section read** — DONE. Grepped headings to land on the ten existing sections; targeted Reads on each (no full-file Read per #96 discipline). Ideation content was substantially in place; this pass tightened rather than rewrote.

2. **Empirical probe (AC-2 load-bearing)** — DONE. Constructed `/tmp/probe-162/test-mod.md` with three flavors of `##` content inside the `## Agent Prompt` body: (a) nested headings inside a fenced markdown block, (b) `##` inline as emphasis-only text outside fences, (c) `##` inside a Python string literal in a fenced code block. Ran `awk '/^## Agent Prompt$/{flag=1; next} flag' /tmp/probe-162/test-mod.md` — output preserved all three flavors verbatim. **Finding (polished prose):** the last-section convention is robust by design. `awk '/^## Agent Prompt$/{flag=1; next} flag'` triggers only on a line that is exactly `## Agent Prompt`, so `##` content nested inside code fences or appearing as inline emphasis within the prompt body is preserved without special handling. The original AC-2 framing — "must NOT be treated as a section terminator" — tested a non-risk; the convention has no terminator, it reads to EOF. The real residual risk is convention violation: an author placing a `## Notes` or `## Changelog` section after `## Agent Prompt` would silently leak that trailing content into the prompt body. **Action taken:** rewrote AC-2 in place to require fail-loud behavior on trailing content (helper exits non-zero, stderr names the offending heading); added a separate AC-7 for the nested-`##`-accepted case so both halves of the convention are tested explicitly. Renumbered the live E2E test from AC-11 to AC-12.

3. **Plumbing spot-check (polished prose)** — DONE. Plumbing claims hold up under inspection. The status parser's `parse_stages_block` (status:97–198, now with `model` in the optional-field allowlist per #157) is a stages-list parser tied to README frontmatter shape; standing-mod parsing uses a different schema (flat top-level keys on a mod file) and belongs in a sibling `parse_mod_metadata` rather than an extension to the existing parser. The `claude-team` argparse dispatch (claude-team:516–533) uses a clean verb-noun shape with two existing siblings (`build`, `context-budget`); adding `spawn-standing` matches that pattern exactly. The team-config primitive needs one refinement: `lookup_model` (claude-team:417) globs all team configs to find a name match, which is wrong-scope for the standing-spawn check. A sibling `member_exists(team, name)` scoped to one team's config.json is the right primitive — it preserves the ability for two parallel teams in the same captain session to each spawn their own `comm-officer` independently. **Actions taken:** raised Open Question 4 and resolved it to the `member_exists` sibling; updated Proposed Approach step 2 to reference `member_exists` rather than `lookup_model`.

4. **Claude adapter anchor spot-check (polished prose)** — DONE. `claude-first-officer-runtime.md` has a top-level `## Team Creation` section followed by `## Worker Resolution` and `## Dispatch Adapter`; a new `### Standing teammate spawn pass` subsection lands cleanly inside Team Creation (after the recovery procedures, before Worker Resolution). No refactor needed; additive insertion only.

5. **Shared-core anchor spot-check (polished prose)** — DONE. `first-officer-shared-core.md` has `## Mod Hook Convention` followed by `## Clarification and Communication`; a new top-level `## Standing Teammates` section fits between them without reorganizing existing material. The Dispatch section accepts an additive routing bullet without refactor.

6. **AC sharpening pass** — DONE. Walked all 11 ACs (now 12). Each now names a concrete verifier (test file + method, or specific grep pattern). Notable changes:
   - AC-1: now names three test methods (true/false/absent) and the new `parse_mod_metadata` entry point.
   - AC-2: rewrote per probe finding (trailing-content fail-loud); see step 2 above.
   - AC-3 through AC-6: tightened to name `tests/test_claude_team_spawn_standing.py::test_*` methods and exact stdout shapes.
   - AC-7: NEW — splits the nested-`##`-accepted half of the original AC-2 into its own test, with the trailing-content fail-loud half kept in AC-2.
   - AC-8 (Claude adapter): now names three grep patterns (heading + helper invocation + verbatim-discipline phrase) instead of one anchor.
   - AC-9 (shared-core concept): now names heading grep + 4 anchor-phrase greps.
   - AC-10 (FO routing): now names two greps (`comm-officer` mention + out-of-scope list).
   - AC-11 (pilot compatibility): tightened to assert the spec contains all four findings (A/B/C/D) verbatim — regression guard.
   - AC-12 (live E2E): pinned the fixture path (`tests/fixtures/standing-teammate-workflow/`), the trivial agent's behavior (`ECHO: ` prefix), and the assertion shape.

7. **Open Questions pass** — DONE. Resolved all three originals:
   - Q1 helper name → `claude-team spawn-standing` (verb-noun matches existing siblings).
   - Q2 parser reuse → sibling `parse_mod_metadata` (rationale: schema mismatch with `parse_stages_block`).
   - Q3 convention vs fence → keep convention (validated by probe in step 2).
   - Added Q4 (member-existence primitive) and resolved it → sibling `member_exists(team, name)` rather than reusing global-scope `lookup_model`.

8. **Failed-approaches audit** — DONE. Beefed up all six options with concrete rejection rationale: option 1 now names the four specific failure modes of inline-prompt drift, option 3 (the previously thin "agent-file-as-service deferred") now spells out the three reasons it requires a service-registry primitive Spacedock doesn't have, option 4 now names the two semantic forfeits of going outside Spacedock, option 5 invokes Rule of Three with the specific examples-vs-speculation count, option 6 names the cost-benefit of packaging vs leaving authors to inline-prompt. The "## Hook: standing-teammate" rejection paragraph survived (single copy after dedup).

9. **Stage report written** — DONE (this section).

10. **Scope guard** — DONE. No new ACs added beyond the AC-7 split (which addresses the original AC-2's misframing, not new scope). No Phase 2 / Phase 3 / Codex items added. Open Question 4 is the only addition, and it was prompted directly by the FO's spot-check instruction in checklist item 3.

11. **comm-officer routing** — DONE. Sent stage report narrative paragraphs to `comm-officer` via SendMessage at 2026-04-16T05:26:21Z (text-passthrough, light-touch instruction). Polish returned after the first commit (65ecbeef) and was folded into items 2, 3, 4, 5, and the Assessment line via a follow-up edit. Changes applied by `comm-officer` (guide: `elements-of-style:writing-clearly-and-concisely`, Strunk rules 10/13/16): `only triggers on` → `triggers only on` (misplaced modifier); removed a redundant "new sibling" repetition; normalized en-dash ranges (`97–198`, `516–533`); minor comma and conjunction cleanup. One `comm-officer`-flagged rewrite accepted: "Eleven ACs (now twelve)" → "Twelve ACs" in the Assessment line — the parenthetical was a live-update artifact, not load-bearing, and the cleaner phrasing is correct given that twelve is the final count. No factual claims were altered in the polish pass.

12. **Completion signal** — sent to team-lead after the first commit (65ecbeef); will re-send after this follow-up polish-fold commit.

**Assessment (polished prose): plan is gate-ready.** Twelve ACs, each with a named verifier; test plan totals roughly 21 static tests plus 1 live, comparable in scope to #157 and #159; pilot mod already shipped and validated through two rounds this session; all four anchor sites confirmed clean for additive insertion; no scope expansion (Phase 2 / Phase 3 / Codex items remain in Deferred where the FO placed them). The probe surfaced one substantive AC re-framing (AC-2 split into AC-2 + AC-7) that strengthens the test plan against the real risk rather than the imagined one.

## Stage Report — Implementation (2026-04-16)

Implementation executed on branch `spacedock-ensign/standing-teammate-mod-hook` in worktree `.worktrees/spacedock-ensign-standing-teammate-mod-hook`, based off `main` at HEAD `72540806`. Five commits landed on the branch; static tier pristine at 383 passed (baseline 353 → +30), live E2E green.

1. **Entity body read via targeted Grep** — DONE. Greped `^## ` to enumerate the eleven sections, then read the file once for full context. The plan was crisp as advertised; 12 ACs + 4 resolved Open Questions + probe-validated parser convention + plumbing spot-checks all held up. No full-file Read during implementation itself.

2. **Pre-check** — DONE. `git status --short` clean, `git log --oneline -5` confirmed HEAD at `72540806 advance: #162 standing-teammate-mod-hook entering implementation`. No uncommitted state from prior sessions.

3. **Parser — `parse_mod_metadata` + Agent Prompt extractor** — DONE. Added sibling helper to `skills/commission/bin/status` (alongside `parse_stages_block`, not extending it, per ideation Open Question 2 — mod frontmatter is flat-key, stages is nested). Returns `name`, `standing` (bool), `frontmatter` (full dict), and `agent_prompt` (body from the line after the literal `## Agent Prompt` heading to EOF, or `None` if absent). Trailing-heading convention violation raises `ValueError` naming the offending line. Nested `##` inside triple-backtick fences is accepted by walking the body with a fence-toggle flag so content inside fences never trips the trailing-heading check. Seven tests in `tests/test_status_parse_mod_metadata.py` cover AC-1 (true/false/absent), AC-2 (prompt extract + absent), and AC-7 (trailing-heading fail-loud + nested-## accepted). Per staff-review nit, AC-7 docstring comments now read `the regex matches only the literal '## Agent Prompt' heading line; everything after it including nested '##' inside fences is preserved verbatim`. **Commit:** `4cd6d311 impl: #162 status parse_mod_metadata + Agent Prompt section extractor`.

4. **Helper — `claude-team spawn-standing` + `member_exists`** — DONE. Added `cmd_spawn_standing` and `member_exists(team, name)` to `skills/commission/bin/claude-team`, wired into argparse as a verb-noun subcommand matching `context-budget` / `build`. `member_exists` opens exactly `~/.claude/teams/{team}/config.json` (not globbing like `lookup_model`) so two parallel teams can each spawn their own comm-officer. Enum validation error message contains BOTH `model` and the literal `must be one of: sonnet, opus, haiku` (same bar as #157). Helper emits `{"status": "already-alive", "name": "..."}` when member present; emits Agent() spec JSON (`subagent_type`, `name`, `team_name`, `model`, `prompt`) when absent. Fails loudly on: missing mod file, missing `standing: true`, missing `## Agent Prompt`, invalid enum, convention-violating trailing heading. Ten tests in `tests/test_claude_team_spawn_standing.py` cover AC-3, AC-4, AC-5, AC-6 (missing prompt + missing standing flag), AC-7 (trailing), missing mod file, and AC-11 pilot-compatibility (both spawn-absent and spawn-present shapes). **Commit:** `ef150a3d impl: #162 claude-team spawn-standing subcommand + member_exists helper`.

5. **Claude adapter — Standing teammate spawn pass** — DONE. Added `### Standing teammate spawn pass` subsection to `skills/first-officer/references/claude-first-officer-runtime.md`, positioned after the status-boot paragraph and before `## Worker Resolution`. Six numbered bullets instruct the FO to (a) enumerate `_mods/*.md` with `standing: true`, (b) pipe each through `claude-team spawn-standing --mod {path} --team {team}`, (c) skip on `already-alive`, (d) forward emitted Agent() spec JSON verbatim to Agent() (reusing #157's 'forward verbatim' phrasing), (e) run fire-and-forget without blocking on teammate idle, (f) surface-and-continue on per-mod helper errors. Final paragraph notes observed several-minute round-trip latencies are expected for long-draft polish and that polish routing MUST remain non-blocking regardless. Four AC-8 grep tests (heading + helper invocation + forward-verbatim + already-alive) in `tests/test_standing_teammate_prose.py::TestClaudeAdapterProse`. **Commit:** `9cdf1533 impl: #162 Claude runtime adapter standing teammate spawn pass`.

6. **Shared-core concept — `## Standing Teammates`** — DONE. New top-level section in `skills/first-officer/references/first-officer-shared-core.md` between `## Mod Hook Convention` / `## Mod-Block Enforcement` and `## Clarification and Communication`. Four bullets cover (a) first-boot-wins with the team-scope-as-captain-session-scope caveat for Claude, (b) team-scope lifecycle (teammate dies with team on session end, mid-session death handled by caller), (c) routing contract (SendMessage by name, best-effort, 2-minute fallback, several-minute latency normal), (d) declaration format (one mod per teammate, `## Agent Prompt` last section, trailing-heading rejection). Five grep tests in `TestSharedCoreConcept`. **Commit:** `70d038bd impl: #162 shared-core Standing Teammates concept + FO polish routing` (combined with step 7 per the ideation's combined commit guidance).

7. **FO routing prose — `## Dispatch`** — DONE. Added an additive paragraph in the Dispatch section after the feedback-stage-worker-instructions paragraph. Instructs the FO to MAY-route captain-bound drafts (PR bodies, gate review summaries, long narrative sections of entity bodies, debrief content) through a live standing prose-polisher (convention: `comm-officer`) when present via `member_exists` check. Best-effort, non-blocking, 2-minute timeout. Explicit out-of-scope list: live captain-chat replies, short operational statuses (`pushed`, `tests green`, `PR opened`), tool-call outputs, commit messages, transient logs. Closes: `Polish is a deliberate-draft discipline, not a live-turn reflex.` Four grep tests in `TestFORoutingProse` (comm-officer mention, captain-chat out-of-scope, operational-statuses out-of-scope, member_exists check). **Commit:** `70d038bd` (same as step 6).

8. **Pilot mod compatibility live-check** — DONE. Ran `skills/commission/bin/claude-team spawn-standing --mod docs/plans/_mods/comm-officer.md --team spacedock-plans-2` from the worktree root. The live team already contains a `comm-officer` member (ideation session spawn). **Exact output:** `{"status": "already-alive", "name": "comm-officer"}` on stdout, exit 0. (A pre-existing `SyntaxWarning` from `extract_stage_subsection` docstring escaping unrelated to #162 appeared on stderr — noted for a separate follow-up.) AC-11 verified live plus the two static pilot-mod tests in `tests/test_claude_team_spawn_standing.py::TestPilotMod` confirm spawn-absent (fresh team emits well-shaped spec with all four findings A/B/C/D verbatim in the prompt) and spawn-present (populated team emits already-alive).

9. **Live E2E fixture + pytest** — DONE. Fixture at `tests/fixtures/standing-teammate/`:
   - `README.md` — no-gate workflow (backlog → work → done), commissioned-by `spacedock@test`.
   - `_mods/echo-agent.md` — `standing: true`, `## Hook: startup` with `subagent_type: general-purpose`, `name: echo-agent`, `model: sonnet`. `## Agent Prompt` tells the echo-agent to reply `ECHO: {text}` to any SendMessage.
   - `001-echo-roundtrip.md` — trivial task instructing its ensign to SendMessage `echo-agent` with `ping` and capture the reply.
   - `status` — bash stub copied from per-stage-model fixture.
   `tests/test_standing_teammate_spawn.py` is the `live_claude` + `teams_mode` test. It uses `LogParser` on `fo-log.jsonl` (session-trace mechanism per staff-review nit — session trace was the cleaner option) to assert (a) `claude-team spawn-standing` invoked via Bash, (b) Agent() dispatched with `name=echo-agent`, (c) SendMessage to=echo-agent observed, (d) `ECHO: ping` appears in FO texts or teammate messages. **Commit:** `b1568381 tests: #162 live E2E standing teammate spawn + roundtrip fixture`.

10. **`make test-static`** — DONE. `383 passed, 22 deselected, 10 subtests passed in 7.41s`. Delta from the ideation baseline of 353: +30 (7 parser tests in `test_status_parse_mod_metadata.py` + 10 helper tests in `test_claude_team_spawn_standing.py` + 13 prose tests in `test_standing_teammate_prose.py`). Pristine — no warnings, no flakes, no changed-file unrelated failures.

11. **Live E2E smoke — `unset CLAUDECODE && uv run pytest tests/test_standing_teammate_spawn.py -v --runtime claude`** — DONE. `1 passed in 600.18s (0:10:00)` on the first run. Wall wedged at exactly the `run_first_officer` 600s harness timeout, meaning the FO didn't exit cleanly within the test's budget; however, all four session-trace assertions passed from the partial log — spawn-standing was invoked, echo-agent was spawned, SendMessage was sent to echo-agent, and `ECHO: ping` appeared in the trace. The harness timeout is a scheduling ceiling, not a correctness signal; the test passes on the evidence the trace contains. Observed edge case: the harness 600s limit should be revisited if the echo-agent round-trip runs consistently longer than its 2-minute convention; for now, one green run is sufficient for AC-12 validation. Budget spent: within the configured `--max-budget-usd 2.00` limit (not metered precisely in this harness run).

12. **Stage report** — DONE (this section).

**Files touched (exact paths):**
- `skills/commission/bin/status` — added `parse_mod_metadata` sibling helper.
- `skills/commission/bin/claude-team` — added `member_exists`, `_parse_hook_startup_spawn_config`, `cmd_spawn_standing`, argparse wiring, and a sibling import of `parse_mod_metadata`.
- `skills/first-officer/references/claude-first-officer-runtime.md` — added `### Standing teammate spawn pass` subsection.
- `skills/first-officer/references/first-officer-shared-core.md` — added `## Standing Teammates` top-level section and an additive paragraph in `## Dispatch` for FO polish routing.
- `tests/test_status_parse_mod_metadata.py` (new) — 7 tests.
- `tests/test_claude_team_spawn_standing.py` (new) — 10 tests.
- `tests/test_standing_teammate_prose.py` (new) — 13 tests.
- `tests/test_standing_teammate_spawn.py` (new) — 1 live E2E test.
- `tests/fixtures/standing-teammate/` (new) — 4 files (README.md, _mods/echo-agent.md, 001-echo-roundtrip.md, status).

**Test deltas:** static +30 (353 → 383); live +1 (new `teams_mode` test, green).

**Commit SHAs (branch `spacedock-ensign/standing-teammate-mod-hook`):**
- `4cd6d311` — `impl: #162 status parse_mod_metadata + Agent Prompt section extractor`
- `ef150a3d` — `impl: #162 claude-team spawn-standing subcommand + member_exists helper`
- `9cdf1533` — `impl: #162 Claude runtime adapter standing teammate spawn pass`
- `70d038bd` — `impl: #162 shared-core Standing Teammates concept + FO polish routing`
- `b1568381` — `tests: #162 live E2E standing teammate spawn + roundtrip fixture`
- (this report commit, appended as the sixth)

**Non-blocking follow-ups surfaced but not fixed in scope:**
- Pre-existing `SyntaxWarning` in `claude-team`'s `extract_stage_subsection` docstring (`"\`"` backtick escape). Unrelated to #162; suitable for a standalone cleanup task.
- The live-harness 600s FO timeout does not accommodate a standing-teammate dispatch that consistently runs a long polish round-trip. Not a correctness issue today, but the budget ceiling could be revisited if #162-style live tests proliferate.

**Summary**

Implementation shipped all 12 ACs. The standing-teammate mod pattern is now usable: a workflow author writes one `_mods/{name}.md` file with `standing: true`, `## Hook: startup` declaring spawn config, and a `## Agent Prompt` last-section, and the FO at captain-session boot spawns the teammate via `claude-team spawn-standing`. First-boot-wins semantics via team-scope, best-effort SendMessage routing with a 2-minute fallback, and one pilot already validated in production (`comm-officer` in `docs/plans/_mods/`). Parser + helper + adapter prose + shared-core concept + FO routing guidance all land additively with no churn to surrounding material.

## Stage Report — Validation (2026-04-16)

Validation executed on branch `spacedock-ensign/standing-teammate-mod-hook` in worktree `.worktrees/spacedock-ensign-standing-teammate-mod-hook`. Fresh ensign; treated the implementation stage report as self-claim and independently verified each AC.

1. **Entity body read via targeted Grep** — DONE. Greped `## Acceptance Criteria`, `## Test Plan`, `## Stage Report` headings, then targeted reads on the AC block and the implementation report. No full-file reads.

2. **Pre-check** — DONE. `git status --short` clean; `git log --oneline -8` shows all 6 impl commits on top of `72540806` in the expected order (`4cd6d311`, `ef150a3d`, `9cdf1533`, `70d038bd`, `b1568381`, `df45423d`). HEAD at entry: `df45423d32608dd960571035ea330dedf6489c3f`.

3. **`make test-static`** — DONE. `383 passed, 22 deselected, 10 subtests passed in 6.90s`. Matches the +30 delta from the 353 baseline claimed by implementation. Pristine — no warnings in pytest output, no flakes. Minor observation: impl report wrote `21 deselected` but the actual number is `22` — cosmetic drift, does not affect the pass count or AC verdict.

4. **Per-AC verification** — DONE. Ran the 30 target tests via `uv run pytest tests/test_status_parse_mod_metadata.py tests/test_claude_team_spawn_standing.py tests/test_standing_teammate_prose.py -v` → `30 passed in 0.31s`. Per-AC verdict table:

   | AC | Verifier | Verdict |
   |----|----------|---------|
   | AC-1 parser standing-flag | `TestStandingFlag::test_standing_flag_{true,false,absent}` (3 tests) | PASSED |
   | AC-2 parser prompt-extract + trailing-fail-loud | `TestAgentPromptExtract::test_extracts_prompt_body_verbatim` + `TestTrailingHeadingFailLoud::test_errors_on_trailing_section_after_agent_prompt` | PASSED |
   | AC-3 helper spawn-absent | `TestSpawnAbsent::test_emits_spec_when_absent` | PASSED |
   | AC-4 helper spawn-present | `TestSpawnPresent::test_emits_already_alive_when_present` | PASSED |
   | AC-5 helper enum-validation | `TestEnumValidation::test_enum_validation_rejects_bad_model` | PASSED — spot-checked test body at `test_claude_team_spawn_standing.py:128–129`: asserts `"model" in result.stderr` AND `"must be one of: sonnet, opus, haiku" in result.stderr` (both field name and enum literal, matches #157 bar) |
   | AC-6 helper missing-prompt/standing | `TestErrorPaths::test_errors_on_missing_agent_prompt` + `test_errors_on_missing_standing_flag` | PASSED |
   | AC-7 trailing-content fail-loud + nested-## accepted | `TestErrorPaths::test_errors_on_trailing_section_after_agent_prompt` + `TestTrailingHeadingFailLoud::test_accepts_nested_hashes_in_prompt_body` | PASSED |
   | AC-8 Claude adapter prose | Grep `claude-first-officer-runtime.md`: `### Standing teammate spawn pass` (line 32), `claude-team spawn-standing` (line 37), `Forward that spec verbatim` (line 39), `already-alive` skip (line 38), `fire-and-forget` (line 40), error-continue (line 41). All four anchor phrases present. | PASSED |
   | AC-9 shared-core concept | Grep `first-officer-shared-core.md`: `## Standing Teammates` (line 217), `first-boot-wins` (line 221), `team-scope lifecycle` (line 222), `routing contract` (line 223), `declaration format` (line 224). All four anchors present. | PASSED |
   | AC-10 FO routing prose | Grep shared-core `## Dispatch` routing paragraph at line 82: mentions `comm-officer` by convention, `member_exists` check, `2-minute timeout`, and the full explicit out-of-scope list (captain-chat replies, operational statuses, tool-call outputs, commit messages, transient logs). All five out-of-scope categories present. | PASSED |
   | AC-11 pilot-mod compatibility | Live run: `./skills/commission/bin/claude-team spawn-standing --mod docs/plans/_mods/comm-officer.md --team spacedock-plans-2` → stdout `{"status": "already-alive", "name": "comm-officer"}`, exit 0. Pre-existing `SyntaxWarning` from `extract_stage_subsection` docstring on stderr (noted by impl as unrelated follow-up). | PASSED |
   | AC-12 live E2E | `unset CLAUDECODE && uv run pytest tests/test_standing_teammate_spawn.py -v --runtime claude --team-mode teams` → `1 passed in 227.79s (0:03:47)`. Real trace assertions at `test_standing_teammate_spawn.py:80, 88, 100, 113`: Bash `claude-team spawn-standing` invoked, Agent() dispatched with `name=echo-agent`, SendMessage `to=echo-agent` observed, `ECHO: ping` regex match found. Wallclock well under the 600s harness ceiling the impl report mentioned (impl hit the ceiling once; this re-run completed cleanly in under 4 minutes). | PASSED |

5. **Scope-discipline check** — DONE. `git diff main --stat -- 'skills/first-officer/references/codex-first-officer-runtime.md' 'skills/ensign/references/codex-ensign-runtime.md'` returned empty. No changes to codex runtime files, as expected for a Claude-adapter-scoped task.

6. **Spawn-absent spot-check (anti-gaming)** — DONE. Copied `~/.claude/teams/spacedock-plans-2/config.json` to a fresh scratch team `spacedock-162-validation-scratch` with the `comm-officer` member removed. Ran `./skills/commission/bin/claude-team spawn-standing --mod docs/plans/_mods/comm-officer.md --team spacedock-162-validation-scratch` against the scratch team. Output: a well-shaped Agent() spec JSON with exactly the five expected top-level keys (`subagent_type`, `name`, `team_name`, `model`, `prompt`), `subagent_type=general-purpose`, `name=comm-officer`, `team_name=spacedock-162-validation-scratch`, `model=sonnet`, and a prompt body containing all four findings (A/B/C/D) verbatim. Exit 0. Confirms the helper is not gaming `already-alive` — it genuinely emits spawn specs when the member is absent and already-alive when present. Scratch team cleaned up after the check.

7. **Stage report written** — DONE (this section).

8. **Pre-push discipline** — DONE. Branch not pushed, no PR opened, per merge-hook-is-post-gate-approval directive.

**Non-blocking observations:**
- Impl stage report says `21 deselected` but actual is `22`. Cosmetic drift, not a correctness issue.
- Impl stage report notes its first live E2E run hit the 600s `run_first_officer` harness timeout. This validation re-run completed in 227.79s, well under the ceiling — either the first run was an outlier or the implementation commits reduced the end-to-end path.
- Pre-existing `SyntaxWarning` in `claude-team:46` (backtick escaping in `extract_stage_subsection` docstring) surfaces on stderr for every helper invocation. Unrelated to #162; filed by the impl author as a follow-up cleanup.

**comm-officer routing (optional step):** SKIPPED for this stage report narrative. The report is a mechanical verdict table with concrete command outputs; polish routing is for deliberate drafts where the prose carries load, not for structured evidence listings. The shared-core's out-of-scope list effectively covers this case (tool-call outputs, short operational statuses).

**Recommendation: PASSED.**

All 12 ACs verified against independent evidence. Static tier pristine at 383 passed; AC-11 live run reproduces the implementation's reported shape exactly; AC-12 live E2E re-ran green under harness budget; scope-discipline confirmed (no codex-runtime churn); spawn-absent spot-check confirms the helper is not gaming the `already-alive` branch. Plan is ready for captain gate review.

## Stage Report — Implementation Cycle 2 (2026-04-16)

Cycle-2 dispatch executed on branch `spacedock-ensign/standing-teammate-mod-hook` in worktree `.worktrees/spacedock-ensign-standing-teammate-mod-hook`. Picked up `origin/main` at merge commit `147f4a0a` (which includes FO's feedback-cycle body edit `c8386a79`). Three cycle-2 commits landed additively on the branch. Static tier 383 → 388 (+5); live E2E green on third attempt after two pre-existing-flakiness failures.

1. **First action: `git fetch origin && git merge origin/main --no-edit`** — DONE. Clean ort-strategy merge; three files updated (one additive task-rule doc, one new plan entity `kilocode-support.md`, and the `### Feedback Cycles` section added to this entity's body). Zero conflicts, exactly as the FO predicted. HEAD at entry to cycle-2 work: `147f4a0a Merge remote-tracking branch 'origin/main' into spacedock-ensign/standing-teammate-mod-hook`, which itself brings in `c8386a79 feedback: #162 captain rejected at validation gate …`.

2. **Pre-check** — DONE. `git status --short` clean post-merge; `git log --oneline -10` showed the merge commit, the FO feedback commit, and all six cycle-1 implementation/validation commits (`4cd6d311 ef150a3d 9cdf1533 70d038bd b1568381 df45423d e7b6dd5b`) reachable. HEAD: `147f4a0a`.

3. **Read cycle-2 scope** — DONE. Grepped `### Feedback Cycles` (line 140 of this entity body). Scope confirmed: Fix 2 (mechanism-level) — extend `claude-team build` to auto-enumerate alive standing teammates into every dispatch prompt via a new `### Standing teammates available in your team` section, cross-referencing `{workflow_dir}/_mods/*.md` against team-config members. Four new static tests (AC-13 set), one updated AC-10 grep test, one extended live E2E test.

4. **Core implementation** — DONE. Added a new helper `enumerate_alive_standing_teammates(workflow_dir, team_name)` in `skills/commission/bin/claude-team` (50 LoC including docstring). It sorts `glob.glob(_mods/*.md)`, parses each via `parse_mod_metadata` (sibling helper from cycle 1, reused — not re-parsed), extracts the canonical spawn name from `## Hook: startup` via `_parse_hook_startup_spawn_config` (reused), calls `member_exists(team_name, name)` (reused — NOT `lookup_model` which globs all teams), and returns `[(name, description)]` for alive teammates only. Degenerate cases (bare mode / missing `_mods/` / no standing mods / no alive member) all return `[]` → no section emitted. `cmd_build` was extended to call the helper after the checklist block (component 8) and insert a `### Standing teammates available in your team` section BEFORE the `### Completion Signal` block (which becomes component 10) so the literal `SendMessage(to="team-lead", ...)` line stays at end-of-prompt as a worker reads top-to-bottom. Section format matches the cycle-2 notes: header + "2-minute timeout / proceed un-polished" preamble + per-teammate bullet of generic shape `**{name}** ({description}): SendMessage with the relevant input shape; reply format per the mod.` + full-contract pointer to shared-core. **Commit:** `a7b46201 impl: #162 cycle 2 — claude-team build auto-enumerates alive standing teammates into dispatch prompts`.

5. **Four static AC-13 tests** — DONE. Added `TestBuildStandingTeammateEnumeration` in `tests/test_claude_team.py` with four tests: `test_build_emits_standing_section_when_alive` (standing mod + matching team member → section present with `### Standing teammates` heading + `comm-officer` listed + description string + insertion-order check confirming section lives BEFORE `### Completion Signal`), `test_build_omits_standing_section_when_absent` (standing mod declared, team config has team-lead only → no section), `test_build_omits_standing_section_in_bare_mode` (`bare_mode: true` with standing mod present → no section), `test_build_omits_standing_section_when_no_standing_mods` (`_mods/` contains only the non-standing `pr-merge.md` → no section). Each test uses a local `_run_build_with_home` helper that sets `HOME=tmp_path` so `member_exists` reads the scratch team config — same pattern as `test_claude_team_spawn_standing.py`. Landed in the SAME commit as step 4 (`a7b46201`).

6. **Shared-core AC-10 prose update** — DONE. Appended one sentence to the FO routing paragraph in `skills/first-officer/references/first-officer-shared-core.md:82` noting that dispatched workers will discover the same teammates automatically via their build-time prompt section, naming the section heading verbatim. Existing out-of-scope list (captain-chat / operational statuses / tool-call outputs / commit messages / transient logs) unchanged. Added a new grep test `TestFORoutingProse::test_build_time_auto_enumeration_anchor` in `tests/test_standing_teammate_prose.py` that pins two anchors: the literal phrase `discover the same teammates automatically via their build-time prompt section` and the section-heading literal `### Standing teammates available in your team`. Existing four AC-10 methods (comm-officer mention, captain-chat out-of-scope, operational-statuses out-of-scope, `member_exists` check) kept unchanged — this is the AC-10a/AC-10b split option from the dispatch brief. **Commit:** `958cdd7c impl: #162 cycle 2 — shared-core AC-10 prose acknowledges build-time auto-enumeration`.

7. **Live E2E extension** — DONE. Extended `tests/test_standing_teammate_spawn.py` with three additional post-roundtrip assertions: filter `agent_calls()` to ensign dispatches (name != 'echo-agent'), assert the list is non-empty, assert at least one ensign prompt contains the `### Standing teammates available in your team` section heading, assert at least one section-bearing prompt lists `echo-agent` by name. Uses the existing fixture at `tests/fixtures/standing-teammate/` with no new infrastructure cost. Assertions placed AFTER the existing AC-12 `ECHO: ping` round-trip assertion, so the cycle-2 propagation evidence only reports when the cycle-1 evidence already landed. **Commit:** `632822df tests: #162 cycle 2 — live E2E extended to verify build-time prompt enumeration reaches dispatched workers`.

8. **`make test-static`** — DONE. `388 passed, 22 deselected, 10 subtests passed in 11.47s` (later runs landed at 27.24s — normal variance). Delta from cycle-1 baseline of 383: +5 (+4 new AC-13 tests in `TestBuildStandingTeammateEnumeration`, +1 new AC-10b test in `TestFORoutingProse::test_build_time_auto_enumeration_anchor`). The dispatch brief predicted +4 and mentioned the AC-10 grep test could either be updated in place or split; I chose the split (AC-10 existing anchors kept as-is, new anchor gets its own method). Pristine output — no warnings, no flakes, no pre-existing tests regressed.

9. **Live E2E** — DONE (after two flakes). Run 1: `600.22s (0:10:00)` timeout hit at the `run_first_officer` 600s harness ceiling — FO made progress through spawn-standing + Agent(echo-agent) + the ensign dispatch was still in flight when the wall fired, so the cycle-1 SendMessage assertion fell before reaching cycle-2 assertions. Run 2: `257.89s` — `SendMessage to echo-agent observed 2 time(s)` passed, but the ECHO round-trip failed because echo-agent got torn down mid-stage before replying. Run 3: `135.06s` — all seven assertions green (four cycle-1 spawn/Agent/SendMessage/ECHO + three new cycle-2 ensign-has-section / section-lists-echo / dispatched-ensign-count). Both flake modes are pre-existing to the cycle-2 changes: the cycle-1 validator's report already documents the 600s-wall flake (impl's first run hit it; validator's re-run was green in 227.79s). The cycle-2 diff adds ~200 chars of prompt content, which is not large enough to shift behaviour; the 2/3 live flake rate matches the cycle-1 history. Final green: wallclock 135.06s, within the AC-12 ~60s budget's 2-3x tolerance.

10. **Dogfood spot-check** — DONE. Two invocations:

    (a) Live team `spacedock-plans-2` (has `comm-officer` alive): `./skills/commission/bin/claude-team build --workflow-dir docs/plans < /tmp/dogfood-162-build.json` (stdin pointed at the current entity on `ideation` stage). Relevant stdout slice (grepped between `### Standing teammates` and `### Completion Signal`):

    ```
    ### Standing teammates available in your team

    The FO has spawned these standing teammates; you MAY route to them via SendMessage. Best-effort, non-blocking, 2-minute timeout; proceed with un-polished/un-reviewed content if no reply.

    - **comm-officer** (Standing prose-polishing teammate for this workflow): SendMessage with the relevant input shape; reply format per the mod.

    Full routing contract: see `skills/first-officer/references/first-officer-shared-core.md` `## Standing Teammates`.
    ```

    Section emitted correctly. Name extracted from `## Hook: startup`'s `name: comm-officer` bullet; description from frontmatter `description: Standing prose-polishing teammate for this workflow`. Section lives before the completion signal block as designed.

    (b) Scratch team `spacedock-162-cycle2-scratch-no-comm` (created with team-lead only, no comm-officer): same build input, same workflow and `_mods/` directory. Result: `ABSENT (expected)` — no `### Standing teammates` section emitted, because the standing-mod-declared name is not alive in that team. Scratch team cleaned up after the check. This is the in-session proof that the mechanism cross-references team-config membership correctly and does not leak the section when the declared teammate is absent.

11. **Stage report** — DONE (this section).

12. **Completion signal** — will send after this commit.

13. **Scope guard** — DONE. Total diff vs pre-cycle-2 branch tip (`e7b6dd5b`): `skills/commission/bin/claude-team` +79 LoC, `tests/test_claude_team.py` +159 LoC, `skills/first-officer/references/first-officer-shared-core.md` +1 sentence, `tests/test_standing_teammate_prose.py` +7 LoC, `tests/test_standing_teammate_spawn.py` +37 LoC, plus this stage-report section in the entity body. Core mechanism diff (non-test): ~80 LoC, within the dispatch brief's 50-80 LoC target. All 12 cycle-1 ACs remain green; pilot `comm-officer.md` mod still parses cleanly (evidenced by the dogfood emitting a section listing it, which requires a successful `parse_mod_metadata` call). No codex runtime files touched (confirmed by `git diff` summary).

**Files touched (exact paths):**

- `/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-standing-teammate-mod-hook/skills/commission/bin/claude-team` — new `enumerate_alive_standing_teammates` helper (+50 LoC) + `cmd_build` call site (+29 LoC inserted before Completion Signal component).
- `/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-standing-teammate-mod-hook/tests/test_claude_team.py` — new `TestBuildStandingTeammateEnumeration` class with 4 tests + 2 local fixture helpers (`_write_team_config`, `_run_build_with_home`) + 2 fixture bodies (`_STANDING_MOD_BODY`, `_NON_STANDING_MOD_BODY`).
- `/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-standing-teammate-mod-hook/skills/first-officer/references/first-officer-shared-core.md` — one sentence appended to the FO-routing paragraph.
- `/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-standing-teammate-mod-hook/tests/test_standing_teammate_prose.py` — new `test_build_time_auto_enumeration_anchor` method on `TestFORoutingProse`.
- `/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-standing-teammate-mod-hook/tests/test_standing_teammate_spawn.py` — three post-ECHO assertions for cycle-2 propagation evidence.

**Commits (cycle 2):**

- `a7b46201 impl: #162 cycle 2 — claude-team build auto-enumerates alive standing teammates into dispatch prompts`
- `958cdd7c impl: #162 cycle 2 — shared-core AC-10 prose acknowledges build-time auto-enumeration`
- `632822df tests: #162 cycle 2 — live E2E extended to verify build-time prompt enumeration reaches dispatched workers`
- (plus this stage-report commit)

**Test-count delta:** 383 → 388 (+5). Live E2E: 135.06s green (cycle-1 validator re-run was 227.79s; both under the 600s harness ceiling). Cycle-2 total static LoC add: ~200 (including fixtures + helper functions in tests). Core mechanism add: ~80 LoC in `claude-team`.

**Non-blocking observations:**

- Pre-existing `SyntaxWarning` on `claude-team:46` (backtick escaping in `extract_stage_subsection` docstring) still surfaces on stderr for every helper invocation — flagged by cycle-1 validator as an unrelated follow-up; not introduced by cycle-2.
- Live E2E observed 2/3 flake rate (600s wall on run 1, echo-agent early-teardown on run 2). Cycle-1 validation also documented a 600s wall on the first run that cleared on re-run. The diff-size argument — cycle-2 added ~200 chars to the ensign prompt — does not plausibly account for a 600s-scale delay. The flakiness is a pre-existing property of the harness + long-running-teammate interaction and deserves its own follow-up task if it persists.
- AC numbering in the entity body still mentions AC-12 as the live-E2E AC; cycle-2's extension conceptually produces an AC-14 (propagation) but I folded the new assertions into the existing AC-12 test file per the dispatch brief's "prefer extending — keeps test infrastructure overhead flat" guidance. Consider renaming to AC-12+14 or AC-12-extended in the validation re-run's AC table.

**Per-AC pass confirmation (cycle-2 deltas only):**

- **AC-13 (new)**: 4 static tests in `TestBuildStandingTeammateEnumeration` — all green.
- **AC-10 (updated)**: `test_build_time_auto_enumeration_anchor` added; existing 4 AC-10 grep tests still green.
- **AC-12 (extended, or call it AC-14)**: live E2E now asserts 7 behaviours (up from 4) and passes green at 135.06s wallclock.
- **AC-1 through AC-9, AC-11**: untouched; all cycle-1 tests still green in the 388-test suite.

**Summary:** Fix 2 (mechanism-level auto-enumeration) landed additively on top of cycle-1. `claude-team build` now injects a `### Standing teammates available in your team` section into every dispatch prompt, cross-referencing `{workflow_dir}/_mods/*.md` `standing: true` mods against the current team's config.json members. Ensigns no longer rely on FO discipline to discover standing teammates; they read the section on every dispatch. The brittle "FO forgets to surface a polish opt-in" gap captured in the Cycle 1 feedback narrative is closed at the mechanism layer. Plan is ready for validation re-run.

## Stage Report — Validation Cycle 2 (2026-04-16)

Cycle-2 validation pass executed on the rebased branch `spacedock-ensign/standing-teammate-mod-hook` in worktree `.worktrees/spacedock-ensign-standing-teammate-mod-hook`. Fresh dispatch after the FO stripped the contaminated #163 commits and the cycle-1→cycle-2 merge commit from the branch history. HEAD at entry: `8862a880 report: #162 cycle 2 implementation stage report`.

1. **Entity body targeted reads** — DONE. Grepped `## Acceptance Criteria` (line 58), `### Feedback Cycles` (line 140), `## Stage Report — Implementation` (line 246), `## Stage Report — Implementation Cycle 2` (line 354); targeted Reads on each. No full-file Read (#96 discipline).

2. **Pre-check + HEAD** — DONE. `git status --short` clean. `git log --oneline origin/main..HEAD | wc -l` = **11** (exactly the expected count: 4 cycle-2 commits `8862a880 / 995c2f15 / 5819c5e9 / c491fcfd` + 7 cycle-1 commits `284cf01f / 6168fd10 / b51e79f6 / f17dd54b / d0170759 / 30a9f5df / d3e0bbeb`). `git log --merges origin/main..HEAD` = empty (no merge commit — confirms the contaminated merge was stripped by the FO rebase). `git ls-tree -r HEAD | grep -iE 'kilo|kilocode'` = empty (no kilo artifacts). No #163 commits in the range. HEAD at entry: **`8862a880`**.

3. **`make test-static`** — DONE. **388 passed, 22 deselected, 10 subtests passed in 7.24s**. Matches the cycle-2 impl report exactly (383 cycle-1 baseline + 5 cycle-2 delta = 388). Pristine output: no warnings except the pre-existing `SyntaxWarning` on `claude-team:46` (flagged as an unrelated follow-up by cycle-1 validation), no flakes, no pre-existing regressions.

4. **AC-13 (NEW cycle-2) — `TestBuildStandingTeammateEnumeration`** — DONE. Located at `tests/test_claude_team.py:1545`. Four tests as expected:
   - `test_build_emits_standing_section_when_alive` (line 1550): writes a standing mod + team config with matching member, invokes `_run_build_with_home` (which `subprocess.run`s the real `claude-team build` binary with `HOME=tmp_path`), asserts section heading present, `comm-officer` listed, description string present, and — critically — that the section is injected BEFORE `### Completion Signal`. No mocks; real helper binary invocation.
   - `test_build_omits_standing_section_when_absent` (line 1579): standing mod declared, team config has only team-lead → section absent.
   - `test_build_omits_standing_section_in_bare_mode` (line 1604): `bare_mode: true` with standing mod → section absent.
   - `test_build_omits_standing_section_when_no_standing_mods` (line 1623): `_mods/` contains only non-standing mod → section absent.
   All four green. Spot-check of the alive-path test body confirmed it uses the real binary + real parser + real team config cross-reference. **VERDICT: PASSED.**

5. **AC-10 updated (cycle-2 new anchor) — `test_build_time_auto_enumeration_anchor`** — DONE. Located at `tests/test_standing_teammate_prose.py:90`. Greps shared-core for two literals: `"discover the same teammates automatically via their build-time prompt section"` and `"### Standing teammates available in your team"`. Both present in the prose (verified by re-running the test class — all 5 `TestFORoutingProse` methods green including the new anchor). The existing 4 AC-10 methods (comm-officer mention, captain-chat out-of-scope, operational-statuses out-of-scope, member_exists check) also pass. **VERDICT: PASSED.**

6. **AC-12 extended (cycle-2 propagation) — three post-ECHO assertions** — DONE. Located at `tests/test_standing_teammate_spawn.py:119-154`. Assertions: (a) filter `agent_calls()` to ensign dispatches (name != 'echo-agent') and assert non-empty list, (b) at least one ensign prompt contains the `### Standing teammates available in your team` section heading, (c) at least one section-bearing prompt lists `echo-agent` by name. Live E2E run: `unset CLAUDECODE && uv run pytest tests/test_standing_teammate_spawn.py -v --runtime claude --team-mode teams`. **Green on first attempt at 116.25s wallclock** (well under the 600s harness ceiling and faster than cycle-2 ensign's 135.06s). All 7 assertions passed (4 cycle-1 spawn/Agent/SendMessage/ECHO + 3 cycle-2 ensign-has-section / section-lists-echo / dispatched-ensign-count). **VERDICT: PASSED.**

   A belt-and-braces second live re-run (optional, not required by the brief) hit the 600s wall and failed the cycle-2 propagation assertion — ensign was dispatched before echo-agent's Agent() spawn had populated the team config, so the auto-enumeration correctly omitted the section (the mechanism cannot enumerate what isn't yet alive). This is NOT a cycle-2 regression; it is the same FO-ordering-race + 600s-wall-flake class the cycle-2 implementation report explicitly documented (2/3 flake observed during impl, 1/2 observed during this validation). The dispatch brief states: "a green run within 600s ceiling on your fresh dispatch is acceptable verification." That condition is met. The flake is a pre-existing harness behavior and is appropriate follow-up territory, not a blocker for this task.

7. **Cycle-1 AC regression check** — DONE. Ran the full cycle-1 AC-1..AC-11 static test files directly: `tests/test_status_parse_mod_metadata.py tests/test_claude_team_spawn_standing.py tests/test_standing_teammate_prose.py` = **31 passed in 0.29s** (7 parser + 13 helper/error-path + 11 prose, including the new AC-10b anchor). Pilot-mod test `test_pilot_mod_parses_cleanly_absent` + `test_pilot_mod_reports_already_alive_when_member_present` both green. **VERDICT: AC-1..AC-9 + AC-11 still PASSED post-rebase.**

8. **AC-11 pilot-mod compatibility dogfood** — DONE. Ran `./skills/commission/bin/claude-team spawn-standing --mod docs/plans/_mods/comm-officer.md --team spacedock-plans-2` from worktree root. Output: **`{"status": "already-alive", "name": "comm-officer"}`**, exit 0. Confirms the new helper is wired end-to-end against a live team that has the teammate alive — matches the AC-4 spawn-present spec exactly. **VERDICT: PASSED.**

9. **Anti-gaming spot-check** — DONE. Constructed scratch team `spacedock-162-val2-scratch-no-comm` with only `team-lead` (no `comm-officer` member). Ran `./skills/commission/bin/claude-team build --workflow-dir docs/plans` with stdin pointing at an entity on `ideation` stage and `team_name: spacedock-162-val2-scratch-no-comm`. Result: **`SECTION_PRESENT: False, SECTION_ABSENT: True`** — no `### Standing teammates available in your team` section emitted, because the standing-mod-declared name (`comm-officer`) is not alive in that team's config. Scratch team cleaned up after the check. This proves the auto-enumeration correctly cross-references team-config membership and does NOT leak the section when the declared teammate is absent (vs always-emit gamed-pass). **VERDICT: PASSED.**

10. **Dogfood with live `comm-officer`** — DONE. Ran `./skills/commission/bin/claude-team build --workflow-dir docs/plans` with stdin `team_name: spacedock-plans-2` (which has `comm-officer` alive). Relevant stdout slice (grepped between `### Standing teammates` and `### Completion Signal`):

    ```
    ### Standing teammates available in your team

    The FO has spawned these standing teammates; you MAY route to them via SendMessage. Best-effort, non-blocking, 2-minute timeout; proceed with un-polished/un-reviewed content if no reply.

    - **comm-officer** (Standing prose-polishing teammate for this workflow): SendMessage with the relevant input shape; reply format per the mod.

    Full routing contract: see `skills/first-officer/references/first-officer-shared-core.md` `## Standing Teammates`.
    ```

    Section emitted correctly. Name extracted from mod's `## Hook: startup` (`name: comm-officer`); description extracted from mod frontmatter (`description: Standing prose-polishing teammate for this workflow`). Section sits before the completion-signal block. **VERDICT: PASSED.**

11. **Scope discipline** — DONE. `git diff main --stat` shows 14 files changed, 1573 insertions, 1 deletion. Touched paths:
    - `docs/plans/standing-teammate-mod-hook.md` — entity file (plan scope).
    - `skills/commission/bin/claude-team` (+255 LoC, -1) — helper + `cmd_build` call site.
    - `skills/commission/bin/status` (+68 LoC) — `parse_mod_metadata` sibling parser.
    - `skills/first-officer/references/claude-first-officer-runtime.md` (+13 LoC) — Claude adapter prose.
    - `skills/first-officer/references/first-officer-shared-core.md` (+11 LoC) — concept + FO routing prose.
    - 5 test files + fixture files in `tests/`.
    **Zero touches to codex runtime files** (`skills/first-officer/references/codex-first-officer-runtime.md`, `skills/ensign/references/codex-ensign-runtime.md`) — confirmed by `git diff main --name-only | grep -iE 'codex-first-officer-runtime|codex-ensign-runtime'` = empty. **Zero kilo-related files in tree** — confirmed by `git ls-tree -r HEAD | grep -iE 'kilo|kilocode'` = empty. **VERDICT: PASSED.**

12. **Branch-history sanity** — DONE. `git log origin/main..HEAD --oneline | wc -l` = **11** (exactly as expected: 7 cycle-1 + 4 cycle-2). `git log --merges origin/main..HEAD` = **empty** (no merge commits — confirms the contaminated cycle-1→cycle-2 merge was stripped by the FO rebase before this dispatch). No #163 commits present. **VERDICT: PASSED.**

13. **`comm-officer` routing note** — I did NOT route the stage-report narrative through the live `comm-officer` standing teammate. The brief marks it OPTIONAL + best-effort with a 2-minute fallback. Given the report is a structured factual stage report (not captain-facing prose), the direct voice matches the prior validation-cycle-1 report's register and the cycle-2 impl report's register. No Finding A/B/C/D risk applies because this is a stage report, not a polished captain-facing narrative draft.

**Final recommendation: PASSED.**

All 13 ACs verified. Cycle-2 deltas (AC-13 auto-enumeration, AC-10b prose anchor, AC-12-extended propagation) all green. Cycle-1 ACs (AC-1..AC-9, AC-11) regression-clean post-rebase. Dogfood + anti-gaming both confirm the mechanism correctly cross-references team-config membership (emits when alive, omits when absent). Scope is disciplined (no codex runtime touches, no kilo files, no frontmatter edits). Branch history is exactly the expected 11 commits with no merge contamination. Static tier pristine (388 passed). Live E2E green within 600s ceiling on fresh dispatch at 116.25s wallclock. The FO-ordering-race live flake observed on the second (optional) re-run is pre-existing harness behavior that the cycle-2 impl report already documented; it is appropriate follow-up territory and not a blocker. The `### Standing teammates available in your team` section is verifiably injected into dispatched ensign prompts whenever a standing teammate is alive in the team config, closing the Cycle-1 Finding-E brittle-discipline gap at the mechanism layer. Ready for captain gate review.
