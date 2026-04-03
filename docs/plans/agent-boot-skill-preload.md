---
id: 085
title: Agent boot via skill preloading — eliminate runtime path resolution
status: backlog
source: CL — 084 validation findings (haiku path resolution failure)
started:
completed:
verdict:
score: 0.7
worktree:
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

Skills have access to `${CLAUDE_SKILL_DIR}` for reliable path resolution. Skills also support inline shell execution (`!command`) for materializing file content at load time. This means:

1. Agent files stay thin (identity + frontmatter)
2. A boot skill reads reference files via `${CLAUDE_SKILL_DIR}` and inline shell
3. The skill content is injected into the agent's conversation before it sees the task prompt
4. No model-dependent file reading — content is materialized by the platform

### Architecture

```
agents/
  first-officer.md              ← thin: identity + skills: ["spacedock:first-officer-boot"]
  ensign.md                     ← thin: identity + skills: ["spacedock:ensign-boot"]

skills/
  first-officer-boot/SKILL.md   ← inlines FO references via shell
  ensign-boot/SKILL.md          ← inlines ensign references via shell
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

Each boot skill is ~3 lines of inline shell that cats the relevant reference files:

```markdown
---
name: first-officer-boot
---
`!cat ${CLAUDE_SKILL_DIR}/../../references/first-officer-shared-core.md`
`!cat ${CLAUDE_SKILL_DIR}/../../references/code-project-guardrails.md`
`!cat ${CLAUDE_SKILL_DIR}/../../references/claude-first-officer-runtime.md`
```

The platform substitutes `${CLAUDE_SKILL_DIR}`, executes the shell commands, and injects the combined output as a user message before the agent sees its task. No model guessing, no path resolution failures.

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
2. Boot skills use `${CLAUDE_SKILL_DIR}` + inline shell to cat reference files — no `Read` instructions
3. Agent files use `skills: ["spacedock:first-officer-boot"]` / `["spacedock:ensign-boot"]` in frontmatter
4. Agent files contain only identity (no operational instructions in the body)
5. Haiku/low follows the preloaded instructions without path resolution issues
6. Merge hook E2E test passes with haiku/low
7. Codex path unchanged — `skills/first-officer/SKILL.md` still works via relative paths
8. All existing E2E tests pass
9. References remain the single source of truth — no content duplication
