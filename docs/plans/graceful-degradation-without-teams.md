---
id: 033
title: First-officer graceful degradation without agent teams
status: validation
source: testflight sd11-test observation
started: 2026-03-28T00:00:00Z
completed:
verdict:
score: 0.80
worktree: .worktrees/ensign-033-graceful-degradation
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

## Experiment: Commission auto-run with teams disabled

### Problem statement

The generated first-officer template uses team tools (TeamCreate, SendMessage) for dispatch. When agent teams are disabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=0`), these tools don't exist. We need to know what actually breaks and whether the first-officer degrades gracefully — before deciding whether to change any templates.

This is an experiment, not a template rewrite. Commission a workflow normally (templates unchanged), disable teams via env, and observe what happens.

### How the commission auto-run works

From `skills/commission/SKILL.md` Phase 3, Step 2: the commission skill does NOT spawn a separate `claude` process for the pilot run. Instead, it reads the generated `first-officer.md` agent file and assumes that role inline within the same `claude -p` session. The flow is:

1. Phase 2 generates all files (README, status, entities, first-officer.md, ensign.md)
2. Phase 3 Step 2: commission reads first-officer.md and follows its instructions directly
3. The first-officer behavior (TeamCreate, status --next, Agent dispatch) happens in the same process
4. Ensigns are dispatched via `Agent()` tool calls — subagents within the same session

This means environment variables set on the outer `claude -p` command propagate to the entire session, including the auto-run phase. There is no process boundary between commission and pilot.

### How to inject the env override

Set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=0` as an environment variable on the `claude -p` invocation:

```bash
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=0 claude -p "$PROMPT" \
  --plugin-dir "$REPO_ROOT" \
  --permission-mode bypassPermissions \
  --verbose --output-format stream-json \
  2>&1 > test-log.jsonl
```

This is sufficient because:
- The commission runs Phase 2 (file generation) — no team tools needed
- The commission runs Phase 3 (pilot) inline — same process, same env
- Ensign subagents spawned via `Agent()` inherit the parent's environment

No project `settings.local.json` manipulation is needed. The env var on the command line is the simplest and most direct approach.

**Caveat from sd11-test:** When running `claude -p --agent first-officer` (a separate invocation, not the commission auto-run), the env var may not propagate or agent mode may enable teams automatically. This experiment focuses on the commission auto-run path first. The `--agent` path can be tested separately.

### Experiment design

**What to commission:** Use the standard dogfood test case from `scripts/test-harness.md` — same prompt as `test-commission.sh` but WITH the pilot phase enabled (remove the "Do NOT run the pilot phase" line).

**How to disable teams:** Prefix the `claude -p` invocation with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=0`.

**What to observe** (from the stream-json log):
1. Does Phase 2 (file generation) complete normally? (Expected: yes — no team tools needed)
2. Does the first-officer startup sequence fail at TeamCreate? If so, how? (Error message? Tool not found?)
3. Does the first-officer attempt to dispatch ensigns via `Agent()` with `team_name`? What happens?
4. Does the first-officer fall back to any alternative dispatch pattern?
5. What is the final state of the workflow entities? (status, worktree fields)

**How to run:**
```bash
cd "$(mktemp -d)" && git init test-project && cd test-project

PROMPT="/spacedock:commission

All inputs for this workflow:
- Mission: Test graceful degradation without agent teams
- Entity: A test task
- Stages: backlog → work → done
- Approval gates: none
- Seed entities:
  1. hello-world — Simple test entity (score: 0.80)
- Location: ./test-workflow/

Skip interactive questions and confirmation."

CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=0 claude -p "$PROMPT" \
  --plugin-dir /path/to/spacedock \
  --permission-mode bypassPermissions \
  --verbose --output-format stream-json \
  --max-budget-usd 2.00 \
  2>&1 > test-log.jsonl
```

Key choices:
- **No gates.** Simplifies the test — the pilot should run to completion without blocking for captain input.
- **One entity.** Minimal scope to isolate the teams-disabled behavior.
- **Budget cap.** Safety limit in case the first-officer enters a retry loop.

### Acceptance criteria

**PASS** if either:
- The first-officer completes the pilot run successfully despite teams being disabled (graceful degradation works)
- The first-officer fails clearly with an identifiable error at a specific point (TeamCreate, Agent with team_name), giving us concrete information about what to fix

**FAIL** if:
- The commission Phase 2 (file generation) breaks due to teams being disabled
- The env var has no effect and teams are still available during the auto-run
- The session hangs or loops without producing useful diagnostic output

### Open questions

1. Does `Agent()` with `team_name` fail gracefully when teams are disabled, or does it error?
2. Does `Agent()` without `team_name` still work when teams are disabled? (The sd11-test findings suggest yes — Agent as parent-child subagent works without teams)
3. If TeamCreate fails, does the commission/first-officer recover or abort the pilot?

## Stage Report: ideation

- [x] Problem statement: what we're testing and why (commission auto-run with teams disabled)
  See "### Problem statement" — testing whether the first-officer degrades gracefully when teams are disabled via env override during the commission auto-run.
- [x] Experiment design: how to inject env override, what to commission, what to observe
  See "### Experiment design" — env var on `claude -p`, no-gates single-entity workflow, 5 specific observations to capture from stream-json log.
- [x] Key finding: how the commission auto-run works and where env injection is needed
  See "### How the commission auto-run works" — Phase 3 Step 2 runs the first-officer inline (same process), so env var on the outer command is sufficient. No settings.json or process-boundary tricks needed.
- [x] Acceptance criteria for the experiment (what constitutes pass/fail)
  See "### Acceptance criteria" — PASS if clear success or clear failure with diagnostic info; FAIL if env has no effect, generation breaks, or session hangs.

### Summary

Replaced the template-rewrite approach with an experiment design. The key finding is that the commission auto-run (Phase 3 Step 2) executes the first-officer role inline — same process, same env — so `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=0` on the `claude -p` command line propagates to the entire pilot run including ensign subagents. The experiment uses a minimal no-gates workflow with one entity and a budget cap, observing 5 specific behaviors from the stream-json log.
