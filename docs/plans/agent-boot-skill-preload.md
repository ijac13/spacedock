---
id: 085
title: Agent boot via skill preloading — eliminate runtime path resolution
status: validation
source: CL — 084 validation findings (haiku path resolution failure)
started: 2026-04-03T03:40:00Z
completed:
verdict:
score: 0.7
worktree: .worktrees/ensign-agent-boot-skill-preload
issue:
pr:
---

# Agent boot via skill preloading

## Problem

Claude Code agent files (`agents/first-officer.md`, `agents/ensign.md`) use a multi-file read chain: thin wrapper → read `references/first-officer-shared-core.md` → read `references/code-project-guardrails.md` → read `references/claude-first-officer-runtime.md`. This fails because:

1. **`${CLAUDE_PLUGIN_ROOT}` doesn't expand in agent markdown files** — known Claude Code issue (#9354)
2. **No env var for plugin directory** — agents have no programmatic way to discover their own plugin path (confirmed: `env | grep PLUGIN` returns nothing at runtime)
3. **Haiku/opus guesses wrong paths** — when the agent says "Read `references/...`", the model searches globally and finds the wrong files (test fixtures, unrelated directories). Confirmed with haiku (merge hook test) and opus (inconsistent namespace usage)
4. **Platform best practice is self-contained agents** — plugin-dev agent-development skill says agent body IS the system prompt, max 10K chars, no external reads

Evidence: merge hook E2E test consistently fails with haiku/low because the FO never loads its reference files and skips the entire dispatch/hook protocol. Opus/low is non-deterministic — sometimes reads references correctly, sometimes doesn't.

## Design

### Key insight: skill preloading

From Claude Code source analysis (ch08-sub-agents.md, Step 10):

> Agent definitions can specify `skills: ["my-skill"]` in their frontmatter. Loaded skills become user messages prepended to the agent's conversation. This means the agent "reads" its skill instructions before seeing the task prompt.

Skills have access to `${CLAUDE_SKILL_DIR}` for reliable path resolution. Verified: haiku/low correctly resolves `${CLAUDE_SKILL_DIR}/../../references/...` paths from a skill and reads the target files. This means:

1. Agent files stay thin (identity + frontmatter)
2. A boot skill instructs the model to Read reference files via `${CLAUDE_SKILL_DIR}` resolved paths
3. The skill content is injected into the agent's conversation before it sees the task prompt
4. Path resolution is reliable because `${CLAUDE_SKILL_DIR}` is substituted by the platform before the model sees it

### Architecture

```
agents/
  first-officer.md              ← thin: identity + skills: ["spacedock:first-officer-boot"]
  ensign.md                     ← thin: identity + skills: ["spacedock:ensign-boot"]

skills/
  first-officer-boot/SKILL.md   ← Read instructions with resolved paths
  ensign-boot/SKILL.md          ← Read instructions with resolved paths
  first-officer/SKILL.md        ← Codex entry point (unchanged)

references/                     ← source of truth (unchanged)
  first-officer-shared-core.md
  ensign-shared-core.md
  code-project-guardrails.md
  claude-first-officer-runtime.md
  claude-ensign-runtime.md
  codex-first-officer-runtime.md
  codex-ensign-runtime.md
```

### Boot skill content

Each boot skill uses `Read` instructions with `${CLAUDE_SKILL_DIR}` for reliable path resolution:

```markdown
---
name: first-officer-boot
---
Read these reference files before doing anything else:

1. Read `${CLAUDE_SKILL_DIR}/../../references/first-officer-shared-core.md`
2. Read `${CLAUDE_SKILL_DIR}/../../references/code-project-guardrails.md`
3. Read `${CLAUDE_SKILL_DIR}/../../references/claude-first-officer-runtime.md`

Then begin the Startup procedure from the shared core.
```

The platform substitutes `${CLAUDE_SKILL_DIR}` with the skill's absolute directory path. The model then reads the files using resolved absolute paths — no guessing, no global search.

**Verified:** haiku/low correctly resolves `${CLAUDE_SKILL_DIR}/../../references/...` paths from a skill and reads the target files.

**Why not inline shell (`!cat`)?** Inline shell execution can be disabled by user settings. `Read` instructions work regardless of shell permissions.

### Agent file changes

```markdown
---
name: first-officer
description: Orchestrates a workflow
skills: ["spacedock:first-officer-boot"]
---

You are the first officer for the workflow at `{workflow_dir}/`.

You are a DISPATCHER. You read state and dispatch crew. You NEVER do stage work yourself.
```

The agent body keeps only the core identity. All operational instructions come from the preloaded skill.

### Why not a build step?

A build step (concatenate references into agent files at release time) was considered but rejected:

- Adds build complexity and a drift risk (stale builds)
- Requires a release script change
- Produces generated files that look editable but shouldn't be
- Skill preloading is a platform feature designed for exactly this use case

### Codex path unchanged

Codex entry point (`skills/first-officer/SKILL.md`) continues reading references via relative paths. Codex skills resolve paths reliably. The boot skills are Claude Code specific — Codex doesn't use them.

## Relationship to other tasks

- **036 (compile targets)**: Orthogonal — 036 is about commission output format, this is about agent boot mechanics
- **084 (unified test harness)**: This fixes the root cause of the merge hook E2E test failure with haiku/low
- **076 (plugin-shipped agents)**: Evolved — 076 created the layered architecture, this fixes the path resolution gap

## Acceptance criteria

1. Boot skills exist: `skills/first-officer-boot/SKILL.md` and `skills/ensign-boot/SKILL.md`
2. Boot skills use `${CLAUDE_SKILL_DIR}` + `Read` instructions for reference files — paths resolve reliably
3. Agent files use `skills: ["spacedock:first-officer-boot"]` / `["spacedock:ensign-boot"]` in frontmatter
4. Agent files contain only identity (no operational instructions in the body)
5. Haiku/low follows the preloaded instructions without path resolution issues
6. Merge hook E2E test passes with haiku/low
7. Codex path unchanged — `skills/first-officer/SKILL.md` still works via relative paths
8. All existing E2E tests pass
9. References remain the single source of truth — no content duplication
