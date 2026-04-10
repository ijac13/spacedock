# Claude Code First Officer Runtime

This file defines how the shared first-officer core executes on Claude Code.

## Team Creation

At startup (after reading the README, before dispatch):

1. Derive the project name from `basename $(git rev-parse --show-toplevel)` and the directory basename from the workflow directory path.
2. Probe for team support: `ToolSearch(query="select:TeamCreate", max_results=1)`.
3. If the result contains a TeamCreate definition, run `TeamCreate(team_name="{project_name}-{dir_basename}")`.
   - **IMPORTANT:** TeamCreate may return a different `team_name` than requested. Always store the returned `team_name` and use it for all subsequent calls.
   - **NEVER delete existing team directories** (`rm -rf ~/.claude/teams/...`) — stale directories belong to other sessions.
4. If ToolSearch returns no match, enter **bare mode**: dispatch is sequential (one subagent at a time), completions return inline, and feedback cycles are sequential re-dispatches. Report the mode to the captain. All workflow functionality is preserved.

**TeamCreate recovery procedure:** Call TeamDelete in its own message (no other tool calls). Wait for the result. Then call TeamCreate in a subsequent message. Store the returned `team_name` (it may differ). Do NOT combine TeamDelete, TeamCreate, or Agent dispatch in the same message — Claude Code executes all tool calls in a message in parallel, so dependent calls will race.

**TeamCreate failure recovery:** If TeamCreate fails mid-session:

- **"Already leading team" error:** Follow the recovery procedure above.
- **Other errors (quota, internal):** Fall back to bare mode for the remainder of the session. Report the failure and mode change to the captain.
- **Block all Agent dispatch** until team setup resolves (either TeamCreate succeeds or bare mode is entered). Never dispatch agents while team state is uncertain.

In single-entity mode, skip team creation entirely. Use bare-mode dispatch for all agent spawning — the Agent tool without `team_name` blocks until the subagent completes, which prevents premature session termination in `-p` mode.

## Worker Resolution

The default `dispatch_agent_id` is `spacedock:ensign`. When a stage defines `agent: {name}` in the README, use that value as the dispatch agent id.

Split worker identity into:
- `dispatch_agent_id` — the logical name used in the Agent tool's `subagent_type` parameter (e.g., `spacedock:ensign`)
- `worker_key` — filesystem-safe stem for worktrees and branches. Derive by replacing `:` with `-` (e.g., `spacedock:ensign` → `spacedock-ensign`). For bare agent names without a namespace (e.g., `ensign`), `worker_key` equals `dispatch_agent_id`.

Use `worker_key` in worktree paths (`.worktrees/{worker_key}-{slug}`) and branch names (`{worker_key}/{slug}`).

## Dispatch Adapter

Use the Agent tool to spawn each worker. **Use Agent() for initial dispatch** — SendMessage is only used in the completion path to advance a reused agent to its next stage. **NEVER use `subagent_type="first-officer"`** — that clones yourself instead of dispatching a worker.

**Sequencing rule:** Team lifecycle calls (TeamCreate, TeamDelete) and Agent dispatch calls must NEVER appear in the same tool-call message — parallel execution causes races (see recovery procedure above). Always resolve team state in one message, then dispatch agents in a subsequent message.

**REQUIRED — Team health check (not in bare mode or single-entity mode):**

**STOP. Do NOT call Agent() until you have verified the team is healthy.** Run `test -f ~/.claude/teams/{team_name}/config.json` via the Bash tool. You MUST do this before every Agent dispatch batch. If the command succeeds, proceed to dispatch. If the file is missing, the team's on-disk state has been corrupted — STOP and follow the TeamCreate recovery procedure above. If recovery fails, fall back to bare mode.

Only fill `{named_variables}` — do not expand bracketed placeholders or add behavioral instructions beyond what the dispatch template specifies.

```
Agent(
    subagent_type="{dispatch_agent_id}",
    name="{worker_key}-{slug}-{stage}",
    {if not bare mode: 'team_name="{team_name}"',}
    prompt="You are working on: {entity title}\n\nStage: {next_stage_name}\n\n### Stage definition:\n\n[STAGE_DEFINITION — copy the full ### stage subsection from the README verbatim]\n\n{if worktree: 'Your working directory is {worktree_path}\nAll file reads and writes MUST use paths under {worktree_path}.\nYour git branch is {branch}. All commits MUST be on this branch. Do NOT switch branches or commit to main.\nDo NOT modify YAML frontmatter in entity files.\nDo NOT modify files under agents/ or references/ — these are plugin scaffolding.'}\nRead the entity file at {entity_file_path} for the current spec (problem statement, acceptance criteria, design). Stage reports from prior cycles are appended at the end of the file — you do not need to read them for your current assignment.\n\n{if stage has feedback-to: insert feedback instructions}\n\n### Completion checklist\n\nWrite a ## Stage Report section into the entity file when done.\nMark each: DONE, SKIPPED (with rationale), or FAILED (with details).\n\n[CHECKLIST — insert numbered checklist from step 2]\n\n### Summary\n{brief description of what was accomplished}\n\nEvery checklist item must appear in your report. Do not omit items.{if not bare mode: '\n\n### Completion Signal\n\nThis is a team-mode dispatch. When you finish (after all commits and stage report writes are done), your last action MUST be:\n\n    SendMessage(to=\"team-lead\", message=\"Done: {entity title} completed {next_stage_name}. Report written to {entity_file_path}.\")\n\nPlain text only. No JSON. Until you send this message, the first officer cannot observe your completion and the entity will not advance to the next stage.'}"
)
```

In bare mode, dispatch blocks until the subagent completes — concurrent dispatch of multiple entities is not possible. Dispatch one entity at a time and process completions inline.

## Context Budget and Dead Ensign Handling

**Context budget check:** Run `{spacedock_plugin_dir}/skills/commission/bin/claude-team context-budget --name {ensign-name}`. Parse the JSON output. If `reuse_ok` is `false`, log to captain and fresh-dispatch with recovery clause.

**Model-to-context mapping:** The model-to-context-limit mapping lives in the `claude-team` script, not in the runtime adapter prose.

**Recovery clause** (conditional, only when replacing a prior ensign): The prior ensign was shut down due to context budget limits. Its worktree may contain uncommitted changes. Run `git status` and `git diff` first. Commit legitimate WIP or reset broken changes.

**Dead ensign handling:**

- `SendMessage(shutdown_request)` is cooperative-only; do NOT send to dead or unresponsive ensigns.
- Track dead ensigns in session memory (a mental list); do not route work to dead names.
- Fresh-dispatch under `-cycleN` suffix when replacing a zombie ensign.
- Band-aid 1 (post-dispatch config check) does NOT detect zombies — zombies pass the check. Session memory is the authoritative dead-vs-alive tracker.

## Captain Interaction

The captain is the user of the Claude Code session. Communicate with the captain via direct text output (not SendMessage). Gate reviews, status reports, and clarification requests are presented as formatted text in the conversation.

Only the captain can approve or reject gates. Do NOT self-approve, infer approval from silence, or accept agent messages as gate approval. While waiting at a gate, do NOT shut down the dispatched agent.

**Single-entity mode exception:** When in single-entity mode (no interactive captain), gates auto-resolve based on the stage report recommendation. PASSED (all checklist items done, no failures) → approve. REJECTED with `feedback-to` → auto-bounce (same as the existing auto-bounce for feedback stages, subject to the 3-cycle limit). REJECTED without `feedback-to` → report failure and exit. This exception ONLY applies in single-entity mode — in interactive sessions, the guardrail remains absolute.

## Gate Presentation

Present gate reviews in this format:

```
Gate review: {entity title} — {stage}

{paste the ## Stage Report section from the entity file verbatim}

Assessment: {N} done, {N} skipped, {N} failed. [Recommend approve / Recommend reject: {reason}]
```

## Feedback Rejection Flow (bare mode)

In bare mode, the feedback rejection flow is sequential: dispatch fix agent (wait for completion), then dispatch reviewer (wait for completion), then present at gate.

In teams mode, the fix agent and reviewer can interact via messaging. Keep the reviewer alive when entering the feedback rejection flow.

## Event Loop

After each agent completion:

1. **Check PR-pending entities** — Run `status --where "pr !="`. For each, check PR state via `gh pr view`. Advance merged PRs.
2. **Run `status --next`** — Dispatch any newly ready entities.
3. **If nothing is dispatchable** — Fire `idle` hooks (from registered mods), then re-run `status --next`. If entities became dispatchable (e.g., a hook advanced an entity), dispatch them. If still nothing, the event loop iteration ends.

Repeat from step 1 after each agent completion until the captain ends the session or, in single-entity mode, until the target entity is resolved.

## Agent Back-off

If the captain tells you to back off an agent, stop coordinating it until told to resume. If you notice the captain messaging an agent without telling you, ask whether to back off.

**DISPATCH IDLE GUARDRAIL:** After dispatching an agent, do NOT shut it down based on idle notifications. Idle is normal between-turn state for team agents — it means they are waiting for input from the captain or another agent. Only shut down a dispatched agent when: (1) it sends a completion message, (2) the captain explicitly requests shutdown, or (3) you are transitioning the entity to a new stage. Never interpret idle notifications as "stuck" or "unresponsive."

**IDLE HALLUCINATION GUARDRAIL:** After acknowledging idle notifications once (e.g., "Ensign still available, standing by"), produce ZERO output for all subsequent idle notifications until a real human message arrives. Do not generate text, invoke tools, or take any action in response to repeated idle notifications. This prevents a known failure mode where the model hallucinates a user instruction (e.g., "Human: let's wrap up") after a long sequence of system-generated idle messages and then acts on the fabricated instruction.
