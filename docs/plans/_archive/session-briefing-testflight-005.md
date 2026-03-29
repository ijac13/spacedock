---
id: 032
title: Session Briefing — Testflight 005
status: done
source: testflight-005
started:
completed: 2026-03-29T04:15:00Z
verdict: PASSED
score: 0.30
worktree:
---

Briefing from testflight-005 session for the ship's counselor. These are learnings, process gaps, and potential backlog items discovered during the session.

## What Was Accomplished

Closed 4 entities (first-officer-dispatch-bug, relative-paths-in-generated-configs, commission-usability-improvements, deterministic-test-harness). Advanced clarification-protocol and captain-address through implementation and validation. Applied multiple hotfixes directly to main.

## Learnings and Issues to Address

### 1. First Officer Dispatch Failures — Multiple Root Causes

We discovered and fixed 4 distinct dispatch bugs in a single entity, each requiring its own guardrail:

- **Wrong subagent_type**: first officer clones itself instead of spawning general-purpose pilots
- **SendMessage instead of Agent**: first officer sends messages to non-existent teammates
- **Team lifecycle**: no TeamCreate in startup, commission passes team_name creating ownership confusion
- **Report spam**: first officer re-reports status while blocked at approval gates

**Takeaway**: Agents need explicit negative guardrails ("NEVER do X"), not just positive examples ("do Y"). The template's code block with unfilled `{variables}` reads as pseudocode, not as a tool invocation directive. Every observed failure was the agent finding a plausible alternative to the intended tool call.

### 2. Ideation Should Not Use Worktrees

Ideation only modifies entity markdown — no code to isolate. Worktrees created for ideation become orphans when sessions crash. Fixed locally in first-officer.md and filed as `ideation-on-main.md` for the broader fix (stage-specific worktree requirements in pipeline schema).

### 3. Parallel Implementation Creates Merge Debt

Three entities (#1, #2, #3) all modified SKILL.md concurrently. Each branch was created from the same base, so later merges carried stale versions of earlier fixes. Auto-merge worked but required manual verification that guardrails survived. Added a conflict check to the dispatch gate: warn CL and propose combining when entities touch the same files.

### 4. Test Harness Catches Template Regressions But Not Runtime Failures

The batch-mode commission test (`v0/test-commission.sh`) verifies generated output has correct structure and guardrails. All 30 checks passed. But a separate testflight showed the first officer still failing to dispatch — the template was correct, the agent ignored its own instructions. Static validation has a ceiling.

### 5. Test Harness Has Path and False Positive Issues

Running the test harness against the captain-address branch produced 8 failures:
- `first-officer.md` not found — the test expects it at `v0-test-1/.claude/agents/first-officer.md` but the commission may place it at the project root's `.claude/agents/`
- `{slug}` in README File Naming section flagged as leaked template variable — this is intentional documentation, not a leak
- README missing 'Scoring' section — may be a generation variance or the check is too strict

These need investigation and fixes to the test script.

### 6. Validation Pilots Should Run the Test Harness

The README says "Use the test harness for any entity that changes SKILL.md." But validation pilots did code review only — they didn't run the script. Either:
- The validation pilot prompt should explicitly say "run v0/test-commission.sh"
- Or the first officer should dispatch a separate test-runner after validation

### 7. Team Agent Architecture Limits Direct User Interaction

A pilot dispatched as a team agent can't brainstorm directly with CL — its output goes to the team lead, not the user. Workaround: relay messages, or dispatch as a non-team agent. This needs a better pattern for interactive/collaborative work.

### 8. Concurrency Limits Not Enforced by Tooling

Added "max 2 per stage" to the README, but it's honor-system — the first officer reads it and self-enforces. No tooling prevents dispatching a 3rd entity into the same stage.

### 9. The First Officer Should Not Run Tests Directly

The first officer is a dispatcher, not a worker. Running tests itself violates the dispatch principle. Tests should be delegated to a pilot or a dedicated test-runner agent.

## Potential Backlog Items

1. **Fix test harness path issues** — first-officer.md location, `{slug}` false positive, Scoring section check
2. **Validation pilots must run test harness** — update pilot prompt or dispatch procedure for SKILL.md changes
3. **Stage-specific worktree requirements** (already filed as `ideation-on-main.md`)
4. **Interactive pilot pattern** — design a pattern for pilots that need to work directly with CL
5. **Test harness for runtime behavior** — end-to-end test that commissions + launches first-officer + verifies dispatch actually works
6. **Concurrency enforcement in status script** — status script or dispatch tooling that warns/blocks when stage limits are exceeded
