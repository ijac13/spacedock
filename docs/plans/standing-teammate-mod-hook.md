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
