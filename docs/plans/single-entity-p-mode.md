---
id: 080
title: Single-entity -p mode for first-officer
status: validation
source: CL
started: 2026-03-31T00:00:00Z
completed:
verdict:
score:
worktree: .worktrees/ensign-single-entity-p-mode
issue:
pr:
---

## Problem Statement

The first-officer agent hangs when invoked via `claude -p`. It never terminates on its own.

The root cause is the FO's event loop design: it dispatches agents, waits at gates for captain approval, fires idle hooks, and repeats "until the captain ends the session." In an interactive session, the captain (human) is the termination signal. In `-p` mode, there is no captain — the session has no mechanism to end.

**Evidence from existing tests:**
- The gate guardrail test (`tests/test_gate_guardrail.py`) uses `--max-budget-usd 1.00` to kill the session. Comment on line 70: "expected — session ends when budget runs out at gate." The FO never exits on its own at a gate.
- The checklist E2E test (`scripts/test_checklist_e2e.py`) uses `--max-budget-usd 2.00` as a safety cap AND a prompt hint: "Process one entity through one stage, then stop." The "then stop" is a prompt-level suggestion to the LLM — not a platform mechanism.
- Both tests rely on the budget cap as the actual termination mechanism, not the FO deciding it's done.

This is not just about gates. Even in a gate-free workflow, the FO's event loop says "repeat... until the captain ends the session." Whether the LLM decides to stop producing output after processing all entities is undefined behavior — it works sometimes (the LLM happens to go idle), but it's not reliable and it's not by design.

**Current production workaround:** The spacedock solver (which invokes the FO via `claude -p` to process entities) cannot use `run_command_streaming` because it blocks forever. Instead, it polls the filesystem every 5 seconds for the expected artifact (e.g., `answers.json`). Once the file appears and has content, it waits 10 more seconds for any final writes, then kills the process and reads the result from the file system. This is file-polling + process kill — it works but it's brittle, artifact-specific, and throws away anything the FO might have printed to stdout.

**The deeper question:** What actually controls session termination in `claude -p`? Is it the LLM deciding it has nothing left to say? A token limit? An explicit exit mechanism agents can invoke? Until we understand this, any template changes are speculative.

**Use case:** A user wants to run a single entity through a workflow as a batch job:
```bash
claude -p "Process my-feature through all stages" --agent first-officer
```

This needs to:
1. Accept a target entity slug in the prompt
2. Run only that entity through its remaining stages
3. Handle gates without a captain (auto-approve or skip)
4. Print a structured result to stdout
5. **Terminate reliably** — not hang, not depend on budget caps, not require file-polling + process kill

## Spike: Session Termination in `claude -p`

Before committing to any template changes, we need to understand the termination mechanism. The proposed approach below is conditional on spike findings.

**Why this matters now:** The production workaround (file-polling + process kill) is artifact-specific — it only works when you know the exact output file to watch for. It can't generalize to arbitrary workflows. Any solution needs to be at least as reliable as "poll for known artifact + kill" but work for any entity/workflow combination without knowing the artifact name in advance.

### What we need to learn

1. **What controls session termination in `claude -p`?** When does the process exit? Options:
   - **LLM-driven:** The LLM produces a final assistant turn with no tool calls, and `claude -p` treats that as "done." The session ends because the LLM decided to stop talking.
   - **Explicit mechanism:** There's an API or tool the agent can call to signal "I'm done" (e.g., a `done()` tool, a special return value, an exit status mechanism).
   - **Token/budget exhaustion:** The session runs until `--max-budget-usd` or token limits are hit. There is no graceful termination.

2. **Can prompt instructions reliably trigger termination?** The checklist E2E test uses "then stop" in the prompt. Does the LLM reliably stop, or does it sometimes keep going (checking for more work, firing idle hooks)?

3. **Does `initialPrompt` interact with `-p` prompts?** When using `claude -p "Process X" --agent first-officer`, the agent frontmatter has `initialPrompt: "Report workflow status."` Does the `-p` prompt replace or supplement `initialPrompt`? This determines whether the FO sees the user's entity-targeting prompt at all.

4. **Can template prose override the event loop?** If the FO template says "repeat until the captain ends the session" but a single-entity-mode section says "exit after this entity is done," does the LLM follow the termination instruction, or does the event loop prose win?

### Spike design

Run three experiments in a temp project with a simple gate-free workflow (backlog -> work -> done, 1 entity):

**Experiment A — Baseline: does the FO terminate naturally?**
```bash
claude -p "Report workflow status." --agent first-officer \
  --permission-mode bypassPermissions \
  --verbose --output-format stream-json \
  --max-budget-usd 3.00 \
  2>&1 > baseline.jsonl
```
Observe: Does it process the entity and exit? Or does it hang at idle until budget runs out? Check the stream-json log for the last few turns — is there a natural end or a budget-cap kill?

**Experiment B — Prompt-directed termination**
```bash
claude -p "Process test-entity through all stages, then stop." --agent first-officer \
  --permission-mode bypassPermissions \
  --verbose --output-format stream-json \
  --max-budget-usd 3.00 \
  2>&1 > directed.jsonl
```
Observe: Does "then stop" cause reliable termination after the entity is done? Compare with Experiment A.

**Experiment C — Gated workflow, prompt-directed**
Same as B but with `gate: true` on the work stage. Observe: Does the FO auto-approve and exit, or hang at the gate despite the prompt instruction?

**Cost:** ~$1.50-3.00 total for all three experiments. Time: ~5-10 min.

### Spike outcomes and next steps

| Spike finding | Implication for approach |
|---|---|
| LLM-driven termination works reliably with prompt instructions | Template approach is viable. Add single-entity mode section with termination prose. The LLM will follow "exit after done" instructions. |
| LLM-driven termination is unreliable (sometimes hangs) | Need a harder mechanism. Options: (a) a wrapper script with a timeout, (b) a hook/mod that checks entity status and calls an exit tool if one exists, (c) accept `--max-budget-usd` as the termination mechanism and document it. |
| Explicit exit mechanism exists (exit tool, done signal) | Template approach is viable AND reliable. Use the explicit mechanism in the single-entity mode section. |
| `-p` prompt does not override `initialPrompt` | Entity targeting via prompt won't work. Need a different injection point (env var, config file, or a separate agent variant). |
| Template prose cannot override event loop behavior | The FO template is too rigid for conditional modes. Need either a separate agent file (`first-officer-batch.md`) or a fundamentally different approach. |

## Proposed Approach (pending spike)

The approach below assumes the spike confirms that LLM-driven or explicit termination works. If the spike reveals a harder problem, the approach will need revision.

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

### Template changes (contingent on spike)

Add a new section to the FO template: `## Single-Entity Mode`

This section instructs the FO to detect when the user prompt names a specific entity and requests processing to completion. When detected, the FO:

1. **Scopes dispatch to only the named entity.** After `status --next`, filter to only the target entity. Ignore all others.
2. **Auto-approves gates.** In single-entity mode, the captain is absent. Gates auto-approve if the stage report recommends PASSED. If the stage report recommends REJECTED and the stage has `feedback-to`, the auto-bounce feedback loop runs as normal (up to the 3-cycle limit). If REJECTED with no `feedback-to`, or after 3 failed cycles, the FO reports the failure and exits.
3. **Terminates after the target entity is resolved.** When the target entity reaches terminal status or fails irrecoverably, the FO prints a structured result and stops. The specific termination mechanism depends on spike findings (prompt instruction, explicit exit tool, or documented `--max-budget-usd` pattern).
4. **Prints result to stdout.** On completion, the FO outputs the entity's final state: frontmatter fields, verdict, and the last stage report. This is the "return value" for the pipe.

#### Key template modifications (before/after)

**Gate handling** — currently the GATE APPROVAL GUARDRAIL says "NEVER self-approve." This needs a single-entity-mode exception:
```
**Single-entity mode exception:** When in single-entity mode (no interactive captain), gates auto-resolve based on the stage report recommendation. PASSED → approve. REJECTED with feedback-to → auto-bounce (same as the existing auto-bounce for feedback stages). REJECTED without feedback-to → report failure and exit. This exception ONLY applies in single-entity mode — in interactive sessions, the guardrail remains absolute.
```

**Event loop termination** — currently says "repeat... until the captain ends the session." Add:
```
**Single-entity mode termination:** In single-entity mode, the event loop exits when the target entity reaches terminal status or is irrecoverably blocked. On exit, print the entity's final state (frontmatter, verdict, last stage report body) and terminate. Do not fire idle hooks or wait for captain input.
```

**New section — `## Single-Entity Mode`** — detection logic, behavior table, gate auto-resolution rules, and exit protocol. Full wording to be finalized after the spike confirms the termination mechanism.

### What does NOT change

- **Startup steps 1-6** (discovery, README, team, mods, startup hooks). Single-entity mode still needs to discover the workflow and read the README. It skips orphan detection since it only cares about the target entity.
- **Dispatch mechanics** (Agent tool, worktree creation, ensign instructions). The dispatch itself is identical — only the selection of *which* entities to dispatch changes.
- **Merge and cleanup.** Terminal entities still go through the merge/archive flow.
- **State management.** Frontmatter updates are the same.
- **Feedback rejection flow.** The mechanics are identical — only the trigger changes (auto-bounce instead of captain-initiated rejection).

### Alternative approaches (if spike reveals problems)

**If prompt-directed termination is unreliable:**
- **Separate agent file** (`first-officer-batch.md`): A stripped-down FO with no event loop — just linear entity processing. Duplicates dispatch logic but guarantees termination. Downside: two agent files to maintain.
- **Wrapper script approach:** A shell script that invokes `claude -p` with a timeout and checks entity status after termination. Pragmatic but loses the "exit cleanly" property.
- **Accept budget-cap termination:** Document `--max-budget-usd` as the official termination mechanism for `-p` mode. Crude but honest. The FO does its work, the budget cap kills it, and the caller checks entity status from the file system.

**If `-p` prompt doesn't reach the FO:**
- **Environment variable injection:** `SPACEDOCK_TARGET_ENTITY=my-feature claude -p --agent first-officer`. The FO template reads the env var at startup.
- **Config file:** Write target entity to a temp file, FO reads it. More complex than needed.

## Acceptance Criteria

### Spike phase (must pass before implementation)

S1. **Termination mechanism is understood and documented.**
    - Test: Spike experiments A, B, C produce clear answers to the four questions in the spike design.

S2. **A reliable termination path exists for single-entity mode.**
    - Test: At least one spike experiment shows the FO terminating naturally (not via budget cap) after entity processing completes.

### Implementation phase (contingent on spike)

1. **Entity targeting works by slug.**
   - Test: Invoke FO with `claude -p "Process test-entity through all stages" --agent first-officer` on a workflow with multiple entities. Only the named entity advances.

2. **Gate auto-approval works for PASSED recommendations.**
   - Test: Create a gated workflow with a single entity. Run in `-p` mode. The entity should pass through the gate without captain input and reach terminal status.

3. **Session terminates reliably after entity completes.**
   - Test: The FO exits without hitting the budget cap. Stream-json log shows a natural end, not a budget-kill.

4. **Entity not found is handled.**
   - Test: Run single-entity mode with a non-existent slug. The FO should report "Entity not found" and exit.

5. **Interactive mode is unaffected.**
   - Test: The FO template still contains "NEVER self-approve" guardrail. The single-entity mode exception text explicitly limits itself to single-entity mode.

6. **Final state is printed to stdout.**
   - Test: After successful processing, the entity's frontmatter and stage reports appear in the session output.

## Test Plan

### Phase 1: Spike (pre-implementation)

Three experiments as described in "Spike: Session Termination in `claude -p`" above. Each uses a minimal fixture workflow (backlog -> work -> done, 1 entity). Validate from stream-json logs.

- Cost: ~$1.50-3.00 total
- Time: ~5-10 min
- Pass criteria: Clear answers to all four spike questions. At least one experiment shows natural termination.

### Phase 2: Implementation tests (post-spike, contingent on findings)

**Approach: Fixture-based tests using `claude -p`, same pattern as existing tests.**

Tests validate from `--output-format stream-json` logs and final file state.

#### Test 1: Single-entity targeting (E2E)
- Fixture: 3 entities in backlog, no gates, 3 stages (backlog -> work -> done).
- Invoke: `claude -p "Process entity-b through all stages" --agent first-officer`
- Validate: entity-b reaches `done`, entity-a and entity-c remain in `backlog`. Session terminates without hitting budget cap.
- Cost: ~$0.50-1.00. Run time: ~1-2 min.

#### Test 2: Gate auto-approval (E2E)
- Fixture: 1 entity, stages backlog -> work -> done, work has `gate: true`.
- Invoke: `claude -p "Process test-entity through all stages" --agent first-officer`
- Validate: entity reaches `done` (gate was auto-approved). Stream log shows gate auto-resolution, NOT captain approval.
- Cost: ~$0.50-1.00. Run time: ~1-2 min.
- **Critical test** — this is the core behavioral change. The existing gate guardrail test confirms the FO blocks in interactive mode; this test confirms it auto-approves in single-entity mode.

#### Test 3: Interactive mode regression (static check)
- Validate: The FO template still contains "NEVER self-approve" guardrail text.
- Validate: The single-entity mode section contains "ONLY applies in single-entity mode."
- Cost: $0 (grep, no LLM).

#### Tests NOT needed (and why)

- **Feedback loop E2E:** The feedback loop mechanics are unchanged — only the trigger differs. The existing feedback tests cover the mechanics. A static check that the 3-cycle limit text is preserved is sufficient.
- **Already-terminal entity:** This is a simple conditional (check status, print, exit). A static check that the instruction exists in the template is sufficient.
- **Entity not found E2E:** The FO simply reports and exits. If the spike shows prompt-directed termination works, this is the trivial case. A static check is sufficient.

#### Cost estimate
- Spike: ~$1.50-3.00
- 2 E2E tests: ~$1.00-2.00
- 1 static check: $0
- Total: ~$2.50-5.00

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
  See "## Problem Statement" — the root issue is that the FO hangs in `-p` mode because it has no termination signal. Evidence from existing tests (budget caps as kill mechanism) and from the production workaround (file-polling + process kill for the spacedock solver).
- [x] Proposed approach with specific template changes (before/after wording for key sections)
  See "## Proposed Approach (pending spike)" — logic lives in the FO template, contingent on spike confirming the termination mechanism. Before/after wording for gate handling exception and event loop termination. Full single-entity-mode section deferred until spike resolves the termination question. Alternative approaches documented for each spike failure mode.
- [x] Acceptance criteria with testable conditions
  See "## Acceptance Criteria" — split into spike phase (2 criteria: termination mechanism understood, reliable path exists) and implementation phase (6 criteria: entity targeting, gate auto-approval, reliable termination, not-found, interactive regression, stdout output).
- [x] Test plan with cost/complexity estimates and whether E2E tests are needed
  See "## Test Plan" — Phase 1 spike ($1.50-3.00, 3 experiments), Phase 2 implementation (2 E2E tests + 1 static check, $1.00-2.00). Total ~$2.50-5.00.
- [x] Edge cases considered (entity doesn't exist, entity already done, gate failures, feedback loops)
  See "## Edge Cases" — 7 edge cases: entity not found, already terminal, mid-workflow orphan, gate failure without feedback-to, feedback exhaustion (3 cycles), multiple workflows, ambiguous reference.

### Summary

Revised ideation to acknowledge the root issue: the FO literally never terminates in `-p` mode. Existing tests use budget caps to kill sessions. Added a spike phase (3 experiments, ~$1.50-3.00) to answer the fundamental question: what controls session termination in `claude -p`? The proposed template approach is contingent on the spike confirming that LLM-driven or explicit termination works. If the spike reveals termination is unreliable, alternative approaches are documented: separate agent file, wrapper script, or accept budget-cap termination. Implementation acceptance criteria and tests are contingent on spike results.

### Feedback Cycles

Cycle: 2

## Stage Report: implementation

- [x] Spike experiments A, B, C executed and findings documented
  Ran via `tests/test_spike_termination.py`. Results: A terminated naturally in 47s (reported status, asked to dispatch, stopped); B terminated naturally in 130s (processed entity to done, archived, printed summary); C terminated naturally in 132s (stopped at gate awaiting captain approval). All 3 used natural_end, 0/3 hit budget cap. Fixtures at `tests/fixtures/spike-no-gate/` and `tests/fixtures/spike-gated/`.
- [x] Termination mechanism understood and documented (spike acceptance criterion S1)
  LLM-driven termination: `claude -p` sessions end when the LLM produces a final assistant turn with no tool calls. This happens reliably in all tested scenarios. The `-p` prompt supplements (does not replace) `initialPrompt` — both reach the FO. Prompt instructions like "then stop" work but are not strictly necessary; the FO stops naturally when it needs captain input or has nothing left to do.
- [x] Reliable termination path identified (spike acceptance criterion S2)
  All 3 experiments terminated naturally without budget cap. Exp B confirms end-to-end: entity processed through all stages, archived, and session exited cleanly. The template approach is viable.
- [x] FO template updated with single-entity mode section (if spike confirms viability)
  Added `## Single-Entity Mode` section (6 behavior items: scoped dispatch, entity resolution, gate auto-approval, orphan auto-decision, termination, already-terminal). Added gate guardrail exception for single-entity mode. Updated event loop termination clause. Changes at `templates/first-officer.md`.
- [ ] SKIP: Commission skill updated to emit the new FO section (if spike confirms viability)
  The commission skill copies the FO template verbatim (`cp` in step 2d of SKILL.md). No commission changes are needed — the template update is sufficient.
- [x] Update FO template items 5 and 6 to support README-configurable output format
  Items 5 and 6 in `## Single-Entity Mode` now check for a `## Output Format` section in the workflow README. If present, the FO follows those formatting instructions. If absent, falls back to printing terminal state (status and verdict) and entity ID. See `templates/first-officer.md` lines 56-57.
- [x] Create test fixture(s) with and without `## Output Format` sections
  Two fixtures: `tests/fixtures/output-format-custom/` (README has `## Output Format` with RESULT/ENTITY/TITLE format, already-terminal entity) and `tests/fixtures/output-format-default/` (README has no Output Format section, entity starts at backlog for real dispatch testing).
- [x] Create test script(s) that verify the output format behavior
  `tests/test_output_format.py` — Phase 1: static checks on template and fixtures. Phase 2: E2E with custom format (already-terminal entity, $1 budget). Phase 3: E2E with default format (entity starts at backlog, FO dispatches ensign through work -> done, $3 budget). Phase 3 verifies entity file reaches terminal status and output contains done/entity ID/verdict.
- [x] Commit all changes on the ensign/single-entity-p-mode branch
  Latest commit `da3cc6c` on `ensign/single-entity-p-mode` — Phase 3 updated to use real dispatch.

### Summary

Spike phase confirmed that `claude -p` sessions terminate reliably via LLM-driven natural end (3/3 experiments). The `-p` prompt reaches the FO and directs its behavior. Template approach is viable. Implemented three changes to `templates/first-officer.md`: a new Single-Entity Mode section defining scoped dispatch, entity resolution, gate auto-approval, orphan auto-decision, and termination; a gate guardrail exception for single-entity mode; and an event loop termination clause. The commission skill needs no changes since it copies the template verbatim. Post-validation feedback cycle 1: updated items 5 and 6 to support workflow-configurable output format via README `## Output Format` section, with fallback to default (terminal state + entity ID). Feedback cycle 2: updated Phase 3 of test to exercise full single-entity mode flow (dispatch -> process -> terminate -> output) instead of only testing the already-terminal shortcut. The default fixture entity now starts at backlog, budget increased to $3, and the test verifies the entity file reaches terminal status.

## Stage Report: validation

- [x] Verify the template changes correctly implement README-configurable output format (items 5 and 6)
  Item 5 (line 56): "Check the workflow README for a `## Output Format` section. If present, follow those formatting instructions for the final output. If no `## Output Format` section exists, fall back to printing the terminal state (status and verdict) and entity ID." Item 6 (line 57): "Same rule as item 5 — use the README's `## Output Format` section if present, otherwise print the terminal state and entity ID." Both items now delegate to the README for output format, with a clearly defined fallback.
- [x] Run the output format test script (`tests/test_output_format.py`) — Phase 1 static checks
  Phase 1 (4 static checks): all PASS. (1) item 5 references `## Output Format` section from README, (2) item 6 references same rule as item 5, (3) custom fixture has `## Output Format` section, (4) default fixture has no `## Output Format` section. Phase 2/3 E2E tests could not run — `claude` cannot be launched inside another `claude` session (expected infrastructure limitation, not a test defect). E2E test logic is sound: custom fixture checks for RESULT/ENTITY/TITLE lines; default fixture checks for terminal status, entity ID, verdict.
- [x] Verify original acceptance criteria (AC 1-6) still hold after the template changes
  AC 1 (entity targeting): Item 1 (line 52) scopes dispatch, item 2 (line 53) resolves by slug/title/ID — unchanged. AC 2 (gate auto-approval): Item 3 (line 54) references gate guardrail exception at line 135 — unchanged. AC 3 (reliable termination): Item 5 (line 56) defines termination; event loop clause at line 98 — unchanged, output format addition does not alter termination logic. AC 4 (entity not found): Item 2 (line 53) handles not-found — unchanged. AC 5 (interactive unaffected): "NEVER self-approve" guardrail at line 133 preserved; exception at line 135 scoped to single-entity mode — unchanged. AC 6 (stdout output): Items 5 and 6 now configurable via README `## Output Format` section with sensible fallback — this is the enhancement from feedback cycle 1, strictly additive.
- [x] Static checks: gate guardrail still contains "NEVER self-approve", single-entity mode exception is scoped, output format fallback is clearly defined
  Confirmed via grep: "NEVER self-approve" at line 133. "ONLY applies in single-entity mode" at line 135. Output format fallback at line 56: "fall back to printing the terminal state (status and verdict) and entity ID." All three checks pass.
- [x] Overall PASSED/REJECTED recommendation with evidence

### Recommendation: PASSED

### Findings

1. Items 5 and 6 in the Single-Entity Mode section correctly implement README-configurable output format: check for `## Output Format` in the workflow README, follow those instructions if present, fall back to terminal state + entity ID if absent.
2. Test fixtures are correctly structured: `output-format-custom/README.md` has a `## Output Format` section with RESULT/ENTITY/TITLE format; `output-format-default/README.md` has no such section. Both entities are already-terminal (`status: done`, `verdict: PASSED`) for fast testing.
3. The test script (`tests/test_output_format.py`) has sound Phase 1 static checks (4/4 pass) and well-structured E2E phases that verify both custom and default output format paths. E2E phases could not execute in this session (nested `claude` limitation) but test logic is correct.
4. All 6 original acceptance criteria remain satisfied after the output format changes — the enhancement is strictly additive and does not alter entity targeting, gate auto-approval, termination, not-found handling, or the interactive mode guardrail.
5. The "NEVER self-approve" guardrail is intact at line 133, the single-entity mode exception is narrowly scoped at line 135, and the output format fallback is clearly defined at line 56.

### Summary

Re-validated after feedback cycle 1. The implementation agent added README-configurable output format to items 5 and 6 of the Single-Entity Mode section. The template now checks for a `## Output Format` section in the workflow README and follows those instructions if present, falling back to terminal state + entity ID if absent. Test fixtures and test script are correctly structured. All original acceptance criteria (AC 1-6) remain satisfied — the output format change is strictly additive. Static checks confirm the gate guardrail, scoping, and fallback are all in place.
