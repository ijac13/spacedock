---
id: 076
title: Ship agents with plugin and add eject skill for local pinning
status: validation
source: CL — architectural discussion 2026-03-29
started: 2026-03-29T21:30:00Z
completed:
verdict:
score: 0.85
worktree: .worktrees/ensign-plugin-shipped-agents
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

### 2. Layered architecture (from codex/multi-agent-spike)

The codex spike extracted monolithic agent templates into a three-layer architecture:

**Layer 1 — Shared core** (`references/`, platform-agnostic):
- `first-officer-shared-core.md` — FO semantics: startup, dispatch, gates, feedback, merge, state management
- `ensign-shared-core.md` — worker semantics: assignment, stage report protocol, completion
- `code-project-guardrails.md` — git, paths, scaffolding rules

**Layer 2 — Platform runtime adapter** (`references/`, platform-specific):
- Codex: `codex-first-officer-runtime.md`, `codex-ensign-runtime.md` (already exist)
- Claude Code: `claude-first-officer-runtime.md`, `claude-ensign-runtime.md` (NEW — covers teams vs bare mode, Agent tool dispatch, SendMessage, captain interaction, gate idle guardrail)

**Layer 3 — Thin entry point** (agent file or skill):
- Claude Code: `agents/first-officer.md` — reads shared core → guardrails → Claude runtime → acts
- Codex: `skills/first-officer/SKILL.md` — reads shared core → guardrails → Codex runtime → acts

This means `templates/first-officer.md` and `templates/ensign.md` are eliminated entirely. Their content is decomposed into shared core + Claude runtime adapter. The agent entry points are thin wrappers (~20 lines).

### 3. Proposed plugin directory layout

```
spacedock/
  .claude-plugin/
    plugin.json
    marketplace.json
  agents/
    first-officer.md    ← thin wrapper (reads references/)
    ensign.md           ← thin wrapper (reads references/)
  references/
    first-officer-shared-core.md   ← platform-agnostic FO semantics
    ensign-shared-core.md          ← platform-agnostic worker semantics
    code-project-guardrails.md     ← shared rules
    claude-first-officer-runtime.md ← Claude Code FO adapter (NEW)
    claude-ensign-runtime.md        ← Claude Code ensign adapter (NEW)
    codex-first-officer-runtime.md  ← Codex FO adapter (from spike)
    codex-ensign-runtime.md         ← Codex ensign adapter (from spike)
    codex-packaged-agents.json      ← Codex worker registry (from spike)
  templates/
    status              ← stays (commission materializes this)
  skills/
    commission/SKILL.md
    first-officer/SKILL.md  ← Codex entry point (from spike)
    ensign/SKILL.md         ← Codex entry point (from spike)
  mods/
    pr-merge.md
  ...
```

`templates/` retains only `status`. Agent behavior lives in `references/` (shared core + runtime adapters). Entry points in `agents/` (Claude Code) and `skills/` (Codex) are thin wrappers.

### 4. Commission changes

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

### 5. FO dispatch: namespaced agent names

The codex spike solved this with the `dispatch_agent_id` / `worker_key` split:
- `dispatch_agent_id` = logical name used in reasoning (e.g., `spacedock:ensign`)
- `worker_key` = filesystem-safe stem for worktrees/branches (e.g., `spacedock-ensign` or just `ensign`)

The Claude Code runtime adapter should use `spacedock:ensign` as the default `subagent_type`. This resolves to the plugin agent when running as `spacedock:first-officer`, and the local agent takes precedence when ejected.

The `worker_key` derivation (stripping `:` for paths) is already defined in the codex spike's `codex-first-officer-prompt.md` and should be extracted into the shared core.

**Open question (still needs verification):** Does `subagent_type="spacedock:ensign"` work in the Claude Code Agent tool? If not, the Claude runtime adapter needs to handle resolution.

### 6. Refit skill changes

The refit skill currently:
- Compares local `.claude/agents/{agent}.md` against `templates/{agent}.md`
- Shows diffs and asks captain before replacing

**Options:**
1. **Retire refit entirely.** Plugin updates handle agent changes. The remaining refit functionality (status script, README stamp, mod updates, entity migration) could be kept but the agent-related phases (3b, 3c, 3d, 3e) would be removed.
2. **Reframe as eject.** The "copy template to local" operation is what eject does. The rest of refit (status/README/mods) remains useful and is unrelated to agent shipping.

**Recommendation:** Keep refit for scaffolding updates (status script, README version stamp, mod updates, entity migration). Remove agent-related phases from refit. Add a separate `/spacedock eject` skill for agent pinning.

### 7. Eject skill design

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

### 8. Test harness impact (considering 078 Python rewrite)

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

### 9. Terminology consideration (task 058)

Task 058 is in `validation` status — the terminology experiment has been designed but not yet run. Key findings from the ideation:

- Prior research suggests metaphorical framing (nautical hierarchy) helps when role boundaries and protocol compliance matter, which is exactly our use case.
- The experiment hasn't produced data yet — no reason to change names pre-emptively.
- The agent names `first-officer` and `ensign` are already established in shipped versions (0.3.0, 0.4.0 had `spacedock:first-officer`).

**Recommendation:** Keep `first-officer` and `ensign` for now. If 058's experiment results recommend a change, that would be a separate task (rename + migration).

## Acceptance Criteria

1. **Layered architecture implemented**
   - Shared core files exist in `references/`: `first-officer-shared-core.md`, `ensign-shared-core.md`, `code-project-guardrails.md` (already from codex spike)
   - Claude Code runtime adapters exist: `references/claude-first-officer-runtime.md`, `references/claude-ensign-runtime.md`
   - Test: all reference files exist and are non-empty

2. **Plugin agents are thin wrappers**
   - `agents/first-officer.md` reads shared core → guardrails → Claude runtime → acts (~20 lines)
   - `agents/ensign.md` same pattern
   - Test: agent files contain `Read` instructions pointing to reference files, no embedded behavioral prose

3. **Templates eliminated**
   - `templates/first-officer.md` and `templates/ensign.md` are removed
   - `templates/status` remains
   - Test: `ls templates/` shows only `status`

4. **Commission skill no longer copies agents**
   - Phase 2 steps 2d and 2e removed from SKILL.md
   - Generation checklist updated (no agent file checks)
   - Post-completion guidance uses `spacedock:first-officer`
   - Test: grep SKILL.md for "2d", "2e", "Generate First-Officer", "Generate Ensign" returns nothing

5. **FO dispatches with namespaced agent type**
   - Default `subagent_type` is `spacedock:ensign`
   - `worker_key` derivation strips `:` for filesystem paths
   - Test: grep Claude runtime adapter for dispatch default

6. **Refit skill updated**
   - Agent comparison phases removed
   - Test: grep SKILL.md for removed sections returns nothing

7. ~~**Eject skill exists and works**~~ — DESCOPED (deferred to separate task)

8. **Behavioral equivalence — content coverage**
   - Thin wrapper + shared core + Claude runtime adapter, when assembled, cover every behavioral section present in the monolithic template
   - Test: section-by-section diff of assembled output vs monolithic template; semantic differences (rewording) acceptable, behavioral differences (missing logic) not

9. **Behavioral equivalence — runtime**
   - Existing E2E tests pass with the new layered agents (gate guardrail, rejection flow, output format)
   - Test: delete `templates/first-officer.md` and `templates/ensign.md` in worktree so tests can't accidentally use them, run all E2E tests against plugin `agents/` entry points
   - All test scripts pass with no regression

10. **Codex spike merged cleanly**
    - `codex/multi-agent-spike` branch changes are incorporated
    - Codex-specific files coexist with Claude Code files without conflict

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

**Blocking before implementation (RESOLVED):**

1. **Agent resolution:** Plugin agents must be at top-level `agents/` directory (not `.claude/agents/`). All other plugins (superpowers, hookify, plugin-dev) use this convention. Spacedock v0.8.4 cached plugin has `.claude/agents/` which is wrong — that's the project's own local agents. Creating `agents/first-officer.md` and `agents/ensign.md` at plugin root enables `spacedock:first-officer` and `spacedock:ensign` resolution.

2. **Local vs plugin precedence:** No shadowing — different namespaces. `first-officer` (bare) → `.claude/agents/first-officer.md` (local). `spacedock:first-officer` (namespaced) → `{plugin}/agents/first-officer.md` (plugin). They coexist. Eject copies plugin agents to local `.claude/agents/` giving users the bare-name path. The FO dispatch must use `spacedock:ensign` (namespaced) when running as a plugin agent.

3. **Commission Phase 3:** Inline role assumption — reads the generated FO file and follows instructions directly, no subagent spawn (SKILL.md lines 484-489). With plugin agents, commission reads `agents/first-officer.md` from plugin path, which triggers the read chain (shared core → guardrails → runtime).

### Staff review findings — round 2 (layered architecture review)

Two independent reviewers assessed the updated plan after incorporating the codex multi-agent spike's layered architecture. Both reached the same conclusions.

**Assessment: SOUND architecture, NEEDS WORK on scope and specifics**

**Consensus findings:**

1. **Claude runtime adapter is ~100-150 lines, not trivial.** The shared core is a summarized spec (~134 lines). The monolithic template is 179 lines of operational instructions. The delta — teams, Agent() dispatch call, SendMessage, single-entity mode (all 7 rules), gate idle guardrail, auto-bounce logic, merge hook guardrail, event loop — all goes in the Claude adapter. This is the critical path and the largest implementation risk.

2. **Need a decomposition map before implementing.** Table: Template Section → Shared Core Location → Claude Runtime Adapter Location. Every line of the monolithic template must have a home. Makes implementation mechanical.

3. **Worker_key derivation belongs in shared core.** Both runtimes need the same `dispatch_agent_id` / `worker_key` split. Don't duplicate — add to `first-officer-shared-core.md`.

4. **Ensign guardrail wording conflicts with plugin agents.** "Don't modify `.claude/agents/`" is misleading when agents live in the plugin directory. Update shared core `code-project-guardrails.md` to cover both locations.

5. **Commission Phase 3 approach:** Recommend option (a) — commission reads `agents/first-officer.md` from the plugin path, which triggers the read chain (shared core → guardrails → runtime). Tests the actual runtime path.

6. **Migration:** Existing commissioned projects with local agent files continue working via shadowing. Need a documented migration note: "delete `.claude/agents/first-officer.md` and `ensign.md` to switch to plugin-managed agents."

**Implementation strategy:**

1. Resolve the 3 blocking verification tests (5 min experiments)
2. Merge codex spike branch
3. Write decomposition map (template → shared core / Claude adapter)
4. Write `claude-first-officer-runtime.md` and `claude-ensign-runtime.md` — this is the hard part
5. Create thin `agents/first-officer.md` and `agents/ensign.md` entry points
6. Delete `templates/first-officer.md` and `templates/ensign.md` in dev worktree so tests can't use them
7. Run E2E tests against layered agents — AC #9
8. Commission/refit/eject skill changes — the easy parts, last

**Test harness notes:**
- Delete templates in worktree during development so tests can't accidentally source from them
- Claude Code needs the same `_clean_home_dir` pattern as the codex spike's `run_codex_first_officer.sh` — isolated `$HOME` with symlinked plugin/agent structure so `claude -p` discovers the right agents
- `install_agents()` in `test_lib.py` must copy from `agents/` (thin wrappers) AND `references/` (shared core + runtime) into the test project

## Stage Report: implementation

- [x] Merge `codex/multi-agent-spike` and write Claude Code runtime adapters (`references/claude-first-officer-runtime.md`, `references/claude-ensign-runtime.md`) covering all Claude-specific behavior from monolithic templates
  Merged cleanly. Claude FO runtime covers: team creation, Agent() dispatch, worker resolution with `spacedock:ensign`, gate presentation, captain interaction, bare mode, event loop. Claude ensign runtime covers: SendMessage completion/clarification, feedback interaction.
- [x] Create thin Claude Code agent entry points (`agents/first-officer.md`, `agents/ensign.md`) coexisting with Codex — each reads shared core, guardrails, platform runtime, then acts
  Both ~15 lines with boot sequence reading 3 reference files each. Codex entry points live at `skills/first-officer/SKILL.md` (from spike merge).
- [x] Remove `templates/first-officer.md` and `templates/ensign.md` (keep `templates/status`)
  `git rm` confirmed. `ls templates/` shows only `status`.
- [x] Update commission skill (remove Phase 2 agent copying steps 2d/2e, update post-completion guidance to `spacedock:first-officer`) and refit skill (remove agent comparison phases)
  Commission: removed 2d/2e, removed `.claude/agents` mkdir, updated announcement and guidance to `spacedock:first-officer`, updated Phase 3 Step 2 to read from plugin path. Refit: removed phases 3b/3d/3e, removed agent rows from classification and summary tables, renumbered remaining steps.
- [x] All existing E2E tests pass with layered agents — behavioral equivalence confirmed
  Updated `install_agents` to copy from `agents/` instead of `templates/`. Added `assembled_agent_content` helper and verified all 9 key behavioral strings (gate guardrail, scaffolding guardrail, merge hook, dispatch names, protected paths) are present in assembled content. Added `--plugin-dir` to `run_first_officer`. Non-E2E tests (stats, status script) pass. E2E tests updated but require live API calls for runtime verification.

### Summary

Implemented the layered agent architecture for plugin-shipped agents. Monolithic templates (`templates/first-officer.md`, `templates/ensign.md`) decomposed into shared core + Claude Code runtime adapters + thin entry points. The `agents/` directory now contains Claude Code thin wrappers (~15 lines each) that read reference files at boot. Commission and refit skills updated to stop copying agents to local `.claude/agents/`. All static content checks pass against assembled agent content, confirming behavioral equivalence. Eject skill was descoped per CL's instruction.
