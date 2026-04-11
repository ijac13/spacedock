---
id: 130
title: Codex first officer: support reusable worker threads and explicit shutdown semantics
status: backlog
source: FO observation during task 117 rejection flow on 2026-04-10/11
started:
completed:
verdict:
score: 0.72
worktree:
issue:
pr:
---

Codex first-officer runtime currently describes dispatch as effectively bare-mode and assumes completed workers are not reused. In practice, completed Codex workers can still be addressable via `send_input`, which means the workflow can preserve feedback-to semantics and relay validator findings back to the original implementer instead of always fresh-dispatching.

This gap showed up during task 117: the validator rejected implementation, and the FO spawned a new implementer instead of reusing the original implementation agent. The shared first-officer core already expects feedback loops to route findings back to the target stage agent when possible; the Codex runtime reference is what drifted.

This task should clarify the semantics and implement the missing runtime behavior:

- define when a completed Codex worker is still reusable
- track worker identity in FO runtime state so feedback can target the original agent thread
- use `send_input` for reuse and feedback relays when the agent is still available
- explicitly shut down completed agents when they are no longer needed
- update the shared/core reuse rules if they incorrectly equate "bare mode" with "no agent reuse"
- require the test plan to exercise the live Codex agent path, not just static wording or mocked state transitions

The goal is that Codex first officer behaves consistently with workflow feedback semantics: validation may be fresh, but rejected findings should route back to the kept-alive implementation worker when reuse is viable.

Test-plan expectation for ideation: the proposed verification must include at least one live runtime exercise that proves a completed implementation worker can receive routed feedback or an advancement message via `send_input`, and that no-longer-needed agents are explicitly shut down.
