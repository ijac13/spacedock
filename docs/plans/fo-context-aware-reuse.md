---
id: 121
title: FO should respawn fresh ensign when kept-alive context > 60%
status: backlog
source: CL directive after 116 cycle-2 impl ensign died at ~80% context without completing cycle-2 feedback
score: 0.75
---

Kept-alive ensigns (feedback-to keepalive, reuse across stages) can run out of context mid-cycle and die silently, losing uncommitted work. This happened during task 116 cycle-2: the kept-alive implementation ensign was at 80.7% of 200k (155 turns) when the FO routed cycle-2 feedback to it. The ensign consumed enough additional context during the cycle-2 rewrite to hit the 200k ceiling and died mid-turn. It left +43/-53 lines of uncommitted README.md changes in the worktree, never sent a completion signal, and never escalated — the FO had explicitly warned "escalate if you hit a context wall" but the ensign just died without self-reporting.

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

1. Add a **"context budget check"** step to `skills/first-officer/references/first-officer-shared-core.md` in the Dispatch and Feedback Rejection Flow sections.
2. Document the model-to-context mapping in `skills/first-officer/references/claude-first-officer-runtime.md`.
3. Fresh-dispatch template must include a recovery-from-uncommitted-work clause.
4. Static assertion in `tests/test_agent_content.py` that the new rule text is present in the assembled FO content.

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
4. `tests/test_agent_content.py` has a new assertion covering the three points above.
   - Test: the new test passes on the fix commit and fails on the parent commit.
5. Existing suites stay green.
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
