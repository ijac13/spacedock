---
id: 091
title: TeamCreate failure causes duplicate agent dispatch
status: validation
source: CL — observed in recce-gtm session, 3x duplicate agents per entity
started: 2026-04-06T00:00:00Z
completed:
verdict:
score: 0.8
worktree: .worktrees/spacedock-ensign-teamcreate-failure-sequencing
issue:
pr:
---

# TeamCreate failure causes duplicate agent dispatch

When TeamCreate fails (e.g., "Already leading team X"), the first officer retries team setup but also dispatches Agent calls in the same tool-call message. Since Claude Code executes all tool calls in a message in parallel, the Agent calls run regardless of the TeamCreate failure. Each retry spawns another batch of agents, producing duplicates that all write to the same entity files.

## Observed behavior

From a recce-gtm discovery-outreach session:

1. FO dispatches agents with `team_name` — agents spawn as `spacedock-ensign-{slug}-draft`
2. Team expires. FO tries TeamCreate, gets "Already leading team" error
3. FO batches TeamDelete + TeamCreate + Agent calls in same message — TeamCreate fails again, but agents spawn as `ensign-{slug}-draft`
4. FO retries again — more agents spawn as `@ensign-{slug}`
5. Result: 3 copies of each agent running simultaneously, all hitting the same entity files

## Root cause

The `claude-first-officer-runtime.md` has no guidance for:
- What to do when TeamCreate fails mid-session
- That team lifecycle calls and Agent dispatch calls must never share a tool-call message (since parallel execution means failure of one doesn't prevent the others)

## The fix

Two changes to `references/claude-first-officer-runtime.md`:

1. **Team Creation section**: Add TeamCreate failure recovery — "Already leading team" → TeamDelete in its own turn, then retry TeamCreate in a subsequent turn. Other failures → fall back to bare mode. Block all Agent dispatch until team setup resolves.

2. **Dispatch Adapter section**: Add explicit sequencing rule — team lifecycle calls (TeamCreate, TeamDelete) and Agent dispatch calls must NEVER appear in the same tool-call message.

## Stage Report

### 1. Problem statement with root cause analysis

**Root cause:** Claude Code executes all tool calls within a single assistant message in parallel. When the FO batches TeamCreate (or TeamDelete + TeamCreate) alongside Agent dispatch calls in the same message, the Agent calls proceed regardless of whether TeamCreate succeeds or fails. Each retry cycle that repeats this pattern spawns additional duplicate agents.

The failure cascade:
1. Team expires mid-session (or was never cleaned up from a prior session)
2. FO calls TeamCreate → gets "Already leading team X" error
3. FO attempts recovery by issuing TeamDelete + TeamCreate + Agent calls in a single message
4. TeamCreate fails again (TeamDelete hasn't completed yet — parallel execution), but Agent calls succeed and spawn workers
5. FO retries → more workers spawn with slightly different names (due to TeamCreate fallback naming)
6. Result: 2-3x duplicate agents all writing to the same entity files

Two missing guardrails in `claude-first-officer-runtime.md`:
- No failure recovery protocol for TeamCreate (what to do when it fails, how to retry safely)
- No sequencing rule preventing team lifecycle and dispatch from sharing a tool-call message

### 2. Before/after wording — Team Creation section

**BEFORE** (current text, lines 6-25 of `claude-first-officer-runtime.md`):

```markdown
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
```

**AFTER** (proposed replacement):

```markdown
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

**TeamCreate failure recovery:** If TeamCreate fails mid-session:

- **"Already leading team" error:** Call TeamDelete in its own message (no other tool calls). Wait for the result. Then call TeamCreate in a subsequent message. Do NOT combine TeamDelete, TeamCreate, or Agent dispatch in the same message — Claude Code executes all tool calls in a message in parallel, so the dependent calls will race.
- **Other errors (quota, internal):** Fall back to bare mode for the remainder of the session. Report the failure and mode change to the captain.
- **Block all Agent dispatch** until team setup resolves (either TeamCreate succeeds or bare mode is entered). Never dispatch agents while team state is uncertain.

In single-entity mode, skip team creation entirely. Use bare-mode dispatch for all agent spawning — the Agent tool without `team_name` blocks until the subagent completes, which prevents premature session termination in `-p` mode.
```

### 3. Before/after wording — Dispatch Adapter section

**BEFORE** (current text, first paragraph of Dispatch Adapter, line 39):

```markdown
## Dispatch Adapter

Use the Agent tool to spawn each worker. **Use Agent() for initial dispatch** — SendMessage is only used in the completion path to advance a reused agent to its next stage. **NEVER use `subagent_type="first-officer"`** — that clones yourself instead of dispatching a worker.
```

**AFTER** (proposed replacement):

```markdown
## Dispatch Adapter

Use the Agent tool to spawn each worker. **Use Agent() for initial dispatch** — SendMessage is only used in the completion path to advance a reused agent to its next stage. **NEVER use `subagent_type="first-officer"`** — that clones yourself instead of dispatching a worker.

**Sequencing rule:** Team lifecycle calls (TeamCreate, TeamDelete) and Agent dispatch calls must NEVER appear in the same tool-call message. Claude Code executes all tool calls within a message in parallel — if TeamCreate fails, Agent calls in the same message still execute, spawning orphan workers. Always resolve team state in one message, then dispatch agents in a subsequent message.
```

### 4. Acceptance criteria with test plans

| # | Criterion | Test Plan |
|---|-----------|-----------|
| AC1 | Team Creation section documents "Already leading team" recovery: TeamDelete alone → wait → TeamCreate alone | **Static test** in `test_agent_content.py`: assert assembled FO text contains "Already leading team" and "TeamDelete" and verifies the sequential recovery language (TeamDelete in its own message, then TeamCreate in a subsequent message). |
| AC2 | Team Creation section documents fallback to bare mode for non-"Already leading" errors | **Static test** in `test_agent_content.py`: assert assembled FO text contains "bare mode" in the failure recovery context and "Other errors" or equivalent. |
| AC3 | Team Creation section blocks Agent dispatch while team state is uncertain | **Static test** in `test_agent_content.py`: assert assembled FO text contains "Block all Agent dispatch" (or equivalent) language near the failure recovery section. |
| AC4 | Dispatch Adapter section contains the sequencing rule (team lifecycle and Agent never in same message) | **Static test** in `test_agent_content.py`: assert assembled FO text contains the sequencing rule language — team lifecycle calls and Agent dispatch calls must never appear in the same tool-call message. |
| AC5 | E2E: FO never puts TeamCreate/TeamDelete and Agent in the same assistant message | **E2E test** (`test_team_dispatch_sequencing.py`): Run the FO against a multi-entity workflow that requires team creation. Parse the JSONL log. For each assistant message, check that no message contains both a team lifecycle tool call (TeamCreate or TeamDelete) and an Agent tool call. See E2E test design below. |

### 5. Edge case analysis

| Edge Case | Handling |
|-----------|----------|
| **Team expires mid-session** | The "Already leading team" recovery path covers this. TeamDelete → wait → TeamCreate. If TeamCreate fails again, fall back to bare mode. |
| **TeamDelete fails** | Not explicitly handled in the current design. TeamDelete failure is rare (usually succeeds). If it fails, the subsequent TeamCreate will also fail with a non-"Already leading" error, triggering the bare-mode fallback. This is acceptable — bare mode preserves all functionality. |
| **Multiple retry cycles** | The design does not add an explicit retry limit because: (a) each step is in its own message, so no duplicate agents spawn, and (b) the "Other errors" catch-all enters bare mode after any non-"Already leading" failure. A TeamDelete → TeamCreate cycle can only repeat if TeamDelete succeeds but TeamCreate fails with "Already leading team" again, which should not happen. If it does, the second TeamCreate failure would be a non-"Already leading" error and trigger bare-mode fallback. No unbounded retry loop is possible. |
| **Bare mode fallback** | Already well-defined in the existing template. The only addition is that bare mode is now also triggered by TeamCreate failures (not just missing ToolSearch). All dispatch and gate behavior is preserved. |
| **Race between TeamDelete and TeamCreate** | Explicitly prevented by the sequencing rule — they must be in separate messages. TeamDelete completes before TeamCreate is issued. |

### 6. E2E test design

**Test file:** `tests/test_team_dispatch_sequencing.py`

**Approach:** Log-analysis E2E test (same pattern as `test_reuse_dispatch.py` and `test_scaffolding_guardrail.py`). Run the FO against a multi-entity workflow fixture that requires team creation. Parse the JSONL log and verify the sequencing invariant.

**What it tests:** The sequencing rule (AC5) — that no single assistant message contains both team lifecycle tool calls and Agent dispatch calls.

**Test structure:**

```python
# Phase 1: Set up test project with a simple 2-entity workflow fixture
#   (reuse an existing fixture like gated-pipeline or create a minimal one)
create_test_project(t)
setup_fixture(t, "gated-pipeline", "gated-pipeline")
install_agents(t)
git_add_commit(t.test_project_dir, "setup: team dispatch sequencing test")

# Phase 2: Run FO (Claude runtime only — teams are Claude-specific)
run_first_officer(t, "Process all tasks through the workflow.", ...)

# Phase 3: Parse log and validate sequencing invariant
log = LogParser(t.log_dir / "fo-log.jsonl")

# New helper: check that no assistant message mixes team lifecycle and Agent calls
TEAM_LIFECYCLE = {"TeamCreate", "TeamDelete"}
for msg in log.assistant_messages():
    tool_names = {
        block["name"]
        for block in msg["message"].get("content", [])
        if block.get("type") == "tool_use"
    }
    has_team = bool(tool_names & TEAM_LIFECYCLE)
    has_agent = "Agent" in tool_names
    t.check(
        f"message does not mix team lifecycle and Agent dispatch",
        not (has_team and has_agent),
    )

# Phase 4: Static template checks (same as AC1-AC4)
runtime = (REPO_ROOT / "references" / "claude-first-officer-runtime.md").read_text()
assembled = assembled_agent_content(t, "first-officer")

t.check("failure recovery documents Already-leading-team path",
        "Already leading team" in assembled)
t.check("sequencing rule in dispatch adapter",
        bool(re.search(r"team lifecycle.*Agent.*same.*message|NEVER appear in the same tool-call message",
                       assembled, re.IGNORECASE)))
t.check("blocks agent dispatch during uncertain team state",
        bool(re.search(r"block.*agent dispatch|never dispatch.*while team", assembled, re.IGNORECASE)))
```

**Cost/complexity:** Low-medium. The fixture reuses an existing pipeline. The FO run costs ~$1-2 (haiku, low effort). Log parsing is cheap. Total wall-clock ~60-120s.

**Why E2E is needed:** The sequencing rule is a behavioral guarantee about how the FO batches tool calls. Static tests can verify the text exists in the template, but only an E2E test can verify the FO actually follows the rule when running. The log-analysis approach avoids needing to simulate TeamCreate failures — it simply checks the invariant that should hold in all runs, even successful ones.

### Checklist

1. Problem statement with root cause analysis — DONE
2. Specific before/after wording for Team Creation section — DONE
3. Specific before/after wording for Dispatch Adapter section — DONE
4. Acceptance criteria with test plans — DONE (5 criteria, mix of static and E2E)
5. Edge case analysis — DONE (5 edge cases analyzed)
6. E2E test design — DONE (log-analysis approach with sequencing invariant check)
