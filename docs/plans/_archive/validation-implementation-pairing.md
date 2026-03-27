---
id: 061
title: Pair implementation and validation agents — validator judges, implementer fixes
status: done
source: CL
started: 2026-03-27T22:45:00Z
completed: 2026-03-27T23:34:26Z
verdict: PASSED
score:
worktree:
pr: "#7"
---

## Problem Statement

Currently the validation ensign both finds bugs and fixes them, then validates its own fixes. This breaks the independence that `fresh: true` is designed to provide.

Concrete example: The FO dispatches a fresh ensign for validation. The ensign finds a missing edge case in error handling. Instead of just reporting it, the ensign edits the code to add the error handling, commits it, then writes a stage report saying "PASSED" — having validated its own fix. The `fresh: true` guarantee (independent perspective) is defeated because the validator became the implementer.

## Design

### 1. Agent Lifecycle: Respawn Over Keep-Alive

**Decision: Always shut down the implementation agent after implementation completes. Respawn if needed during validation.**

Trade-offs considered:

| Approach | Pros | Cons |
|----------|------|------|
| Keep-alive | No respawn cost, full context | Consumes resources while waiting for validation + gate review; session may end between stages anyway; adds lifecycle complexity to FO |
| Respawn on demand | Simple lifecycle (current shutdown behavior unchanged); no wasted resources; works across session boundaries | Respawn costs one agent dispatch; must reconstruct context |

Respawn wins because:
- The current FO flow already shuts down after implementation. No template change needed for the happy path (validation passes).
- Validation often runs hours or days later (gate review is manual). Keeping an agent alive across that gap is wasteful and fragile.
- The worktree has the full git history. The entity file has the implementation stage report. A respawned implementer reads these and has sufficient context to fix a specific reported bug.
- This matches the existing "always dispatch fresh" principle from the simplify-first-officer work (task 048).

### 2. Validator Agent: Separate Template with Restricted Tools

**Decision: Create a `validator.md` template — a distinct agent type with no Write/Edit/Bash tools.**

Why not behavioral instructions on the ensign? Behavioral instructions ("do NOT edit files") are suggestions the LLM may ignore under pressure. Tool restrictions are enforced by the runtime — a validator without Write/Edit literally cannot modify files. This is the stronger guarantee.

Why not just remove Write/Edit? The validator also should not have Bash — Bash can write files via shell commands (echo, cat, sed, tee, etc.), bypassing the Write/Edit restriction. However, the validator needs to run tests, which requires Bash. Solution: the validator gets Bash but with an explicit instruction that Bash is for running tests and read-only commands only. This is a pragmatic compromise — removing Bash entirely would prevent test execution which is core to validation.

Revised tool restriction: Remove Write and Edit. Keep Bash (needed for test execution) but with strong behavioral framing. Keep Read, Glob, Grep, SendMessage.

Template structure:
```yaml
---
name: validator
description: Validates workflow stage work for __MISSION__
tools: Read, Bash, Glob, Grep, SendMessage
commissioned-by: spacedock@__SPACEDOCK_VERSION__
---
```

The validator template will:
- State its role: read code, run tests, judge against acceptance criteria
- Explicitly forbid: creating/editing files, making commits, fixing bugs
- Define its completion protocol: findings go in the stage report, PASSED or REJECTED recommendation, specific findings listed for relay to implementer
- Define its rejection protocol: when it finds issues, it sends a structured finding to the FO via SendMessage rather than fixing them itself

### 3. Communication and Iteration Protocol

Practice runs showed the serial model (shut down validator, dispatch implementer, respawn validator) adds unnecessary FO round-trips. The parallel model lets implementer and validator coordinate directly while the FO observes.

**Flow when validation finds issues:**

```
Validator finds bug
  → Validator writes finding in stage report (REJECTED recommendation)
  → Validator sends completion message to FO
  → FO presents stage report at gate (validation has gate: true)
  → Captain reviews: approve REJECTED, or reject (redo validation)
  → If captain agrees findings are valid:
      → FO ensures implementer is alive (respawn if needed) with findings
      → FO ensures validator is alive (keep running or respawn if crashed)
      → Implementer fixes, commits, messages validator directly
      → Validator re-checks, updates stage report, messages FO
      → FO presents updated result at gate
      → Cycle repeats
```

Key design points:

- **Peer-to-peer fix cycles.** The implementer and validator coordinate directly via SendMessage for the fix/re-check cycle. The FO only re-enters when the validator sends its updated completion message. This avoids unnecessary FO round-trips between each fix and re-check.
- **Validator persists across cycles.** The validator is NOT shut down between cycles — it stays alive as a reviewer. If it crashes or the session ends, the FO respawns a fresh one.
- **FO owns the gate.** While agents coordinate directly for fixes, the FO still presents the updated stage report at the gate for captain review. The FO remains the single source of truth for entity state transitions.
- **Iteration limit: 3 fix cycles** before escalation to captain. The FO tracks cycle count in the entity file body (a `### Validation Cycles` section). After 3 cycles of rejected validation, the FO reports to the captain with a summary of all findings and asks for direction.
- **Implementer disagreement:** Not an issue in this model. The implementer gets findings as context, not as a debate. If the finding is invalid, the implementer fixes the actual issue (or does nothing if there's nothing to fix), and the next validation pass should reflect the true state.

### 4. Changes to First-Officer Template

The FO template (`templates/first-officer.md`) needs changes in three areas:

**A. Dispatch section — agent type resolution (existing step 4):**
Currently: "If the stage has an `agent` property, use that value. If no `agent` property, default to `ensign`."
Change: Add awareness that validation stages use `validator` as the default agent type. Specifically: if the stage has `fresh: true` and no explicit `agent` property, default to `validator` instead of `ensign`. If the stage has an explicit `agent` property, that always wins.

This means the README stages block would look like:
```yaml
- name: validation
  worktree: true
  fresh: true
  gate: true
```
No `agent:` property needed — `fresh: true` implies `validator`. Pipelines that want a custom validation agent can still set `agent: my-custom-validator`.

**B. Validation rejection flow — new section:**
Add a `## Validation Rejection Flow` section after the existing "Completion and Gates" section. When a validation stage's gate results in a REJECTED verdict from the captain:

1. Check cycle count. If >= 3, escalate to captain with full history.
2. Ensure implementer is alive (respawn if needed) with validator findings.
3. Ensure validator is alive (keep running or respawn if crashed).
4. Implementer fixes and messages validator directly. Validator re-checks and reports to FO.
5. FO increments cycle count and presents updated result at gate.

**C. Validation instructions update:**
Currently: "Determine what work was done in the previous stage. For code changes, check the README for a Testing Resources section — run applicable tests and include results..."
Add: "You are a validator. You read and judge — you do NOT write code or fix bugs. If you find issues, describe them precisely in your stage report with a REJECTED recommendation. The first officer will relay findings to an implementation agent for fixes."

### 5. Changes to Ensign/Validator Templates

**New file: `templates/validator.md`**

The validator template is small — it references the ensign for common protocol but overrides the working section:

```markdown
---
name: validator
description: Validates workflow stage work
tools: Read, Bash, Glob, Grep, SendMessage
---

# Validator

You are a validator executing stage work. You verify that implementation
work meets acceptance criteria. You NEVER modify code — you only read, test, and judge.

## Your Assignment

[Same as ensign — read assignment from dispatch prompt]

## Working

1. Read the entity file at the path given in your assignment.
2. All file reads MUST use paths under the worktree path given in your assignment.
3. Run tests specified in the README's Testing Resources section.
4. Verify each acceptance criterion with evidence.
5. Write your findings in the entity file's Stage Report section.

## Rules

- Do NOT create, edit, or delete any files other than the entity file.
- Do NOT make commits (except the stage report update to the entity file).
- Do NOT fix bugs. Describe them precisely so an implementer can fix them.
- Do NOT modify YAML frontmatter in entity files.
- Bash is for running tests and read-only inspection commands ONLY (grep, find, cat, git log, git diff, test runners). Do NOT use Bash to write or modify files.

## Completion Protocol

[Same as ensign — write stage report, send completion message]
```

This template is fully static — no template variables. It aligns with #063 (workflow-agnostic-agents): agents read workflow-specific info (mission name, entity labels) from the README at runtime, not from baked-in variables. The dispatch prompt provides all the context the validator needs (entity path, worktree path, stage definition).

**No changes to `templates/ensign.md`.** The ensign template stays as-is. It's the general-purpose worker. The validator is a specialized agent type for stages that need read-only independence.

### 6. Impact on `fresh: true`

`fresh: true` retains its current meaning: dispatch a new agent with no context from prior stages. The addition is that `fresh: true` now also implies `agent: validator` (unless overridden by an explicit `agent:` property). This is a natural extension — the reason you want fresh eyes is independence, and the validator template enforces that independence structurally.

The commission skill should generate `fresh: true` on validation-type stages (it already does) and the FO should resolve `fresh: true` stages to `validator` agent type.

### 7. Commission Skill Changes

The commission skill (`skills/commission/SKILL.md`) needs to:
- Include the `validator.md` template in its generated output (alongside `ensign.md` and any lieutenants)
- No changes to how `fresh: true` is generated — it already marks validation stages

## Acceptance Criteria

1. A `templates/validator.md` exists with full tools (Read, Write, Edit, Bash, Glob, Grep, SendMessage), fully static (no template variables)
2. The first-officer template resolves `fresh: true` stages to `validator` agent type when no explicit `agent:` is set
3. The first-officer template includes a validation rejection flow that dispatches an implementer for fixes and a fresh validator for re-validation
4. The validation rejection flow enforces a 3-cycle limit before escalation
5. The validator template explicitly forbids modifying implementation code but permits creating/modifying test files and the entity file
6. The commission skill generates `validator.md` alongside other agent files
7. Existing validation stage definitions in README.md (with `fresh: true`) work without modification — no new stage properties required
8. The ensign template is unchanged

## Stage Report: ideation

- [x] Problem statement refined — concrete example of validator independence violation
  Added specific scenario: validator finds missing error handling, fixes it, then validates own fix
- [x] Agent lifecycle design — keep-alive vs respawn, with trade-offs
  Chose respawn-on-demand: matches existing "always dispatch fresh" principle, avoids resource waste across gate reviews
- [x] Validator agent design — separate type (restricted tools) vs behavioral instructions
  Chose separate `validator.md` template: tools limited to Read/Bash/Glob/Grep/SendMessage, no Write/Edit — runtime enforcement over behavioral suggestion
- [x] Communication and iteration protocol — how findings flow, fix cycle limits
  FO-mediated relay: validator reports REJECTED → captain reviews at gate → FO dispatches implementer with findings → fresh validator re-validates. 3-cycle limit before escalation.
- [x] Changes to first-officer template specified — what sections change and how
  Three areas: agent type resolution (fresh:true implies validator), validation rejection flow (new section), validation instructions update (read-only framing)
- [x] Changes to ensign/validator template specified
  New `templates/validator.md` with restricted tools and explicit no-fix rules. Fully static (no template variables) per #063. Ensign template unchanged.
- [x] Acceptance criteria written — concrete, testable
  9 criteria covering template existence, tool restrictions, FO behavior, commission skill, and backward compatibility

### Summary

Designed a validation-implementation pairing model where the validator is a distinct agent type (`validator.md`) with restricted tools (no Write/Edit) that can only read, test, and judge. The FO mediates all communication: when validation rejects, the FO dispatches an implementer to fix and a fresh validator to re-check, with a 3-cycle escalation limit. The key architectural decision was respawn-over-keep-alive for the implementation agent — it matches the existing "always dispatch fresh" principle and avoids resource waste during gate reviews. `fresh: true` now implies `agent: validator` as a natural extension of its independence guarantee.

## Stage Report: implementation

- [x] `templates/validator.md` exists — static, tools restricted to Read/Bash/Glob/Grep/SendMessage, explicit no-fix rules
  Created at `templates/validator.md` with tools frontmatter `Read, Bash, Glob, Grep, SendMessage`, no Write/Edit. Rules section explicitly forbids file creation/editing, commits (except stage report), bug fixing, and using Bash to write files.
- [x] FO dispatch resolves `fresh: true` to `validator` agent type
  Updated Dispatch step 4 in `templates/first-officer.md`: "If no `agent` property: default to `validator` when the stage has `fresh: true`, otherwise default to `ensign`."
- [x] FO validation instructions updated for read-only validator role
  Prepended "You are a validator. You read and judge — you do NOT write code or fix bugs." and appended relay instructions to the validation instructions paragraph.
- [x] FO validation rejection flow added — implementer dispatch, fresh re-validation, 3-cycle limit
  Added `## Validation Rejection Flow` section between "Completion and Gates" and "Merge and Cleanup" with 5-step protocol: check cycle count (>=3 escalates), shut down validator, dispatch implementer with findings, increment cycle count, dispatch fresh validator.
- [x] Commission skill copies validator.md alongside other agents
  Added step 2e2 in `skills/commission/SKILL.md` to copy `validator.md`, updated generation checklist, updated Phase 3 announcement, and updated lieutenant agent warnings to exclude `validator`.
- [x] All changes committed
  Commit `0c15b48` on branch `ensign/val-pairing`.

### Summary

Implemented the validation-implementation pairing by creating a `templates/validator.md` with restricted tools (no Write/Edit) and explicit no-fix rules, updating the first-officer template with `fresh: true` -> `validator` agent type resolution, read-only validation instructions, and a full rejection flow with 3-cycle escalation, and updating the commission skill to generate the validator agent file. The ensign template was left unchanged as specified.

## Stage Report: validation

- [x] Validator template — correct tools restriction, no Write/Edit, explicit no-fix rules
  Tools frontmatter is `Read, Bash, Glob, Grep, SendMessage`. Rules section forbids file creation/editing, commits (except stage report), bug fixing, and using Bash to write files.
- [x] FO dispatch — `fresh: true` defaults to `validator`
  Dispatch step 4: "default to `validator` when the stage has `fresh: true`, otherwise default to `ensign`" (first-officer.md line 30).
- [x] FO validation instructions — read-only validator role clarified
  Validation instructions paragraph opens with "You are a validator. You read and judge — you do NOT write code or fix bugs." and closes with relay instructions (first-officer.md line 44).
- [x] FO rejection flow — complete 5-step protocol with 3-cycle limit
  `## Validation Rejection Flow` section at lines 75-93 with: cycle count check (>=3 escalates), shut down validator, dispatch implementer with findings, increment cycle count and dispatch fresh validator, repeat through gate flow.
- [x] Commission skill — validator.md generation included
  Step 2e2 copies validator.md, generation checklist includes it, Phase 3 announcement lists it, lieutenant warnings exclude it (SKILL.md lines 417-427, 454, 483, 460).
- [x] All templates static — zero `__VAR__` markers
  `grep __ templates/` returns only Python dunders (`__file__`, `__name__`) in the status script. No template variable markers in any template including validator.md.
- [x] All 9 acceptance criteria verified
  AC1: validator.md exists, tools correct, static. AC2: FO dispatch resolves fresh:true to validator. AC3: rejection flow with implementer+re-validation. AC4: 3-cycle limit. AC5: explicit no-fix rules. AC6: Bash restricted to tests/read-only. AC7: commission generates validator.md. AC8: existing validation stage (fresh:true, no agent:) works without modification. AC9: ensign.md has zero diff from main.

### Recommendation

PASSED

### Findings

All criteria are met. The implementation correctly creates a validator agent with restricted tools (no Write/Edit), updates the first-officer template with fresh:true-to-validator dispatch logic, adds a complete validation rejection flow with 3-cycle escalation, updates the commission skill to generate the validator agent, and leaves the ensign template unchanged.

### Summary

Validated the validation-implementation pairing implementation against all 9 acceptance criteria. Every artifact was verified: validator template has correct tool restrictions and explicit no-fix rules, the first-officer template correctly resolves fresh:true to validator agent type and includes a complete 5-step rejection flow with 3-cycle limit, the commission skill generates the validator agent, and the ensign template is unchanged. All templates are fully static with zero template variable markers.

## Stage Report: implementation (fix cycle 1)

- [x] Test fixture created at `tests/fixtures/rejection-flow/`
  Pipeline README with 4 stages (backlog gated, implementation worktree, validation worktree+fresh+gated, done). Entity pre-set to `status: implementation` with buggy `math_ops.py` (subtracts instead of adding). Tests at `tests/test_add.py` verify correct addition and fail against the buggy implementation.
- [x] Test script created at `tests/test-rejection-flow.sh`
  Three-phase E2E test: fixture setup with agent generation, FO run via `claude -p` with haiku/$5 budget and prompt instructing captain-role approval of REJECTED verdicts, validation of Agent() calls in stream-json log. Checks: (1) FO dispatched a validator for validation stage, (2) REJECTED found in entity file or FO output, (3) ensign implementer dispatched after validator.
- [x] Testing Resources table updated in `docs/plans/README.md`
  Added rejection flow test row to the table and added "rejection flow" to the E2E test list paragraph.

### Summary

Added a lightweight E2E test for the validation rejection flow. The test fixture contains a deliberate bug (subtract instead of add) that the validator will detect, and the test script verifies the full relay: validator dispatched for fresh:true stage, REJECTED recommendation produced, implementer dispatched after rejection. The test prompt simulates captain approval of the REJECTED verdict to allow the rejection flow to proceed without interactive input.

Additionally, updated the FO rejection flow from serial to parallel model: validator persists across fix cycles, implementer messages validator directly via SendMessage, FO only re-enters at gate reviews. Updated the task design section (### 3. Communication and Iteration Protocol) and the FO validation instructions to match.

## Stage Report: validation (re-check after fix cycle 1)

- [x] E2E test fixture valid — deliberate bug, test files, pipeline structure
  `tests/fixtures/rejection-flow/` has: README with 4-stage pipeline (backlog gated, implementation worktree, validation worktree+fresh+gated, done), `buggy-add-task.md` at `status: implementation` with a completed implementation stage report, `math_ops.py` with `return a - b` (deliberate bug), `tests/test_add.py` with 3 test cases that assert correct addition (will fail against the buggy implementation).
- [x] E2E test script checks the right things — validator dispatch, REJECTED, implementer dispatch
  `tests/test-rejection-flow.sh` has 3 phases: (1) fixture setup with FO template expansion and agent file generation, (2) FO run via `claude -p` with haiku/$5 budget and stream-json logging, (3) validation parsing agent calls from the log and checking: `subagent_type=validator` present, REJECTED in entity file or FO text output, `subagent_type=ensign` dispatched after the validator.
- [x] FO rejection flow uses parallel model — validator persists, direct peer messaging
  `templates/first-officer.md` lines 75-93: Step 2 says "Ensure implementer is alive" (not "shut down and redispatch"), Step 3 says "Ensure validator is alive — Keep the existing validator running", Step 4 says "Implementer commits fixes and messages the validator directly via SendMessage." No "shut down validator" or "dispatch fresh validator" for normal cycles — fresh dispatch only as crash/session-boundary fallback. Validation instructions (line 44) include "If an implementer messages you with fixes, re-run tests and update your stage report."
- [x] Validator template has Write/Edit tools
  `templates/validator.md` frontmatter: `tools: Read, Write, Edit, Bash, Glob, Grep, SendMessage`. Write and Edit are present, enabling the validator to create/modify test files and write the entity stage report.
- [x] All templates static — zero `__VAR__` markers
  `grep '__[A-Z][A-Z_]*__' templates/` returns zero matches. All templates (first-officer.md, ensign.md, validator.md) are free of double-underscore template variable markers.
- [x] PASSED recommendation

### Summary

Validated the implementer's fix cycle 1 additions: E2E test fixture at `tests/fixtures/rejection-flow/` correctly sets up a deliberate bug scenario with test coverage, the test script at `tests/test-rejection-flow.sh` verifies the full rejection relay (validator dispatch, REJECTED output, implementer dispatch after rejection), the FO rejection flow in `templates/first-officer.md` uses the parallel model (validator persists, implementer messages validator directly, FO observes), and the validator template has Write/Edit tools. All templates remain fully static with zero template variable markers.
