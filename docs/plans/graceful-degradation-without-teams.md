---
id: 033
title: First-officer graceful degradation without agent teams
status: ideation
source: testflight sd11-test observation
started: 2026-03-28T00:00:00Z
completed:
verdict:
score: 0.80
worktree:
---

The generated first-officer requires CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 (research preview, v2.1.32+). Without teams, TeamCreate and SendMessage don't exist, so the first-officer's current dispatch pattern fails at startup step 1.

## Findings from sd11-test

- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=0` disabled teams for `claude -p` commission (no TeamCreate/Agent/SendMessage in tool calls)
- But `claude -p --agent first-officer` still had teams available — the env var may not propagate to agent mode, or agent mode enables teams automatically
- The commission skill itself doesn't need teams (it's file generation + Bash)
- The first-officer needs teams for: TeamCreate (step 1), Agent with team_name (dispatch), SendMessage (shutdown_request, redo feedback)

## What works without teams (from release notes)

- Agent() tool exists as parent-child subagent dispatch (v1.0.60+)
- Subagent output returns to parent context when the subagent completes
- `isolation: "worktree"` works without teams (v2.1.49)
- Background agents work without teams (v2.0.60)

## Degraded mode design

Without teams, the first-officer could still function:

1. Skip TeamCreate entirely (no team to create)
2. Dispatch ensigns via Agent() WITHOUT team_name — ensign runs as a subagent, output returns to first-officer context when done
3. No SendMessage for completion — the first-officer sees the ensign's output directly when the Agent() call returns
4. No SendMessage for shutdown — ensign exits naturally when its Agent() call completes
5. No SendMessage for redo — dispatch a new Agent() with feedback appended to the prompt

The trade-off: without teams, ensigns can't run in parallel. Each Agent() call blocks until the ensign completes. The first-officer processes one entity at a time instead of dispatching multiple ensigns and handling completion messages asynchronously.

## What needs to change

### Approach: Disable teams by default, no runtime detection

The captain's direction: rather than detecting teams at runtime and branching, just disable teams via env so the first-officer template works without teams from the start. This avoids conditional logic in the template entirely.

### Evidence: existing env override

The project already has an env override mechanism. In `~/.claude/settings.json`:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

This global setting is what currently enables teams. The same `env` key works in project-level `.claude/settings.local.json`. A commissioned project can set `"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "0"` to guarantee teams are off, overriding the user's global setting.

### What the first-officer template needs without teams

The template currently uses three team-dependent tools:

1. **`TeamCreate` (Startup step 3)** — Remove entirely. No team to create.
2. **`team_name` in Agent() dispatch** — Remove the `team_name` parameter. Agent() without `team_name` runs the ensign as a child subagent whose output returns to the first-officer when it completes.
3. **`SendMessage` (ensign completion, feedback flow, redo)** — Replace with direct return. Without teams, the ensign's output returns to the FO when Agent() completes. No explicit messaging needed.

The ensign template also uses `SendMessage(to="team-lead")` in two places:
- Completion protocol: "Send a minimal completion message" — becomes unnecessary since Agent() return delivers output to parent.
- Clarification: "ask for clarification via SendMessage(to='team-lead')" — needs an alternative. Without teams, the ensign can't message the FO. Options: (a) the ensign includes questions in its stage report and the FO reads them on return, or (b) we accept that clarification is fire-and-forget in non-team mode.

### Template changes needed

**first-officer.md:**
- Remove Startup step 3 (TeamCreate) entirely, renumber subsequent steps
- Remove `team_name="{project_name}-{dir_basename}"` from Agent() dispatch call
- Remove all `SendMessage` references in Completion and Gates / Feedback Rejection Flow sections
- Rewrite completion detection: instead of "When a dispatched agent sends its completion message" → "When Agent() returns" (the subagent's output is the completion signal)
- Rewrite feedback flow: instead of SendMessage between agents, dispatch a new Agent() with feedback in the prompt

**ensign.md:**
- Remove `SendMessage(to="team-lead", message="Done: ...")` from Completion Protocol — the Agent() return is the completion signal
- Change `SendMessage(to="team-lead")` for clarification → include questions in stage report output (the FO reads this on Agent() return)
- Remove the SendMessage instruction from Rules section

**commission SKILL.md Phase 3:**
- Already works without teams — the commission skill acts as FO directly and dispatches via Agent()
- No changes needed here

**Project settings (optional):**
- Commission could generate `.claude/settings.local.json` with `"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "0"` in the `env` block
- This guarantees teams are off even if the user has them globally enabled
- However, this may be unnecessary if the template simply doesn't reference team tools — the tools just won't be present, and the template won't try to use them

### Trade-offs

**What breaks:**
- Parallel dispatch. With teams, the FO can dispatch multiple ensigns and they run concurrently. Without teams, each Agent() call blocks until the ensign returns. Entities are processed sequentially.
- Inter-agent communication. The feedback flow (reviewer ↔ implementer SendMessage loop) can't work. Instead, the FO would dispatch implementer, read findings, dispatch reviewer, read findings, dispatch implementer with feedback, etc. Each round-trip is a separate Agent() call.
- Ensign clarification requests. The ensign can't message the FO mid-task. It must include questions in its output and the FO reads them after.

**What works:**
- All core dispatch: Agent() with subagent_type works (v1.0.60+)
- Worktree isolation: works without teams (v2.1.49)
- Stage progression, state management, gates, merge — all FO-local operations, no team tools needed
- Mods — execute in FO context, no team dependency

**What improves:**
- Works for all Claude Code users, not just those with experimental teams enabled
- Simpler template — no TeamCreate boilerplate, no stale team cleanup
- More predictable execution — sequential means the FO always knows exactly what's happening

### Acceptance criteria

1. The first-officer template (`templates/first-officer.md`) contains zero references to `TeamCreate`, `team_name`, or `SendMessage`
2. The ensign template (`templates/ensign.md`) contains zero references to `SendMessage`
3. A commissioned workflow runs successfully with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=0` (or unset)
4. Agent dispatch uses `Agent(subagent_type="{agent}", name="{agent}-{slug}-{stage}", prompt="...")` without `team_name`
5. The FO reads ensign output from Agent() return value instead of waiting for SendMessage
6. Feedback flow works via sequential Agent() dispatch (FO dispatches implementer, then reviewer, then implementer with feedback if rejected)
7. Existing worktree, gate, merge, mod, and orphan-detection logic works unchanged

### Open questions (resolved)

- **Should we set env in project settings.local.json?** Probably not needed — if the template doesn't use team tools, it doesn't matter whether teams are enabled. The template simply won't call TeamCreate/SendMessage. Setting env would be a belt-and-suspenders measure. Decision: skip it for now, add later if needed.
- **What about users who DO want parallel dispatch?** That's a future enhancement (teams mode). The v0 spec already says "shuttle-only (one pilot agent)" — sequential dispatch is the v0 design. Teams can be added as a v1 upgrade path.

## Stage Report: ideation

- [x] Problem statement clarified with evidence from the codebase (settings.json env config)
  `~/.claude/settings.json` line 4: `"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"` — the global env override that enables teams. Project-level `.claude/settings.local.json` supports the same `env` key.
- [x] Proposed approach: how to disable teams via env override and what template changes follow
  Remove all TeamCreate/team_name/SendMessage from first-officer and ensign templates. Agent() without team_name returns output to parent. No env override needed if templates don't reference team tools — but available as belt-and-suspenders via project settings.local.json.
- [x] Edge cases considered (what breaks, what works, parallel dispatch tradeoff)
  Parallel dispatch lost (sequential Agent() calls), inter-agent messaging lost (feedback becomes sequential dispatch rounds), ensign clarification becomes post-hoc (questions in output). Core dispatch, worktrees, gates, merge, mods all work unchanged.
- [x] Acceptance criteria defined — testable conditions for "done"
  Seven criteria: zero team tool references in templates, successful run with teams disabled, Agent() without team_name, FO reads return value, sequential feedback flow, existing logic unchanged.

### Summary

Investigated the existing env override in `~/.claude/settings.json` and mapped all team-dependent tool usage in the first-officer and ensign templates. The approach is to remove all team tool references (TeamCreate, team_name, SendMessage) rather than adding runtime detection. This aligns with v0's shuttle-only design — sequential dispatch via Agent() without team_name is the baseline. Parallel dispatch via teams becomes a future upgrade path, not a degradation target.
