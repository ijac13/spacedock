---
id: 080
title: Single-entity -p mode for first-officer
status: ideation
source: CL
started: 2026-03-31T00:00:00Z
completed:
verdict:
score:
worktree:
issue:
pr:
---

## Problem Statement

The first-officer currently assumes an interactive session with a captain (human). Its event loop runs indefinitely: dispatch agents, wait at gates for captain approval, fire idle hooks, repeat "until the captain ends the session." This makes it unsuitable for `claude -p` (non-interactive, pipe mode) when you want to process a single entity through a workflow programmatically.

Today's workaround: `claude -p` already works for gate-free workflows because the FO dispatches all entities, processes completions, and eventually hits an idle state where there's nothing to dispatch. The session then ends naturally when the LLM has nothing left to do. But it processes **all** dispatchable entities, not a targeted one. And for gated workflows, the FO blocks forever at the gate waiting for captain approval that never comes.

**Use case:** A user wants to run a single entity through a workflow as a batch job:
```bash
claude -p "Process my-feature through all stages" --agent first-officer
```

This needs to:
1. Accept a target entity slug in the prompt
2. Run only that entity through its remaining stages
3. Handle gates without a captain (auto-approve or skip)
4. Print a structured result to stdout
5. Exit cleanly — no idle loop, no waiting

## Proposed Approach

### Where the logic lives: In the FO template itself

The single-entity mode is a behavioral modification to the first-officer template, not a separate agent or wrapper. The FO already reads its instructions from the prompt — `initialPrompt` triggers the startup sequence. In `-p` mode, the user provides a prompt instead (e.g., "Process my-feature through all stages and exit"). The FO detects this instruction and enters a constrained mode.

**Why in the template:** The FO is the dispatcher — it owns the event loop, gate logic, and state management. A wrapper would need to duplicate all of this. A mod can't override the event loop. The FO template already has conditional behavior (bare mode vs team mode, worktree vs non-worktree stages). Adding a single-entity mode is the same pattern.

**How the FO knows which entity to target:** The user names it in the prompt. The FO matches the slug (or title, or ID) against the workflow entities. No frontmatter flag needed — the targeting is in the invocation, not the entity.

Example invocations:
```bash
# By slug
claude -p "Process my-feature through all stages and exit" --agent first-officer

# By ID
claude -p "Process entity 042 through all stages and exit" --agent first-officer
```

### Template changes

Add a new section to the FO template: `## Single-Entity Mode`

This section instructs the FO to detect when the user prompt (the `initialPrompt` override from `-p`) names a specific entity and requests processing to completion. When detected, the FO:

1. **Scopes dispatch to only the named entity.** After `status --next`, filter to only the target entity. Ignore all others.
2. **Auto-approves gates.** In single-entity mode, the captain is absent. Gates auto-approve if the stage report recommends PASSED. If the stage report recommends REJECTED and the stage has `feedback-to`, the auto-bounce feedback loop runs as normal (up to the 3-cycle limit). If REJECTED with no `feedback-to`, or after 3 failed cycles, the FO reports the failure and exits.
3. **Exits after terminal or failure.** When the target entity reaches terminal status (done/archived) or fails irrecoverably, the FO prints a structured result and stops. No idle hooks, no "waiting for captain."
4. **Prints result to stdout.** On completion, the FO outputs the entity's final state: frontmatter fields, verdict, and the last stage report. This is the "return value" for the pipe.

#### Before/after for key FO template sections

**Startup (step 7)** — currently:
```
7. **Run status --next** — `{workflow_dir}/status --next` to find dispatchable entities.
```
After (add to end of Startup):
```
8. **Detect single-entity mode** — If the initial prompt names a specific entity (by slug, ID, or title) and requests processing to completion (phrases like "process X", "run X through", "advance X"), enter single-entity mode:
   - Resolve the target: match against entity slugs, IDs, and titles in the workflow directory.
   - If no match found, report "Entity not found: {name}" and exit.
   - If the entity is already terminal, report its current state and exit.
   - Set the scope: only this entity will be dispatched. All other entities are ignored by `status --next` filtering.
```

**Gate handling** — currently the GATE APPROVAL GUARDRAIL says "NEVER self-approve." This needs a single-entity-mode exception. After the guardrail paragraph, add:
```
**Single-entity mode exception:** When in single-entity mode (no interactive captain), gates auto-resolve based on the stage report recommendation. PASSED → approve. REJECTED with feedback-to → auto-bounce (same as the existing auto-bounce for feedback stages). REJECTED without feedback-to → report failure and exit. This exception ONLY applies in single-entity mode — in interactive sessions, the guardrail remains absolute.
```

**Event loop termination** — currently:
```
This is the event loop — repeat from step 1 after each agent completion until the captain ends the session.
```
After:
```
This is the event loop — repeat from step 1 after each agent completion until the captain ends the session.

**Single-entity mode termination:** In single-entity mode, the event loop exits when the target entity reaches terminal status or is irrecoverably blocked. On exit, print the entity's final state (frontmatter, verdict, last stage report body) and terminate. Do not fire idle hooks or wait for captain input.
```

**New section to add after "Clarification and Communication":**
```
## Single-Entity Mode

When the initial prompt names a specific entity and requests it be processed to completion, the first officer enters single-entity mode. This mode is designed for non-interactive `claude -p` invocations.

### Detection

Single-entity mode activates when the initial prompt (from `-p` or `initialPrompt` override) contains:
- A reference to a specific entity by slug, ID, or title
- A request to process, run, or advance it (e.g., "process X through all stages", "run X to completion")

If the prompt says "Report workflow status" (the default `initialPrompt`), this is NOT single-entity mode — it is the normal interactive startup.

### Behavior differences

| Aspect | Interactive mode | Single-entity mode |
|--------|-----------------|-------------------|
| Scope | All dispatchable entities | Named entity only |
| Gates | Captain approves/rejects | Auto-resolve from stage report |
| Feedback loops | Run with captain oversight | Run autonomously (3-cycle limit) |
| Idle hooks | Fire when nothing dispatchable | Do not fire |
| Orphan detection | Report to captain | Skip (not relevant) |
| Termination | Captain ends session | Entity reaches terminal or fails |
| Output | Status reports to captain | Final entity state to stdout |

### Gate auto-resolution

In single-entity mode, gate approval is automatic:
- **PASSED recommendation:** Auto-approve. Proceed to next stage or terminal.
- **REJECTED + feedback-to:** Auto-bounce into feedback loop. The 3-cycle limit still applies. After 3 failed cycles, exit with failure.
- **REJECTED + no feedback-to:** Exit with failure. Print the stage report.

### Exit protocol

When the target entity reaches terminal status or fails:

1. Print the entity's final state: all frontmatter fields and the body content (including stage reports).
2. If terminal with verdict PASSED, exit code 0 (natural session end).
3. If terminal with verdict REJECTED or failed mid-workflow, print the failure reason.

The first officer does not attempt to process other entities, fire idle hooks, or wait for input after the target entity is resolved.
```

### What does NOT change

- **Startup steps 1-6** (discovery, README, team, mods, startup hooks, orphan detection in interactive mode). Single-entity mode still needs to discover the workflow and read the README. It skips orphan detection since it only cares about the target entity.
- **Dispatch mechanics** (Agent tool, worktree creation, ensign instructions). The dispatch itself is identical — only the selection of *which* entities to dispatch changes.
- **Merge and cleanup.** Terminal entities still go through the merge/archive flow.
- **State management.** Frontmatter updates are the same.
- **Feedback rejection flow.** The mechanics are identical — only the trigger changes (auto-bounce instead of captain-initiated rejection).

## Acceptance Criteria

1. **Entity targeting works by slug, ID, and title.**
   - Test: Invoke FO with `claude -p "Process test-entity through all stages" --agent first-officer` on a workflow with multiple entities. Only the named entity advances.
   - Test: Also test by ID (`Process entity 001`) and title (`Process "My Feature"`).

2. **Gate auto-approval works for PASSED recommendations.**
   - Test: Create a gated workflow with a single entity. Run in `-p` mode. The entity should pass through the gate without captain input and reach terminal status.

3. **Gate auto-bounce works for REJECTED + feedback-to.**
   - Test: Create a gated workflow with `feedback-to`. Seed an entity that will produce a REJECTED validation. Verify the feedback loop runs and either resolves (PASSED on retry) or hits the 3-cycle limit and exits with failure.

4. **Gate REJECTED without feedback-to exits cleanly.**
   - Test: Create a gated workflow without `feedback-to`. Force a REJECTED result. Verify the FO exits with the failure reason printed.

5. **Entity already terminal is handled.**
   - Test: Run single-entity mode on an entity with `status: done`. The FO should report its current state and exit immediately.

6. **Entity not found is handled.**
   - Test: Run single-entity mode with a non-existent slug. The FO should report "Entity not found" and exit.

7. **Interactive mode is unaffected.**
   - Test: Run `claude --agent first-officer` (interactive, no `-p`) normally. The gate guardrail still blocks. The event loop still waits. No single-entity behavior activates.

8. **Final state is printed to stdout.**
   - Test: After successful processing, the entity's frontmatter and stage reports appear in the session output (stdout for `-p` mode).

## Test Plan

**Approach: Fixture-based tests using `claude -p`, same pattern as existing test-gate-guardrail.sh.**

Tests validate from `--output-format stream-json` logs and final file state — same approach as the existing E2E tests.

### Test 1: Single-entity targeting (E2E)
- Fixture: 3 entities in backlog, no gates, 3 stages (backlog -> work -> done).
- Invoke: `claude -p "Process entity-b through all stages" --agent first-officer`
- Validate: entity-b reaches `done`, entity-a and entity-c remain in `backlog`.
- Cost: ~$0.50-1.00. Run time: ~1-2 min.

### Test 2: Gate auto-approval (E2E)
- Fixture: 1 entity, stages backlog -> work -> done, work has `gate: true`.
- Invoke: `claude -p "Process test-entity through all stages" --agent first-officer`
- Validate: entity reaches `done` (gate was auto-approved). Stream log shows gate auto-resolution, NOT captain approval.
- Cost: ~$0.50-1.00. Run time: ~1-2 min.
- **Critical test** — this is the core behavioral change. The existing gate guardrail test confirms the FO blocks in interactive mode; this test confirms it auto-approves in single-entity mode.

### Test 3: Entity not found (E2E, cheap)
- Fixture: 1 entity named `real-entity`.
- Invoke: `claude -p "Process nonexistent-entity through all stages" --agent first-officer`
- Validate: FO output contains "not found" or equivalent. No entities advance.
- Cost: ~$0.25. Run time: ~30s.

### Test 4: Interactive mode regression (static check)
- Validate: The FO template still contains "NEVER self-approve" guardrail text.
- Validate: The single-entity mode section contains "ONLY applies in single-entity mode."
- Cost: $0 (grep, no LLM).

### Tests NOT needed (and why)

- **Feedback loop E2E:** The feedback loop mechanics are unchanged — only the trigger differs. The existing feedback tests cover the mechanics. A static check that the 3-cycle limit text is preserved is sufficient.
- **Already-terminal entity:** This is a simple conditional (check status, print, exit). A static check that the instruction exists in the template is sufficient. An E2E test would cost $0.50+ for a trivial branch.

### Cost estimate
- 3 E2E tests: ~$1.50-3.00 total
- 1 static check: $0
- Total: ~$1.50-3.00

## Edge Cases

### Entity doesn't exist
The FO resolves the entity name against workflow files. If no match: print "Entity not found: {name}. Available entities: {list}" and exit. No dispatch, no state changes.

### Entity already at terminal status
If the entity's status is the terminal stage: print its current state (frontmatter + body) and exit. No dispatch needed.

### Entity mid-workflow with active worktree
If the entity has a non-empty `worktree` field (orphan from a previous session), single-entity mode should check the worktree state (same as orphan detection) and either resume from the existing worktree or report the conflict. This reuses the existing orphan detection logic but auto-decides instead of asking the captain: if a stage report exists, proceed with gate review; if no stage report, redispatch into the same worktree.

### Gate failure with no feedback-to
The entity is stuck — REJECTED with no way to fix. The FO prints the REJECTED stage report and exits. The entity remains in its current (non-terminal) status so a human can intervene later.

### Feedback loop exhaustion (3 cycles)
After 3 REJECTED cycles, the FO prints all cycle findings and exits. Same as the interactive escalation, but instead of asking the captain, it terminates. The entity remains in its current status.

### Multiple workflows in the project
The FO's workflow discovery (step 1) still runs. If multiple workflows exist, the FO can't know which one the entity belongs to. Options: (a) search all workflows for the slug, (b) require the user to specify. Given single-entity mode is for automation, option (a) is better — search all workflows, error if the slug is ambiguous (exists in multiple workflows).

### Ambiguous entity reference
If the user's prompt matches multiple entities (e.g., "Process test" matches "test-a" and "test-b"), the FO should report the ambiguity and list matches. Do not guess.

## Stage Report: ideation

- [x] Problem statement clearly articulated
  See "## Problem Statement" — the FO's interactive event loop and gate guardrail make it incompatible with `claude -p` for targeted single-entity processing.
- [x] Proposed approach with specific template changes (before/after wording for key sections)
  See "## Proposed Approach" — logic lives in the FO template as a new `## Single-Entity Mode` section. Before/after wording provided for Startup step 7→8, gate handling exception, event loop termination, and the full new section with detection/behavior/gate/exit subsections.
- [x] Acceptance criteria with testable conditions
  See "## Acceptance Criteria" — 8 criteria covering entity targeting (slug/ID/title), gate auto-approval, gate auto-bounce, gate rejection exit, already-terminal, not-found, interactive regression, and stdout output.
- [x] Test plan with cost/complexity estimates and whether E2E tests are needed
  See "## Test Plan" — 3 E2E tests ($1.50-3.00 total), 1 static check ($0), with explicit rationale for tests NOT needed (feedback loop E2E, already-terminal E2E).
- [x] Edge cases considered (entity doesn't exist, entity already done, gate failures, feedback loops)
  See "## Edge Cases" — 7 edge cases: entity not found, already terminal, mid-workflow orphan, gate failure without feedback-to, feedback exhaustion (3 cycles), multiple workflows, ambiguous reference.

### Summary

The single-entity mode is a behavioral addition to the FO template, not a separate agent or wrapper. The FO detects when the user prompt names a specific entity and enters a constrained mode: scoped dispatch (one entity), auto-resolving gates from stage report recommendations, autonomous feedback loops (3-cycle limit), and clean exit on terminal/failure. The key design decision is that gate auto-approval is a single-entity-mode exception to the existing "NEVER self-approve" guardrail — interactive mode is completely unaffected. Three E2E tests validate the core behaviors; the critical test is gate auto-approval, which directly inverts the existing gate guardrail test.
