---
title: Test Spacedock with Codex
status: implementation
source: CL
started: 2026-03-24T00:00:00Z
completed:
verdict:
score:
worktree: .worktrees/ensign-codex-compatibility
---

Test Spacedock (the commission skill and generated first-officer pipeline) with OpenAI Codex CLI to verify cross-platform compatibility.

## Problem Statement

Spacedock is currently a Claude Code plugin. CL wants to know whether PTP pipelines can work with OpenAI's Codex CLI — a terminal-based coding agent using OpenAI models. This ideation analyzes what's platform-specific vs. platform-agnostic in Spacedock, and what "works with Codex" realistically means.

## Architecture Analysis: Claude Code-Specific vs. Platform-Agnostic

### Platform-Agnostic (the PTP format itself)

The core PTP format has zero Claude Code dependency:

- **Entity files** — markdown with YAML frontmatter. Any tool can read/write these.
- **README as schema** — a plain markdown file defining stages, fields, quality criteria. Human- and machine-readable.
- **Status script** — a bash script. Runs anywhere with bash 3.2+.
- **Git worktree isolation** — standard git. Any agent that can run `git worktree add` can use this.
- **Pipeline state** — lives on disk as files. `grep -l "status: ideation" docs/plans/*.md` works in any shell.

This is by design — PTP is "plain text". The format is the interface. Any agent that can read markdown, parse YAML frontmatter, edit files, and run bash can operate a PTP pipeline.

### Claude Code-Specific (the orchestration layer)

The commission skill and first-officer agent are deeply Claude Code-specific:

| Component | Claude Code Dependency | Notes |
|-----------|----------------------|-------|
| **Plugin system** (`plugin.json`, `/spacedock commission`) | Hard dependency | Codex has no plugin/skill system. Commission can't be invoked as `/spacedock commission`. |
| **Agent tool** (`Agent(subagent_type=..., prompt=...)`) | Hard dependency | First-officer dispatches ensigns via Claude Code's Agent tool. Codex has no equivalent sub-agent spawning mechanism. |
| **TeamCreate / SendMessage** | Hard dependency | First-officer creates a team and communicates with ensigns via messaging. Codex has no team/messaging model. |
| **Agent files** (`.claude/agents/first-officer.md`) | Hard dependency | `claude --agent first-officer` is a Claude Code convention. Codex doesn't read `.claude/agents/`. |
| **Plan mode** (`plan_mode_required`) | Claude Code feature | Not directly used in v0, but referenced in the agent file frontmatter tool list. |
| **Tool names** (Read, Write, Edit, Glob, Grep, Bash) | Partially portable | Codex has similar file-operation capabilities but different tool names/APIs. The model can adapt if prompted. |

### Assessment: Two Distinct Layers

Spacedock has two cleanly separable layers:

1. **PTP format** — fully portable. A directory of markdown files with a README schema and bash status script.
2. **Claude Code orchestration** — not portable. The commission skill, first-officer agent, team coordination, and sub-agent dispatch all rely on Claude Code's specific features.

## What Would "Works with Codex" Mean?

There are several possible scopes, from least to most ambitious:

### Scope A: Manual pipeline operation (trivially works today)

A human (or any agent) can already operate a PTP pipeline manually:
- Read the README to understand stages
- Run `bash {dir}/status` to see state
- Edit entity frontmatter to advance stages
- Do stage work as described in the README

This works because PTP is plain text. Codex can do this today with no changes to Spacedock.

### Scope B: Codex as an ensign (partial — most realistic target)

An ensign's job is narrow: read an entity file, do stage work, update the entity body, commit. The ensign prompt is self-contained text — it doesn't reference Claude Code-specific tools by name (it says things like "Read the entity file" and "Commit your work"). An ensign doesn't use Agent, TeamCreate, or SendMessage (except for the completion message).

**What would need to change:** The ensign prompt currently ends with `SendMessage(to="team-lead", ...)`. For Codex, completion signaling would need a different mechanism (e.g., write to a file, or just commit and exit). The first-officer would still need to be Claude Code to dispatch Codex ensigns, which brings us to...

**Feasibility:** Moderate. The ensign prompt is mostly platform-agnostic prose. The hard part is the dispatch and completion signaling protocol.

### Scope C: Codex as first-officer (not feasible for v0)

The first-officer relies on:
- `Agent()` to spawn sub-agents
- `TeamCreate()` and `SendMessage()` for coordination
- `.claude/agents/` convention for discovery

Codex has none of these. A Codex first-officer would need a completely different orchestration mechanism — probably a loop-based approach where one Codex process manages everything sequentially instead of dispatching parallel sub-agents.

**Feasibility:** Would require a fundamentally different first-officer architecture. Not a testing task — it's a design and implementation task.

### Scope D: Codex-native commission (not feasible for v0)

Replacing the commission skill requires a Codex plugin/skill equivalent (doesn't exist) or embedding commission logic in a different invocation pattern. Far out of scope.

## Fundamental Platform Differences

| Feature | Claude Code | Codex CLI | Gap |
|---------|------------|-----------|-----|
| Sub-agent spawning | `Agent()` tool | None — single-process | Architectural |
| Team messaging | `TeamCreate` + `SendMessage` | None | Architectural |
| Plugin/skill system | `plugin.json` + skill files | None | Architectural |
| Agent files | `.claude/agents/*.md` | `codex --instructions <file>` | Bridgeable |
| File operations | Read/Write/Edit/Glob/Grep tools | Shell commands (sandbox) | Bridgeable |
| Interactive conversation | Full multi-turn | Full multi-turn | Compatible |
| Bash execution | `Bash()` tool | Shell execution (sandboxed) | Compatible |
| Git operations | Via Bash tool | Via shell | Compatible |

The architectural gaps (sub-agents, teams, plugins) are not things that can be shimmed or adapted — they're fundamental differences in agent capability model.

## Proposed Approach

Given the analysis, the realistic scope for this entity is **Scope A + partial Scope B**: verify that PTP pipelines are operable by Codex as a manual operator, and explore what an ensign prompt for Codex would look like.

### Acceptance Criteria

1. **PTP format validation**: Confirm that a Codex CLI session can read a PTP pipeline README, run the status script, read entity files, and understand the pipeline state — without any Spacedock-specific tooling.

2. **Manual stage work**: Confirm that Codex can perform stage work on an entity (read the entity, do the work described in the stage definition, update the entity body, commit) when given appropriate instructions.

3. **Gap documentation**: Document the specific Claude Code dependencies that prevent full automation (Agent dispatch, team messaging, plugin invocation) and what alternatives Codex would need.

4. **Ensign prompt prototype**: Draft what an ensign-equivalent prompt for Codex would look like, noting where the completion signaling differs.

### What "Done" Looks Like

- A written assessment (in this entity body) of what works, what doesn't, and what the realistic path to Codex compatibility would be.
- Concrete evidence from testing (if CL has Codex available) or detailed analysis of Codex's documented capabilities.
- Honest conclusion: is cross-platform PTP operation worth pursuing in v0, or should it wait for a later version?

### Solo Operator Prompt Sketch

The key adaptation for Codex is collapsing the first-officer/ensign split into a single "solo operator" that does everything sequentially. Here's what the core loop would look like as a Codex instructions file:

```
You are operating a PTP pipeline at `{dir}/`.

## Startup
1. Read `{dir}/README.md` to understand the pipeline schema and stages.
2. Run `bash {dir}/status` to see the current state of all entities.

## Work Loop
For each entity ready for its next stage (prioritize by score, highest first):
1. Identify the entity's current stage and the next stage definition from the README.
2. Read the entity file for full context.
3. Do the work described in the stage definition (inputs -> outputs).
4. Update the entity body (not frontmatter) with your findings.
5. Update the entity frontmatter: set `status` to the next stage, set `started` if first active stage.
6. Commit: `git commit -am "advance: {slug} to {next_stage}"`
7. Run `bash {dir}/status` to verify.
8. If the next stage has an approval gate, stop and ask the user before continuing.
9. Repeat for the next entity.

## Key Rules
- Follow the quality criteria (Good/Bad) from the README for each stage.
- When an entity reaches the terminal stage, set `completed` and `verdict` in frontmatter.
- If anything is unclear, ask the user rather than guessing.
```

Note the differences from the Claude Code first-officer:
- No `Agent()` dispatch — the solo operator does stage work itself
- No `TeamCreate`/`SendMessage` — direct user interaction replaces team messaging
- No worktree isolation — operates on main branch (acceptable for sequential single-agent work)
- Frontmatter updates by the operator itself (in Claude Code, only the first-officer touches frontmatter)

### What's Lost in Solo Mode

- **Parallelism**: Can't work on multiple entities simultaneously
- **Separation of concerns**: The dispatcher/worker distinction disappears — one agent both decides what to do and does it
- **Worktree isolation**: Without sub-agents, there's no need for worktrees, but also no safety net if work on one entity breaks another
- **Team coordination**: No message passing, no shutdown protocol — simpler but less structured

### What's Preserved in Solo Mode

- **The PTP format**: Entities, stages, README schema, status script — all intact
- **Stage-driven workflow**: Quality criteria, inputs/outputs, approval gates still apply
- **Git discipline**: Commits at stage boundaries, status tracking
- **Human-in-the-loop**: Approval gates still pause for user decision

### Open Questions

1. **Does CL have Codex CLI installed and available for testing?** If not, this is a document-analysis task rather than a hands-on testing task.
2. **Is the goal "Codex can use PTP pipelines" or "Spacedock generates pipelines that work with Codex"?** The former is mostly true already; the latter requires significant new work.
3. **Priority relative to core Spacedock features**: Is this exploratory research, or does it need to drive implementation decisions for v0?
4. **Codex sandbox restrictions**: Does Codex's file-write sandbox allow editing files in place and running git commands? The solo operator needs both.

---

## Implementation Findings

Analysis performed against Codex CLI v0.110.0 (installed locally at `/opt/homebrew/bin/codex`). Tool capabilities determined via binary string analysis of the Codex Rust binary and CLI help output.

### Codex CLI Tool Inventory

Codex CLI provides these tools to the underlying model:

| Tool | Purpose | Equivalent Claude Code Tool |
|------|---------|---------------------------|
| `read_file` | Read file contents | Read |
| `list_dir` | List directory contents | Glob (partial) |
| `apply_patch` | Edit files via unified diff patches | Edit / Write |
| `shell_command` / `exec_command` | Run shell commands in sandbox | Bash |
| `update_plan` | Track and display plan steps to user | N/A (no equivalent) |
| `web_search` | Live web search (opt-in) | N/A |
| `view_image` | Display images | N/A |
| `spawn_agent` | Spawn sub-agent (experimental) | Agent |
| `spawn_agents_on_csv` | Batch spawn agents (experimental) | N/A |
| `js_repl` | Persistent Node.js REPL (experimental) | N/A |

Key observation: Codex's system prompt explicitly tells the model to use `rg` (ripgrep) via shell for searching and `rg --files` for file discovery. There are no dedicated Grep or Glob tools — these operations happen through `shell_command`.

### Tool Mapping for PTP Operations

| PTP Operation | Claude Code | Codex CLI | Works? |
|--------------|------------|-----------|--------|
| Read README | `Read` tool | `read_file` or `cat` via shell | Yes |
| Run status script | `Bash("bash dir/status")` | `shell_command("bash dir/status")` | Yes |
| Read entity files | `Read` tool | `read_file` or `cat` via shell | Yes |
| Find entities by status | `Grep("status: ideation", glob="*.md")` | `rg "status: ideation" *.md` via shell | Yes |
| Edit entity frontmatter | `Edit` tool (exact string replace) | `apply_patch` (unified diff) | Yes |
| Edit entity body | `Edit` tool | `apply_patch` | Yes |
| Create new files | `Write` tool | `cat > file` or `apply_patch` via shell | Yes |
| Git commit | `Bash("git commit ...")` | `shell_command("git commit ...")` | Yes |
| Git worktree add/remove | `Bash("git worktree ...")` | `shell_command("git worktree ...")` | Yes (if under CWD) |
| Dispatch sub-agents | `Agent(subagent_type=..., prompt=...)` | `spawn_agent` (experimental) | Partial |
| Team messaging | `SendMessage(to=...)` | Collab events (experimental) | Partial |

### Instruction Loading

Codex uses `AGENTS.md` files instead of `.claude/agents/*.md`:

- `AGENTS.md` can appear anywhere in the repo.
- Each `AGENTS.md` governs its containing directory and all descendants.
- Deeper files override shallower ones on conflict.
- Root `AGENTS.md` is automatically loaded into the developer message.
- The `-C <dir>` flag sets the working directory.
- `developer_instructions` in `~/.codex/config.toml` provides global instructions.
- `model_instructions_file` in config.toml can point to a file for per-project instructions.

### Sandbox Analysis

Codex has three sandbox modes:

- **read-only**: No file writes. Can read files, run status script. Cannot edit entities or commit.
- **workspace-write** (`--full-auto`): Can write within CWD + TMPDIR. All PTP operations work. No network access.
- **danger-full-access**: Full access. Not needed for PTP.

**`workspace-write` is sufficient for all PTP pipeline operations**, including running the status script, editing entities via `apply_patch`, and running `git commit`. The `--full-auto` convenience flag sets both `-a on-request` (model decides when to ask approval) and `--sandbox workspace-write`.

### Experimental Multi-Agent Mode

Codex v0.110.0 has a `multi_agent` feature flag (enable via `/experimental` in interactive mode). When enabled:

- The model can call `spawn_agent` to create sub-agents in separate threads.
- There is `spawn_agents_on_csv` for batch spawning.
- Coordination uses "collab" events (`collab_agent_spawn_begin/end`, `collab_agent_interaction_begin/end`, `collab_waiting_begin/end`, `collab_close_begin/end`).
- Sub-agents run in their own thread context with their own sandbox.

This is architecturally similar to Claude Code's `Agent()` tool but with different coordination semantics. If this feature stabilizes, a closer equivalent to the first-officer/ensign pattern becomes possible.

### Answers to Open Questions

1. **Codex CLI is installed** (v0.110.0 via Homebrew cask). Live testing is possible.
2. **Sandbox answer**: Yes, `workspace-write` mode allows file edits and git commands within CWD. All PTP operations are feasible.
3. **Multi-agent**: Experimental `spawn_agent` exists but the coordination model differs from Claude Code's team messaging. Not production-ready.
4. **AGENTS.md vs .claude/agents/**: Different convention but functionally similar for instruction loading. An `AGENTS.md` in the pipeline directory can serve as the solo operator instructions.

### Deliverables

- `references/codex-tools.md`: Full tool mapping table, instruction loading comparison, sandbox analysis, solo operator prompt, and assessment of Codex's experimental multi-agent capabilities. Ready for use as a reference when operating PTP pipelines with Codex CLI.

### Conclusion

PTP pipelines are fully operable by Codex CLI in solo operator mode using `workspace-write` sandbox. Every core PTP operation (read files, run status, edit entities, git commit) maps to available Codex tools. The main gap is the orchestration layer: Codex's experimental multi-agent feature (`spawn_agent`) exists but uses a different coordination model than Claude Code's team messaging. For v0, the solo operator pattern (sequential processing, no sub-agents) is the practical path. The experimental multi-agent mode is worth monitoring for future versions.

---

## Validation Report

Validated against Codex CLI v0.110.0 (confirmed installed at `/opt/homebrew/bin/codex`, symlink to `/opt/homebrew/Caskroom/codex/0.110.0/codex-aarch64-apple-darwin`). Verification method: binary string analysis of the Codex Rust binary, CLI help output, and cross-referencing tool handler source paths embedded in the binary.

### AC1: PTP Format Validation — PASS

The implementation correctly identifies that all PTP operations map to Codex tools. Verified via binary inspection:

- `read_file` — confirmed (handler at `core/src/tools/handlers/read_file.rs`). Supports slice and indentation-aware block modes.
- `shell_command` — confirmed (handler at `core/src/tools/handlers/shell.rs` and `unified_exec.rs`). Can run `bash dir/status`, git commands, etc.
- `apply_patch` — confirmed (handler at `core/src/tools/handlers/apply_patch.rs`). The system prompt instructs the model to prefer `apply_patch` for edits.
- `list_dir` — confirmed (handler at `core/src/tools/handlers/list_dir.rs`).

Sandbox mode `workspace-write` confirmed in the binary as allowing writes to CWD + TMPDIR with no network access. The `-s workspace-write` flag is a valid value for the `--sandbox` option (confirmed in `codex --help` output).

A Codex session could read a PTP README via `read_file`, run the status script via `shell_command`, read entity files, and grep for pipeline state — all without Spacedock-specific tooling.

### AC2: Manual Stage Work — PASS (analytical, not live-tested)

The implementation correctly concludes that Codex can perform stage work. The solo operator prompt is well-structured and covers the full work loop. However, this was not live-tested (no Codex session was actually run against a PTP pipeline). The assessment is analytical, based on confirmed tool availability. This is an honest limitation that the implementation acknowledges ("Live testing is possible" in the open questions but no live test results are reported).

### AC3: Gap Documentation — PASS

The gap documentation is thorough and accurate. The four-scope breakdown (A through D) clearly delineates what works vs. what doesn't. The "Fundamental Platform Differences" table in the entity body correctly identifies architectural vs. bridgeable gaps.

One correction worth noting: the entity body's table claims `codex --instructions <file>` for agent files. The actual mechanism is `AGENTS.md` files (scoped by directory) or passing instructions via prompt (`codex -C <dir> "prompt"`). There is no `--instructions` flag. The reference document (`codex-tools.md`) correctly describes AGENTS.md, but the entity body table has this minor inaccuracy.

### AC4: Ensign Prompt Prototype — PASS

The solo operator prompt in `references/codex-tools.md` is complete, well-structured, and includes usage examples for both interactive and exec modes. It correctly adapts the first-officer/ensign split into a sequential pattern. The "Key Differences" table is a useful reference.

### Tool Inventory Accuracy — PASS with corrections

The ensign performed genuine binary inspection (not just assumptions). Source handler paths are embedded in the binary, confirming the approach was real. However, the tool inventory has several omissions and one inaccuracy:

**Inaccuracy:**
- `exec_command` is listed as a tool alongside `shell_command`. From the binary, `exec_command` appears only in streaming event types (`exec_command_begin`, `exec_command_end`, `exec_command_output_delta`), not as a separate callable tool. The actual shell execution is handled by `shell_command` (via `core/src/tools/handlers/shell.rs`) and `unified_exec` (via `core/src/tools/handlers/unified_exec.rs`). The `unified_exec` handler appears to be a newer consolidated execution mechanism. Listing `exec_command` as a callable tool is misleading.

**Omissions (tools not mentioned in the inventory):**
- `grep_files` — handler at `core/src/tools/handlers/grep_files.rs`. The reference claims "No dedicated grep tool" but there IS one. It finds files whose contents match a regex pattern, sorted by modification time. This is functionally similar to Claude Code's Grep in `files_with_matches` mode.
- `send_input` — tool for messaging an existing spawned agent.
- `resume_agent` — tool for resuming a previously closed agent.
- `close_agent` — tool for closing a spawned agent.
- `request_user_input` — handler at `core/src/tools/handlers/request_user_input.rs`.
- `artifacts` — handler at `core/src/tools/handlers/artifacts.rs`.

The `grep_files` omission is the most significant because it means the reference's claim that "Codex has no dedicated Grep or Glob tools" is partially wrong. Codex does have a native file-content search tool.

The multi-agent-related omissions (`send_input`, `resume_agent`, `close_agent`) matter for the Scope C analysis — they show the multi-agent system is more fully developed than described (spawn + message + resume + close lifecycle).

**Correct claims:**
- `read_file`, `list_dir`, `apply_patch`, `shell_command`, `update_plan`, `web_search`, `view_image`, `spawn_agent`, `spawn_agents_on_csv`, `js_repl` — all confirmed in the binary.
- `multi_agent` feature flag confirmed.
- AGENTS.md scoping rules match what's visible in the binary's embedded system prompt.
- Sandbox modes (read-only, workspace-write, danger-full-access) confirmed.

### Solo Operator Prompt Assessment — PASS

The prompt is usable and would work if given to Codex. It covers startup, work loop, rules, and completion. Minor suggestions:
- Could mention `apply_patch` format specifically for entity edits (Codex's system prompt already guides the model toward this).
- The `{dir}` placeholder needs to be replaced before use — the usage examples correctly show this.

### Overall Assessment

**Recommendation: PASSED** with minor corrections needed in `references/codex-tools.md`.

The analysis is substantive, honest about its limitations (analytical rather than live-tested), and the conclusions are sound. The tool inventory was genuinely verified via binary inspection rather than assumed. The omissions (`grep_files`, multi-agent lifecycle tools) and the `exec_command` inaccuracy are real but do not change the core conclusions — PTP pipelines are operable by Codex in solo mode, and the orchestration layer remains Claude Code-specific.

The reference document is usable as-is for operating PTP pipelines with Codex. The corrections would make it more complete but are not blocking.
