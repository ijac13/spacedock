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

**What's NOT possible with current infrastructure:**
- `claude -p` is single-prompt, single-response. There is no way to simulate multi-turn captain-to-ensign conversation
- `--input-format stream-json` exists for streaming input but it's still within a single session — no mechanism to inject a second user turn after the agent goes idle
- Testing "FO sees idle notification and does NOT kill agent" requires observing the FO's response to an ongoing team interaction — this is inherently interactive and cannot be driven by `claude -p`
- Testing "captain talks directly to an ensign" requires the captain to send a user message to a specific agent in the team — no test harness for this exists
- We cannot simulate or inject "idle notifications" from the team runtime into the FO's context

**What CAN be tested:**
1. **Static template checks** (fast, deterministic, zero API cost):
   - FO assembled content contains the dispatch idle guardrail wording
   - FO assembled content contains the agent back-off section
   - Ensign assembled content contains captain communication instructions
   - Ensign completion signal uses `SendMessage(to="team-lead")` (existing)
   - Ensign does NOT have instructions to relay all output through SendMessage to FO
2. **Log-based E2E checks** (expensive, partial coverage):
   - In a standard dispatch run, verify the FO does not call `SendMessage` to shut down agents that completed normally — but this doesn't test the idle-notification scenario specifically

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

**Achievable tests (static template checks):**

1. `test_agent_content.py` — add new test functions:
   - `test_assembled_claude_first_officer_has_dispatch_idle_guardrail`: Check that the assembled FO content contains "DISPATCH IDLE GUARDRAIL" and the key phrases "idle notifications", "between-turn state", "never interpret idle"
   - `test_assembled_claude_ensign_has_captain_communication`: Check that the assembled ensign content contains "captain" communication instructions and "direct text output"

2. These are the same pattern used by `test_assembled_claude_first_officer_has_gate_guardrails`, `test_assembled_claude_first_officer_has_team_health_check`, etc.

**Not achievable with current infrastructure:**

- E2E test that the FO actually ignores idle notifications (requires multi-turn interactive session with team)
- E2E test that an ensign outputs direct text instead of SendMessage during a brainstorming stage (requires captain-to-ensign multi-turn interaction)
- E2E test that the captain can talk to an ensign and the FO doesn't kill it (requires three-party interaction: captain, FO, ensign)

These would require a test harness that can:
1. Start an interactive `claude` session (not `-p`)
2. Inject user messages at specific points during the session
3. Observe team events (idle notifications, SendMessage calls) in real time
4. Run for an extended duration with multiple turns

This infrastructure does not exist and building it is a separate project.

### Acceptance criteria

1. **AC1:** FO assembled content contains "DISPATCH IDLE GUARDRAIL" with the key behavioral rules (idle is normal, three shutdown conditions)
   - Test: static check in `test_agent_content.py` via `assembled_agent_content("first-officer")`
   - Verifiable: YES

2. **AC2:** Ensign assembled content contains captain communication instructions (direct text output for captain, SendMessage for agent-to-agent)
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

### Edge cases

1. **Bare mode agents:** In bare mode, the Agent tool blocks until completion — there are no idle notifications and no team. The dispatch idle guardrail is irrelevant in bare mode. No special handling needed.

2. **Single-entity mode:** Gates auto-resolve, so the captain isn't interacting. The dispatch idle guardrail still applies (agents dispatched in single-entity mode could still go idle if waiting for external input), but the captain communication section is less relevant. No special handling needed — the ensign instructions are conditional on "stages that involve direct interaction with the captain."

3. **Feedback stages:** During feedback loops, agents are kept alive for messaging. The dispatch idle guardrail should not conflict with the existing feedback flow — the shutdown conditions (completion message, captain request, stage transition) already align with the feedback flow.

4. **FO receives idle notification AND completion message simultaneously:** The guardrail says to act on completion messages. If both arrive, the completion message takes precedence. No conflict.

5. **Ensign dispatched for non-interactive stage:** The captain communication section says "when dispatched for a stage that involves direct interaction with the captain." For non-interactive stages, the ensign continues using SendMessage for clarification and completion as before. No behavioral change.

### Checklist summary

- [x] 1. Investigate test infrastructure — DONE. Static template checks are achievable. Interactive multi-agent E2E tests are NOT possible with current infrastructure (requires multi-turn harness that doesn't exist).
- [x] 2. Research root causes — DONE. Problem 1: FO has no idle guardrail for dispatched agents (only gate-waiting). Problem 2: Ensign has no captain communication instructions (defaults to SendMessage for everything).
- [x] 3. Propose approach — DONE. Two reference doc changes with specific before/after wording above.
- [x] 4. Propose testing — DONE. Static template checks in `test_agent_content.py`. E2E idle/interaction tests are not achievable without new test infrastructure.
- [x] 5. Define acceptance criteria — DONE. Five ACs, all verifiable via static checks or existing test runs.
- [x] 6. Consider edge cases — DONE. Five edge cases analyzed (bare mode, single-entity, feedback stages, simultaneous signals, non-interactive stages).
