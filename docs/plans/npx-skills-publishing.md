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

1. **Add a `templates/` symlink inside each skill directory** pointing to `../../templates/`:
   - `skills/commission/templates` -> `../../templates`
   - `skills/refit/templates` -> `../../templates`

2. **Update skill prompts** to reference templates relative to the skill's own directory:
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
2. `npx skills add clkao/spacedock -a claude-code` installs both skills to `.claude/skills/`
3. After skills-CLI install, `/commission` generates a working workflow (templates are accessible)
4. After skills-CLI install, `/refit` can detect and upgrade workflow scaffolding
5. `claude plugin marketplace add clkao/spacedock` continues to work (no regression)
6. Template files exist in the installed skill directories (e.g., `.claude/skills/commission/templates/first-officer.md`)
7. The spacedock version is accessible to the refit skill regardless of install method

## Open questions

1. **Symlink deref verification:** The skills CLI `copyDirectory()` uses `dereference: true` on individual file copies, but does it follow directory symlinks when iterating with `readdir`? Need to verify that `skills/commission/templates/` (a symlink to `../../templates/`) is traversed during copy. The `readdir` uses `withFileTypes` and filters `entry.isDirectory()` — need to confirm this returns true for symlinked directories. If not, actual directories with copies may be needed instead.

2. **Skill prompt self-location:** How does a skill installed via the skills CLI know its own directory path? If the agent (e.g., Claude Code) presents skills by injecting their content into the system prompt, the skill has no way to know its filesystem location. This may require the skill to use a known install path (`.claude/skills/commission/templates/`) instead of a relative reference. Needs investigation.

## Cross-agent compatibility analysis

### Claude Code constructs spacedock depends on

Spacedock uses seven Claude Code-specific constructs, grouped by portability:

**Tier 1 — Portable with phrasing changes:**
- Tool name references (`Read`, `Write`, `Bash`, `Glob`, `Edit`) — all agents have file/shell equivalents, just different names. Fix: use generic language ("read the file") instead of tool names.
- `{spacedock_plugin_dir}` template resolution — fix with symlink approach (templates travel with skill directory).
- Git worktree commands — universal shell commands, work everywhere.

**Tier 2 — Requires architecture decisions:**
- `.claude/agents/` agent definitions — only Claude Code loads these as spawnable subagent types. Other agents have no equivalent (Codex: none, Gemini CLI: none, OpenCode: `agents.json` config is not equivalent).
- Slash command invocation (`/commission`) — other agents load skills as ambient context, not on-demand. A 500-line skill as always-loaded context is problematic.

**Tier 3 — Claude Code exclusive (no equivalent):**
- `Agent()` subagent spawning — the multi-agent orchestration model (first-officer dispatching ensigns). Codex, Gemini CLI, and OpenCode are all single-agent systems.
- `TeamCreate` / `SendMessage` inter-agent communication — no other agent has this.

### Per-agent assessment

| Agent | Install works? | Commission skill runs? | Generated workflow runs? | Classification |
|-------|---------------|----------------------|------------------------|----------------|
| Claude Code (no plugin) | Yes | Yes (with Tier 1 fixes) | Yes | REALISTIC |
| Codex | Yes | No (Tier 2+3 constructs) | No (single-agent) | ASPIRATIONAL |
| Gemini CLI | Yes | No (Tier 2+3 constructs) | No (single-agent) | ASPIRATIONAL |
| OpenCode | Yes | Partial (if Claude backend) | No (single-agent) | ASPIRATIONAL |

### Key insight: distribution vs. execution

The skills CLI solves **distribution** universally — `npx skills add` installs to all agents. But **execution** splits into two layers:

1. **Commission/refit skills** — need only Tier 1 fixes to become portable. These are the install-time tools.
2. **Generated workflow runtime** (first-officer/ensign orchestration) — depends on Tier 3 constructs (Agent spawning, TeamCreate, SendMessage). This is fundamentally a Claude Code multi-agent system. Making it work on single-agent platforms would require a different execution engine (sequential single-agent mode).

### Decision

Scope this issue to Claude Code (no-plugin) as the realistic target. Cross-agent runtime portability is a separate initiative — follow up in a new issue for ideation on a single-agent execution mode.

## Stage Report: ideation

- [x] Skills CLI mechanics researched — how it resolves repos, what it installs, expected structure
  Analyzed all core source files: source-parser.ts, git.ts, skills.ts, installer.ts, plugin-manifest.ts, agents.ts
- [x] Spacedock's full plugin structure documented — what files are needed for a working install
  Documented all 9 components: 2 skills, 5 templates, 2 manifests; identified template dependency as the core challenge
- [x] Compatibility assessment — can skills CLI and plugin marketplace coexist
  Yes, they install to different locations; the gap is template access, not conflicts
- [x] Proposed approach — concrete plan for making spacedock skills-installable
  Option A: symlinks in repo + relative template references in skill prompts + version file for refit
- [x] Acceptance criteria written — testable conditions for "done"
  7 concrete, testable criteria covering both install methods and no regressions
- [x] Compatibility assessment per agent (Claude Code no-plugin, Codex, Gemini, OpenCode)
  Full construct inventory (7 constructs, 3 tiers) with per-agent mapping tables
- [x] Realistic vs aspirational classification for each
  Claude Code no-plugin: REALISTIC. Codex, Gemini CLI, OpenCode: ASPIRATIONAL (Tier 3 constructs block execution)
- [x] Updated approach if compatibility findings change the design direction
  Scope unchanged for this issue (Claude Code no-plugin target). Cross-agent runtime portability deferred to new issue per CL direction.

### Summary

Audited all seven Claude Code-specific constructs spacedock depends on and mapped equivalents (or lack thereof) across Codex, Gemini CLI, and OpenCode. The constructs fall into three portability tiers. Only Claude Code (no-plugin) is a realistic execution target — other agents lack subagent spawning (Agent tool), team communication (TeamCreate/SendMessage), and agent definitions (.claude/agents/). The proposed symlink approach remains correct for the scoped goal. CL directed that cross-agent runtime portability be spun off as a separate ideation issue.
