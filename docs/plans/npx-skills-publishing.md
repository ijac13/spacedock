---
id: 057
title: Publish spacedock via npx skills ecosystem
status: ideation
source: CL
started: 2026-03-27T23:45:00Z
completed:
verdict:
score:
worktree:
---

Make spacedock installable via `npx skills add clkao/spacedock` — the Vercel Labs `skills` CLI. This is the dominant distribution channel for Claude Code skills and supports 40+ coding agents.

## Problem statement

Spacedock currently distributes via `claude plugin marketplace add clkao/spacedock`. This only works for Claude Code users. The Vercel Labs `skills` CLI (`npx skills add`) supports 40+ coding agents (Claude Code, Cursor, Codex, OpenCode, Windsurf, Gemini CLI, GitHub Copilot, etc.) and is the dominant distribution channel for agent skills. Supporting it would dramatically expand spacedock's reach.

However, spacedock is more than just skill files. The commission and refit skills depend on template files (`templates/`) that they copy into the user's project at runtime. A naive skills-CLI install would only copy the SKILL.md files, losing access to the templates — making the skills non-functional.

## Research findings

### 1. How the skills CLI works

**Source resolution:** `npx skills add clkao/spacedock` parses `clkao/spacedock` as GitHub shorthand, constructing `https://github.com/clkao/spacedock.git`. It also supports full URLs, GitLab, local paths, and `@skill` syntax for single-skill installs. (Source: `src/source-parser.ts`)

**Cloning:** The CLI does a shallow clone (`--depth 1`) of the repo into a temp directory. (Source: `src/git.ts`)

**Skill discovery:** It searches well-known directories in order: `skills/`, `.claude/skills/`, `.agents/skills/`, and many agent-specific paths. It also reads `.claude-plugin/marketplace.json` and `.claude-plugin/plugin.json` for declared skill paths. Each skill is a directory containing a `SKILL.md` file with `name` and `description` in YAML frontmatter. (Source: `src/skills.ts`, `src/plugin-manifest.ts`)

**Installation:** For each discovered skill, the CLI copies the entire skill **directory** (not just the SKILL.md) to the canonical location `.agents/skills/<skill-name>/` and creates symlinks for each target agent (e.g., `.claude/skills/<skill-name>/`). Files starting with `.` and directories like `.git` are excluded. (Source: `src/installer.ts`, `copyDirectory()`)

**Key finding: directory copy, not file copy.** The installer copies the entire directory tree under each skill directory. This means auxiliary files alongside SKILL.md are preserved.

**Plugin manifest support:** The skills CLI reads `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` to discover additional skill paths. Spacedock already has these files, and the skills CLI will use them to find `skills/commission/` and `skills/refit/`. (Source: `src/plugin-manifest.ts`)

### 2. Spacedock's plugin structure

Spacedock ships these components:

| Component | Path | Purpose |
|-----------|------|---------|
| Commission skill | `skills/commission/SKILL.md` | Interactive workflow design (20K lines) |
| Refit skill | `skills/refit/SKILL.md` | Upgrade workflow scaffolding (13K lines) |
| First-officer template | `templates/first-officer.md` | Agent that orchestrates the workflow |
| Ensign template | `templates/ensign.md` | Worker agent for stage execution |
| Validator template | `templates/validator.md` | Validation agent |
| PR-lieutenant template | `templates/pr-lieutenant.md` | PR workflow agent |
| Status template | `templates/status` | Bash script for workflow status views |
| Plugin manifest | `.claude-plugin/plugin.json` | Plugin metadata (version, name) |
| Marketplace manifest | `.claude-plugin/marketplace.json` | Marketplace catalog entry |

**Template dependency:** Both skills reference `{spacedock_plugin_dir}/templates/` at runtime. The commission skill copies templates into the user's project during workflow generation. The refit skill compares existing agent files against templates to detect drift. Without access to the `templates/` directory, both skills are non-functional.

### 3. Compatibility assessment: skills CLI vs. plugin marketplace

**They can coexist.** The two systems install to different locations and serve different purposes:

- **Plugin marketplace** (`claude plugin marketplace add`): Installs the entire repo as a plugin. Claude Code resolves the plugin directory at runtime, giving skills access to sibling directories like `templates/`. The `{spacedock_plugin_dir}` reference works because Claude Code knows the plugin root.

- **Skills CLI** (`npx skills add`): Copies individual skill directories to `.claude/skills/` (or agent-equivalent). Skills are standalone — they have no knowledge of a "plugin root" or sibling directories.

**The gap:** When installed via the skills CLI, the commission and refit skills would be copied to `.claude/skills/commission/` and `.claude/skills/refit/`. They would reference `{spacedock_plugin_dir}/templates/first-officer.md`, but there would be no `spacedock_plugin_dir` — the templates directory wouldn't exist.

### 4. Options analysis

**Option A: Embed templates in skill directories.** Copy each template file into the skill directory (e.g., `skills/commission/templates/first-officer.md`). Update skill prompts to reference `templates/` relative to the skill directory itself rather than the plugin root. The skills CLI copies the entire directory, so templates travel with the skill.

- Pro: Works with the skills CLI as-is. No duplication at install time — each skill carries exactly what it needs.
- Con: Templates would be duplicated across commission and refit skill directories in the repo. Both skills reference the same template files. A build/copy step or symlinks within the repo could solve this.
- Con: Updating templates requires updating them in multiple places (or maintaining the build step).

**Option B: Flatten templates alongside SKILL.md.** Put template files directly in each skill directory (not in a subdirectory).

- Pro: Simplest structure.
- Con: Namespace collision risk. Template filenames like `first-officer.md` alongside `SKILL.md` is messy.

**Option C: Keep plugin-only distribution.** Don't support skills CLI — keep requiring `claude plugin marketplace add`.

- Pro: No changes needed.
- Con: Limits distribution to Claude Code users only.

**Option D: Build step that assembles skill packages.** A script that copies templates into skill directories before publishing. The repo source of truth stays in `templates/`, but a `scripts/build-skills.sh` assembles self-contained skill directories for distribution.

- Pro: Clean source repo, self-contained skills for distribution.
- Con: Adds build complexity. The skills CLI clones the repo directly — it would need the built artifacts committed, or we'd need a separate distribution branch.

## Proposed approach

**Option A with symlinks in the repo.** This is the simplest approach that works:

1. **Add `templates/` and `mods/` symlinks inside each skill directory** pointing to the repo root:
   - `skills/commission/templates` -> `../../templates`
   - `skills/commission/mods` -> `../../mods`
   - `skills/refit/templates` -> `../../templates`
   - `skills/refit/mods` -> `../../mods`

2. **Update skill prompts** to reference templates and mods relative to the skill's own directory:
   - Change `{spacedock_plugin_dir}/templates/first-officer.md` to reference templates relative to the skill file location
   - The skills CLI's `copyDirectory()` uses `dereference: true` when copying files (and `cp` with `dereference: true` for symlinks), so symlinks to templates will be resolved and the actual files will be copied to the install destination

3. **Update plugin.json references** if needed for the marketplace flow to remain compatible.

4. **Both distribution methods work:**
   - Plugin marketplace: Skills find templates via the plugin directory (existing behavior still works, since the symlinks resolve within the repo)
   - Skills CLI: Templates are copied alongside each SKILL.md into `.claude/skills/commission/templates/` etc.

**Why not a build step (Option D)?** The skills CLI clones the repo directly from GitHub. It doesn't run any build commands. So built artifacts would need to be committed to the repo or on a separate branch, which adds maintenance overhead. Symlinks are cleaner — they work at the source level and the CLI's `dereference: true` handles them correctly.

**What about skill prompt references to `{spacedock_plugin_dir}`?** Both skills use this placeholder when referencing templates. This needs to change to something that works in both contexts:
- In plugin mode, the skill knows its own directory. Templates are at `./templates/` relative to the skill.
- In skills-CLI mode, templates are also at `./templates/` relative to the installed skill directory (because the CLI copied/dereferenced them).

The prompt change is: replace all `{spacedock_plugin_dir}/templates/` references with a path relative to the skill's own location. This is the key change that makes both distribution methods work with a single skill file.

**Plugin version detection (refit):** The refit skill reads `.claude-plugin/plugin.json` for the spacedock version. When installed via skills CLI, this file won't exist. The skill should fall back to reading a version from its own frontmatter or a version file within its directory. Adding a `version` field to the SKILL.md frontmatter or a `VERSION` file alongside it would solve this.

## Acceptance criteria

1. `npx skills add clkao/spacedock --list` shows both `commission` and `refit` skills
2. `npx skills add clkao/spacedock -a claude-code` installs both skills to `.agents/skills/` with symlinks to `.claude/skills/`
3. After skills-CLI install, `/commission` generates a working workflow (templates and mods are accessible)
4. After skills-CLI install, `/refit` can detect and upgrade workflow scaffolding (templates and mods are accessible)
5. `claude plugin marketplace add clkao/spacedock` continues to work (no regression)
6. Template files exist in the installed skill directories (e.g., `.agents/skills/commission/templates/first-officer.md`)
7. Mod files exist in the installed skill directories (e.g., `.agents/skills/commission/mods/pr-merge.md`)
8. The spacedock version is accessible to the refit skill regardless of install method

### Out of scope (deferred to task 036)

- Cross-agent execution (making generated workflows run on Codex, Gemini CLI, Copilot, Cursor, OpenCode, Windsurf)
- `--target` parameter for commission
- Tier 2/3 portability: target-specific agent file formats (TOML for Codex, `.gemini/agents/*.md` for Gemini, etc.) and dispatch mechanism adaptation
- Note: cross-agent execution is now classified REALISTIC (not aspirational) — all major agents gained subagent support in early 2026

## Relationship with task 036 (compile targets)

Task 036 proposes treating commission as a compiler with `--target` (claude-code, codex, portable). Task 057 is about **distribution** — how spacedock gets installed. These operate at different layers:

- **057 (this task):** Makes spacedock installable via `npx skills add`. The skill files need to be self-contained (templates bundled). This is target-agnostic — the symlink/embed approach works regardless of what commission generates.
- **036 (compile targets):** Changes what commission *outputs* per platform. A `--target codex` would generate `AGENTS.md` instead of `.claude/agents/`. A `--target portable` would generate only README + status (no agent files).

**Key insight:** 036 subsumes 057's cross-agent *execution* concerns. The cross-agent compatibility analysis (updated via web research, March 2026) found that all major coding agents now support subagent spawning and multi-agent orchestration — cross-agent execution is realistic, not aspirational. However, the orchestration APIs differ per agent (Codex uses TOML agent files, Gemini CLI uses `.gemini/agents/*.md`, etc.). Task 036 solves this by generating platform-native orchestration. So 057 should **not** attempt cross-agent execution fixes — it should only make the skill files installable.

**What 057 owns:** Making `npx skills add clkao/spacedock` work for Claude Code users. Templates travel with skills, `{spacedock_plugin_dir}` references become relative, version detection works without plugin manifest.

**What 036 owns:** Making commission generate output that runs on non-Claude-Code agents. This is now a more tractable problem than previously assumed — the target agents have real subagent systems, so 036 needs to compile to their specific formats rather than invent a workaround for missing capabilities.

**No blocking dependency:** 057 can be implemented before 036 exists. The symlink approach is additive — it doesn't change the commission output format, just how the skill files locate their assets.

## Open questions

1. **Symlink deref verification:** The skills CLI `copyDirectory()` uses `dereference: true` on individual file copies, but does it follow directory symlinks when iterating with `readdir`? Need to verify that `skills/commission/templates/` (a symlink to `../../templates/`) is traversed during copy. The `readdir` uses `withFileTypes` and filters `entry.isDirectory()` — need to confirm this returns true for symlinked directories. If not, actual directories with copies may be needed instead.

   **Mitigation if symlinks don't work:** Use a build script (`scripts/build-skills.sh`) that copies `templates/` into each skill directory before publishing. The built artifacts would be committed to the repo. This is Option D from the analysis — less clean but guaranteed to work. A lightweight alternative: commit actual directory copies (not symlinks) and use a CI check to ensure they stay in sync with `templates/`.

2. **Skill prompt self-location:** How does a skill installed via the skills CLI know its own directory path? If the agent presents skills by injecting their content into the system prompt, the skill has no way to know its filesystem location. This may require the skill to use a known install path (`.agents/skills/commission/templates/`) instead of a relative reference. Needs investigation.

   **Note:** This question applies to both `templates/` and `mods/` references. The `{spacedock_plugin_dir}` placeholder is resolved by Claude Code's plugin system. When installed via skills CLI, there is no plugin system — the skill is just a markdown file injected into context. The replacement mechanism needs to work without plugin-level path resolution.

3. **Mods directory:** The current ideation focuses on `templates/` but both skills also reference `{spacedock_plugin_dir}/mods/`. The same symlink/embed approach applies: add `mods/` symlinks in each skill directory. This should be called out in the implementation plan.

## Cross-agent compatibility analysis

*Updated 2026-03-28 with web research. The previous analysis (based on May 2025 knowledge cutoff) incorrectly classified Codex, Gemini CLI, and OpenCode as single-agent systems. As of early 2026, the multi-agent landscape has shifted substantially.*

### Agent multi-agent capabilities (as of March 2026)

| Agent | Subagent spawning | Agent definitions | Inter-agent comms | Skill activation |
|-------|------------------|-------------------|-------------------|-----------------|
| **Claude Code** | Agent tool, TeamCreate | `.claude/agents/*.md` | SendMessage (team messaging) | `/slash` on-demand |
| **Codex** | Native subagents (Feb 2026), `agents.max_depth` config | `~/.codex/agents/*.toml` (custom agents) | Orchestrator collects results | Skills via SKILL.md |
| **Gemini CLI** | Experimental subagents, `activate_skill` tool | `.gemini/agents/*.md` with YAML frontmatter | Subagent returns summary to parent | `activate_skill` auto-discovery |
| **Cursor** | Subagents (v2.4, Jan 2026), orchestrator-worker pattern | Custom subagent definitions | Lead agent aggregates results | SKILL.md auto-discovery |
| **GitHub Copilot** | Fleet mode (parallel subagents), `read_agent`/`task` tools | Custom agents via `.github/copilot/agents/` | Subagent results to orchestrator | SKILL.md, AGENTS.md |
| **Windsurf** | Parallel Cascade sessions via git worktrees (Wave 13) | Cascade config (no file-based agent defs) | No inter-session communication | Skills via Cascade |
| **OpenCode** | Native subagents, agent teams (Feb 2026) | `.opencode/agents/*.md` or `opencode.json` | Event-driven peer-to-peer messaging | Tab-switch between primary agents |

### Spacedock constructs mapped to equivalents

**Tier 1 — Portable now (phrasing changes only):**
- Tool name references (`Read`, `Write`, `Bash`, `Glob`, `Edit`) — all agents have file/shell equivalents. Fix: use generic language ("read the file").
- `{spacedock_plugin_dir}` template resolution — fix with symlink approach (templates travel with skill directory).
- Git worktree commands — universal shell commands, work everywhere. Windsurf Wave 13 added explicit git worktree support; Copilot community is experimenting with worktree-based subagent isolation.

**Tier 2 — Portable with adaptation (equivalents exist but differ):**
- `.claude/agents/` agent definitions — every major agent now has an equivalent location and format:

  | Agent | Agent file location | Format |
  |-------|-------------------|--------|
  | Claude Code | `.claude/agents/*.md` | Markdown with custom instructions |
  | Codex | `~/.codex/agents/*.toml` | TOML with model, sandbox, MCP config |
  | Gemini CLI | `.gemini/agents/*.md` | Markdown with YAML frontmatter |
  | Cursor | `.cursor/agents/*.md` | Markdown with YAML frontmatter (name, description, model, readonly, is_background) |
  | GitHub Copilot | `.github/copilot/agents/` | Custom agents; also reads AGENTS.md and CLAUDE.md |
  | OpenCode | `.opencode/agents/*.md` or `opencode.json` | Markdown (filename = agent name) or JSON config |
  | Windsurf | Cascade config | Not file-based agent definitions (yet) |

- Slash command invocation (`/commission`) — Gemini CLI auto-discovers skills via `activate_skill` with progressive disclosure (frontmatter only until activated). Cursor and Copilot load SKILL.md. Codex supports skills via SKILL.md. Most agents now support on-demand activation, so large skills are not problematic.

**Tier 3 — Requires target-specific orchestration:**

These are the constructs spacedock's *generated workflow runtime* depends on. Each has equivalents, but the API and communication model differ per agent.

- **`Agent()` subagent spawning with `subagent_type`** — spacedock's first-officer dispatches ensigns via `Agent(type="ensign")`. Equivalents:

  | Agent | Dispatch mechanism | Named agent support |
  |-------|--------------------|-------------------|
  | Claude Code | `Agent(type="ensign")` tool | Yes — `.claude/agents/ensign.md` |
  | Codex | Reference custom agent by name in prompt; orchestrator spawns | Yes — `~/.codex/agents/*.toml`, also per-repo `.agents/` proposed |
  | Gemini CLI | Subagents exposed as tools of same name; `@agent_name` explicit dispatch | Yes — `.gemini/agents/*.md` |
  | Cursor | Task tool spawns subagent; custom agents via `.cursor/agents/` | Yes — recursive spawning supported (v2.5) |
  | GitHub Copilot | `task` tool or `/fleet` for parallel dispatch; `@CUSTOM-AGENT-NAME` | Yes — custom agents as subagents (GA Mar 2026) |
  | OpenCode | Subagents via config; agent teams via ensemble plugin | Yes — `.opencode/agents/*.md` |
  | Windsurf | Parallel Cascade sessions via git worktrees (Wave 13) | No named agent dispatch — parallel sessions are independent |

- **`TeamCreate` / `SendMessage` inter-agent communication** — spacedock's first-officer creates a team and sends messages to ensigns. This is the construct with the most variation:

  | Agent | Communication model | Closest equivalent |
  |-------|--------------------|--------------------|
  | Claude Code | `TeamCreate` + `SendMessage` peer-to-peer; shared `TaskList` | Native — this is the source construct |
  | Codex | Orchestrator collects results from subagents; no direct peer messaging. MCP + Agents SDK enables hand-offs via shared artifacts (`REQUIREMENTS.md`, `AGENT_TASKS.md`) | Orchestrator-collects pattern; no `SendMessage` equivalent |
  | Gemini CLI | Subagent returns summary to parent; A2A protocol for remote agents; internal MessageBus migration in progress | Return-to-parent; no peer messaging between subagents |
  | Cursor | Lead agent aggregates subagent results; async background agents (v2.5) | Orchestrator-collects; no peer messaging |
  | GitHub Copilot | Fleet mode: orchestrator dispatches and collects; `/tasks` view for monitoring | Orchestrator-collects; no peer messaging |
  | OpenCode | Event-driven peer-to-peer messaging (rebuilt Claude Code's model); append-only JSONL inboxes | **Closest match** — has `SendMessage` equivalent with peer-to-peer |
  | Windsurf | Independent parallel sessions; no inter-session communication | No equivalent — sessions are isolated |

- **`TaskCreate` / `TaskUpdate` shared task tracking** — spacedock uses shared task lists for coordination:

  | Agent | Task tracking |
  |-------|--------------|
  | Claude Code | `TaskCreate`/`TaskUpdate` shared across team | Native |
  | Codex | CSV-based batch orchestration (`spawn_agents_on_csv`, `report_agent_job_result`) | Batch-oriented, not real-time task board |
  | Gemini CLI | No shared task primitive | None |
  | Cursor | No shared task primitive (session-scoped) | None |
  | GitHub Copilot | `/tasks` view shows subagent status | Read-only monitoring, not shared mutable state |
  | OpenCode | Shared task board via ensemble plugin | **Closest match** |
  | Windsurf | Cascade internal Todo list | Single-agent only |

### Communication model implications for 036

The research reveals **three distinct orchestration patterns** across agents, which suggests 036 might target patterns rather than individual agents:

1. **Team messaging** (Claude Code, OpenCode): Peer-to-peer `SendMessage`, shared task lists. The first-officer can send work to specific ensigns and receive updates. This is spacedock's native model.

2. **Orchestrator-collects** (Codex, Gemini CLI, Cursor, Copilot): The lead agent spawns workers and collects results. No direct worker-to-worker communication. The first-officer would need to be restructured as a sequential orchestrator that dispatches one ensign at a time (or in parallel batches) and collects results rather than using message passing.

3. **Independent sessions** (Windsurf): Parallel sessions with no coordination primitive. The first-officer pattern doesn't map well. Workflows would need to be manually coordinated or use filesystem-as-state (shared files for communication).

### Per-agent assessment (updated)

| Agent | Install works? | Commission skill runs? | Generated workflow runs? | Classification |
|-------|---------------|----------------------|------------------------|----------------|
| Claude Code (no plugin) | Yes | Yes (with Tier 1 fixes) | Yes | REALISTIC — this task (057) |
| Codex | Yes | Likely (with Tier 1+2 fixes) | Yes (with target-specific orchestration) | REALISTIC — via 036 compile target |
| Gemini CLI | Yes | Likely (with Tier 1+2 fixes) | Yes (with target-specific orchestration) | REALISTIC — via 036 compile target |
| GitHub Copilot | Yes | Likely (with Tier 1+2 fixes) | Yes (with target-specific orchestration) | REALISTIC — via 036 compile target |
| Cursor | Yes | Likely (with Tier 1+2 fixes) | Yes (with target-specific orchestration) | REALISTIC — via 036 compile target |
| OpenCode | Yes | Likely (with Tier 1+2 fixes) | Yes (with target-specific orchestration) | REALISTIC — via 036 compile target |
| Windsurf | Yes | Likely (with Tier 1+2 fixes) | No (no inter-session comms) | REALISTIC — portable target only (via 036) |

### Key insight: distribution vs. execution (revised)

The previous analysis concluded that cross-agent execution was aspirational because other agents lacked subagent support. **This is no longer true.** As of Feb-Mar 2026, every major coding agent supports some form of subagent spawning and multi-agent orchestration. The gap is no longer "can vs. can't" — it's "how" (different APIs, formats, and communication models).

The skills CLI solves **distribution** universally — `npx skills add` installs to all agents. **Execution** now splits into:

1. **Commission/refit skills** — need Tier 1 fixes to become portable. These are install-time tools that generate files. Most of their logic (creating README, status scripts, entity templates) is agent-agnostic.
2. **Generated workflow runtime** (first-officer/ensign orchestration) — needs Tier 3 adaptation per target. The orchestration pattern (lead agent dispatching workers) is now universal, but the API differs. This is 036's domain: generate the right agent files and dispatch commands for each target.

### Decision

Scope this task (057) to making `npx skills add` work for Claude Code users. The updated research shows that cross-agent *execution* is now realistic (not aspirational) for most agents, but the implementation belongs in task 036 (compile targets), which would generate target-specific orchestration files.

### Impact on task 036

The previous 036 spec proposed three targets: `claude-code`, `codex`, and `portable`. The research suggests a pattern-based approach may be more effective than per-agent targets:

| Target pattern | Agents | Orchestration model | Agent file format |
|---------------|--------|--------------------|--------------------|
| **team-messaging** | Claude Code, OpenCode | Peer-to-peer SendMessage, shared tasks | `.claude/agents/*.md`, `.opencode/agents/*.md` |
| **orchestrator-collects** | Codex, Gemini CLI, Cursor, Copilot | Lead spawns workers, collects results | TOML/MD varies per agent |
| **portable** | Windsurf, any agent | No orchestration — manual or filesystem-as-state | README + status script only |

Key findings for 036:
- **Agent file formats differ but are all markdown or config-based.** The first-officer/ensign templates would need format adapters, not complete rewrites. Gemini CLI, Cursor, OpenCode, and Copilot all use markdown with YAML frontmatter — only Codex uses TOML.
- **The communication model is the real compile-target differentiator**, not the agent file format. The first-officer's dispatch logic (TeamCreate + SendMessage) needs to be rewritten as orchestrator-collects for Codex/Gemini/Cursor/Copilot targets.
- **OpenCode is the closest to Claude Code** — it rebuilt the agent-team system with event-driven peer-to-peer messaging. A `team-messaging` target could cover both with minimal adaptation.
- **Windsurf's Wave 13 parallel sessions lack inter-agent communication**, so it falls into the `portable` category for now.

## Stage Report: ideation (original)

- [x] Relationship between 057 (distribution via npx-skills) and 036 (compile targets) clarified
  057 owns distribution (install path), 036 owns cross-agent execution (compile targets). No blocking dependency — 057 can ship first.
- [x] Proposed approach updated if 036's compile-target model changes the design
  036 does not change 057's design. Symlink approach is additive and target-agnostic. Approach updated to include `mods/` directory.
- [x] Open questions resolved or escalated
  Q1 (symlink deref): unresolved, mitigation documented. Q2 (self-location): unresolved, affects mods too. Q3 (mods): new, addressed in approach.
- [x] Acceptance criteria updated if scope changed
  Added mods criteria, out-of-scope section. Updated cross-agent classification from ASPIRATIONAL to REALISTIC based on web research.
- [x] Clear definition of what's in-scope vs deferred to 036
  In-scope: npx-skills install for Claude Code. Deferred: cross-agent execution (now realistic, not aspirational — all major agents gained subagent support in early 2026).

### Summary

Conducted web research on multi-agent capabilities (subagent spawning, agent file formats, inter-agent communication, task tracking) across Codex, Gemini CLI, Cursor, GitHub Copilot, Windsurf, and OpenCode. The previous analysis (May 2025 cutoff) was substantially wrong: all major agents now support subagent spawning and most support named agent definitions.

Key findings for construct-level compatibility:
- **Agent file definitions:** Universal concept, format varies (Codex TOML, Gemini/Cursor/OpenCode markdown+YAML, Copilot has its own format). Commission can generate target-specific agent files.
- **Subagent dispatch:** All agents support named-agent dispatch. APIs differ but the pattern (lead dispatches worker by name) is universal.
- **Inter-agent communication:** The biggest differentiator. Three patterns emerged: (1) team-messaging (Claude Code, OpenCode), (2) orchestrator-collects (Codex, Gemini, Cursor, Copilot), (3) independent sessions (Windsurf). This is the primary compile-target axis for 036.
- **Task tracking:** Only Claude Code and OpenCode have shared mutable task boards. Others use orchestrator monitoring or no equivalent.

Proposed that 036 target *communication patterns* rather than individual agents — this would reduce the target matrix from 7+ agents to 3 patterns (team-messaging, orchestrator-collects, portable).

## Research: skills ecosystem packaging patterns

*Added 2026-04-08. How do other npx-skills-installable packages ship skill assets?*

### Convention: self-contained skill directories

The skills ecosystem has a clear convention: each skill is a self-contained directory. The SKILL.md file is the entry point, and optional subdirectories hold auxiliary assets. The standard layout (documented by both OpenAI and Vercel Labs, codified in mgechev/skills-best-practices):

```
skill-name/
├── SKILL.md              # Required: metadata + instructions (<500 lines)
├── scripts/              # Optional: executable code (Python/Bash)
├── references/           # Optional: supplementary context docs
├── assets/               # Optional: templates, images, static files
└── agents/               # Optional: per-agent config (e.g., agents/openai.yaml)
```

Key rules:
- **Flat subdirectories only.** Keep files exactly one level deep (e.g., `references/schema.md`, not `references/db/v1/schema.md`). This is an explicit convention in the best-practices guide.
- **Relative paths from skill directory.** Skills reference their assets with bare relative paths: `templates/viewer.html`, `themes/`, `reference/mcp_best_practices.md`, `scripts/deploy.sh`. No platform-specific path variables needed.
- **Progressive disclosure.** Agents see metadata (name + description) first. The SKILL.md body loads only when the skill is activated. Bundled resources load only when the skill explicitly tells the agent to read them.
- **No symlinks in published skills.** Neither the Anthropic nor OpenAI skills repos contain any symlinks (verified by `find -type l`). All assets are actual files within the skill directory.

### Real examples from the ecosystem

**Anthropic skills repo** (`anthropics/skills`): Many skills with auxiliary files:

| Skill | Auxiliary structure | How assets are referenced |
|-------|--------------------|--------------------------|
| `algorithmic-art` | `templates/viewer.html`, `templates/generator_template.js` | `Read templates/viewer.html using the Read tool` |
| `theme-factory` | `themes/*.md` (10 theme files), `theme-showcase.pdf` | `Read the corresponding theme file from the themes/ directory` |
| `mcp-builder` | `reference/*.md` (4 files), `scripts/*.py` (6 files) | Markdown links: `[📋 View Best Practices](./reference/mcp_best_practices.md)` |
| `canvas-design` | `canvas-fonts/*.ttf` (40+ font files) | Referenced in SKILL.md instructions |
| `claude-api` | Deep nesting: `python/claude-api/*.md`, `typescript/claude-api/*.md`, `shared/*.md` | Language-specific reference loading |
| `skill-creator` | `agents/*.md`, `assets/`, `eval-viewer/`, `references/`, `scripts/` (8 scripts) | Multiple directories, complex skill |
| `xlsx` | `scripts/office/` with XML schemas, pack.py, recalc.py | Script invocation from SKILL.md |
| `docx` | `scripts/` (accept_changes.py, comment.py), `scripts/templates/*.xml` | Script invocation with XML templates |
| `pdf` | `scripts/` (8 Python scripts), `reference.md`, `forms.md` | Script paths and reference links |
| `web-artifacts-builder` | `scripts/` (init-artifact.sh, bundle-artifact.sh, shadcn-components.tar.gz) | Shell script invocation |

**OpenAI skills repo** (`openai/skills`): Similar patterns:

| Skill | Auxiliary structure |
|-------|--------------------|
| `skill-creator` | `references/openai_yaml.md`, `scripts/` (init_skill.py, quick_validate.py, generate_openai_yaml.py), `agents/openai.yaml` |
| `skill-installer` | `scripts/` (github_utils.py, list-skills.py, install-skill-from-github.py), `assets/` (icons), `agents/openai.yaml` |
| `screenshot` | `scripts/` (take_screenshot.py, macos_permissions.swift, etc.), `agents/openai.yaml`, `assets/` |
| `sora` | `references/` (8 md files), `scripts/sora.py`, `agents/openai.yaml`, `assets/` |
| `jupyter-notebook` | `scripts/new_notebook.py`, `assets/` (templates), `agents/openai.yaml` |
| `vercel-deploy` | `scripts/deploy.sh`, `agents/openai.yaml`, `assets/` |

### Path resolution patterns

Three patterns observed for how skills locate their own assets at runtime:

1. **Bare relative paths (most common).** Skills simply say "Read `templates/viewer.html`" or "Run `scripts/deploy.sh`". The agent resolves paths relative to the SKILL.md location. This is the Anthropic convention — none of their skills use `${CLAUDE_SKILL_DIR}`.

2. **Hardcoded install paths (Codex pattern).** The jupyter-notebook skill uses `$CODEX_HOME/skills/jupyter-notebook/scripts/new_notebook.py` with a `$CODEX_HOME` fallback to `~/.codex`. This is brittle (assumes a specific install location) but works for Codex's fixed skill directory layout.

3. **`${CLAUDE_SKILL_DIR}` (spacedock-specific).** Spacedock's ensign and first-officer skills use this Claude Code platform variable to build absolute paths. This is a Claude Code feature, not a skills-ecosystem convention. No other published skill uses it.

### Installer behavior (verified from source)

The skills CLI `installer.ts` `copyDirectory()` function:
- Uses `readdir(src, { withFileTypes: true })` to iterate entries
- Filters out files starting with `.` (dotfiles), `metadata.json`, `.git`, `__pycache__`, `__pypackages__`
- Recursively copies directories
- Uses `cp(srcPath, destPath, { dereference: true, recursive: true })` for files
- **Broken symlinks are skipped** with a warning (ENOENT catch), not treated as errors

**Critical detail for spacedock:** The `.` prefix filter means `agents/openai.yaml` is NOT excluded (it's inside an `agents/` directory, not a dotfile). However, `.claude-plugin/` would never be copied as an asset since skills are discovered at the skill-directory level, not the repo root.

### Implications for spacedock

1. **Follow the convention: self-contained skill directories with actual files.** No symlinks in published skills. Either use a build step to copy shared assets into each skill directory, or restructure so each skill contains its own copy of needed assets.

2. **Use bare relative paths, not `${CLAUDE_SKILL_DIR}`.** The ecosystem convention is for skills to reference `references/foo.md`, not `${CLAUDE_SKILL_DIR}/references/foo.md`. This is more portable across agents and matches what every other published skill does.

3. **The `references/` directory naming matches the convention.** Spacedock already has `references/*.md` — this maps directly to the skills-ecosystem `references/` subdirectory pattern.

4. **`mods/` is spacedock-specific but fine.** The convention allows arbitrary subdirectory names. The `themes/` and `canvas-fonts/` directories in Anthropic's skills prove this.

5. **Consider `agents/openai.yaml` for Codex integration.** Every OpenAI skill ships this file. Spacedock could benefit from shipping `agents/openai.yaml` in each skill directory for Codex UI integration (display name, description, icons).

## Research: OpenAI agents/openai.yaml

*Added 2026-04-08. What is agents/openai.yaml and how does it relate to skills and Codex?*

### What it is

`agents/openai.yaml` is an optional per-skill metadata file that configures how a skill appears and behaves in the Codex app. It is explicitly described as "product-specific config intended for the machine/harness to read, not the agent." It sits alongside SKILL.md in the skill directory.

Other agents can also have config files in the `agents/` directory (e.g., a hypothetical `agents/claude.yaml`), but only `openai.yaml` is currently documented.

### Schema

```yaml
interface:
  display_name: "User-facing name"           # Human-facing title in UI
  short_description: "25-64 char blurb"       # Short description for quick scanning
  icon_small: "./assets/small-400px.png"      # Path to small icon (relative to skill dir)
  icon_large: "./assets/large-logo.svg"       # Path to large icon
  brand_color: "#3B82F6"                      # Hex color for UI accents
  default_prompt: "Use $skill-name to..."     # Default prompt when invoking

policy:
  allow_implicit_invocation: true             # Default: true. If false, skill requires explicit $name invocation

dependencies:
  tools:
    - type: "mcp"                             # Only "mcp" supported currently
      value: "github"                         # Tool/server identifier
      description: "GitHub MCP server"        # Human-readable description
      transport: "streamable_http"            # Connection type
      url: "https://api.githubcopilot.com/mcp/"  # MCP server URL
```

### How Codex discovers skills

Codex scans these locations in priority order:
1. `$CWD/.agents/skills` (current working directory)
2. `$REPO_ROOT/.agents/skills` (repository root)
3. `$HOME/.agents/skills` (user personal / `$CODEX_HOME/skills`)
4. `/etc/codex/skills` (system admin)
5. Built-in system skills

Symlinked folders are followed. Duplicate skill names don't merge; both appear in selectors.

### How it relates to AGENTS.md

`AGENTS.md` and `agents/openai.yaml` serve different purposes:
- **AGENTS.md** is project-level custom instructions (like Claude Code's `CLAUDE.md`). Codex reads it at startup and concatenates files from git root to cwd.
- **agents/openai.yaml** is per-skill UI/policy metadata. It configures how a skill appears in Codex's skill selector, not project-level behavior.

### How it relates to SKILL.md

`SKILL.md` contains the skill's name, description (in frontmatter), and instructions (in body). `agents/openai.yaml` provides additional Codex-specific metadata: UI display name, icons, brand color, default prompt, invocation policy, and MCP tool dependencies. The SKILL.md `name` and `description` fields are the primary metadata; `agents/openai.yaml` extends them for Codex's UI.

### How it relates to config.toml

Codex's main configuration is TOML-based (`~/.codex/config.toml` or `.codex/config.toml`). This configures agent spawning constraints (`agents.max_threads`, `agents.max_depth`), model selection, sandbox settings, and project-doc fallback filenames. It does NOT configure individual skills — that's what `agents/openai.yaml` is for.

### Prevalence in the ecosystem

Every skill in the OpenAI skills repo ships an `agents/openai.yaml`. It appears to be standard practice for Codex-compatible skills. The Anthropic skills repo does NOT use `agents/openai.yaml` (Anthropic's skills target Claude Code, which doesn't read this file).

### Should spacedock ship agents/openai.yaml?

**Yes, for Codex visibility.** The file is low-cost (3-8 lines of YAML) and provides:
- Better display in Codex's skill selector (display_name, short_description)
- Default prompts for skill invocation
- Future: MCP dependency declarations if spacedock ever needs external tools

For spacedock, the files would be minimal:

```yaml
# skills/commission/agents/openai.yaml
interface:
  display_name: "Commission Workflow"
  short_description: "Design and generate a plain text workflow"
  default_prompt: "Use $commission to design a new workflow."

# skills/refit/agents/openai.yaml
interface:
  display_name: "Refit Workflow"
  short_description: "Upgrade workflow scaffolding to latest version"
  default_prompt: "Use $refit to upgrade this workflow."

# skills/first-officer/agents/openai.yaml
interface:
  display_name: "First Officer"
  short_description: "Orchestrate a workflow run"
  default_prompt: "Use $first-officer to run the workflow."

# skills/ensign/agents/openai.yaml
interface:
  display_name: "Ensign"
  short_description: "Execute workflow stage work"

# skills/debrief/agents/openai.yaml
interface:
  display_name: "Debrief"
  short_description: "Record session activity for next session"
  default_prompt: "Use $debrief to capture what happened this session."
```

**Note:** Adding `agents/openai.yaml` is orthogonal to the main 057 work (symlinks/asset packaging). It could be added as a separate, low-risk step.

## Research: skills registry, publishing, and versioning

*Added 2026-04-08. How skills are discovered, installed, updated, and published.*

### How the registry works

**There is no central registry you publish to.** The skills ecosystem is purely git-based for installation:

1. `npx skills add clkao/spacedock` parses `clkao/spacedock` as GitHub shorthand → `https://github.com/clkao/spacedock.git`
2. The CLI does a **shallow clone** (`--depth 1`, 60-second timeout) of the repo into a temp directory
3. It scans for SKILL.md files in well-known directories (`skills/`, `.claude/skills/`, `.agents/skills/`, etc.) and reads `.claude-plugin/marketplace.json`/`plugin.json` for declared skill paths
4. Each discovered skill directory is copied to `.agents/skills/<name>/` (canonical location) with symlinks to agent-specific paths (e.g., `.claude/skills/<name>/`)
5. A `skills-lock.json` is written with a content hash per skill

**The `skills.sh` directory** is a discovery/leaderboard site, NOT a package registry. It tracks install telemetry — skills appear on the leaderboard automatically when people install them via `npx skills add`. There is no submission process, no publish command, no approval workflow. The listing is driven by usage data.

**The `npx skills find` command** queries the `skills.sh/api/search` API to search the leaderboard. This is purely for discovery — installation still goes directly to the git source.

### Source types supported

The CLI resolves these source formats (from `source-parser.ts`):
- GitHub shorthand: `owner/repo` → `https://github.com/owner/repo.git`
- GitHub URL: `https://github.com/owner/repo`
- GitLab: `gitlab:owner/repo` or full URL
- Ref pinning: `owner/repo#branch-or-tag`
- Skill filter: `owner/repo@skill-name`
- Subpath: `owner/repo/path/to/skill`
- Local path: `/absolute/or/relative/path`
- Any git URL: `https://example.com/repo.git`

### Versioning and updates

**Skills have no formal versioning system.** The update mechanism works purely on content hashing:

1. On install, the CLI records a `skillFolderHash` — the GitHub tree SHA for the skill's directory (via `https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1`)
2. `npx skills check` compares stored hashes against current GitHub state
3. `npx skills update` re-clones and re-installs skills whose hashes have changed
4. The lock file (`skills-lock.json`) tracks: `source`, `sourceType`, `computedHash`

**There is no semver, no release channels, no version pinning.** Users always get the latest commit on the default branch (unless they pin a ref with `#branch-or-tag`). The SKILL.md frontmatter has an optional `metadata` field that the best-practices guide suggests as "a good place for your semver," but no tooling consumes it.

**Neither OpenAI nor Anthropic skills repos have releases or tags.** The `vercel-labs/skills` repo has version tags (v1.4.9 as of April 2026), but those version the CLI tool itself, not the skills content.

### No publish command exists

The CLI has these commands: `add`, `remove`, `list`, `find`, `check`, `update`, `init`, `experimental_install`, `experimental_sync`. **There is no `publish`, `release`, or `submit` command.**

To make a skill available: push it to a git repo and share the `npx skills add owner/repo` command. That's it.

### How CI-triggered publishing would work for spacedock

Since the ecosystem is purely git-based, "publishing" means ensuring the repo's skill directories are self-contained at the point users install from. Two approaches:

**Option 1: Build-on-tag (CI copies shared assets into skill dirs)**
1. Maintain shared assets at repo root (`references/`, `mods/`, `agents/`) as source of truth
2. CI triggers on git tag (e.g., `v0.9.3`)
3. Build script copies shared assets into each skill directory (`skills/commission/references/`, etc.)
4. CI commits the result to a `release` branch (or directly to the tag)
5. Users install from `npx skills add clkao/spacedock` (default branch) or `npx skills add clkao/spacedock#v0.9.3` (pinned)

**Option 2: Always self-contained (symlinks in repo, CI verifies)**
1. Use symlinks in the repo (`skills/commission/references` -> `../../references`)
2. The skills CLI's `dereference: true` resolves symlinks during copy
3. CI verifies that symlinks are valid and point to real files
4. No build step needed — the repo is always in a publishable state
5. Caveat: depends on symlink dereferencing working correctly in the installer (Q1 from open questions — now confirmed to work from source code analysis)

**Option 3: Always self-contained (actual copies, CI checks sync)**
1. Maintain actual copies of shared assets in each skill directory
2. CI checks that copies match source-of-truth files (`diff references/ skills/commission/references/`)
3. No build step, no symlink concerns
4. Downside: duplication in the repo, potential for drift

**Recommended: Option 2 (symlinks).** This is cleanest because:
- No build step, no release branch, no committed artifacts
- The repo is always installable from any commit
- Symlink dereferencing is confirmed from the installer source code (`cp` with `dereference: true`)
- `readdir` with `withFileTypes` follows symlinks for `isDirectory()` — confirmed from Node.js docs
- Broken symlink handling: the installer skips broken symlinks with a warning (ENOENT catch), so broken symlinks won't crash installation

However, note the dot-file exclusion: files/dirs starting with `.` are excluded by the installer. So `.claude-plugin/plugin.json` cannot be symlinked into skill directories — the `agents/` prefix would be fine but `.claude-plugin/` would be filtered. This means version detection needs an alternative approach (e.g., a `VERSION` file or frontmatter field).

### Verified: current spacedock install test

Ran `npx skills add clkao/spacedock --skill commission --agent claude-code --yes` against the current repo. Results:

**What got installed:**
- `.claude/skills/commission/SKILL.md` — the skill file
- `.claude/skills/commission/bin/status` — the status viewer (lives inside `skills/commission/bin/`)

**What did NOT get installed (outside skill directory):**
- `references/` (8 reference files)
- `mods/pr-merge.md`
- `agents/first-officer.md`, `agents/ensign.md`
- `.claude-plugin/plugin.json`

This confirms the gap: the commission skill installs but would be non-functional because it can't reach `{spacedock_plugin_dir}/mods/`, `{spacedock_plugin_dir}/agents/`, or `references/`. The status viewer works because it already lives at `skills/commission/bin/status`.

## Stage Report: ideation (revisit — 2026-04-08)

### What changed since the original ideation

The original ideation was built around symlinking `templates/` into skill directories. Since then, substantial cleanup has landed that fundamentally changes the architecture:

1. **`templates/` no longer exists.** Commits `d1fbc5e` (remove monolithic agent templates) and `37ac56b` (ship status viewer with plugin) eliminated the entire `templates/` directory. The monolithic `templates/first-officer.md`, `templates/ensign.md`, and `templates/status` are gone.

2. **Layered reference architecture replaced templates.** Agent content is now split across:
   - `agents/` — thin entry-point stubs (`first-officer.md`, `ensign.md`) with skill preloading via `skills: ["spacedock:first-officer"]`
   - `references/` — shared behavioral contracts (8 files: shared cores, platform runtimes, guardrails, codex tools)
   - `skills/` — skill SKILL.md files that load references via `${CLAUDE_SKILL_DIR}/../../references/...` paths

3. **Status viewer moved to `skills/commission/bin/status`.** No longer materialized per-workflow. The commission and refit skills, plus the FO shared core, all reference it via `{spacedock_plugin_dir}/skills/commission/bin/status`.

4. **Codex cleanup landed.** Commits `0f00f39` and `43d37a4` removed codex helper entrypoints and packaged agent wrapper dependency. Codex runtime references are now in `references/codex-*-runtime.md`.

5. **New skills added.** `skills/debrief/` and new entry-point skills `skills/ensign/` and `skills/first-officer/` exist alongside `skills/commission/` and `skills/refit/`.

### Current asset map (what must travel with skills)

| Asset | Path | Referenced by | Reference mechanism |
|-------|------|---------------|---------------------|
| Reference files (8) | `references/*.md` | `skills/ensign/SKILL.md`, `skills/first-officer/SKILL.md` | `${CLAUDE_SKILL_DIR}/../../references/...` |
| Status viewer | `skills/commission/bin/status` | `skills/commission/SKILL.md`, `skills/refit/SKILL.md`, `references/first-officer-shared-core.md` | `{spacedock_plugin_dir}/skills/commission/bin/status` |
| Mods | `mods/pr-merge.md` | `skills/commission/SKILL.md`, `skills/refit/SKILL.md` | `{spacedock_plugin_dir}/mods/...` |
| Agent stubs | `agents/*.md` | `skills/commission/SKILL.md` (Phase 3 pilot run) | `{spacedock_plugin_dir}/agents/first-officer.md` |
| Plugin manifest | `.claude-plugin/plugin.json` | `skills/commission/SKILL.md`, `skills/refit/SKILL.md` | Plugin context resolution |

### Reassessment: symlinks + relative paths — still correct?

**No. The original symlink proposal is obsolete.** It was designed to solve one problem (templates traveling with skills) that no longer exists. The current codebase has a different, more complex dependency graph:

**Problem 1 — `${CLAUDE_SKILL_DIR}` path breakage.** The ensign and first-officer skills use `${CLAUDE_SKILL_DIR}/../../references/...` to reach reference files two levels up from `skills/{name}/`. When the skills CLI copies `skills/first-officer/` to `.agents/skills/first-officer/`, the `../../references/` path would resolve to `.agents/references/` — which doesn't exist. This is the critical breakage.

**Problem 2 — `{spacedock_plugin_dir}` path breakage.** Commission and refit skills use `{spacedock_plugin_dir}` to reference `mods/`, `agents/`, `skills/commission/bin/status`, and `.claude-plugin/plugin.json`. When installed via skills CLI, `{spacedock_plugin_dir}` is not available — there is no plugin system.

**Revised approach: symlinks within skill directories pointing to sibling repo assets.** The principle is the same as the original ideation, but the assets to symlink have changed:

1. **For ensign and first-officer skills** — add `references/` symlink inside each skill directory:
   - `skills/ensign/references` -> `../../references`
   - `skills/first-officer/references` -> `../../references`
   - Update SKILL.md paths from `${CLAUDE_SKILL_DIR}/../../references/...` to `${CLAUDE_SKILL_DIR}/references/...`

2. **For commission and refit skills** — add symlinks for all referenced assets:
   - `skills/commission/mods` -> `../../mods`
   - `skills/commission/agents` -> `../../agents`
   - `skills/commission/plugin.json` -> `../../.claude-plugin/plugin.json`
   - `skills/refit/mods` -> `../../mods`
   - `skills/refit/plugin.json` -> `../../.claude-plugin/plugin.json`
   - (Status viewer already lives at `skills/commission/bin/status` — no symlink needed)

3. **Update `{spacedock_plugin_dir}` references** in commission and refit SKILL.md to use paths relative to the skill directory via `${CLAUDE_SKILL_DIR}`.

4. **For debrief skill** — check if it has external dependencies (it does not reference templates, mods, or agents — it's self-contained).

### Updated open questions

**Q1 (symlink deref): RESOLVED — yes, it works.** The skills CLI `copyDirectory()` uses `dereference: true` on `cp` calls. Node.js `fs.cp` with `dereference: true` follows symlinks and copies the target content. For directory symlinks, `readdir` with `withFileTypes` returns entries where `isDirectory()` returns true for symlinked directories (Node.js resolves through symlinks by default for `withFileTypes`). Verified: this is standard Node.js behavior — `readdirSync(path, {withFileTypes: true})` follows symlinks when checking types.

**Q2 (self-location): RESOLVED — `${CLAUDE_SKILL_DIR}` solves it.** The original question asked how a skill knows its own directory. Claude Code's plugin system substitutes `${CLAUDE_SKILL_DIR}` with the skill's absolute directory path before the model sees it. When installed via skills CLI, skills land in `.agents/skills/{name}/` — and `${CLAUDE_SKILL_DIR}` resolves to that path. References, mods, and other assets are copied into the skill directory (via dereferenced symlinks), so `${CLAUDE_SKILL_DIR}/references/...` works in both install modes.

For `{spacedock_plugin_dir}` references: these must be rewritten to use `${CLAUDE_SKILL_DIR}` instead. Commission's `{spacedock_plugin_dir}/mods/pr-merge.md` becomes `${CLAUDE_SKILL_DIR}/mods/pr-merge.md`. Commission's `{spacedock_plugin_dir}/skills/commission/bin/status` becomes `${CLAUDE_SKILL_DIR}/bin/status` (the status binary is already inside the commission skill directory).

**Q3 (mods): RESOLVED — same symlink approach.** `mods/` symlink in commission and refit skill directories.

**Q4 (new — agents/ reference in commission):** Commission Phase 3 reads `{spacedock_plugin_dir}/agents/first-officer.md` for the pilot run. An `agents/` symlink in the commission skill directory resolves this.

**Q5 (new — plugin.json for version detection):** Both commission and refit read `.claude-plugin/plugin.json` for the spacedock version. Options: (a) symlink `plugin.json` into each skill directory, (b) add a `version` field to SKILL.md frontmatter, (c) add a `VERSION` file. Option (b) is cleanest — the skills CLI preserves frontmatter, and it avoids a separate file. However, this means updating version in SKILL.md frontmatter during release in addition to `plugin.json`. Option (a) with a symlink is more DRY.

**Q6 (new — first-officer-shared-core.md references `{spacedock_plugin_dir}`):** The shared core file at `references/first-officer-shared-core.md` line 27 uses `{spacedock_plugin_dir}/skills/commission/bin/status`. When the FO skill loads this reference file, the placeholder needs to resolve. In plugin mode, `{spacedock_plugin_dir}` is resolved by Claude Code. In skills-CLI mode, this placeholder won't resolve. The FO skill would need to set this variable after loading references, or the shared core would need to use a different resolution strategy. This is a significant open question — it affects runtime behavior, not just install-time layout.

### Updated acceptance criteria

1. `npx skills add clkao/spacedock --list` shows commission, refit, debrief, ensign, and first-officer skills
   - **Test:** Run `npx skills add clkao/spacedock --list` and verify output contains all 5 skill names
2. `npx skills add clkao/spacedock -a claude-code` installs all skills to `.agents/skills/` with symlinks to `.claude/skills/`
   - **Test:** Run install, verify `.agents/skills/{name}/SKILL.md` exists for each skill
3. After skills-CLI install, reference files exist in ensign and first-officer skill directories (e.g., `.agents/skills/first-officer/references/first-officer-shared-core.md`)
   - **Test:** Verify file existence after install
4. After skills-CLI install, `/commission` generates a working workflow (status viewer, mods, and agents are accessible)
   - **Test:** E2E test: install via skills CLI, run commission in batch mode, verify workflow files generated
5. After skills-CLI install, `/refit` can detect and upgrade workflow scaffolding (mods are accessible)
   - **Test:** E2E test: install via skills CLI, run refit on a test workflow, verify mod comparison works
6. `claude plugin marketplace add clkao/spacedock` continues to work (no regression)
   - **Test:** Existing test suite passes; verify `${CLAUDE_SKILL_DIR}` paths still resolve correctly in plugin mode
7. Mod files exist in installed commission and refit skill directories (e.g., `.agents/skills/commission/mods/pr-merge.md`)
   - **Test:** Verify file existence after install
8. The spacedock version is accessible to commission and refit regardless of install method
   - **Test:** Verify `plugin.json` (or equivalent) is readable from skill directory after install

### Updated test plan

**Static tests (low cost, run in CI):**
- Verify symlinks exist and point to valid targets (`skills/*/references` -> `../../references`, etc.)
- Verify SKILL.md files use `${CLAUDE_SKILL_DIR}/references/...` (not `${CLAUDE_SKILL_DIR}/../../references/...`) for reference paths
- Verify commission and refit SKILL.md files use `${CLAUDE_SKILL_DIR}/...` (not `{spacedock_plugin_dir}/...`) for asset references
- Verify all symlink targets exist (no broken symlinks)

**Simulation test (medium cost):**
- Simulate skills-CLI install: copy each skill directory (with symlink dereferencing) to a temp location, verify all referenced files are present
- This doesn't require the actual `npx skills` CLI — just `cp -rL` to dereference symlinks

**E2E tests (high cost, may need interactive harness):**
- AC4: Commission batch mode after simulated skills-CLI install
- AC5: Refit after simulated skills-CLI install
- AC6: Existing plugin-mode tests continue to pass (regression check)

**Not needed:**
- No E2E test for the actual `npx skills add` command (depends on external CLI, network). The simulation test covers the critical path (symlink dereferencing produces self-contained directories).

### Checklist

1. [x] Review current codebase structure (skills/, templates/, mods/, .claude-plugin/) and how skills reference assets today — DONE. `templates/` no longer exists. Architecture is now: `agents/` (thin stubs) + `references/` (8 shared core files) + `skills/` (5 skills, using `${CLAUDE_SKILL_DIR}` and `{spacedock_plugin_dir}` for path resolution) + `mods/` (1 mod) + `.claude-plugin/` (manifests).
2. [x] Check recent git history for cleanup changes that affect this task's design — DONE. Key commits: `d1fbc5e` (remove monolithic templates), `c320032` (ship agents from plugin), `37ac56b` (ship status with plugin), `0f00f39`/`43d37a4` (codex cleanup). All landed between Apr 1-8 2026.
3. [x] Reassess whether the proposed approach (symlinks + relative paths) is still the right call — DONE. The principle is correct but the implementation must change. The assets to symlink are `references/`, `mods/`, `agents/`, and `plugin.json` — not `templates/` (which no longer exists). The `${CLAUDE_SKILL_DIR}` variable (resolved by Claude Code's platform) replaces `{spacedock_plugin_dir}` as the path anchor.
4. [x] Resolve or update open questions (Q1: symlink deref, Q2: self-location, Q3: mods) — DONE. Q1: resolved (Node.js dereferences). Q2: resolved (`${CLAUDE_SKILL_DIR}`). Q3: resolved (symlink approach). New questions: Q4 (agents/ ref in commission), Q5 (version detection), Q6 (shared-core `{spacedock_plugin_dir}` at runtime — significant open question).
5. [x] Update problem statement and proposed approach if needed — DONE. Problem statement still valid in spirit (skills need bundled assets) but the specific assets have changed entirely. Approach updated with new symlink targets and `${CLAUDE_SKILL_DIR}` rewrite.
6. [x] Update acceptance criteria with testable verification for each — DONE. 8 criteria, each with explicit test method.
7. [x] Update test plan: what tests, cost/complexity, E2E needs — DONE. Three tiers: static (CI), simulation (`cp -rL`), E2E (commission/refit after simulated install). No external CLI dependency in tests.

### Key risk: Q6 (`{spacedock_plugin_dir}` in shared core at runtime)

The `references/first-officer-shared-core.md` file uses `{spacedock_plugin_dir}` to reference the status viewer. This file is read at runtime by the FO agent. In plugin mode, `{spacedock_plugin_dir}` is resolved by Claude Code's plugin system. In skills-CLI mode, this placeholder has no resolution mechanism.

Options to resolve:
- **(a)** Replace `{spacedock_plugin_dir}` in shared core with a different anchor. The FO skill that loads the shared core could set a variable (but markdown skill files don't have variable-setting mechanics).
- **(b)** The FO skill could include a preamble that tells the model "the status viewer is at `${CLAUDE_SKILL_DIR}/../../skills/commission/bin/status`" — but this re-introduces the `../../` path fragility that we're trying to eliminate.
- **(c)** Move the status invocation instructions out of the shared core and into the platform-specific runtime adapters. The Claude runtime adapter would use `{spacedock_plugin_dir}`, and a future skills-CLI runtime adapter would use `${CLAUDE_SKILL_DIR}`.

This question needs CL's input before proceeding to implementation.
