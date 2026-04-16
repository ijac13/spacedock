---
id: 162
title: "Standing-teammate mod pattern — `standing: true` hook + `claude-team spawn-standing` helper + FO routing"
status: ideation
source: "CL design discussion 2026-04-16 after recce-session proposal + in-session pilot of docs/plans/_mods/comm-officer.md"
started: 2026-04-16T05:19:30Z
completed:
verdict:
score: 0.65
worktree:
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
   - Check `~/.claude/teams/{team}/config.json` members for a member with matching `name`.
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

1. **AC-parser-standing-flag**: mod parser recognizes `standing: true` in frontmatter and surfaces it to callers. *Verified by* a static unit test on a synthetic mod file.
2. **AC-parser-prompt-extract**: parser extracts the `## Agent Prompt` section body (last-section-of-file convention) verbatim, preserving internal markdown/code-fences/emphasis. *Verified by* a static unit test with a mod file whose prompt contains nested `##` inside code fences (must NOT be treated as a section terminator).
3. **AC-helper-spawn-absent**: `claude-team spawn-standing --mod {path} --team {team}` emits Agent() call spec JSON when team lacks the named member. Output shape: top-level `subagent_type`, `name`, `team_name`, `model`, `prompt`. *Verified by* a static test against a throwaway team config.
4. **AC-helper-spawn-present**: same helper emits `{"status": "already-alive", "name": "..."}` and exits 0 when team already has the named member. *Verified by* a static test with a pre-populated team config.
5. **AC-helper-enum-validation**: helper errors non-zero with stderr naming BOTH the offending field AND the literal `must be one of: sonnet, opus, haiku` when the mod declares an out-of-enum model (same bar as #157's AC-enum-validation). *Verified by* a static test.
6. **AC-helper-missing-prompt**: helper errors non-zero with a clear stderr message when the mod has no `## Agent Prompt` section, or when `standing: true` is missing from frontmatter. *Verified by* two static tests.
7. **AC-claude-adapter-prose**: Claude runtime adapter's startup procedure contains prose instructing the FO to enumerate `standing: true` mods and invoke the helper for each. *Verified by* a grep test on `claude-first-officer-runtime.md` for a documented anchor phrase.
8. **AC-shared-core-concept**: shared-core contains a "Standing Teammates" section covering first-boot-wins, team-scope lifecycle, routing contract, and declaration format. *Verified by* 4 grep tests for anchor phrases.
9. **AC-fo-routing-prose**: shared-core contains routing prose instructing the FO to route drafts + entity-body contents through a live standing prose-polisher when available; explicitly out-of-scope: live captain-chat, short statuses, commit messages. *Verified by* a grep test.
10. **AC-pilot-mod-compatibility**: the pilot `docs/plans/_mods/comm-officer.md` file parses cleanly through the new helper with no changes required (the pilot's shape is the target shape). *Verified by* a static test running the helper against the pilot file.
11. **AC-live-propagation**: one live E2E test. Fixture: a minimal workflow with one `standing: true` mod declaring a trivial teammate (e.g., an echo-agent that just replies with its input). Dispatch the FO; verify (a) the FO invokes `claude-team spawn-standing`, (b) the teammate appears in team config, (c) a SendMessage from the FO reaches the teammate, (d) the teammate's reply is received. Budget ~$0.05, ~60s wallclock. *Verified by* `tests/test_standing_teammate_spawn.py`.

## Test Plan

**Static (all sub-second):**
- 1 parser test for `standing: true` flag extraction (AC-1).
- 1 parser test for `## Agent Prompt` section extraction with nested `##` in code fences (AC-2).
- 2 helper tests for spawn-absent / spawn-present behaviors (AC-3, AC-4).
- 1 helper test for enum validation (AC-5).
- 2 helper tests for error paths (AC-6).
- 1 grep test on Claude runtime adapter (AC-7).
- 4 grep tests on shared-core for concept section anchors (AC-8).
- 1 grep test on shared-core for routing prose (AC-9).
- 1 pilot-compatibility test (AC-10).

**Live (1 test, ~$0.05, ~60s):**
- `tests/test_standing_teammate_spawn.py` — fixture + FO dispatch + spawn verification + roundtrip + verification of team config member (AC-11).

Total: ~14 static tests + 1 live. Comparable scope to #157 and #159.

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

1. **Inline prompt, no abstraction** — the other session's initial move. Works; lacks distribution, drifts, not reusable.
2. **Mod with `standing: true`** — the chosen v1. Reuses existing mod primitive; introduces minimal new surface.
3. **Agent-file-as-service** — cleanest if plugin-per-workflow lands first. Deferred until then.
4. **Session-scoped outside Spacedock** — right in principle for cross-cutting teammates, but forfeits Spacedock's declarative mod semantics.
5. **First-class service primitive** — premature without 3+ examples of need.
6. **Deferred — no explicit support** — rejected because pattern is real enough to package.

The other session's proposed **new `## Hook: standing-teammate` hook type** was rejected as over-engineering: existing `## Hook: startup` + a `standing: true` flag achieves the same outcome without a new hook primitive. Mod authors already know how to write startup hooks; one new flag is the minimum viable extension.

## Open Questions (non-blocking — implementation resolves)

1. **Helper name**: `claude-team spawn-standing` vs `claude-team standing-spawn` vs `claude-team summon`. Cosmetic; implementer picks.
2. **Parser reuse**: fold standing-mod parsing into existing `parse_stages_with_defaults` call site or create a sibling `parse_mod_metadata`. Implementation picks based on code-organization ergonomics.
3. **Agent Prompt section convention vs fence**: "last section of file, everything after `## Agent Prompt` heading to EOF" (simpler; verified by AC-2) vs `<prompt>...</prompt>` fence (explicit; noisier). Pilot uses the convention; AC-2 verifies it handles nested markdown. Keep the convention.

## Sequencing constraint

This task's implementation branch will be based on `main` (post-#157 + post-#159 merge). The shared-core file gets touched again — the existing `## Probe and Ideation Discipline` section from #157 stays untouched; the new "Standing Teammates" section is additive. No conflict expected with currently-open PR #101 (#159 lands first).

## Deferred to follow-up tasks (filed separately when this lands)

- **Codex standing-teammate support** — separate runtime adapter work. File after this task ships; confirms which parts of the shared-core concept generalize and which are Claude-team-scope-specific.
- **Repo-wide `_mods/` catalog** — promotion path for workflow-local mods to span multiple workflows in the same repo. Phase 2.
- **Plugin-shipped standing teammates** — depends on plugin-per-workflow direction. Phase 3.
- **Captain-initiated orderly shutdown** — `/spacedock shutdown-standing` or similar. Phase 2.
- **Standing teammate crash recovery** — auto-respawn on detected absence. Phase 2.
