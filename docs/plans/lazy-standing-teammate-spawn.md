---
id: 172
title: "Lazy-spawn standing teammates on first routing, not at boot"
status: backlog
source: "CL directive during 2026-04-16 session — eager comm-officer spawn adds a sonnet Agent() cold-start to every boot even when no polish is requested"
started:
completed:
verdict:
score: 0.65
worktree:
issue:
pr:
---

## Problem Statement

The Claude FO runtime adapter (`claude-first-officer-runtime.md` lines 34-43) mandates that standing teammates be spawned eagerly — after `TeamCreate` succeeds and before the normal dispatch event loop begins. Every FO session therefore pays one `Agent()` cold-start per standing teammate at boot, regardless of whether any dispatched ensign or the FO itself ever routes work to that teammate.

In the current workflow, the only standing teammate is `comm-officer` (sonnet). Its cold-start adds wallclock time and token cost to every session boot. In sessions where no polish is requested — a quick task-filing session, a pure gate-review session, or a session that dispatches only bare-mode entities — this cost is pure waste.

## Observed cost (2026-04-16 session)

The comm-officer was spawned at boot. Its first actual polish request arrived roughly 20 minutes later (when #167's task body was routed for polish-and-write). In the intervening time it sat idle, having consumed one `Agent()` spawn round-trip plus its ToolSearch probe and online notification — all before the FO had dispatched its first ensign.

## Current design rationale (from the runtime adapter)

The eager-spawn design exists for three reasons documented in the adapter:

1. **first-boot-wins lifecycle** — early name-binding so the teammate's slot is claimed before a second workflow in the same captain session might spawn its own instance.
2. **Message queueing** — Claude Code queues `SendMessage` to an agent that exists but has not completed its first turn yet. If the teammate does not exist at all, the message fails.
3. **Amortized cost** — spawn cost is paid once and amortized across all polish requests in the session.

Reasons (1) and (3) remain valid for long sessions with heavy polish traffic. Reason (2) is the hard constraint: if we defer spawn until first routing, the first `SendMessage` will fail because the teammate does not exist yet.

## Proposed direction

Lazy spawn by default: defer `Agent()` for each standing teammate until the first `SendMessage` is about to be sent to it. The FO (or the ensign) checks whether the teammate exists before routing; if absent, spawns it, waits for the name to register, then sends the message. Subsequent routes to the same teammate hit the live member with no extra cost.

## Open questions for ideation

- How does the FO or ensign detect "teammate doesn't exist yet"? Options: (a) check team config members list, (b) try `SendMessage` and catch the failure, (c) maintain a session-memory set of spawned names.
- Does `SendMessage` to a non-existent teammate fail gracefully (returnable error) or hard-fail (tool error the model must recover from)? If (b), is the recovery path reliable enough for production?
- First-boot-wins under lazy spawn: if two workflows share a team and both try to lazy-spawn the same teammate on their first route, one will race. The eager design avoids this because boot is sequential. Does lazy spawn need a mutex, or is the race benign (first spawn wins, second detects `already-alive`)?
- Should lazy spawn be the default for all standing teammates, or configurable per mod (e.g., `eager: true` in `_mods/` frontmatter for teammates that benefit from warm-start)?
- What changes in the runtime adapter prose? The "Standing teammate spawn pass" section would become a "Standing teammate lazy-spawn protocol" section. `claude-team list-standing` still runs at boot to discover available teammates, but `claude-team spawn-standing` defers to first use.
- Does this interact with the dispatch-prompt `### Standing teammates available in your team` section (#166)? Today that section is populated from `enumerate_alive_standing_teammates`, which checks `member_exists`. Under lazy spawn, the teammate will not be alive at dispatch time. The section would need to enumerate *declared* teammates (from `list-standing`), not *alive* ones.

## Out of Scope

- Changing the standing-teammate mod schema.
- Removing the eager-spawn option entirely — some teammates may benefit from warm-start.
- Codex runtime equivalents.
