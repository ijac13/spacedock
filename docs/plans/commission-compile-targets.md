---
title: Commission compile targets (claude-code, codex, portable)
id: 036
status: backlog
source: CL
started:
completed:
verdict:
score: 0.65
worktree:
---

Treat commission as a compiler with a `--target` parameter. The pipeline definition (stages, quality criteria, entity schema) is source code. Commission compiles it into platform-specific orchestration files.

### Targets

| Target | Generates | Orchestration |
|--------|-----------|---------------|
| **claude-code** (default) | `.claude/agents/first-officer.md`, lieutenant agent files | Agent/TeamCreate/SendMessage, worktrees, team dispatch |
| **codex** | `AGENTS.md`, solo operator prompt | shell_command/apply_patch, sequential loop, workspace-write sandbox |
| **portable** | README + status script only | No orchestration — human or any agent operates manually |

### What's shared across targets (the "source")

- README with stages frontmatter (schema, state machine)
- Status script (bash, platform-agnostic)
- Entity template and schema
- Stage prose definitions (inputs/outputs/good/bad)

### What differs per target (the "binary")

- Agent file format and location (`.claude/agents/` vs `AGENTS.md` vs none)
- Dispatch mechanism (Agent tool vs sequential loop vs manual)
- Communication model (TeamCreate/SendMessage vs direct output vs none)
- Lieutenant agent format (Claude Code agent files vs Codex scoped AGENTS.md vs instruction docs)

### Evidence

- The first-officer template is the Claude Code target
- A portable target is just the PTP format without any orchestration layer

### Scope

- Add `--target` parameter to commission skill (default: claude-code)
- Factor out shared generation (README, status, entities) from target-specific generation (agent files)
- Implement codex target using the solo operator pattern from codex-compatibility research
- Implement portable target (trivial — just skip agent file generation)

### Cross-agent research findings (March 2026)

*Research conducted for task 057 (npx-skills publishing). Full analysis in `docs/plans/npx-skills-publishing.md`.*

The original targets table above (claude-code, codex, portable) was based on a May 2025 knowledge cutoff that classified other agents as single-agent systems. **This is no longer accurate.** As of Feb-Mar 2026, every major coding agent supports subagent spawning and named agent definitions. Cross-agent workflow execution is now realistic, not aspirational.

#### Agent file formats (where generated agents live)

| Agent | Location | Format |
|-------|----------|--------|
| Claude Code | `.claude/agents/*.md` | Markdown |
| Codex | `~/.codex/agents/*.toml` | TOML (model, sandbox, MCP config) |
| Gemini CLI | `.gemini/agents/*.md` | Markdown + YAML frontmatter |
| Cursor | `.cursor/agents/*.md` | Markdown + YAML frontmatter (name, description, model, readonly, is_background) |
| GitHub Copilot | `.github/copilot/agents/` | Custom format; also reads AGENTS.md |
| OpenCode | `.opencode/agents/*.md` | Markdown (filename = agent name) |
| Windsurf | N/A | No file-based agent definitions |

#### Three orchestration patterns (the real compile-target axis)

The **communication model** — not the file format or subagent spawning — is what differentiates targets:

1. **Team messaging** (Claude Code, OpenCode): Peer-to-peer `SendMessage`, shared mutable task lists. Spacedock's native model. OpenCode rebuilt Claude Code's agent-team system with event-driven P2P messaging.

2. **Orchestrator-collects** (Codex, Gemini CLI, Cursor, GitHub Copilot): Lead agent spawns workers and collects results. No worker-to-worker communication. The first-officer would need restructuring as a sequential orchestrator that dispatches ensigns and collects results, rather than using `TeamCreate`/`SendMessage`.

3. **Independent sessions** (Windsurf): Parallel Cascade sessions via git worktrees (Wave 13), no inter-session communication. Maps to the `portable` target.

#### Subagent dispatch equivalents

| Agent | Dispatch mechanism | Named agent support |
|-------|--------------------|-------------------|
| Claude Code | `Agent(type="ensign")` tool | `.claude/agents/ensign.md` |
| Codex | Reference custom agent by name; orchestrator spawns | `~/.codex/agents/*.toml` |
| Gemini CLI | Subagents exposed as tools; `@agent_name` explicit dispatch | `.gemini/agents/*.md` |
| Cursor | Task tool; custom agents in `.cursor/agents/`; recursive spawning (v2.5) | `.cursor/agents/*.md` |
| GitHub Copilot | `task` tool or `/fleet`; `@CUSTOM-AGENT-NAME` | Custom agents (GA Mar 2026) |
| OpenCode | Subagents via config; agent teams via ensemble plugin | `.opencode/agents/*.md` |

#### Inter-agent communication equivalents

| Agent | Communication model | SendMessage equivalent |
|-------|--------------------|-----------------------|
| Claude Code | `TeamCreate` + `SendMessage` P2P; shared `TaskList` | Native |
| Codex | Orchestrator collects; Agents SDK hand-offs via shared artifacts | None — use artifact-based coordination |
| Gemini CLI | Subagent returns summary to parent; A2A protocol for remote | None — return-to-parent only |
| Cursor | Lead aggregates results; async background agents (v2.5) | None — orchestrator-collects |
| GitHub Copilot | Fleet dispatch and collect; `/tasks` monitoring | None — orchestrator-collects |
| OpenCode | Event-driven P2P messaging; append-only JSONL inboxes | **Yes** — closest match to Claude Code |
| Windsurf | Independent parallel sessions | None — sessions isolated |

#### Revised target proposal

Instead of per-agent targets, consider targeting the 3 orchestration patterns:

| Target | Agents covered | Generated orchestration |
|--------|---------------|----------------------|
| `team-messaging` (default) | Claude Code, OpenCode | `TeamCreate`/`SendMessage`, shared tasks — current first-officer model |
| `orchestrator-collects` | Codex, Gemini CLI, Cursor, Copilot | Sequential dispatch-and-collect loop, no peer messaging |
| `portable` | Windsurf, any agent | No orchestration — README + status script only |

This reduces the compile-target matrix from 7+ agents to 3 patterns while covering the full ecosystem.
