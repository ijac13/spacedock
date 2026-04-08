---
id: 097
title: FO guardrail on repo edits before implementation dispatch
status: ideation
source: "#30"
started: 2026-04-08T15:43:14Z
completed:
verdict:
score:
worktree:
issue: "#30"
pr:
---

The first officer should not edit code, tests, or shared assets outside of a proper worktree dispatch cycle. Changes to repo content must happen in a checked-out worktree owned by a dispatched worker, after the captain approves moving the entity into implementation.

This includes scaffolding files like mods, which should go through refit rather than direct FO edits.

## Problem

The FO references define what the first officer **does** own on main (frontmatter via `status --set`, the `### Feedback Cycles` section, archive moves) but never explicitly state what the FO must **not** touch. This gap lets an FO drift into editing code, tests, mods, or other implementation artifacts directly on main — before a worktree dispatch cycle even begins.

Concrete examples of the failure mode (from issue #30):
- FO updates test files on main during ideation, before an ensign is dispatched to a worktree
- FO creates or modifies a mod file (`_mods/`) directly on main instead of going through refit
- FO edits an orchestrator script on main as part of "planning" work

The root cause is that existing guardrails are specified as positive permissions (what the FO may write) rather than also including explicit prohibitions on everything else. The FO can rationalize "this is just a small helper change" because no rule says it cannot.

## Proposed Approach

Add an explicit **FO write scope** section to `references/first-officer-shared-core.md` (the authoritative shared core) and a corresponding brief rule to `references/code-project-guardrails.md`. The guardrail should:

1. Define the **exhaustive list** of what the FO may write on main:
   - Entity frontmatter (via `status --set`)
   - New entity files (seed task creation: frontmatter + brief description body)
   - The `### Feedback Cycles` section in entity bodies
   - Archive moves (`_archive/`)
   - State-transition commits (dispatch, advance, merge boundary)

2. Define everything else as **off-limits** for direct FO edits on main:
   - Code files (any language)
   - Test files
   - Mod files (`_mods/`) — these go through refit or a dispatched worker
   - Scaffolding files (`skills/`, `agents/`, `references/`, `plugin.json`, workflow `README.md`) — already covered by the scaffolding guardrail, but reinforce by cross-reference
   - Entity body content beyond the Feedback Cycles section (stage reports, design content — these belong to workers)

3. State the enforcement principle: **If it would change the behavior or content of the repo beyond entity state tracking, it must go through a dispatched worker in a worktree.**

### Where to put it

- **Primary location:** New subsection `## FO Write Scope` in `references/first-officer-shared-core.md`, placed after the existing `## State Management` section (which already says the FO owns frontmatter). This keeps all FO authority rules together.
- **Secondary location:** A one-line cross-reference in `references/code-project-guardrails.md` under the `## Paths and File Scope` section, pointing to the shared core for the full rule.

### What NOT to do

- Do not add runtime enforcement (pre-commit hooks, etc.) — this is a documentation/instruction guardrail, not a technical enforcement mechanism. The FO is an LLM following instructions; the fix is to make the instructions unambiguous.
- Do not change the ensign or worker references — they already have the right restrictions. The gap is purely on the FO side.

## Acceptance Criteria

1. `references/first-officer-shared-core.md` contains a `## FO Write Scope` section that exhaustively lists what the FO may write on main, and explicitly prohibits everything else.
   - **Test:** Grep the file for the section heading and verify it contains both an allow-list and a prohibition statement. Static content check.

2. `references/code-project-guardrails.md` contains a cross-reference to the FO write scope rule under `## Paths and File Scope`.
   - **Test:** Grep the file for the cross-reference. Static content check.

3. The allow-list includes: entity frontmatter, new entity files, Feedback Cycles section, archive moves, state-transition commits.
   - **Test:** Grep the new section for each of these items. Static content check.

4. The prohibition explicitly names: code files, test files, mod files, scaffolding, and entity body content (except Feedback Cycles).
   - **Test:** Grep the new section for each of these items. Static content check.

5. The wording uses the enforcement principle: changes that affect repo behavior/content beyond state tracking must go through a dispatched worker.
   - **Test:** Grep for the principle statement. Static content check.

6. Existing FO behavior is not broken — the allow-list must cover everything the FO currently does legitimately (frontmatter updates, entity creation, feedback cycle tracking, archive moves).
   - **Test:** Review the full shared core and confirm every existing FO write operation is covered by the allow-list. Manual review during validation.

## Test Plan

All acceptance criteria are testable via static content checks (grep against the modified reference files). No E2E tests are needed because this is a documentation/instruction change, not a code change. The guardrail is enforced by LLM instruction-following, not by runtime mechanisms.

Validation approach:
- For criteria 1-5: grep-based assertions on file content
- For criterion 6: manual cross-reference audit of `first-officer-shared-core.md` to confirm no legitimate FO write is excluded

Estimated complexity: Low. Two file edits (one new section, one cross-reference line).

## Edge Cases

- **Entity file creation:** The FO creates new entity files on main when seeding tasks from backlog. This is legitimate state management (not implementation work) and must be in the allow-list. The new entity contains frontmatter and a brief seed description — body content beyond that belongs to workers.
- **Frontmatter updates via `status --set`:** Already explicitly owned by FO. No change needed.
- **Mod execution at lifecycle hooks:** The FO *runs* mods (startup, idle, merge hooks) but must not *write* them. Running mods is orchestration; writing mods is implementation. The guardrail should clarify this distinction.
- **Archive moves:** The FO moves entity files to `_archive/`. This is state management, not content editing. Already legitimate.
- **Feedback Cycles section:** The FO writes this section in entity bodies on main. This is the one exception to "entity body belongs to workers" and must be explicitly called out in the allow-list.

## Stage Report

1. Research the current FO guardrails and identify what's missing regarding repo edits before dispatch — DONE
   Reviewed `first-officer-shared-core.md`, `code-project-guardrails.md`, `claude-first-officer-runtime.md`, and `ensign-shared-core.md`. Found that existing rules define positive permissions (what the FO owns) but lack explicit prohibitions on everything else.

2. Clarify the problem statement with concrete examples of what goes wrong — DONE
   Problem section documents three concrete failure modes from issue #30 and identifies the root cause (positive-only permission model without explicit prohibitions).

3. Propose approach — where and how the guardrail should be documented/enforced — DONE
   Approach adds a `## FO Write Scope` section to the shared core (after State Management) with an exhaustive allow-list and explicit prohibition. Cross-reference in code-project-guardrails.md. Documentation-only change, no runtime enforcement.

4. Define acceptance criteria with test plan for each — DONE
   Six acceptance criteria, each with a test method. All testable via grep-based static content checks except criterion 6 which requires manual cross-reference audit. No E2E tests needed.

5. Consider edge cases (entity file creation, frontmatter updates, mod execution, archive moves, Feedback Cycles) — DONE
   Five edge cases documented: entity creation (allow-listed as state management), frontmatter updates (already covered), mod execution vs. writing (clarify distinction), archive moves (already legitimate), Feedback Cycles section (explicit exception to entity-body-belongs-to-workers rule).
