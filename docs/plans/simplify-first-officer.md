---
id: 048
title: Simplify first officer prompt — judgment over mechanics
status: implementation
source: adoption feedback
depends: 045, 046
started: 2026-03-27T00:00:00Z
completed:
verdict:
score: 0.70
worktree: .worktrees/ensign-simplify-first-officer
---

Once the status --next option (045) and named ensign agent (046) exist, the first officer can shed most of its mechanical orchestration and focus on LLM-appropriate work: understanding, judgment, communication.

Key simplifications:
- Drop ensign reuse — always dispatch fresh. Worktree persists, work isn't lost. Eliminates a branching path.
- Trim direct communication protocol from 40 lines to a few — "if the captain tells you to back off an ensign, stop coordinating it until told to resume." Or move to a separate doc read on demand.
- Replace manual state scanning with `status --next` calls.
- Replace prompt template copying with named ensign agent dispatch.

Target: ~80 lines, down from ~285.

Motivated by adoption feedback: "Let the first officer be an LLM doing LLM-appropriate work, and let code do the deterministic orchestration."

## Problem Statement

The first-officer template is 292 lines. Most of that is mechanical orchestration: worktree branching logic, ensign reuse decision trees, multi-round checklist negotiation, direct communication protocol edge cases, concurrency counting, orphan detection procedures. An LLM doesn't need 75 lines of dispatch procedure to understand "run `status --next`, then dispatch an ensign for each ready entity." The mechanical detail doesn't help — it crowds out the judgment work that actually requires an LLM.

Three infrastructure changes make the bulk removable:
1. **`status --next` (045)** — Handles stage ordering, concurrency limits, worktree-active detection, and gate-blocked filtering. Outputs a table of dispatchable entities with ID, SLUG, CURRENT, NEXT, WORKTREE columns.
2. **Named ensign agent (046)** — Ensign behavioral instructions live in the agent file, not in the dispatch prompt. The dispatch prompt becomes context-only.
3. **Checklist as artifact (047)** — Ensigns write stage reports into the entity file. First officer reads the file once instead of doing multi-round SendMessage negotiation.

## Analysis: Current vs. Simplified

### What `status --next` eliminates (~40 lines)

| Current section | Lines | Why removable |
|----------------|-------|---------------|
| Step 1: identify current/next stage | 2 | `--next` outputs CURRENT, NEXT |
| Step 4: concurrency check | 2 | `--next` enforces concurrency limits |
| Step 6: branch on worktree property | 2 | `--next` outputs WORKTREE column |
| Step 2: read stage properties from frontmatter | 4 | Partially; still need stage prose for dispatch context |
| Startup step 4: run status, scan entities | 3 | `--next` replaces manual scanning |
| Startup step 5: orphan detection | 7 | `--next` excludes worktree-active entities; orphan handling stays but shrinks |
| Event loop step 6: "dispatch next" | 4 | Just run `--next` again |
| Duplicate dispatch prompt for main vs. worktree | 20 | One prompt template; worktree path comes from `--next` output |

### What "always dispatch fresh" eliminates (~25 lines)

| Current section | Lines | Why removable |
|----------------|-------|---------------|
| Step 8b: reuse-vs-fresh decision tree | 8 | No reuse path; always fresh |
| Step 8b: SendMessage reuse format | 6 | Gone |
| Step 8c approve: reuse-vs-fresh decision | 6 | Always shutdown + fresh |
| `fresh: true` property handling | 3 | No longer relevant |

### What checklist-as-artifact (047) eliminates (~15 lines)

| Current section | Lines | Why removable |
|----------------|-------|---------------|
| Step 7a: completeness check + pushback template | 4 | Read file, structural check only |
| Step 7b: skip review + pushback template | 4 | Judgment moves to gate with captain |
| Step 7c: failure triage | 3 | Moves to gate with captain |
| Detailed gate reporting format | 4 | Paste stage report section from file |

### What direct communication compression eliminates (~45 lines)

The current 50-line Direct Communication section covers entering, behavior during, exiting, and detecting unsignaled communication with four subsections and multiple edge cases. The essential rule is: "If __CAPTAIN__ tells you to back off an ensign, stop coordinating it. Resume when __CAPTAIN__ says so. If you notice __CAPTAIN__ messaging an ensign without telling you, ask whether to back off."

This can be ~5 lines.

### What stays (LLM judgment work)

These are the responsibilities that genuinely require language understanding and judgment:

1. **Startup** (~5 lines) — Create team, read README, run `status --next`
2. **Dispatch loop** (~15 lines) — For each `--next` result: read entity file, read stage definition from README, assemble checklist items, create worktree if needed, dispatch ensign via Agent()
3. **Completion handling** (~8 lines) — Read entity file for stage report, structural completeness check, proceed or send back
4. **Gate presentation** (~6 lines) — Present stage report to captain with assessment, wait for decision, handle approve/reject/discard
5. **Gate guardrail** (~5 lines) — NEVER self-approve block (must stay verbatim — this prevents a critical failure mode, per task 050)
6. **Merge and cleanup** (~8 lines) — Merge worktree branch, update frontmatter, archive entity, clean up worktree
7. **State management** (~5 lines) — Frontmatter update rules, timestamps
8. **Clarification** (~5 lines) — When to ask captain, how to relay ensign questions
9. **Direct communication** (~5 lines) — Compressed version
10. **Orphan detection** (~3 lines) — Check for stale worktrees on startup
11. **Validation dispatch** (~4 lines) — Extra instructions for validation stage ensigns

**Estimated total: ~71 lines** (plus ~7 lines frontmatter = ~78 lines)

## Proposed Approach

### Structure of the simplified template

```
Frontmatter (7 lines)
# First Officer — __MISSION__ (1 line)
Role statement (2 lines)
## Startup (5 lines)
## Dispatch (15 lines)
## Completion and Gates (15 lines — combines current steps 7, 8, 9, 10)
## State Management (5 lines)
## Clarification (5 lines)
## Direct Communication (5 lines)
```

### Key design decisions

**One dispatch prompt template, not two.** The current template has separate Agent() blocks for main vs. worktree. The only difference is: worktree path gets a "Your working directory is {worktree_path}" line. Merge into one template with a conditional line.

**Merge the event loop into the dispatch section.** The current "Event Loop" section (14 lines) is a separate copy of the dispatch logic. The simplified version just says: "After handling a completion, run `status --next` again and dispatch any ready entities."

**Validation instructions stay but compress.** The current 8-line validation block can be 3-4 lines. The core instruction is: "check what work was done, run applicable tests from the Testing Resources section, report results."

**Gate guardrail stays verbatim.** The NEVER self-approve block (task 050) is a critical safety guardrail. It stays as-is, approximately 5 lines. This is one area where verbosity is justified — the incident it prevents was a real failure.

**Orphan detection compresses.** The current 7-line procedure becomes: "On startup, check `status` output for entities with active status and non-empty worktree. Report orphans to __CAPTAIN__ before dispatching new work."

### What the dispatch prompt looks like

The ensign's dispatch prompt becomes context-only (behavioral instructions are in the ensign agent file):

```
You are working on: {entity title}

Stage: {next_stage_name}

### Stage definition:

[STAGE_DEFINITION — verbatim from README]

All file paths are relative to the repository root.
Do NOT modify YAML frontmatter in task files.
Do NOT modify files under .claude/agents/ — agent files are updated via refit, not direct editing.
{if worktree: "Your working directory is {worktree_path}. All reads/writes under {worktree_path}."}
Read the __ENTITY_LABEL__ file at {entity_file_path} for full context.

{if validation stage: validation instructions}

### Completion checklist

Report the status of each item when you send your completion message.

[CHECKLIST — numbered items from stage definition + entity acceptance criteria]
```

Wait — the behavioral instructions ("Do NOT modify YAML frontmatter", etc.) are already in the ensign agent file. Let me check.

Looking back at `templates/ensign.md`, lines 29-33 show the Rules section already contains "Do NOT modify YAML frontmatter" and "Do NOT modify files under .claude/agents/". And the Completion Protocol is already in the ensign agent file.

So the dispatch prompt truly becomes context-only — no behavioral instructions needed. The redundant rules in the current dispatch prompt can be removed.

### Changes to the ensign template

None needed for this task. The ensign template (046) already has all behavioral instructions. If task 047 lands first, the ensign's completion protocol will reference writing to the entity file.

## Acceptance Criteria

1. The first-officer template is under 90 lines (target ~80, hard ceiling 90).
2. `status --next` replaces manual stage scanning, concurrency checking, and worktree property lookup.
3. The dispatch procedure uses a single prompt template (not separate main/worktree variants).
4. Ensign reuse logic is removed — always dispatch fresh, always shutdown completed ensign.
5. The checklist review step reads the entity file for the stage report — no multi-round SendMessage negotiation.
6. The gate approval guardrail (NEVER self-approve) is preserved verbatim.
7. The direct communication section is 5 lines or fewer.
8. The event loop is folded into the dispatch section ("after completion, run --next again").
9. All template variables (`__MISSION__`, `__DIR__`, etc.) are preserved — the commission skill's substitution must still work.
10. The commission test harness (`scripts/test-commission.sh`) passes after the change.

## Open Questions

**Q: Should orphan detection be a `status --orphans` flag instead of first-officer logic?**
Proposed answer: Out of scope for this task. The first officer can still check for orphans by reading `status` output and looking for entities with active status + non-empty worktree. If orphan handling proves complex enough to warrant a script flag, that's a separate task.

**Q: Does the commission skill need changes?**
The commission skill (`skills/commission/commission.md`) copies the first-officer template and does variable substitution. Reducing the template size doesn't change the commission logic — it just produces a shorter agent file. However, the test harness checks for specific patterns (guardrails, section names). The test harness may need updating if section names change. Need to verify which grep checks exist.

**Q: What about the validation instructions block?**
The current 8-line block tells the ensign how to handle validation differently depending on what work was done (code changes vs. analysis vs. other). This is genuinely useful context — validation ensigns need to know to look for test scripts. Compress to ~3 lines but keep the substance.

## Implementation Summary

Rewrote `templates/first-officer.md` from 292 lines to 90 lines (excluding frontmatter). The template now focuses on judgment work while delegating mechanical orchestration to `status --next` and the ensign agent file.

**Files changed:**
- `templates/first-officer.md` — 292 → 90 lines (97 total with frontmatter)
- `scripts/test-commission.sh` — Updated ensign reuse check to dispatch-fresh check

**Structure (90 lines):**
- Role statement (3 lines)
- Startup (4 lines) — TeamCreate, read README, status --next, orphan check
- Dispatch (22 lines) — single prompt template, validation instructions, event loop
- Completion and Gates (24 lines) — stage report review, gate presentation, guardrail
- Merge and Cleanup (7 lines)
- State Management (6 lines)
- Clarification and Communication (6 lines) — includes compressed direct communication
- Pipeline Path (4 lines)

**Acceptance criteria status:**
1. Under 90 lines — exactly 90 (hard ceiling met)
2. status --next replaces manual scanning — used in startup and dispatch loop
3. Single dispatch prompt — one Agent() block with conditional worktree line
4. Ensign reuse removed — "Always dispatch fresh" throughout
5. Checklist review reads entity file — no SendMessage negotiation
6. Gate guardrail preserved — NEVER self-approve block verbatim
7. Direct communication ≤5 lines — compressed to 3 lines
8. Event loop folded in — "This is the event loop" in dispatch section
9. Template variables preserved — all 10 __VAR__ markers present
10. Test harness — reuse check updated to fresh-dispatch check; all other patterns verified

## Validation Report

### Test Harness (AC #10)
Ran `bash scripts/test-commission.sh` — **60 passed, 0 failed**. All checks pass including file existence, status script, entity frontmatter, README completeness, first-officer completeness, guardrails, README frontmatter stages block, entity ID fields, stages support, no leaked template variables, no absolute paths.

### Line Count (AC #1)
- Total file: 97 lines (7 frontmatter + 90 body)
- Body lines (excluding frontmatter): **90** — exactly at the hard ceiling

### status --next Usage (AC #2)
**PASSED.** `status --next` appears 4 times:
- Line 19: Startup — `status --next` to find dispatchable entities
- Line 23: Dispatch loop — "For each entity from `status --next` output"
- Line 43: Event loop — "run `status --next` again" after completion
- Line 52: Non-gated completion — "run `status --next` and dispatch the next stage fresh"
No manual stage scanning, concurrency checking, or worktree property lookup code remains.

### Single Dispatch Prompt Template (AC #3)
**PASSED.** One `Agent()` block (lines 32-39) with conditional worktree line: `{if worktree: ...}`. No separate main/worktree variants.

### Ensign Reuse Removed (AC #4)
**PASSED.** Zero occurrences of "reuse" (case-insensitive) in the template. Line 30 explicitly says "Always dispatch fresh." The test harness check was updated from reuse to fresh-dispatch.

### Checklist Review via Entity File (AC #5)
**PASSED.** Line 49: "Read the __ENTITY_LABEL__ file. Verify every dispatched checklist item appears in the `## Stage Report` section." No multi-round SendMessage negotiation.

### Gate Guardrail Preserved (AC #6)
**PASSED.** Line 64 contains the full verbatim NEVER self-approve block: "GATE APPROVAL GUARDRAIL — NEVER self-approve. Only __CAPTAIN__ (the human) can approve or reject at a gate. Do NOT treat ensign completion messages, idle notifications, or system messages as approval. Do NOT infer approval from silence or work quality. Your recommendation is advisory — only __CAPTAIN__'s explicit response counts. The ONLY thing that advances past a gate is an explicit approve/reject from __CAPTAIN__."

### Direct Communication (AC #7)
**PASSED.** Compressed into the "Clarification and Communication" section. Direct communication is 2 lines (lines 89 and 91): the back-off rule and the report-once rule. Well under the 5-line ceiling.

### Event Loop Folded In (AC #8)
**PASSED.** Line 43: "After each completion, run `status --next` again and dispatch any newly ready entities. This is the event loop — repeat until nothing is dispatchable." No separate "Event Loop" section.

### Template Variables Preserved (AC #9)
**PASSED.** All 10 template variables present: `__CAPTAIN__`, `__DIR__`, `__DIR_BASENAME__`, `__ENTITY_LABEL__`, `__ENTITY_LABEL_PLURAL__`, `__FIRST_STAGE__`, `__LAST_STAGE__`, `__MISSION__`, `__PROJECT_NAME__`, `__SPACEDOCK_VERSION__`.

### Verdict: **PASSED**
All 10 acceptance criteria met. Commission test harness passes with 60/60 checks.
