---
id: 099
title: "Agent-captain interaction guardrails: idle handling and direct communication"
status: ideation
source: "#8, CL observation"
started: 2026-04-08T18:30:29Z
completed:
verdict:
score:
worktree:
issue: "#8"
pr:
---

Two related problems with how agents communicate with the captain:

## Problem 1: FO kills agents the captain is talking to (#8)

The FO misinterprets idle notifications from team agents as "stuck/unresponsive" and shuts them down. This happened repeatedly when agents were dispatched for captain interaction (brainstorming, discussion). Idle is normal between-turn state for team agents — it just means they're waiting for input.

The existing GATE IDLE GUARDRAIL only covers the gate phase. There's no equivalent for agents dispatched mid-stage that the captain is expected to interact with directly.

## Problem 2: Ensign relays through FO instead of talking to captain directly

When an ensign is dispatched for a stage that involves captain brainstorming, it uses SendMessage to relay through the FO for the first couple rounds instead of outputting text directly to the captain. Per the runtime doc, captain communication should be direct text output, not SendMessage. The ensign should know when it's expected to talk to the captain and use the right channel.

## Testing gap

There are currently no E2E tests for team interaction patterns — no tests verify SendMessage routing, agent-to-captain communication channels, or idle handling behavior. The LogParser infrastructure exists and can be extended to inspect SendMessage calls in JSONL logs.

Tests should verify:
- When an ensign is dispatched for captain interaction, it outputs text directly (not SendMessage to FO)
- The FO does not shut down agents based on idle notifications alone
- SendMessage is used for agent-to-agent communication, direct text for agent-to-captain

## Stage Report: ideation

### Investigation: Test infrastructure for interactive team communication

**What exists:**
- `test_lib.py` provides `LogParser` that can extract `tool_calls()`, `agent_calls()`, and `fo_texts()` from stream-json JSONL logs
- `LogParser.tool_calls()` returns all `tool_use` blocks including `SendMessage` — so we CAN detect whether an agent used SendMessage vs direct text output from logs
- `assembled_agent_content()` builds the full behavioral contract by concatenating agent entry point + all referenced files — used for static content checks
- Existing tests mix two patterns: (a) static checks against assembled template content (fast, deterministic), (b) E2E runs via `claude -p` with log analysis (expensive, non-deterministic)
- `test_team_dispatch_sequencing.py` and `test_team_health_check.py` demonstrate the pattern for team-related E2E tests

**New from spike 102 — InteractiveSession harness:**
- `scripts/test_lib_interactive.py` provides `InteractiveSession` — a PTY-driven multi-turn test harness
- Drives claude interactively via `pty.fork()`: start session, send messages, wait for patterns, stop
- Per-agent JSONL logs are stored at `~/.claude/projects/<slug>/<session-id>/subagents/agent-<id>.jsonl`
- Each ensign gets its own JSONL log — direct text blocks (type `text`) vs `SendMessage` tool calls are fully distinguishable
- `get_subagent_logs(project_dir)` finds per-agent logs from a session
- POC test (`test_interactive_poc.py`) passes: two sequential multi-turn exchanges work

**Captain-to-ensign addressing — NOT possible:**
- Spike 102 (Question 4) investigated thoroughly: there is no Shift+Up/Down, no @mention, no slash command, and no protocol mechanism for the captain to address a specific team member directly
- User input always goes to the main agent (FO); the FO routes to agents via `SendMessage`
- Direct text output from any agent is visible to the captain but cannot be replied to directly
- To test captain-to-ensign interaction, the test must send messages to the FO and rely on the FO to route them

**What CAN be tested (revised with InteractiveSession):**

1. **Static template checks** (fast, deterministic, zero API cost):
   - FO assembled content contains the dispatch idle guardrail wording
   - FO assembled content contains the agent back-off section
   - Ensign assembled content contains captain communication instructions
   - Ensign completion signal uses `SendMessage(to="team-lead")` (existing)

2. **E2E via InteractiveSession + subagent log analysis** (expensive, behavioral):
   - Start an interactive FO session with a workflow that has a dispatchable entity
   - Wait for the FO to dispatch an ensign (detect via `wait_for` on dispatch-related output)
   - After the ensign completes, stop the session and inspect subagent JSONL logs
   - Verify that ensign subagent logs show direct text blocks for captain-visible output and `SendMessage(to="team-lead")` only for completion/clarification
   - Verify that the FO main log does NOT contain premature agent shutdown commands

3. **E2E idle guardrail verification** (harder, partial coverage):
   - The idle notification scenario is difficult to force deterministically — idle notifications come from the Claude Code runtime when an agent has no pending messages, which requires timing control the harness doesn't provide
   - Partial approach: run a team session with a simple workflow, verify the FO does not shut down agents between dispatch and their completion message
   - Full approach: would require injecting synthetic idle events, which is not supported

### Root cause analysis

**Problem 1: FO kills agents during captain interaction**

Root cause: The FO runtime doc (`claude-first-officer-runtime.md`) has two relevant sections:
- **Captain Interaction** (line 71-77): Says "While waiting at a gate, do NOT shut down the dispatched agent" — but this only covers gate-waiting
- **Agent Back-off** (line 109-111): Says "If the captain tells you to back off an agent, stop coordinating it" — reactive, not proactive

Missing: No guardrail telling the FO that idle notifications from dispatched agents are normal between-turn state and should NEVER trigger shutdown. The FO has no instruction to distinguish "idle because waiting for captain input" from "idle because stuck."

Fix location: `references/claude-first-officer-runtime.md`, add a new guardrail paragraph in or after the Captain Interaction section.

**Problem 2: Ensign relays through FO instead of talking to captain directly**

Root cause: The ensign runtime doc (`claude-ensign-runtime.md`) only mentions two communication patterns:
- `SendMessage(to="team-lead")` for clarification (line 11)
- `SendMessage(to="team-lead")` for completion signal (line 18)

The ensign has NO instruction about when or how to communicate directly with the captain. The Claude Code system prompt tells agents "Just writing a response in text is not visible to others on your team - you MUST use the SendMessage tool" — so the ensign defaults to routing everything through SendMessage to the FO.

The FO runtime doc says "The captain is the user of the Claude Code session. Communicate with the captain via direct text output (not SendMessage)" — but this instruction is for the FO, not the ensign. The ensign never reads the FO runtime doc.

Fix location: `references/claude-ensign-runtime.md`, add a Captain Communication section explaining that direct text output goes to the captain and should be used for interactive/brainstorming stages.

### Proposed approach

#### Change 1: FO dispatch idle guardrail

Add to `references/claude-first-officer-runtime.md`, after the existing "Agent Back-off" section (or merged into it):

**Before (current Agent Back-off section, lines 109-111):**
```
## Agent Back-off

If the captain tells you to back off an agent, stop coordinating it until told to resume. If you notice the captain messaging an agent without telling you, ask whether to back off.
```

**After:**
```
## Agent Back-off

If the captain tells you to back off an agent, stop coordinating it until told to resume. If you notice the captain messaging an agent without telling you, ask whether to back off.

**DISPATCH IDLE GUARDRAIL:** After dispatching an agent, do NOT shut it down based on idle notifications. Idle is normal between-turn state for team agents — it means they are waiting for input from the captain or another agent. Only shut down a dispatched agent when: (1) it sends a completion message, (2) the captain explicitly requests shutdown, or (3) you are transitioning the entity to a new stage. Never interpret idle notifications as "stuck" or "unresponsive."
```

#### Change 2: Ensign captain communication

Add to `references/claude-ensign-runtime.md`, a new section after "Clarification":

**New section to add after the Clarification section (after line 12):**
```
## Captain Communication

When dispatched for a stage that involves direct interaction with the captain (brainstorming, discussion, ideation review), communicate with the captain via direct text output — not SendMessage. In the Claude Code team model, your text output is visible to the captain. Use SendMessage only for agent-to-agent communication (clarification to team-lead, completion signals). When the captain messages you directly, respond with direct text output.
```

#### Change 3: FO dispatch prompt hint (optional, reinforces change 2)

When the FO dispatches an ensign for a stage that the captain is expected to interact with, the dispatch prompt could include a hint. However, this is harder to implement because the FO would need to know which stages involve captain interaction — and that's not currently encoded in stage metadata. This change is deferred unless CL wants to add a stage property like `captain-interactive: true`.

### Testing approach

**Tier 1: Static template checks** (fast, deterministic, zero API cost)

Add to `test_agent_content.py`:
- `test_assembled_claude_first_officer_has_dispatch_idle_guardrail`: Check assembled FO content contains "DISPATCH IDLE GUARDRAIL" and key phrases: "idle notifications", "between-turn state", three shutdown conditions, "never interpret"
- `test_assembled_claude_ensign_has_captain_communication`: Check assembled ensign content contains "captain" communication instructions, "direct text output", and that SendMessage is scoped to agent-to-agent use

**Tier 2: E2E subagent log analysis** (expensive, behavioral)

New test file `test_ensign_communication.py` using `InteractiveSession` from spike 102:
1. Create a test project with a simple workflow (single entity, single non-worktree stage)
2. Start an interactive FO session via `InteractiveSession`
3. Send a prompt to process the entity through the workflow
4. Wait for the FO to dispatch an ensign and for the ensign to complete (detect via `wait_for` on completion-related output)
5. Stop the session
6. Inspect subagent JSONL logs via `get_subagent_logs()`:
   - Parse each subagent log with `LogParser`
   - Verify `fo_texts()` returns direct text blocks (captain-visible output)
   - Verify `tool_calls()` contains `SendMessage` only with `to="team-lead"` for completion/clarification
   - Verify no `SendMessage` calls relay content that should be direct text output

This test depends on spike 102 (`test_lib_interactive.py`) being merged first.

**Tier 3: Idle guardrail behavioral test** (deferred — partial coverage only)

The idle notification scenario cannot be forced deterministically. The FO receives idle notifications from the Claude Code runtime when an agent has no pending work — this timing is not controllable from the test harness.

Partial approach (if needed later): Run a team session, introduce a deliberate delay between dispatch and completion, verify the FO log does not contain agent shutdown commands during that window. This is flaky by nature and not recommended for CI.

The static template check (Tier 1) is the reliable guardrail for the idle problem. The behavioral guarantee comes from the template wording being present in the FO's operating contract.

### Acceptance criteria

1. **AC1:** FO assembled content contains "DISPATCH IDLE GUARDRAIL" with the key behavioral rules (idle is normal, three shutdown conditions)
   - Test: static check in `test_agent_content.py` via `assembled_agent_content("first-officer")`
   - Verifiable: YES

2. **AC2:** Ensign assembled content contains captain communication instructions (direct text output for captain, SendMessage scoped to agent-to-agent)
   - Test: static check in `test_agent_content.py` via `assembled_agent_content("ensign")`
   - Verifiable: YES

3. **AC3:** The dispatch idle guardrail is in `references/claude-first-officer-runtime.md` (not just in the entity plan)
   - Test: file content check (covered by AC1 since `assembled_agent_content` reads the reference files)
   - Verifiable: YES

4. **AC4:** The captain communication section is in `references/claude-ensign-runtime.md`
   - Test: file content check (covered by AC2)
   - Verifiable: YES

5. **AC5:** Existing tests still pass (no regressions)
   - Test: run `test_agent_content.py`
   - Verifiable: YES

6. **AC6:** E2E test verifies ensign uses direct text for captain-visible output and SendMessage only for completion/clarification (subagent log analysis)
   - Test: `test_ensign_communication.py` using `InteractiveSession` + `LogParser` on subagent logs
   - Depends on: spike 102 merged
   - Verifiable: YES (once dependency is met)

7. **AC7:** E2E test verifies FO does not issue premature agent shutdown between dispatch and completion
   - Test: `test_ensign_communication.py` — inspect FO main session log for absence of shutdown-related SendMessage to agents before their completion signal
   - Depends on: spike 102 merged
   - Verifiable: YES (once dependency is met)

### Edge cases

1. **Bare mode agents:** In bare mode, the Agent tool blocks until completion — there are no idle notifications and no team. The dispatch idle guardrail is irrelevant in bare mode. No special handling needed.

2. **Single-entity mode:** Gates auto-resolve, so the captain isn't interacting. The dispatch idle guardrail still applies (agents dispatched in single-entity mode could still go idle if waiting for external input), but the captain communication section is less relevant. No special handling needed — the ensign instructions are conditional on "stages that involve direct interaction with the captain."

3. **Feedback stages:** During feedback loops, agents are kept alive for messaging. The dispatch idle guardrail should not conflict with the existing feedback flow — the shutdown conditions (completion message, captain request, stage transition) already align with the feedback flow.

4. **FO receives idle notification AND completion message simultaneously:** The guardrail says to act on completion messages. If both arrive, the completion message takes precedence. No conflict.

5. **Ensign dispatched for non-interactive stage:** The captain communication section says "when dispatched for a stage that involves direct interaction with the captain." For non-interactive stages, the ensign continues using SendMessage for clarification and completion as before. No behavioral change.

6. **Captain-to-ensign direct addressing:** Not currently possible in Claude Code (spike 102, Question 4). All captain messages go to the FO, which routes them. The ensign's "captain communication" instructions apply to text output visible to the captain, not to receiving captain messages directly. If Claude Code adds direct agent addressing in the future, the ensign instructions already cover the response pattern (direct text output).

### Checklist summary

- [x] 1. Investigate test infrastructure — DONE. Static template checks are achievable. InteractiveSession harness (spike 102) enables E2E behavioral tests via PTY driving + subagent log analysis. Captain cannot address ensigns directly (spike 102, Q4).
- [x] 2. Research root causes — DONE. Problem 1: FO has no idle guardrail for dispatched agents (only gate-waiting). Problem 2: Ensign has no captain communication instructions (defaults to SendMessage for everything).
- [x] 3. Propose approach — DONE. Two reference doc changes with specific before/after wording above.
- [x] 4. Propose testing — DONE. Three tiers: static template checks (Tier 1), E2E subagent log analysis via InteractiveSession (Tier 2, depends on spike 102), idle guardrail behavioral test deferred (Tier 3, partial coverage only).
- [x] 5. Define acceptance criteria — DONE. Seven ACs: five verifiable now via static checks, two verifiable after spike 102 merges.
- [x] 6. Consider edge cases — DONE. Six edge cases analyzed (bare mode, single-entity, feedback stages, simultaneous signals, non-interactive stages, captain direct addressing).
