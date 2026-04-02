<!-- ABOUTME: Tool mapping between Claude Code and Codex CLI for plain text workflow operation. -->
<!-- ABOUTME: Includes solo operator prompt for running plain text workflows with Codex. -->

# Codex CLI Tool Mapping and Solo Operator

Based on analysis of Codex CLI v0.110.0 (binary inspection + CLI help).

## Tool Mapping: Claude Code to Codex CLI

| Claude Code Tool | Codex Equivalent | Mechanism | Notes |
|-----------------|-----------------|-----------|-------|
| **Read** | `read_file` | Native tool | Codex has a built-in `read_file` tool. Also uses `cat`, `rg` via shell. |
| **Write** | `apply_patch` / shell | `apply_patch` for edits, shell `cat > file` for new files | No dedicated "write new file" tool; `apply_patch` is the primary edit mechanism. |
| **Edit** | `apply_patch` | Native tool | Uses unified diff format: `*** Begin Patch / *** Update File: path / @@ context / -old / +new / *** End Patch`. |
| **Bash** | `shell_command` / `exec_command` | Native tool | Runs in sandbox (read-only, workspace-write, or danger-full-access). Sandbox controls what's writable. |
| **Glob** | `rg --files` / `list_dir` | Shell + native tool | `list_dir` is a native tool. For glob patterns, uses `rg --files` or `find` via shell. |
| **Grep** | `rg` via shell | Shell command | System prompt explicitly prefers `rg` (ripgrep) over `grep`. No dedicated grep tool. |
| **Agent** | `spawn_agent` | Experimental feature | Multi-agent is behind `multi_agent` feature flag in `/experimental`. Uses "collab" mode with thread-based coordination. |
| **TeamCreate** | N/A (collab mode) | Experimental | Collab mode handles agent spawning/coordination, but the protocol differs from Claude Code's team model. |
| **SendMessage** | N/A (collab events) | Experimental | Agents communicate via collab events (`collab_agent_interaction_begin/end`), not explicit message passing. |

## Codex-Specific Tools (no Claude Code equivalent)

| Codex Tool | Purpose |
|-----------|---------|
| `update_plan` | Tracks steps and renders progress to user. |
| `web_search` | Live web search (opt-in via `--search`). |
| `view_image` | Displays images in terminal. |
| `js_repl` | Persistent Node.js REPL (experimental). |
| `spawn_agents_on_csv` | Batch-spawn agents from CSV (experimental). |

## Instruction Loading

| Mechanism | Claude Code | Codex CLI |
|-----------|------------|-----------|
| Project instructions | `.claude/CLAUDE.md` | `AGENTS.md` (any directory; scoped to directory tree) |
| Agent definitions | `.claude/agents/*.md` | No equivalent. Use `AGENTS.md` or pass instructions via prompt. |
| User config | `.claude/settings.json` | `~/.codex/config.toml` |
| Invocation with instructions | `claude --agent spacedock:first-officer` | `codex -C <dir> "prompt..."` or `codex exec "prompt..."` |
| Config overrides | N/A | `-c key=value` flag (TOML values) |
| Developer instructions | CLAUDE.md | `developer_instructions` in config.toml or `model_instructions_file` |

### AGENTS.md Scoping Rules

- An `AGENTS.md` file governs its containing directory and all children.
- Deeper files override shallower ones on conflict.
- Direct prompt instructions override all `AGENTS.md` content.
- Root `AGENTS.md` is automatically loaded; subdirectory ones are checked when touching files in their scope.

## Sandbox Modes

Codex runs shell commands in a sandbox. Three modes:

| Mode | Flag | File writes | Network | Git |
|------|------|------------|---------|-----|
| `read-only` | `-s read-only` | None | No | Read-only |
| `workspace-write` | `-s workspace-write` or `--full-auto` | CWD + TMPDIR | No | Yes (within CWD) |
| `danger-full-access` | `-s danger-full-access` | Anywhere | Yes | Yes |

For workflow operation, `workspace-write` is sufficient for all operations (reading files, running status script, editing entities, git commit) as long as the workflow directory is within the workspace.

## Workflow Operation Feasibility

| Workflow Operation | Codex Capability | Sandbox Requirement | Works? |
|--------------|-----------------|-------------------|--------|
| Read README and entity files | `read_file` or `cat` | Any | Yes |
| Run `bash {dir}/status` | `shell_command` | Any | Yes |
| Edit entity frontmatter | `apply_patch` | workspace-write | Yes |
| Edit entity body | `apply_patch` | workspace-write | Yes |
| `git commit` at stage boundaries | `shell_command` | workspace-write | Yes |
| `git worktree add/remove` | `shell_command` | workspace-write | Yes (if worktree is under CWD) |
| Dispatch sub-agents | `spawn_agent` (experimental) | workspace-write | Partial (experimental feature) |
| Team messaging | N/A | N/A | No |

## Solo Operator Prompt

This prompt collapses the first-officer/ensign split into a single sequential operator. Designed for `codex exec` or interactive mode.

### Usage

```bash
# Interactive mode
codex -s workspace-write -C /path/to/project "$(cat references/codex-solo-operator-prompt.txt)"

# Non-interactive exec mode
codex exec -s workspace-write -C /path/to/project "$(cat references/codex-solo-operator-prompt.txt)"
```

### Prompt

```
You are operating a plain text workflow at `{dir}/`.

## Startup

1. Read `{dir}/README.md` to understand the workflow schema, stages, and quality criteria.
2. Run `bash {dir}/status` to see the current state of all entities.
3. List entity files: `ls {dir}/*.md | grep -v README`

## Work Loop

For each entity ready for its next stage (prioritize by score descending, then alphabetically):

1. Read the entity file to understand its current state and content.
2. Identify the current stage from the `status:` field in YAML frontmatter.
3. Look up the next stage definition in the README (inputs, outputs, good, bad).
4. Check if the transition requires human approval. If yes, ask the user before proceeding.
5. Do the stage work as described in the README's stage definition.
6. Update the entity body with your work output (findings, analysis, implementation notes).
7. Update the YAML frontmatter:
   - Set `status:` to the next stage name.
   - Set `started:` to current ISO 8601 timestamp if this is the first active stage.
   - If reaching the terminal stage, set `completed:` and `verdict:` (PASSED or REJECTED).
8. Commit: `git add {dir}/{entity}.md && git commit -m "advance: {slug} to {next_stage}"`
9. Run `bash {dir}/status` to verify the transition.
10. Move to the next entity.

## Rules

- Follow the quality criteria (Good/Bad) from the README for each stage.
- Never skip approval gates. If a transition says "Human approval: yes", stop and ask.
- Keep entity frontmatter as valid YAML at all times.
- One commit per stage transition. Commit message format: "advance: {slug} to {stage}"
- If anything is unclear about the workflow schema or an entity, ask rather than guess.
- Work sequentially through entities. Do not try to parallelize.

## When Done

After processing all ready entities, run `bash {dir}/status` one final time and report:
- Which entities were advanced and to what stage.
- Which entities are blocked (waiting for approval or at terminal stage).
- Any issues encountered.
```

## Key Differences from Claude Code Operation

| Aspect | Claude Code (first-officer + ensigns) | Codex (solo operator) |
|--------|--------------------------------------|----------------------|
| Parallelism | Multiple ensigns in parallel worktrees | Sequential, one entity at a time |
| Dispatch | `Agent()` spawns sub-agents | Operator does all work itself |
| State management | First-officer manages frontmatter; ensigns write body only | Operator manages both frontmatter and body |
| Worktree isolation | Each ensign gets its own git worktree | Works on current branch (no worktree needed for sequential work) |
| Completion signaling | `SendMessage(to="team-lead", ...)` | Direct output to user |
| Approval gates | First-officer asks captain, relays to ensign | Operator asks user directly |
| Instruction loading | `agents/first-officer.md` (plugin) | Prompt passed via CLI argument or `AGENTS.md` |

## Experimental Multi-Agent Mode

Codex v0.110.0 has an experimental `multi_agent` feature (enable via `/experimental` in interactive mode or `--enable multi_agent`). When enabled:

- The model can call `spawn_agent` to create sub-agents in separate threads.
- Sub-agents run in their own sandbox context.
- Coordination happens via collab events, not explicit message passing.
- There is also `spawn_agents_on_csv` for batch spawning.

This is architecturally closer to Claude Code's `Agent()` tool but with a different coordination model. If this feature stabilizes, a multi-agent workflow operator (closer to the first-officer/ensign pattern) becomes feasible on Codex.
