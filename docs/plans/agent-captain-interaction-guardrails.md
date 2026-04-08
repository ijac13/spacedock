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
