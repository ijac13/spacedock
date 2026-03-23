---
title: Design a pattern for pilots that interact directly with the captain
status: backlog
source: testflight-005
started:
completed:
verdict:
score: 0.50
worktree:
---

A pilot dispatched as a team agent (via the Agent tool with team context) can only communicate with the team lead — its output goes to the first officer, not directly to CL. This makes collaborative work like brainstorming, design review, or clarification-heavy tasks awkward. The first officer has to relay messages back and forth.

Workarounds observed:
- First officer relays messages manually (slow, lossy)
- Dispatch as a non-team agent (loses team coordination)

This needs a deliberate pattern for when a pilot's work requires direct human interaction. The solution may involve dispatch mode selection (team vs solo), or a different communication channel, or accepting that some work shouldn't go through the first officer at all.
