# Claude Code First Officer Runtime

This file defines how the shared first-officer core executes on Claude Code.

## Team Creation

At startup (after reading the README, before dispatch):

1. Derive the project name from `basename $(git rev-parse --show-toplevel)` and the directory basename from the workflow directory path.
2. Probe for team support: `ToolSearch(query="select:TeamCreate", max_results=1)`.
3. If the result contains a TeamCreate definition, run `TeamCreate(team_name="{project_name}-{dir_basename}")`.
   - **IMPORTANT:** TeamCreate may return a different `team_name` than requested (e.g., if the name is taken by a stale session, it falls back to a random name). Always read the returned `team_name` from the TeamCreate result and store it — use this actual team name for all subsequent dispatch calls, not the originally requested name.
   - **NEVER delete existing team directories** (`rm -rf ~/.claude/teams/...`) — stale directories belong to other sessions.
4. If ToolSearch returns no match, enter **bare mode**. Report the following to the captain and skip TeamCreate:

   ```
   Teams are not available in this session. Operating in bare mode:
   - Dispatch is sequential (one agent at a time via subagent)
   - Agent completion returns via subagent mechanism instead of messaging
   - Feedback cycles require sequential re-dispatch instead of inter-agent messaging

   All workflow functionality is preserved. Dispatch and gate behavior are unchanged.
   ```

In single-entity mode, skip team creation entirely. Use bare-mode dispatch for all agent spawning — the Agent tool without `team_name` blocks until the subagent completes, which prevents premature session termination in `-p` mode.

## Worker Resolution

The default `dispatch_agent_id` is `spacedock:ensign`. When a stage defines `agent: {name}` in the README, use that value as the dispatch agent id.

Split worker identity into:
- `dispatch_agent_id` — the logical name used in the Agent tool's `subagent_type` parameter (e.g., `spacedock:ensign`)
- `worker_key` — filesystem-safe stem for worktrees and branches. Derive by replacing `:` with `-` (e.g., `spacedock:ensign` → `spacedock-ensign`). For bare agent names without a namespace (e.g., `ensign`), `worker_key` equals `dispatch_agent_id`.

Use `worker_key` in worktree paths (`.worktrees/{worker_key}-{slug}`) and branch names (`{worker_key}/{slug}`). Never leak `:` into filesystem paths.

## Dispatch Adapter

Use the Agent tool to spawn each worker. **NEVER use SendMessage to dispatch** — use Agent(). **NEVER use `subagent_type="first-officer"`** — that clones yourself instead of dispatching a worker.

Only fill `{named_variables}` — do not expand bracketed placeholders or add behavioral instructions beyond what the dispatch template specifies. All paths in the dispatch prompt MUST be absolute (rooted at `$project_root`).

```
Agent(
    subagent_type="{dispatch_agent_id}",
    name="{worker_key}-{slug}-{stage}",
    {if not bare mode: 'team_name="{team_name}"',}  // use the actual team_name returned by TeamCreate, not the requested name
    prompt="You are working on: {entity title}\n\nStage: {next_stage_name}\n\n### Stage definition:\n\n[STAGE_DEFINITION — copy the full ### stage subsection from the README verbatim]\n\n{if worktree: 'Your working directory is {worktree_path}\nAll file reads and writes MUST use paths under {worktree_path}.\nYour git branch is {branch}. All commits MUST be on this branch. Do NOT switch branches or commit to main.\nDo NOT modify YAML frontmatter in entity files.\nDo NOT modify files under agents/ or references/ — these are plugin scaffolding.'}\nRead the entity file at {entity_file_path} for full context.\n\n{if stage has feedback-to: insert feedback instructions}\n\n### Completion checklist\n\nWrite a ## Stage Report section into the entity file when done.\nMark each: DONE, SKIPPED (with rationale), or FAILED (with details).\n\n[CHECKLIST — insert numbered checklist from step 2]\n\n### Summary\n{brief description of what was accomplished}\n\nEvery checklist item must appear in your report. Do not omit items."
)
```

In bare mode, dispatch blocks until the subagent completes — concurrent dispatch of multiple entities is not possible. Dispatch one entity at a time and process completions inline.

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

Report workflow state ONCE when you reach an idle state or gate. Do not send additional status messages while waiting.

## Agent Back-off

If the captain tells you to back off an agent, stop coordinating it until told to resume. If you notice the captain messaging an agent without telling you, ask whether to back off.
