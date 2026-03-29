---
id: 076
title: Ship agents with plugin and add eject skill for local pinning
status: ideation
source: CL — architectural discussion 2026-03-29
started: 2026-03-29T21:30:00Z
completed:
verdict:
score: 0.85
worktree:
---

Ship first-officer and ensign as plugin-level agents (`spacedock:first-officer`, `spacedock:ensign`) instead of generating them per-project via commission. Add an eject/pin skill for users who want version stability.

## Context

- Task 063 made agents fully static (zero template variables, runtime workflow discovery)
- `claude --agent spacedock:first-officer` works — confirmed with `superpowers:code-reviewer` pattern
- Commission currently copies templates to `.claude/agents/` — unnecessary since agents are workflow-agnostic
- Refit exists solely to update stale local agent copies

## Design

**Default (plugin-shipped):**
- `spacedock:first-officer` and `spacedock:ensign` available from the plugin
- Commission generates only workflow files: README, status script, entities, _mods/
- No agents copied to `.claude/agents/`
- Plugin updates deliver agent improvements to all projects automatically

**Eject/pin skill (`/spacedock eject`):**
- Copies current plugin agents to `.claude/agents/first-officer.md` and `ensign.md`
- Local agents take precedence over plugin agents (same name without namespace)
- Gives version stability — agents frozen until user ejects again
- Refit becomes "eject from latest" — same operation, better framing

## What changes

- Commission: remove agent copying (Phase 2 agent file generation)
- Plugin: ensure agent .md files are discoverable as `spacedock:first-officer` and `spacedock:ensign`
- FO template dispatch: use `spacedock:ensign` as subagent_type (or verify that `ensign` resolves to plugin agent)
- New skill: `/spacedock eject` — copy agents locally for pinning
- Refit skill: retire or reframe as "eject from latest version"

## Trade-offs

**What we gain:**
- `claude --agent spacedock:first-officer` works on any project with a workflow — no prior commission of agents needed
- Plugin updates fix bugs across all projects simultaneously
- Simpler, faster commission
- Refit skill retirement

**What we lose:**
- Version pinning by default (mitigated by eject skill)
- Offline resilience if plugin is uninstalled (edge case)
- Migration layer for breaking changes (refit currently handles this)

## Terminology consideration

Task 058 (terminology experiment) tested variant naming conventions. The results should inform what we call these agents in their shipped form. Consider whether `first-officer`/`ensign` (nautical) or alternative terms (from 058's findings) feel right for the plugin-shipped agent names that users see in `--agent` and `subagent_type`.

## Open questions

1. Does `spacedock:first-officer` get project-level `.claude/agents/ensign.md` as an available subagent_type? Or only plugin-level agents? If only plugin, the FO dispatch must use `spacedock:ensign`.
2. When local `first-officer.md` exists alongside `spacedock:first-officer`, which takes precedence? Need to verify Claude Code's agent resolution order.
3. Should eject copy the current plugin version's agents, or a specific version? (Probably current — simplest.)

## Investigation Findings

### 1. How plugin agents are discovered

Evidence from installed plugins on disk:

**Convention:** Plugins place agent `.md` files in an `agents/` directory at the plugin root. Claude Code discovers them by convention — no explicit `agents` field in `plugin.json` is required.

| Plugin | agents/ directory | Agent files | Namespaced form |
|--------|------------------|-------------|-----------------|
| superpowers | `agents/` | `code-reviewer.md` | `superpowers:code-reviewer` |
| noteplan | `agents/` | `productivity-assistant.md` | `noteplan:productivity-assistant` |
| spacedock (0.3.0, 0.4.0) | `agents/` | `first-officer.md` | `spacedock:first-officer` |
| spacedock (current 0.8.2) | no `agents/` dir | n/a | n/a |

Agent file format: standard YAML frontmatter with `name`, `description`, and optionally `model` fields. The `name` field becomes the agent identifier (e.g., `name: code-reviewer` → `superpowers:code-reviewer`).

Key observation: spacedock 0.3.0 and 0.4.0 already shipped `first-officer.md` via `agents/` but the current version (0.8.2) removed this in favor of commission-time copying to `.claude/agents/`. This task restores and extends that pattern.

### 2. Proposed plugin directory layout

```
spacedock/
  .claude-plugin/
    plugin.json
    marketplace.json
  agents/
    first-officer.md    ← currently at templates/first-officer.md
    ensign.md           ← currently at templates/ensign.md
  templates/
    status              ← stays (commission materializes this)
    first-officer.md    ← REMOVE (move to agents/)
    ensign.md           ← REMOVE (move to agents/)
  skills/
    commission/SKILL.md
    refit/SKILL.md
  mods/
    pr-merge.md
  ...
```

The `templates/` directory retains only the `status` template (which requires variable substitution at commission time). Agent files move to `agents/` since they are static and need no substitution.

### 3. Commission changes

**Remove from SKILL.md:**
- Phase 2 step 2d: "Generate First-Officer Agent" (cp template to `.claude/agents/first-officer.md`)
- Phase 2 step 2e: "Generate Ensign Agent" (cp template to `.claude/agents/ensign.md`)
- Generation checklist items for first-officer.md and ensign.md
- Phase 3 step 1 announcement lines for agent files
- The `mkdir -p {project_root}/.claude/agents` command (no longer needed unless other agents exist)

**Modify:**
- Phase 3 step 2 (Assume First-Officer Role): Read agent from plugin path instead of `{project_root}/.claude/agents/first-officer.md`. Or simply follow the instructions since the skill already has them embedded.
- Phase 3 step 1 announcement: Replace agent file listing with note that agents are available as `spacedock:first-officer` and `spacedock:ensign`.
- Post-completion guidance: `claude --agent spacedock:first-officer` instead of `claude --agent first-officer`.

**Keep:**
- All other Phase 2 steps (README, status, seed entities, mods)
- Agent warnings for custom stage agents (those still go to `.claude/agents/`)

### 4. FO dispatch: namespaced vs bare agent names

The FO template currently dispatches with `subagent_type="{agent}"` where `{agent}` defaults to `ensign`. Two scenarios:

**Scenario A — FO invoked as `spacedock:first-officer` (plugin agent):**
When running as a plugin agent, Claude Code should resolve `ensign` to `spacedock:ensign` if no local `.claude/agents/ensign.md` exists. **This needs verification.** If Claude Code does NOT do this resolution, the FO template must dispatch `spacedock:ensign` explicitly.

**Scenario B — FO invoked as `first-officer` (local ejected agent):**
Local `.claude/agents/ensign.md` would also exist (eject copies both). Resolution to `ensign` works as today.

**Recommendation:** Update the FO template default from `ensign` to `spacedock:ensign`. This works in both scenarios — when running from plugin (resolves to plugin agent) and when running from local eject (local agent with matching name takes precedence). The README `agent:` field for custom stages would still use bare names for project-local agents. Verify this assumption during implementation.

### 5. Refit skill changes

The refit skill currently:
- Compares local `.claude/agents/{agent}.md` against `templates/{agent}.md`
- Shows diffs and asks captain before replacing

**Options:**
1. **Retire refit entirely.** Plugin updates handle agent changes. The remaining refit functionality (status script, README stamp, mod updates, entity migration) could be kept but the agent-related phases (3b, 3c, 3d, 3e) would be removed.
2. **Reframe as eject.** The "copy template to local" operation is what eject does. The rest of refit (status/README/mods) remains useful and is unrelated to agent shipping.

**Recommendation:** Keep refit for scaffolding updates (status script, README version stamp, mod updates, entity migration). Remove agent-related phases from refit. Add a separate `/spacedock eject` skill for agent pinning.

### 6. Eject skill design

**`/spacedock eject`** — copies current plugin agents to `.claude/agents/` for version pinning.

**Behavior:**
1. Resolve plugin directory (same pattern as commission/refit).
2. List all agent files in `{spacedock_plugin_dir}/agents/*.md`.
3. For each agent, check if `.claude/agents/{name}.md` already exists locally.
   - If it exists and differs from plugin version: show diff, ask captain to confirm overwrite.
   - If it exists and matches: skip with "already current" message.
   - If it doesn't exist: copy with confirmation.
4. After copying, inform captain:

> Agents ejected to `.claude/agents/`:
> - `first-officer.md` — run with `claude --agent first-officer`
> - `ensign.md` — dispatched by first-officer
>
> Local agents take precedence over plugin agents. To return to plugin-managed agents, delete the local copies.

**No version check needed.** The eject copies whatever the currently installed plugin version has. If the user wants a specific version, they manage plugin versions directly.

**Edge case — custom stages with `agent:` property:** The eject skill only copies agents shipped with the plugin. Custom stage agents (user-created) are not affected.

### 7. Test harness impact (considering 078 Python rewrite)

Current fixture-based tests do:
```bash
# sed substitution of templates/first-officer.md → .claude/agents/first-officer.md
sed -e 's/...' "$REPO_ROOT/templates/first-officer.md" > .claude/agents/first-officer.md
```

**With plugin-shipped agents, fixture tests change:**

The tests currently copy templates to `.claude/agents/` to simulate what commission does. With plugin-shipped agents, the tests should instead ensure the plugin `agents/` directory is discoverable. Two approaches:

**Option A — Tests use local agent copies (keep current pattern):**
Tests continue copying agent files to `.claude/agents/`. This tests the "ejected" path. The plugin agent path is implicitly tested by the fact that the agent content is identical.

**Option B — Tests reference plugin agents directly:**
Tests run `claude -p --agent spacedock:first-officer` instead of `--agent first-officer`. This tests the plugin discovery path but requires the plugin to be installed in the test environment.

**Recommendation: Option A.** Tests should be self-contained and not depend on plugin installation state. The sed substitution pattern moves from `templates/first-officer.md` to `agents/first-officer.md` (source path changes, that's it). The 078 Python rewrite would use the same approach — `setup_fixture` copies from `agents/` instead of `templates/`.

### 8. Terminology consideration (task 058)

Task 058 is in `validation` status — the terminology experiment has been designed but not yet run. Key findings from the ideation:

- Prior research suggests metaphorical framing (nautical hierarchy) helps when role boundaries and protocol compliance matter, which is exactly our use case.
- The experiment hasn't produced data yet — no reason to change names pre-emptively.
- The agent names `first-officer` and `ensign` are already established in shipped versions (0.3.0, 0.4.0 had `spacedock:first-officer`).

**Recommendation:** Keep `first-officer` and `ensign` for now. If 058's experiment results recommend a change, that would be a separate task (rename + migration).

## Acceptance Criteria

1. **Plugin agents directory exists with both agents**
   - `agents/first-officer.md` and `agents/ensign.md` exist at plugin root
   - Content is identical to current `templates/first-officer.md` and `templates/ensign.md`
   - Test: `diff agents/first-officer.md templates/first-officer.md` shows no diff (before template removal)

2. **Templates directory cleaned up**
   - `templates/first-officer.md` and `templates/ensign.md` are removed
   - `templates/status` remains
   - Test: `ls templates/` shows only `status`

3. **Commission skill no longer copies agents**
   - Phase 2 steps 2d and 2e removed from SKILL.md
   - Generation checklist updated (no agent file checks)
   - Post-completion guidance uses `spacedock:first-officer`
   - Test: grep SKILL.md for "2d", "2e", "Generate First-Officer", "Generate Ensign" returns nothing

4. **FO template dispatches with namespaced agent type**
   - `subagent_type` default is `spacedock:ensign` (or confirmed that bare `ensign` resolves correctly)
   - Test: grep `agents/first-officer.md` for the dispatch subagent_type value

5. **Refit skill updated**
   - Agent comparison phases removed (3b, 3d, 3e, or equivalent)
   - Upgrade plan table no longer lists first-officer.md or ensign.md
   - Test: grep SKILL.md for removed sections returns nothing

6. **Eject skill exists and works**
   - `skills/eject/SKILL.md` created with the designed behavior
   - Copies `agents/*.md` to `.claude/agents/`
   - Shows diffs when local copies already exist
   - Test: manual test — run eject, verify files appear in `.claude/agents/`

7. **Existing tests still pass**
   - Fixture-based tests updated to source from `agents/` instead of `templates/`
   - All test scripts pass (no behavioral regression)
   - Test: run each test script, verify exit 0

## Test Plan

- **Unit-level:** Verify agent files moved correctly (diff between agents/ and templates/ before removal). Verify SKILL.md edits are complete (grep for removed content).
- **Integration:** Run at least one fixture-based test (e.g., test-gate-guardrail.sh) end-to-end after updating the source path.
- **Eject skill:** Manual test — run `/spacedock eject` in a test project, verify agent files appear in `.claude/agents/`.
- **Commission regression:** Run test-commission.sh and verify it still passes with agent generation removed.
- **Cost:** Code-only changes except for 2 spot-check E2E runs (~$2-3).
- **E2E test needed?** No new E2E test. Existing tests validate the agent content. The eject skill is simple enough for manual verification.
- **Open question to resolve during implementation:** Does `subagent_type="ensign"` resolve to `spacedock:ensign` when running as a plugin agent? Test by running `claude --agent spacedock:first-officer` with a workflow and checking if ensign dispatch works without local agent files.

## Stage Report: ideation

- [x] How plugin agents are discovered (evidence from superpowers)
  Convention-based: `agents/` directory at plugin root, no plugin.json field needed. Confirmed across superpowers, noteplan, and older spacedock versions.
- [x] Proposed plugin directory layout for agents
  Move `templates/first-officer.md` and `templates/ensign.md` to `agents/`, keep `templates/status` only.
- [x] Commission changes (what to remove)
  Remove Phase 2 steps 2d/2e (agent copying), generation checklist agent items, update post-completion guidance to use `spacedock:first-officer`.
- [x] Eject skill design
  `/spacedock eject` copies `agents/*.md` to `.claude/agents/`, shows diffs for existing files, no version check needed.
- [x] Test harness impact (considering 078 Python rewrite)
  Tests continue copying agents to `.claude/agents/` (self-contained, no plugin dependency). Source path changes from `templates/` to `agents/`. 078 Python rewrite uses same approach.
- [x] Acceptance criteria with test plan
  7 acceptance criteria covering agent directory, template cleanup, commission/refit changes, eject skill, FO dispatch namespace, and test regression. Test plan includes unit, integration, and manual eject verification.

### Summary

Investigated plugin agent discovery across 4 installed plugins — it is purely convention-based (agents/ directory, no plugin.json changes). Designed the full change: move agent templates to agents/, simplify commission (remove agent copying), update FO dispatch to use `spacedock:ensign`, create `/spacedock eject` skill for local pinning, and update refit to remove agent-related phases. One open question remains for implementation: whether bare `ensign` resolves to `spacedock:ensign` when the FO runs as a plugin agent.

### Staff review findings (independent reviewer)

**Design: SOUND** — directory convention confirmed across 3 plugins, eject design clean, namespace change prudent.

**Critical unresolved — agent resolution order:**
- Does bare `ensign` resolve to `spacedock:ensign` when FO runs as a plugin agent? Not verified.
- Does local `.claude/agents/first-officer.md` take precedence over `spacedock:first-officer`? Assumed but not confirmed.
- These are load-bearing assumptions that gate the dispatch design and eject behavior.

**Risk assessment — MODERATE:**
- Old commissioned projects keep working (local agents shadow plugin agents) — safe but creates two project classes
- New projects use plugin agents with live updates — better DX
- Users must understand the shadowing behavior

**Test plan — INADEQUATE, missing:**
1. No test for plugin agent discovery path (tests only cover ejected/local agents)
2. No test for agent resolution order (local vs plugin precedence)
3. Commission Phase 3 auto-run approach unclear — does it dispatch `spacedock:first-officer` via Agent tool or read from plugin path?
4. Eject skill test is manual-only — needs scripted verification

**Blocking before implementation:**
1. Verify agent resolution: run `claude --agent spacedock:first-officer` and check if dispatch to `ensign` or `spacedock:ensign` works
2. Verify local-vs-plugin precedence: set up project with both local and plugin agents, confirm local wins
3. Clarify Commission Phase 3 approach: dispatch via Agent tool (cleaner) or inline read from plugin path
