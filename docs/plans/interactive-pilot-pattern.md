---
title: Design a pattern for pilots that interact directly with the captain
status: ideation
source: testflight-005
started: 2026-03-24T00:00:00Z
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

## Problem Statement

The Claude Code Agent tool's team model has a fixed communication topology: ensigns dispatched with `team_name` can only `SendMessage` to named teammates (primarily "team-lead", the first officer). Their plain text output is not visible to the captain — it exists only in the ensign's own context. The captain sees the first officer's context.

This creates three categories of work with different interaction needs:

1. **Autonomous work** (implementation, validation) — Ensign reads entity, does work, reports completion. Current pattern works well. The ensign doesn't need CL except for occasional clarification (handled by the existing clarification protocol).

2. **Lightly interactive work** (ideation with clear scope) — Ensign may need one or two clarifications. The relay through the first officer is tolerable. Current clarification protocol covers this adequately.

3. **Heavily interactive work** (brainstorming, design review, open-ended exploration) — Multiple rounds of back-and-forth where context and nuance matter. The first officer relay is slow, lossy, and awkward. Each exchange requires: ensign → SendMessage → first officer reads → first officer relays to CL → CL responds → first officer relays back → ensign reads. The first officer paraphrases and may lose important context.

Category 3 is the gap. Examples from testflight-005:
- Designing the clarification protocol itself required brainstorming with CL about when agents should stop vs. guess
- Design review of generated templates where CL wants to point at specific lines and discuss alternatives
- Exploratory ideation where the scope isn't yet known and the ensign needs to co-discover it with CL

## Constraints

1. **Agent tool limitation**: The `Agent()` tool dispatches a subagent. When `team_name` is provided, the subagent joins a team and can only communicate via `SendMessage`. There is no "talk directly to the user" capability from within a team agent.

2. **No team_name = no coordination**: If an ensign is dispatched without `team_name`, it runs as a standalone subagent. It can produce output the captain sees (since it's in the first officer's context), but the first officer can't send it messages, check on it, or coordinate with it. It's fire-and-forget.

3. **First officer is the bottleneck**: The first officer is the only agent that talks to both the captain and the ensigns. All cross-boundary communication goes through it.

4. **Pipeline state lives on main**: The first officer owns frontmatter. Any ensign doing interactive work on main still needs the first officer to advance its status when done.

## Proposed Approach: Solo Dispatch Mode

Add a **solo dispatch mode** where the first officer dispatches an ensign without `team_name`. The ensign runs as a direct subagent of the first officer, meaning its output appears in the first officer's context — which CL sees directly.

### How it works

1. **Stage property**: Add an optional `Interactive: Yes` property to stage definitions in the README. Stages that involve collaborative work with the captain declare this.

2. **Dispatch variant**: When the first officer encounters a stage with `Interactive: Yes`, it dispatches the ensign WITHOUT `team_name`:

```
Agent(
    subagent_type="general-purpose",
    name="ensign-{slug}",
    prompt="You are working on: {entity title}\n\n..."
)
```

Without `team_name`, the ensign's output goes directly to the first officer's context, which the captain sees. The ensign can ask questions, propose ideas, and receive feedback naturally — CL types responses that appear in the first officer's context, and the ensign reads them.

3. **Tradeoff**: The ensign loses team messaging (can't `SendMessage` to the first officer). But since the captain is the audience for interactive work, this is the right tradeoff. The ensign's output IS the deliverable — it's a conversation with the captain, not a report to the first officer.

4. **Completion**: When the solo ensign finishes, control returns to the first officer, which advances frontmatter and resumes the pipeline.

### Why not relay optimization instead?

An alternative would be to make the first officer a better relay (structured message format, verbatim forwarding, etc.). But this treats the symptom. The fundamental issue is that team agents can't address the user. Making the relay faster doesn't fix the lossy, awkward interaction pattern. Solo dispatch acknowledges that some work belongs in the captain's context, not the team's.

### Why not dispatch all ensigns as solo?

Solo ensigns can't coordinate with each other or with the first officer via messaging. For parallel work (two implementations running simultaneously), team coordination matters — the first officer needs to track which ensigns are active and handle their completion messages. Solo dispatch is a targeted tool for stages that need captain interaction, not a replacement for the team pattern.

### What about worktrees?

Solo ensigns can still work in worktrees. The first officer creates the worktree before dispatching, and the ensign prompt specifies the worktree path as its working directory. The only difference is the absence of `team_name`.

However, interactive stages (brainstorming, ideation) typically don't need worktrees — they modify entity markdown on main. The combination of `Interactive: Yes` + `Worktree: Yes` would be unusual but not prohibited.

## Scope

Changes needed:

1. **README schema** — Document `Interactive` as an optional stage property (alongside `Worktree` and `Approval gate`).

2. **SKILL.md first-officer template** — Add a "Solo dispatch" section under Dispatching that handles `Interactive: Yes` stages. The ensign prompt for solo dispatch omits `SendMessage` instructions and instead tells the ensign it's working directly with the captain.

3. **SKILL.md commission generation** — When generating stage definitions, the commission skill should ask or infer which stages are interactive. Default: no stages are interactive. Ideation stages in pipelines with design-heavy missions might default to interactive.

4. **Reference doc** (`agents/first-officer.md`) — Update with the solo dispatch pattern.

5. **Generated first-officer** (`.claude/agents/first-officer.md`) — The template already branches on `Worktree: Yes/No`. Add a third branch for `Interactive: Yes`.

## What "Done" Looks Like

- The first officer can dispatch ensigns in two modes: team (current) and solo (new)
- Solo ensigns interact directly with CL — no relay through the first officer
- Stage definitions declare `Interactive: Yes` to opt into solo dispatch
- The pipeline still works end-to-end: solo ensigns complete, first officer advances frontmatter, next stage dispatches
- The pattern is documented in the generated first-officer template so all commissioned pipelines get it

## Acceptance Criteria

- [ ] Pipeline README schema supports `Interactive: Yes/No` as an optional stage property
- [ ] First-officer template in SKILL.md includes solo dispatch logic for interactive stages
- [ ] Solo ensign prompt omits team messaging instructions and tells the ensign it works directly with the captain
- [ ] First officer correctly handles solo ensign completion (no SendMessage to wait for — control returns naturally)
- [ ] Commission skill generates `Interactive` property in stage definitions when appropriate
- [ ] Reference doc (`agents/first-officer.md`) documents the solo dispatch pattern
- [ ] Solo dispatch works with worktree stages (ensign prompt still gets worktree path)
- [ ] Non-interactive stages continue to use team dispatch (no regression)

## Open Questions

1. **Should the commission skill ask about interactivity per stage, or infer it?** Asking adds another question to the design phase (which CL explicitly wanted to keep short — see commission-speed entity). Inference based on stage purpose (ideation = interactive, implementation = not) might be good enough. Leaning toward: infer by default, allow override in the design confirmation step.

2. **What happens if CL goes silent during a solo ensign's interactive session?** The ensign is blocking the first officer's context. Unlike team ensigns, solo ensigns don't have a timeout or a way for the first officer to intervene. This is the same as any subagent waiting for user input — it just waits. Probably fine for v0 but worth noting.

3. **Should the first officer pause other dispatches while a solo ensign is active?** A solo ensign occupies the first officer's context, so the first officer can't dispatch other team ensigns simultaneously. This effectively serializes interactive stages. This might be acceptable (interactive work wants CL's attention anyway) or might need a workaround in v1.
