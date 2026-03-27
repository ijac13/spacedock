---
id: 061
title: Pair implementation and validation agents — validator judges, implementer fixes
status: ideation
source: CL
started: 2026-03-27T22:45:00Z
completed:
verdict:
score:
worktree:
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

**Flow when validation finds issues:**

```
Validator finds bug
  → Validator writes finding in stage report (REJECTED recommendation)
  → Validator sends completion message to FO
  → FO presents stage report at gate (validation has gate: true)
  → Captain reviews: approve REJECTED, or reject (redo validation)
  → If captain agrees findings are valid:
      → FO dispatches implementation agent in worktree with findings
      → Implementer fixes, commits, sends completion
      → FO dispatches fresh validator to re-validate
      → Cycle repeats
```

Key design points:

- **FO mediates all communication.** No direct validator-to-implementer messaging. The FO is the dispatcher; it relays findings as dispatch context. This keeps the FO as the single source of truth for entity state.
- **Iteration limit: 3 fix cycles** before escalation to captain. The FO tracks cycle count in the entity file body (a `### Validation Cycles` section or similar). After 3 cycles of rejected validation, the FO reports to the captain with a summary of all findings and asks for direction.
- **Implementer disagreement:** Not an issue in this model. The implementer gets findings as dispatch context, not as a debate. If the finding is invalid, the implementer fixes the actual issue (or does nothing if there's nothing to fix), and the next validation pass should reflect the true state.
- **Each validation dispatch is fresh.** The validator never accumulates state from prior cycles — each dispatch gets the current code state and the current acceptance criteria.

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
2. Shut down the validator (existing behavior).
3. Dispatch an implementation agent (ensign or the agent type from the prior implementation stage) into the same worktree with findings from the validation stage report.
4. When the implementer completes, dispatch a fresh validator.
5. Increment cycle count.

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

1. A `templates/validator.md` exists with tools limited to Read, Bash, Glob, Grep, SendMessage (no Write, no Edit), fully static (no template variables)
2. The first-officer template resolves `fresh: true` stages to `validator` agent type when no explicit `agent:` is set
3. The first-officer template includes a validation rejection flow that dispatches an implementer for fixes and a fresh validator for re-validation
4. The validation rejection flow enforces a 3-cycle limit before escalation
5. The validator template explicitly forbids file creation/editing and code fixes
6. The validator template's Bash instructions restrict usage to test execution and read-only commands
7. The commission skill generates `validator.md` alongside other agent files
8. Existing validation stage definitions in README.md (with `fresh: true`) work without modification — no new stage properties required
9. The ensign template is unchanged

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
