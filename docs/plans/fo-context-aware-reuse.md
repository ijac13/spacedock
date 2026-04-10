---
id: 121
title: FO context-aware reuse — respawn fresh above 60%, and handle zombie dead ensigns
status: ideation
source: CL directive after 116 cycle-2 impl ensign died at ~80% context without completing cycle-2 feedback
score: 0.80
---

Two related FO runtime gaps observed during task 116 cycle 2, both about kept-alive ensign lifecycle:

**Gap 1 — context overflow from reuse.** Kept-alive ensigns (feedback-to keepalive, reuse across stages) can run out of context mid-cycle and die silently, losing uncommitted work. During 116 cycle 2: the kept-alive impl ensign was at 80.7% of 200k (155 turns) when the FO routed cycle-2 feedback. It consumed enough additional context during the cycle-2 rewrite to hit 200k and died mid-turn. It left +43/-53 lines of uncommitted README.md changes in the worktree, never sent a completion signal, and never escalated — the FO had warned "escalate if you hit a context wall" but the ensign died without self-reporting.

**Gap 2 — dead ensigns cannot be shut down.** Once an ensign has died (context overflow, tool-use error, or any other mid-turn failure), the FO has no mechanism to evict it from the team config. The documented shutdown path is `SendMessage(to=..., message={type: "shutdown_request"})`, which is cooperative — it requires the target agent to be responsive enough to process the request and approve its own shutdown. A dead agent cannot do that. The FO observed this in the 116 cycle-2 recovery: after the impl ensign died and CL confirmed the death, the FO sent a shutdown_request anyway out of reflex, which was silently dropped. The dead ensign remained listed in `~/.claude/teams/{team}/config.json` as a zombie member for the rest of the session. This bloats the team state, confuses post-dispatch verification (band-aid 1 from issue #63 still passes for the zombie, so it can't be used to detect the dead state), and violates the least-surprise principle.

The two gaps compound: because dead ensigns can't be shut down, the FO must fresh-dispatch a sibling with a distinct name (e.g., `...-cycle3`) rather than reusing the original slot. This is workable but noisy — the team config accumulates dead zombies until the session ends.

## Proposed rule

Before routing any additional work to a kept-alive ensign (feedback rejection routing OR stage reuse advancement), the first officer must:

1. Locate the ensign's subagent jsonl at `~/.claude/projects/<project>/<parent_session_id>/subagents/agent-<id>.jsonl` (lookup via the sibling `.meta.json` file's `agentType` field matching the ensign's name).
2. Extract the most recent assistant turn's `usage` block and compute **resident tokens** = `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`.
3. Compare to the model's context window × 0.6. If resident > threshold, **do not reuse** the ensign — shut it down and fresh-dispatch a new ensign for the work instead.

The **60% threshold** is CL's explicit directive. Rationale: at 60% there's enough headroom (80k+ for a 200k model) for one more substantial stage of work without hitting the limit. At 80%+, a single large feedback cycle can push past 200k.

## Model-to-context mapping (document in runtime adapter)

| Model | Context window |
|---|---|
| `claude-opus-4-6` | 200,000 |
| `claude-opus-4-6[1m]` | 1,000,000 |
| `claude-sonnet-*` | varies; document per variant |
| `claude-haiku-*` | varies |

The FO reads the team config `model` field for the ensign to look up the appropriate threshold.

## Recovery path for fresh dispatch

When the 60% check fails and the FO fresh-dispatches, the fresh ensign must be told in its dispatch prompt that the prior ensign's uncommitted worktree state is available for recovery. The fresh ensign's first action is to inspect `git status` and `git diff` in its worktree and decide whether the prior ensign's work-in-progress represents legitimate progress to commit, or should be reset and redone.

## Scope

**Gap 1 — context-aware reuse:**

1. Add a **"context budget check"** step to `skills/first-officer/references/first-officer-shared-core.md` in the Dispatch and Feedback Rejection Flow sections.
2. Document the model-to-context mapping in `skills/first-officer/references/claude-first-officer-runtime.md`.
3. Fresh-dispatch template must include a recovery-from-uncommitted-work clause.
4. Static assertion in `tests/test_agent_content.py` that the new rule text is present in the assembled FO content.

**Gap 2 — dead ensign handling:**

5. Document in `skills/first-officer/references/claude-first-officer-runtime.md` that `SendMessage(shutdown_request)` is cooperative-only and has no effect on dead/unresponsive ensigns. The FO must NOT reflexively send shutdown_request to an ensign believed to be dead — it's a no-op that creates false confidence.
6. Document the "fresh-dispatch with distinct name" recovery pattern: when an ensign is known dead, the FO dispatches a sibling with a `-cycleN` or `-fresh` suffix rather than trying to reuse the dead slot. The dead ensign's entry stays as a zombie in team config until session end; the FO must not conflate the zombie with live state.
7. Add a post-dispatch assertion note: band-aid 1 (verify new member in config) does NOT detect zombies — a zombie still passes the band-aid 1 check. The FO must track dead ensigns in session memory (or via sentinel file in the worktree) rather than relying on team config state alone.
8. Consider: if the captain or an operator signals that an ensign is dead (e.g., "the impl ensign is over and dead"), the FO should (a) NOT send shutdown_request, (b) stop routing any further work to that name, (c) fresh-dispatch under a new name, (d) optionally note the zombie in session state so it's not accidentally addressed again later.

## Out of scope

- General-purpose context monitoring / watchdog mod (that's a larger discussion from earlier in the session — the jsonl-tailing approach could become an implementation helper for this task, but the helper itself is a separate surface).
- Mid-turn context death detection (no signal from Claude Code when a subagent's turn errors from overflow; the FO can only observe the absence of a completion signal).
- Upstream change to Claude Code to expose context state directly via an Agent tool result.

## Acceptance Criteria

1. `skills/first-officer/references/first-officer-shared-core.md` has a new **context budget check** rule in the Dispatch section and the Feedback Rejection Flow section, with the 60% threshold explicit and a concrete procedure for reading the subagent jsonl.
   - Test: grep for "60%" and "resident tokens" (or equivalent phrasing) in the file returns matches in both sections.
2. `skills/first-officer/references/claude-first-officer-runtime.md` documents the model-to-context-limit mapping for at least `claude-opus-4-6` and `claude-opus-4-6[1m]`.
   - Test: grep for `200` and `1000000` (or `1M`) in the Claude runtime file.
3. When the FO decides to fresh-dispatch (either from the 60% check or any other cause), the dispatch prompt template includes a clause that tells the fresh ensign to inspect the worktree for uncommitted prior work and decide whether to preserve or reset it.
   - Test: grep for "uncommitted" or "prior ensign" in the dispatch template section of the runtime adapter.
4. `skills/first-officer/references/claude-first-officer-runtime.md` documents the dead-ensign shutdown gap: `SendMessage(shutdown_request)` is cooperative and has no effect on dead/unresponsive ensigns; the FO must NOT reflexively send it, and must fresh-dispatch under a distinct name (typically `-cycleN` or `-fresh` suffix) to recover.
   - Test: grep for "shutdown_request is cooperative" or "dead ensign" or equivalent in the Claude runtime file returns matches.
5. The same runtime file documents that band-aid 1 (post-dispatch team config membership check) does NOT detect zombies — a dead ensign still passes band-aid 1. The FO must track dead ensigns in session memory, not rely on team config state alone.
   - Test: grep for "zombie" or "does not detect" or equivalent in the band-aid 1 section of the Claude runtime file.
6. `tests/test_agent_content.py` has new assertions covering AC-1 through AC-5 above.
   - Test: the new tests pass on the fix commit and fail on the parent commit.
7. Existing suites stay green.
   - Test: `unset CLAUDECODE && uv run --with pytest python tests/test_agent_content.py -q`, `tests/test_rejection_flow.py`, `tests/test_merge_hook_guardrail.py`.

## Test Plan

- Static test for the new rule text (low cost, required).
- Adjacent E2E suites re-run to confirm no regression.
- **No new E2E test** for the 60% behavior itself — simulating the context overflow condition in a test harness is too expensive. The rule is documented behavior; compliance is verified by the static assertion + live captain observation across subsequent sessions.
- Ideation may decide whether a unit test of the jsonl-parsing logic is worth building (depends on whether the FO runtime adapter gains a helper script or stays as prose instructions).

## Open questions for ideation

1. Does the 60% rule apply to **reuse across stage advancement** in addition to feedback routing? Example: an ensign that reuses from implementation to a next-stage that is worktree-mode and not fresh. If it's at 65% at the reuse boundary, does the FO fresh-dispatch?
2. How should the FO compute "model's context window" for models not in a hardcoded mapping? Fallback rule (e.g., 200k) or hard error?
3. Does the check need to run at every turn during a long feedback round, or only at the start when routing new work? (At the start seems sufficient — mid-turn checks require the ensign to pause and report, which defeats the point.)
4. Should the FO warn the captain when it pre-emptively fresh-dispatches due to the 60% rule, or silently replace?

## Related

- Task 117 `fo-idle-guardrail-flake-on-haiku` — adjacent FO reliability issue with kept-alive ensigns
- Task 119 `fo-dispatch-phase-1-band-aids` — Phase 1 of issue #63, adjacent FO runtime reliability work
- Task 120 `build-dispatch-structured-helper` — Phase 2 of issue #63
- anthropics/claude-code (local) issue #63 — umbrella for FO dispatch reliability
- Session observation (2026-04-10): 116 cycle-2 impl ensign peaked at ~140k tokens during cycle-2 work before dying somewhere past 200k. This is the datapoint that motivates the 60% threshold — the gap between "safe to reuse" and "dead in the water" is narrower than expected.
