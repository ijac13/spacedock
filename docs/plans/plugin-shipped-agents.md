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
