---
id: 149
title: "FO runtime: fail-early team-infrastructure defense (rules 1, 2, 4 of team-fragility issue)"
status: backlog
source: "CL direction during 2026-04-14 session from /tmp/2026-04-14-team-fragility-issue.md"
started:
completed:
verdict:
score: 0.82
worktree:
issue:
pr:
---

The Claude Code `Agent`/`Team*` tooling has compounding bugs that cause the FO to spawn untracked zombie ensigns and duplicate work whenever a session is interrupted (rate-limit re-auth, long idle at a gate, or any event that desyncs the in-memory team registry). Upstream: anthropics/claude-code #45683, #36806, #35355, #25131.

The 2026-04-14 Discovery Outreach session evidence:

- `test -f ~/.claude/teams/{team}/config.json` returned OK after rate-limit + re-auth
- `Agent(team_name=...)` returned "Team does not exist" — but the agent process spawned anyway
- Retries compounded the zombie count; one zombie completed work and committed to main without FO coordination
- `TeamDelete` "succeeded" but didn't clear session in-memory contamination

## Scope — robustness and fail-early, no ledger

CL direction: focus on robustness and failing early rather than building our own agent-tracking infrastructure. Rules 1, 2, and 4 from the team-fragility issue are in scope. Rule 3 (session-memory agent ledger) is deferred — we accept that zombies exist and rely on git history / UI surfacing rather than building tracking.

### Rule 1 — Remove the useless `test -f config.json` health check from normal dispatch flow

**Problem:** The filesystem probe before each dispatch batch passes even when the in-memory team registry is invalidated. Guaranteed false-positive after rate-limit-then-reauth and #36806 contamination scenarios.

**Fix:** Remove the check from `claude-first-officer-runtime.md`'s normal pre-dispatch path. Keep the filesystem probe only as a startup sanity check when picking up an orphan worktree or deciding if a team directory was externally mutated.

### Rule 2 — Treat "Team does not exist" as terminal; never retry to the same name

**Problem:** The current shared-core recovery procedure calls `TeamDelete` then `TeamCreate` (same or new name). In practice the retry re-contaminates and re-zombifies per #36806.

**Fix:** On the first "Team does not exist" error (or equivalent registry-desync signal), stop dispatching to that team name for the rest of the session. Options in priority order:

1. `TeamCreate` with a fresh, uniquely-suffixed name (e.g. `{workflow}-{YYYYMMDD-HHMM}-{shortuuid}`). Ignore any returned rename — the new name is whatever TeamCreate gives back. Re-dispatch in-flight entity work from checkpoint state (the entity frontmatter is authoritative).
2. Fall back to bare mode (Rule 4).
3. Surface to captain with a clear recovery prompt. Do not silently retry.

Retry-same-name is banned.

### Rule 4 — First-class bare-mode fallback with explicit mid-session transition

**Problem:** The runtime adapter treats bare mode as the startup default when ToolSearch can't find `TeamCreate`, but mid-session fallback is vague.

**Fix:** Define an explicit "degraded mode" transition in `claude-first-officer-runtime.md`:

- **Trigger:** any of {first "Team does not exist" error, 2+ dispatch failures inside a 5-minute window, captain command `/spacedock bare`}.
- **Effect:** FO stops using `team_name` on Agent dispatches for the rest of the session. Reuse-via-SendMessage is no longer available; every stage dispatches fresh and blocks until completion.
- **Report to captain:** "Falling back to bare mode for the remainder of this session due to team-infrastructure failure. Prior team agents are presumed-zombified; I will not route work to them or through the team registry."
- **On degrade:** attempt cooperative shutdown of every known agent name once, then assume at least some won't respond and move on.

`claude-team build` already accepts `bare_mode: true` — the prose just needs to tell the FO when to flip it.

### Uniquely-suffixed TeamCreate names (from Rule 6, folded into Rule 2)

The fragility issue's Rule 6 says TeamCreate requests should include a uniqueness suffix. This is a prerequisite for Rule 2 option 1 (fresh-suffixed TeamCreate). Fold it into the implementation of Rule 2:

- Always request `{project_name}-{dir_basename}-{YYYYMMDD-HHMM}` or similar unique name
- Always store and use the actual returned `team_name` from TeamCreate (it may rename)

## Deferred (not this task)

- **Rule 3 — Agent ledger** (CL declined; focus on robustness/fail-early, not tracking)
- **Rule 5 — Prior-session zombie awareness**
- **Rule 6 — Defensive naming** (folded into Rule 2 above)
- **Rule 7 — Operator docs for re-auth gotcha** (can be a small doc update task later)
- **Rule 8 — Nuclear mitigation hook** (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=0`)

## Acceptance criteria (provisional — finalize in ideation)

1. `claude-first-officer-runtime.md` has the `test -f config.json` check removed from the dispatch adapter's pre-dispatch flow (Rule 1).
2. `claude-first-officer-runtime.md` has updated recovery prose that treats "Team does not exist" as terminal — no retry-to-same-name path (Rule 2).
3. `claude-first-officer-runtime.md` has an explicit "Degraded Mode" section with triggers, effect, and captain-facing report template (Rule 4).
4. TeamCreate invocation includes a uniqueness suffix (Rule 6 subset).
5. Static tests assert the new prose structure exists and the old retry-same-name language is gone.
6. Optional: one E2E test that simulates a dispatch failure and observes the FO follows the new rules without spawning zombies via retry.

## Out of scope

- Fixing any upstream Claude Code bugs. This is defense-in-depth on top of them.
- Changing Spacedock core state model (entity frontmatter, worktrees, stages stay as they are).
- OS-level zombie reaping.

## Related

- `/tmp/2026-04-14-team-fragility-issue.md` — full context document
- Session debrief for 2026-04-14 Discovery Outreach (to be written)
- anthropics/claude-code#45683, #36806, #35355, #25131 — upstream bugs
- #120 (merged) — structured dispatch helper provides deterministic `name` derivation and `bare_mode` input flag; this task builds on that
- #114 (in flight) — mod-block enforcement; adjacent runtime-enforcement mechanism
