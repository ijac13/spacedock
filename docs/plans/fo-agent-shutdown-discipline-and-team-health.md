---
id: 199
title: "FO agent-shutdown discipline + general claude-team health subcommand"
status: backlog
source: "session 2026-04-18 self-diagnosis — FO accumulated 9 zombie ensigns across the session because the merge-and-cleanup contract is git-centric and silent on agent shutdown. Captain initiated a manual team sweep; FO shut down 9/9 in one batch but the discipline gap remains a recurring failure mode under multi-PR load."
started:
completed:
verdict:
score: 0.65
worktree:
issue:
pr:
mod-block:
---

## Why this matters

During the 2026-04-18 session, the FO juggled 4 PRs and ~6 entities concurrently. By mid-session the team had 11 ensigns alive — 9 of them were zombies whose entity had merged or whose stage had advanced past their stamped role. The captain caught this via a manual team sweep and asked "why so many idle ensigns".

Root causes (per the session's self-diagnosis):

1. **Merge-and-Cleanup contract is git-centric.** The shared-core enumerates `git worktree remove`, `git branch -d`, archive move, frontmatter clear. It does NOT name "shutdown_request the worker." The FO followed the contract diligently — the contract itself was incomplete.
2. **Auto-advance fresh-dispatch path drops the consequence.** The contract says "if fresh dispatch: shut down the agent." The FO tracked reusability via `claude-team context-budget` but never wrote the no-reuse-case shutdown back into the dispatch chain.
3. **Feedback-to keep-alive forgot its expiration.** The FO correctly kept impl ensigns alive while validation could route back. After validation PASSED, the kept-alive agent was never explicitly shut down.
4. **Idle notifications are signal-as-noise.** The IDLE HALLUCINATION GUARDRAIL tells the FO to ignore repeated idle pings. So idle is not a prompt — there's no event-driven "this agent is idle AND its entity merged" alert.
5. **Lifecycle state is ephemeral, entity state is durable.** Entity state lives in git+status (cross-session). Agent state lives in working memory. Under context pressure with multiple PRs, the agent half fades.
6. **No mechanism enforcement.** `status --set` and `status --archive` enforce mod-block invariants. There's no analogous guard preventing terminal advancement while a stamped agent is still alive.

## Proposed approach

Two coordinated changes:

### Part A — Update the FO contract (prose-only)

Add explicit `SendMessage(to=..., shutdown_request)` steps to:

- **Merge-and-Cleanup section** (`first-officer-shared-core.md`): after archive completes, shutdown_request the most recent stage worker for the merged entity.
- **Auto-advance fresh-dispatch path** ("If reuse / If fresh dispatch" branch): when fresh-dispatching the next stage, shutdown_request the previous-stage worker before building the new dispatch.
- **Gate-approval handler** ("If the captain approves and the next stage is not terminal"): shutdown the kept-alive feedback-to target when the next stage doesn't need it. (The contract already mentions this in the runtime adapter's gate flow — promote it to the shared-core for visibility.)

The shape is the same in all three places: read the worker name from the entity's stamped `agent:` field (added by #112 — see cross-references), call SendMessage with shutdown_request, do not block on the response (cooperative shutdown is best-effort).

### Part B — Add `claude-team health` subcommand

A general-purpose health-introspection command, NOT specifically a "sweep" verb. The output is structured data the FO (or the captain) can consume in multiple ways. The verb is `health`; the consumers can be auto-shutdown, captain reports, or future tooling.

Concrete shape:

```
claude-team health --workflow-dir <wd> [--team <name>] [--format=text|json]
```

Output dimensions per team member:
- `name` — agent name as stored in team config
- `agent_type` — subagent_type
- `stamped_entity` — slug of the entity whose dispatch named this agent (from entity frontmatter `agent:` stamp; null if no stamp found)
- `stamped_stage` — stage suffix encoded in the agent name (e.g., `-implementation`, `-validation`)
- `current_entity_status` — current `status` field of the stamped entity (null if entity archived)
- `current_entity_archived` — bool (true if entity is in `_archive/`)
- `lifecycle_state` — derived enum: `active` (stage matches current), `kept_alive_for_feedback` (stamped stage is fed-back-to from current stage), `zombie_archived` (entity archived), `zombie_advanced` (entity at later stage and not kept-alive), `standing` (mod-declared standing teammate), `unstamped` (no entity link)
- `recommendation` — derived enum: `keep`, `shutdown`, `respawn`, `none`

The FO can pipe this output into a follow-up sweep loop, render it for the captain, or simply emit warnings at boot.

This is **NOT** a single-purpose "sweep" verb. The data is the deliverable; the actions are the consumer's choice. Compose it freely with `--auto-shutdown` if a one-shot sweep ergonomic is needed later.

## Acceptance criteria

**AC-1 — Merge-and-Cleanup contract names worker shutdown.**
Verified by: `grep -n 'SendMessage.*shutdown_request' skills/first-officer/references/first-officer-shared-core.md` returns ≥1 match in the `## Merge and Cleanup` section.

**AC-2 — Auto-advance fresh-dispatch path names worker shutdown.**
Verified by: `grep -n 'shutdown' skills/first-officer/references/first-officer-shared-core.md` shows a hit in the `## Completion and Gates` section's "If fresh dispatch" branch.

**AC-3 — Gate-approval handler names kept-alive shutdown.**
Verified by: the captain-approval branch in `## Completion and Gates` explicitly says "shut down kept-alive feedback-to target if next stage does not need it" (or equivalent).

**AC-4 — `claude-team health` subcommand exists and emits structured output.**
Verified by: `claude-team health --help` lists the subcommand with the documented flags; `claude-team health --workflow-dir <wd> --format=json` outputs valid JSON with the documented per-member fields.

**AC-5 — Health output classifies zombies correctly on a synthetic test.**
Verified by: a static test in `tests/test_claude_team.py` constructs a fixture team + workflow with known zombie agents and asserts the `lifecycle_state` field returns `zombie_archived` / `zombie_advanced` for the seeded zombies.

**AC-6 — Static suite green post-merge.**
Verified by: `make test-static` passes on main after the implementation lands.

## Test plan

- **Static, primary:** AC-1/AC-2/AC-3 are grep checks against shared-core. AC-4/AC-5 are static tests in `tests/test_claude_team.py` (extending the existing harness from #164).
- **Behavioral, optional:** one local FO dispatch on a trivial fixture that completes one full lifecycle (dispatch → completion → merge) and asserts `claude-team health` reports zero zombies after the FO's shutdown step. ~$1, deferrable.
- **Cost estimate:** ~$1-2 if the optional behavioral check runs; otherwise $0.

## Out of scope

- The agent-stamp on entity frontmatter (`agent:` field) — that lives in #112 (multi-player claim semantics) where the broader claim-vs-worktree-vs-branch separation is being designed. This task assumes the stamp exists; if #112 hasn't shipped yet, defer this task or land a minimal stamp shim.
- Auto-shutdown-on-idle (a periodic FO event-loop sweep). Decoupled — the health command is the data source; auto-shutdown is one of several possible consumers and can ship in a follow-up.
- Mechanism guards at `status --archive` time (refuse archival while stamped agent alive). Belt-and-suspenders; defer until contract update + health command prove insufficient on their own.

## Cross-references

- **#112** — multi-player claim semantics. Owns the `agent:` stamp on entity frontmatter. AC-4/AC-5 here depend on that stamp existing.
- **#143** — `claude-team health subcommand` (already in backlog). May overlap; check before implementing. Likely candidates: this task absorbs #143 or vice versa, depending on which scope is broader.
- 2026-04-18 session debrief (when written) — captures the zombie-sweep observation and the self-diagnosis output.
