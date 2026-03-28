## Finding: Skill tool unavailable to team-spawned subagents

**Date:** 2026-03-28
**Context:** Discovered while dispatching ensigns from the spacedock first-officer workflow

### Problem

Subagents spawned with `team_name` parameter (or auto-joined to a team via `name` parameter when spawned by a team lead) do not receive the `Skill` tool, even when:
- The agent definition in `.claude/agents/` explicitly lists `Skill` in its `tools:` frontmatter
- The `Skill` tool works for non-team subagents in the same project
- The plugin providing the skills (superpowers) is installed and enabled at user scope

### Evidence

| Spawn config | Has Skill? | Notes |
|---|---|---|
| `subagent_type="ensign"` + `team_name="spacedock-plans"` | No | 7 tools only |
| `subagent_type="ensign-test"` (no agent file) + `team_name` | No | 7 tools only |
| `subagent_type="general-purpose"` + `team_name` | No | 7 tools only |
| `subagent_type="ensign"` — no `name`, no `team_name` | **Yes** | 8 tools including Skill |
| `subagent_type="ensign"` + `name` (no explicit `team_name`) | No | Auto-joined team via team lead inheritance |

### Cross-project confirmation

In the `conn` project (spacedock@0.5.0, Claude Code 2.1.85):
- The FO was the **top-level conversation** (commission skill transitioned to FO behavior in same session)
- FO called `TeamCreate` but dispatched all ensigns **without** `team_name`
- Ensigns successfully invoked `Skill("superpowers:test-driven-development")`
- No `.claude/agents/` directory existed in that project

### Root cause

**Updated 2026-03-28:** The original hypothesis below was wrong. The root cause is the **intersection model** for team-spawned tool inheritance.

Team members receive the **intersection** of:
1. The team lead's available tools (from its own `tools:` declaration, or the full set if `tools:` is omitted)
2. The agent's own `tools:` declaration (from `.claude/agents/*.md`)

When the first-officer declared `tools: Agent, TeamCreate, SendMessage, Read, Write, Edit, Bash, Glob, Grep` (omitting Skill), team-spawned agents lost Skill — even though their own `tools:` listed it — because Skill wasn't in the team lead's set.

**Evidence for intersection model:** After removing `tools:` from the FO (giving it the full set), a team-spawned ensign with `tools: Read, Write, Edit, Bash, Glob, Grep, SendMessage, Skill` gained Skill but still lacked Agent — because Agent is in the FO's inherited full set but not in the ensign's `tools:` list.

**Fix:** Remove `tools:` from all agent templates so they inherit the full set. Behavioral instructions (not tool restrictions) define agent roles.

### Related GitHub issues

- [#29441](https://github.com/anthropics/claude-code/issues/29441) — Agent `skills:` frontmatter not preloaded for team-spawned teammates
- [#25834](https://github.com/anthropics/claude-code/issues/25834) — Plugin agent `skills:` frontmatter silently fails to inject skill content
- [#24072](https://github.com/anthropics/claude-code/issues/24072) — Skill tool not available in Plan mode
- [#19077](https://github.com/anthropics/claude-code/issues/19077) — Sub-agents can't create sub-sub-agents (same class: `tools:` not enforced)
- [#13605](https://github.com/anthropics/claude-code/issues/13605) — Custom plugin subagents cannot access MCP tools

### Workarounds

1. **Dispatch without team membership** — omit both `name` and `team_name`. Agent runs as foreground, returns results directly. Loses SendMessage (no mid-flight communication) but gains Skill. Suitable for brainstorming/ideation tasks.

2. **Inline skill content in dispatch prompt** — the FO reads the skill file and pastes relevant instructions into the ensign's prompt. Reliable, no platform dependency, but increases prompt size.

3. **Reference skills in README stage definitions** — the conn project's README included `**Skill:** superpowers:test-driven-development — MUST invoke before writing any code` in each stage definition. When the FO copies the stage definition into the dispatch prompt, the ensign sees the instruction and invokes the Skill tool (if available).

4. **`skills:` frontmatter in agent definition** — theoretically preloads skill content into the agent's context at startup, but this is buggy per issues #25834 and #29441.

### Architectural note

The issue stems from how the FO is instantiated:
- **Commission-to-FO-in-same-session** (conn pattern): FO is the top-level process. Ensigns are first-level subagents with full tool set.
- **FO-as-spawned-subagent** (spacedock plugin pattern): FO is spawned by the user's session. FO creates a team. Ensigns are team-spawned teammates whose tools are the intersection of the FO's tools and their own `tools:` declaration.

The fix is removing `tools:` from all agent definitions so they inherit the full set from the platform. Agent behavior is governed by instructions, not tool restrictions.
