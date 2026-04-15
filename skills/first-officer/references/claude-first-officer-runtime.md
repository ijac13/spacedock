# Claude Code First Officer Runtime

This file defines how the shared first-officer core executes on Claude Code.

## Team Creation

At startup (after reading the README, before dispatch):

1. Derive the project name from `basename $(git rev-parse --show-toplevel)` and the directory basename from the workflow directory path.
2. Probe for team support: `ToolSearch(query="select:TeamCreate", max_results=1)`.
3. If the result contains a TeamCreate definition, run `TeamCreate(team_name="{project_name}-{dir_basename}-{YYYYMMDD-HHMM}-{shortuuid}")`. The timestamp token must be lowercase and hyphen-separated — avoid uppercase letters and colons so the name stays compatible with Claude Code's NAME_PATTERN and with the `claude-team` helper's derived-name rules. `{shortuuid}` is eight lowercase alphanumeric characters (the shortuuid default).
   - **IMPORTANT:** TeamCreate may return a different `team_name` than requested. Always store the returned `team_name` and use it for all subsequent calls.
   - **NEVER delete existing team directories** (`rm -rf ~/.claude/teams/...`) — stale directories belong to other sessions.
4. If ToolSearch returns no match, enter **bare mode**: dispatch is sequential (one subagent at a time), completions return inline, and feedback cycles are sequential re-dispatches. Report the mode to the captain. All workflow functionality is preserved.

**Diagnostic-only startup probe:** At startup the FO MAY inspect `~/.claude/teams/` with `ls` or `test -f ~/.claude/teams/{project_name}-{dir_basename}*/config.json` to REPORT existing on-disk team directories from prior sessions to the captain in the boot summary. This probe is DIAGNOSTIC-ONLY. Its result does NOT gate, short-circuit, or skip `TeamCreate` — `TeamCreate` always runs with the fresh-suffixed name above regardless of what the probe reports. On-disk state is not evidence of team health (Claude Code bug anthropics/claude-code#36806 leaves config files on disk after the in-memory registry desyncs). Deletion of any such directory is STILL forbidden per the NEVER-delete constraint above — the probe only surfaces their existence so the captain knows stale directories exist; it does not authorize removal. No such probe belongs in the `## Dispatch Adapter` pre-dispatch path.

**TeamCreate recovery procedure:** Call TeamDelete in its own message (no other tool calls). Wait for the result. Then call TeamCreate in a subsequent message. Store the returned `team_name` (it may differ). Do NOT combine TeamDelete, TeamCreate, or Agent dispatch in the same message — Claude Code executes all tool calls in a message in parallel, so dependent calls will race. This procedure applies ONLY to the narrow "Already leading team" case at startup (where Claude Code's in-memory slot holds a team the FO wants to replace cleanly). It is NOT a mid-session failure recovery and MUST NOT be invoked in response to "Team does not exist" or any other registry-desync signal — see Degraded Mode below.

**TeamCreate failure recovery (priority-ordered ladder):** If TeamCreate or any subsequent `Agent()` dispatch surfaces "Team does not exist" or any equivalent registry-desync signal mid-session, follow this ladder in order — do NOT retry within the same tier:

1. **Fresh-suffixed TeamCreate.** Attempt a single new `TeamCreate` with a fresh name of the form `{project_name}-{dir_basename}-{YYYYMMDD-HHMM}-{shortuuid}` computed at call time (new timestamp, new shortuuid, different from any name used earlier in this session). Retry to the same team name is banned. Do NOT call `TeamDelete` on the failed team — the registry is already desynced and another `TeamDelete → TeamCreate` cycle will re-contaminate the same slot per anthropics/claude-code#36806. Store the returned `team_name` and dispatch from entity frontmatter state. All prior agent names are presumed zombified. Do not SendMessage them; re-dispatch from entity frontmatter.
2. **Fall back to Degraded Mode per the Degraded Mode section below.** A second dispatch failure (including a failure of the tier-1 fresh-suffixed TeamCreate, or a second "Team does not exist" at any point in the session) trips Degraded Mode immediately.
3. **Surface to captain** with an explicit recovery prompt if tiers 1 and 2 both fail (e.g., TeamCreate itself errors with quota or internal failure on the fresh name, AND Degraded Mode cannot be entered for some reason such as `Agent` itself being unavailable). Do not silently retry. Do not block indefinitely — report the failure, name the tiers attempted, and wait for captain direction.

**Block all Agent dispatch** until team setup resolves (either tier-1 fresh-suffixed TeamCreate succeeds or Degraded Mode is entered). Never dispatch agents while team state is uncertain.

In single-entity mode, skip team creation entirely. Use bare-mode dispatch for all agent spawning — the Agent tool without `team_name` blocks until the subagent completes, which prevents premature session termination in `-p` mode.

When filing a new task, use `status --next-id` to fetch only the next sequential ID. Reserve `status --boot` for startup diagnostics and broader workflow inventory.

## Worker Resolution

The default `dispatch_agent_id` is `spacedock:ensign`. When a stage defines `agent: {name}` in the README, use that value as the dispatch agent id.

Split worker identity into:
- `dispatch_agent_id` — the logical name used in the Agent tool's `subagent_type` parameter (e.g., `spacedock:ensign`)
- `worker_key` — filesystem-safe stem for worktrees and branches. Derive by replacing `:` with `-` (e.g., `spacedock:ensign` → `spacedock-ensign`). For bare agent names without a namespace (e.g., `ensign`), `worker_key` equals `dispatch_agent_id`.

Use `worker_key` in worktree paths (`.worktrees/{worker_key}-{slug}`) and branch names (`{worker_key}/{slug}`).

## Dispatch Adapter

Use the Agent tool to spawn each worker. **Use Agent() for initial dispatch** — SendMessage is only used in the completion path to advance a reused agent to its next stage. **NEVER use `subagent_type="first-officer"`** — that clones yourself instead of dispatching a worker.

**Sequencing rule:** Team lifecycle calls (TeamCreate, TeamDelete) and Agent dispatch calls must NEVER appear in the same tool-call message — parallel execution causes races (see recovery procedure above). Always resolve team state in one message, then dispatch agents in a subsequent message.

**No pre-dispatch filesystem probe.** Do NOT run any filesystem check against `~/.claude/teams/{team_name}/` before `Agent()` in the normal dispatch path. The on-disk check is a guaranteed false positive under registry-desync (anthropics/claude-code#36806 leaves on-disk state intact even when the in-memory team slot is invalidated). Trust the in-memory team handle returned by `TeamCreate` and let `Agent()` itself surface any registry-desync error. On such an error, follow the TeamCreate failure recovery ladder (Team Creation section) and Degraded Mode semantics below — do NOT reintroduce a pre-dispatch probe.

**MANDATORY — Dispatch assembly via `claude-team build`:**

Do NOT assemble `Agent()` prompts manually. Do NOT construct the `prompt` string yourself. Do NOT invent `name` values. ALWAYS pipe input through `claude-team build` first and forward its output to `Agent()` verbatim. The key fields that MUST come from the helper output are `subagent_type`, `name`, `team_name`, `model`, and `prompt` (which contains the completion signal). Assembling these manually is a protocol violation except in the documented break-glass fallback below.

The only permitted path for initial `Agent()` dispatch is:

1. **REQUIRED — Assemble the input JSON** from the entity, stage, and your judgment:
   ```json
   {
     "schema_version": 1,
     "entity_path": "{absolute path to entity file}",
     "workflow_dir": "{absolute path to workflow directory}",
     "stage": "{target stage name}",
     "checklist": ["1. ...", "2. ..."],
     "team_name": "{team_name or null if bare mode}",
     "feedback_context": "{reviewer findings or null}",
     "scope_notes": "{additional context or null}",
     "bare_mode": false,
     "is_feedback_reflow": false
   }
   ```
   The `bare_mode` field must match the current dispatch context — never infer it from the stage, always from the live team state. Set `is_feedback_reflow` to true only when routing a rejection back to its `feedback-to` target stage.
2. **REQUIRED — Pipe the JSON to the helper** (do NOT skip this step):
   ```
   echo '<json>' | {spacedock_plugin_dir}/skills/commission/bin/claude-team build --workflow-dir {workflow_dir}
   ```
3. **REQUIRED — On exit 0, parse the stdout JSON and call `Agent()` with the emitted fields verbatim.** The `name`, `prompt`, and `model` fields MUST be taken from the helper output unchanged. The `prompt` already contains the team-mode `SendMessage(to="team-lead", ...)` completion signal — do not strip it, do not rewrite it. Forward `output.model` as the `Agent()` `model=` parameter when present; when `output.model` is null, OMIT the `model=` argument entirely (do NOT pass `model=None` — the Agent tool's default-inheritance only applies when the argument is absent):
   ```
   Agent(
       subagent_type=output.subagent_type,
       name=output.name,           // omit if bare mode (field absent)
       team_name=output.team_name, // omit if bare mode (field absent)
       model=output.model,         // omit when output.model is null
       prompt=output.prompt
   )
   ```
4. **On non-zero exit ONLY** (or if the binary is unavailable): read stderr for the error message, report the helper failure to the captain, and fall back to the Break-Glass Manual Dispatch procedure below. A zero-exit helper run is never a break-glass trigger.

In bare mode, dispatch blocks until the subagent completes — concurrent dispatch of multiple entities is not possible. Dispatch one entity at a time and process completions inline.

**Reuse dispatch (SendMessage advancement):** `claude-team build` serves only initial `Agent()` dispatch. When advancing a reused ensign to its next stage via `SendMessage(to="{ensign_name}")`, assemble the advancement message directly — the helper is not involved in the reuse path.

**Break-Glass Manual Dispatch (fallback ONLY when `claude-team build` exits non-zero or is unavailable):** Do NOT use this template while the helper is working. Report the helper failure to the captain before proceeding. Use this minimal template only as a degraded fallback:
```
Agent(
    subagent_type="{dispatch_agent_id}",
    name="{worker_key}-{slug}-{stage}",
    team_name="{team_name}",
    model="{effective_model}",
    prompt="You are working on: {entity title}\n\nStage: {stage}\n\n### Stage definition:\n\n{copy stage subsection from README verbatim}\n\nRead the entity file at {entity_file_path}.\n\n### Completion checklist\n\n{numbered checklist}\n\n### Completion Signal\n\nSendMessage(to=\"team-lead\", message=\"Done: {entity title} completed {stage}. Report written to {entity_file_path}.\")"
)
```
The break-glass template omits worktree instructions, feedback context, and scope notes. The `model=` slot is conditional — include it only when the stage (or `stages.defaults`) declares a model from the enum `sonnet | opus | haiku`; omit the entire `model=` argument when no model is declared. Use only when the helper is unavailable.

## Degraded Mode

Degraded Mode is an explicit, session-wide mid-session transition. Once entered, it persists until the session ends — there is no recovery back to teams mode in the same session.

### Triggers

Any one of the following trips Degraded Mode:

- First "Team does not exist" error (or equivalent registry-desync signal) surfaced by `Agent()` or any team-registry tool.
- Any SECOND dispatch failure within the session (any second failure regardless of timing — no time window, no durable counter). The stricter, counter-free rule is deliberate: the FO has no reliable way to track failure timestamps across context pressure and idle notifications, so "second failure anywhere in the session" is the fail-early trigger.
- Captain command `/spacedock bare` (explicit operator-initiated degrade).

### Effects

Once Degraded Mode is active, the following invariants hold for the remainder of the session:

- No `team_name` parameter on any subsequent `Agent()` dispatch. The dispatch input JSON sets `team_name: null` and `bare_mode: true`, and `claude-team build` emits the bare-mode Agent call with the `name` and `team_name` fields absent.
- Every stage dispatches fresh and blocks until completion. Concurrent dispatch is no longer available; the FO processes one entity through one stage at a time.
- No SendMessage reuse of prior agent names. Stage advancement is always a fresh `Agent()` dispatch seeded from entity frontmatter; `SendMessage(to="{ensign_name}")` against any pre-degrade name is forbidden.

### Captain Report Template

On Degraded Mode entry, the FO emits the following sentence verbatim to the captain (direct text output, not SendMessage):

> Falling back to bare mode for the remainder of this session due to team-infrastructure failure. Prior team agents are presumed-zombified; I will not route work to them or through the team registry. If you want to escalate: restart the session to retry team mode with a fresh name, or let me continue — every stage will still complete, just without concurrent dispatch.

### Cooperative Shutdown Sweep

On Degraded Mode entry, perform a single-pass cooperative shutdown sweep of every known agent name from session memory: one `SendMessage(to="{ensign_name}", message="shutdown_request")` per name. Ignore failures — the sweep is best-effort, not transactional. Do not retry. Do not track responses. Do not block on the sweep's outcome; proceed immediately to the first fresh bare-mode dispatch after the sweep is issued.

Exempt from the sweep any agent whose entity is currently in an active feedback-cycle state (tracked via a `### Feedback Cycles` subsection in the entity body). Those reviewers may still hold load-bearing context from the prior cycle that re-dispatch cannot reconstruct. Sweep feedback-cycle reviewers only on explicit captain confirmation.

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

1. **Check PR-pending entities** — Run `status --where "pr !="`. For each, check PR state via `gh pr view`. Advance merged PRs. When advancing a merged PR entity, clear its `mod-block` field if set: `status --set {slug} mod-block=`.
2. **Check mod-blocked entities** — Run `status --where "mod-block !="`. For each, re-read the blocking mod and resume its pending action (e.g., re-present the PR summary to the captain). Do not dispatch new work for a mod-blocked entity.
3. **Run `status --next`** — Dispatch any newly ready entities.
4. **If nothing is dispatchable** — Fire `idle` hooks (from registered mods), then re-run `status --next`. If entities became dispatchable (e.g., a hook advanced an entity), dispatch them. If still nothing, the event loop iteration ends.

Repeat from step 1 after each agent completion until the captain ends the session or, in single-entity mode, until the target entity is resolved.

## Mod-Block Enforcement at Terminal Transitions

Before advancing an entity into the Merge and Cleanup path, the FO must:

1. Check whether merge hooks are registered (from boot-time MODS data).
2. If merge hooks exist, set `mod-block` on the entity before invoking the first hook.
3. Invoke merge hooks in order. If a hook creates a blocking condition (sets `pr`, requires captain approval), leave `mod-block` set and report the pending state.
4. Only clear `mod-block` after the blocking condition is resolved (PR merged, captain chose alternative, hook completed without blocking).
5. Only proceed to terminal frontmatter updates (completed, verdict, worktree clear) and archival after `mod-block` is clear.

**The mechanism enforces this even if you forget.** `status --set` and `status --archive` refuse terminal transitions (status to a terminal stage, completed, verdict, worktree clear) and archival when all of the following hold:

- the workflow registers at least one merge hook (`_mods/*.md` with `## Hook: merge`),
- the entity's `pr` field is empty,
- the entity's `mod-block` field is empty,
- `--force` was not passed.

In that state the merge hook has provably not run. The refusal names the blocking hook so you can recover by either setting `mod-block=merge:{mod_name}` and invoking the hook (normal flow), or letting the hook set `pr` (which satisfies the invariant), or passing `--force` (captain explicitly approved bypassing the hook). Do NOT pass `--force` just because the guard is in the way — it exists to catch exactly the mistake of skipping the hook.

On session resume, scan entities with non-empty `mod-block` and resume the pending action. Do not re-run the hook from scratch — check what state the hook left (was a PR created? is the branch pushed?) and continue from there.

If the blocking mod file (`{workflow_dir}/_mods/{mod_name}.md`) is missing or unreadable, report to the captain: "Blocking mod {mod_name} is missing. The entity is stuck. Options: restore the mod file, or use `--force` to clear the block and resume normal flow." Wait for captain direction before proceeding.

## Agent Back-off

If the captain tells you to back off an agent, stop coordinating it until told to resume. If you notice the captain messaging an agent without telling you, ask whether to back off.

**DISPATCH IDLE GUARDRAIL:** After dispatching an agent, keep waiting until an explicit completion message arrives. Idle notifications are normal between-turn state for team agents — they are not a reason to tear down the team, and they usually mean the agent is waiting for input from the captain or another agent. Only shut down a dispatched agent when: (1) it sends a completion message, (2) the captain explicitly requests shutdown, or (3) you are transitioning the entity to a new stage. Never interpret idle notifications as "stuck" or "unresponsive."

**IDLE HALLUCINATION GUARDRAIL:** After acknowledging idle notifications once (e.g., "Ensign still available, standing by"), produce ZERO output for all subsequent idle notifications until a real human message arrives. Do not generate text, invoke tools, or take any action in response to repeated idle notifications. This prevents a known failure mode where the model hallucinates a user instruction (e.g., "Human: let's wrap up") after a long sequence of system-generated idle messages and then acts on the fabricated instruction.
