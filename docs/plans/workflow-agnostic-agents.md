---
id: 063
title: Make agents workflow-agnostic — one agent definition serves multiple workflows
status: backlog
source: CL
started:
completed:
verdict:
score: 0.85
worktree:
issue:
pr:
---

Currently the commission generates per-workflow agent files (first-officer, ensign, pr-lieutenant) with hardcoded workflow-specific values baked in via sed substitution (`__DIR__`, `__MISSION__`, `__CAPTAIN__`, `__ENTITY_LABEL__`, etc.). This means:

1. A project with two workflows gets naming collisions in `.claude/agents/` (both generate `ensign.md`)
2. Each refit regenerates all agents even though most content is identical
3. The agents carry workflow knowledge they could derive at runtime from the README

## Current state

The ensign is already nearly workflow-agnostic — it reads everything from the dispatch prompt and has no `__DIR__`. The first-officer has ~10 hardcoded `__DIR__` references and 2 `__PROJECT_NAME__` references. The pr-lieutenant has 1 `__DIR__` reference in its hooks.

### Variable audit

| Variable | Truly needed at commission time? | Alternative |
|----------|--------------------------------|-------------|
| `__DIR__` | Maybe — FO needs to know which directory | Could be passed at invocation or read from a config |
| `__MISSION__` | No — decorative heading/description | Read from README or omit |
| `__CAPTAIN__` | No — should be literal "the captain" (see #062) | Literal string |
| `__ENTITY_LABEL__` | No — cosmetic | Read from README frontmatter |
| `__FIRST_STAGE__` / `__LAST_STAGE__` | No | Read from README frontmatter |
| `__PROJECT_NAME__` / `__DIR_BASENAME__` | Maybe — used for team naming | Derive at runtime |
| `__SPACEDOCK_VERSION__` | No — metadata only | Could be in a comment or omitted |

## Key design questions

1. If agents are static (no per-workflow customization), can they ship as part of the plugin itself? Can a skill/plugin ship agent definitions, or must agents live in `.claude/agents/`?
2. If agents need minimal per-workflow config (just the directory path), what's the lightest way to pass it? Options: invocation argument, a small config file, naming convention.
3. How does the first-officer know which workflow to manage if it's not baked into the agent file? The current entry point is `--agent first-officer` which loads the agent file.
4. What happens to the commission and refit skills if agents become static? Commission still generates the README, status script, and directory structure — but agent generation could become a copy or a no-op if agents ship with the plugin.

## Acceptance criteria

1. Design document covers: how the FO learns which workflow directory to manage at runtime, how agents are distributed (plugin-shipped vs generated), and what changes in commission/refit.
2. The design handles the multi-workflow case: two workflows in the same project both work without agent file collisions.
3. The design preserves the current behavioral contract — agents behave identically to today for single-workflow projects.
4. Trade-offs between static agents (simpler, plugin-shippable) vs minimal-config agents (one sed variable) are analyzed.
5. Ideation consults two staff software engineers on the design pattern for workflow-agnostic agent dispatch.
