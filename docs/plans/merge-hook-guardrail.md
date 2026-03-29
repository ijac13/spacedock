---
id: 077
title: Add merge hook guardrail to prevent skipping mod hooks at merge time
status: implementation
source: 073 merge incident — FO skipped pr-merge hook and went straight to local merge
started: 2026-03-29T19:25:00Z
completed:
verdict:
score: 0.75
worktree: .worktrees/ensign-077-merge-guardrail
---

When the captain approved 073 at the validation gate, the FO went straight to `git merge` without running the pr-merge mod's merge hook. The hook should have presented a PR summary and waited for push approval. Instead the entity was locally merged, archived, and cleaned up — bypassing the PR workflow entirely.

## Root cause

The merge hook step is a single sentence embedded in one of 5 branching paths in the gate approval flow:

> "Run merge hooks (from `_mods/`) here, before any status change."

The FO had been doing local merges all session (072 had no PR, 068/059 were startup PR detections). The local-merge pattern was grooved in, and the merge hook step didn't interrupt the flow.

## Proposed fix

Add a bold guardrail (matching the GATE APPROVAL and GATE IDLE guardrail pattern) that fires before any merge operation. Pull it out of the branching paths and make it a standalone check.

Also consider: a pre-merge checklist in the approve+terminal path to force the FO to verify hooks before proceeding.

## Ideation

### All merge code paths in the FO template

**Path 1 — Gate Approve + terminal + worktree (line 113-116):**
The primary merge path. Steps: shut down agent, run merge hooks, check `pr` field, fall through to Merge and Cleanup if no PR. This is where the 073 incident happened — the hook instruction is a subordinate bullet inside a branching flow, easy to skip.

**Path 2 — Gate Approve + terminal + no worktree (line 117):**
Falls directly to Merge and Cleanup. No merge hooks mentioned inline — relies on step 1 of Merge and Cleanup to fire them. This path has no code to push (no worktree), so PR-creating hooks are a no-op, but the hooks should still fire for consistency.

**Path 3 — Merge and Cleanup section (lines 146-149):**
The shared merge section reached from Paths 1 and 2. Step 1 says "Run merge hooks." This is a redundant safety net for Path 1, and the only hook mention for Path 2. The problem: in 073, the FO skipped to step 2 (local merge) without executing step 1.

**Path 4 — After-completion PR detection (lines 70-71):**
Detects merged PRs after each agent completion. Advances entity to terminal, archives, cleans up. This is post-PR advancement — the merge hook already fired when the PR was created. No guardrail needed here.

**Path 5 — Startup PR detection (pr-merge startup hook):**
Same as Path 4 but at session start. Post-PR advancement, not a hook point. No guardrail needed.

### Proposed guardrail

Add a standalone **MERGE HOOK GUARDRAIL** in the same bold ALL-CAPS pattern as the existing GATE APPROVAL GUARDRAIL and GATE IDLE GUARDRAIL. The guardrail should be placed in the "Merge and Cleanup" section as an interrupter before step 1, since all merge paths funnel through this section (or should).

**Proposed wording:**

> **MERGE HOOK GUARDRAIL — BEFORE any merge operation (local or otherwise), you MUST run all registered merge hooks from `_mods/`.** Do NOT proceed to `git merge`, archival, or status advancement until all merge hooks have completed and you have acted on their results. If a merge hook created a PR, do NOT perform a local merge — set the `pr` field and stop. Check `{workflow_dir}/_mods/*.md` for `## Hook: merge` sections. If no merge hooks are registered, proceed with default local merge.

**Placement rationale:**

Put it in one place: at the top of "Merge and Cleanup," right before step 1. The reason: every merge path should funnel through this section. The gate approval path (lines 113-116) currently has its own inline hook instruction, which creates two places to maintain and two places where the instruction can be missed. Instead:

1. Remove the inline "Run merge hooks" bullet from the gate approval path (line 115).
2. Make the gate approval path explicitly say "Fall through to Merge and Cleanup" for the terminal+worktree case (same as it already says for terminal+no-worktree).
3. Place the guardrail at the top of Merge and Cleanup so it's impossible to miss.

This consolidation means there's exactly one code path for merge hooks, not two.

Additionally, update the gate approval "Approve + terminal + worktree" path to:
1. Shut down the agent.
2. Check the entity's `pr` field on main. If `pr` is already set (from a previous push), do NOT merge — entity stays at current stage, report PR is pending.
3. If `pr` is NOT set, fall through to Merge and Cleanup (which fires hooks and handles everything).

### Acceptance criteria

1. A bold ALL-CAPS MERGE HOOK GUARDRAIL exists in the Merge and Cleanup section of the FO template, matching the style of GATE APPROVAL GUARDRAIL and GATE IDLE GUARDRAIL.
2. All merge code paths funnel through a single hook execution point (Merge and Cleanup), not scattered inline instructions.
3. The gate approval "Approve + terminal + worktree" path no longer has its own inline merge hook instruction — it delegates to Merge and Cleanup.
4. The guardrail explicitly states: no `git merge`, no archival, and no status advancement until merge hooks have completed.
5. The guardrail explicitly addresses the PR-created case: if a hook set `pr`, stop — do not local merge.
6. An E2E test (`tests/test-merge-hook-guardrail.sh`) verifies the merge hook fires at merge time. Design:
   - Create a test mod (`_mods/test-hook.md`) with `## Hook: merge` that appends to `_merge-hook-fired.txt`
   - Commission a no-gates workflow (backlog → work → done), one entity
   - Run `claude -p --agent first-officer` to completion
   - Assert `_merge-hook-fired.txt` exists and contains the entity slug
   - Assert the entity was archived (merge completed after hook)
   - Additional case: run WITHOUT any mods — verify local merge still completes (no-mods fallback)
7. The guardrail wording references the in-memory hook registry (discovered at startup), not a filesystem scan at merge time. The FO discovers hooks once at startup; mid-session changes to `_mods/` are not picked up.
8. The E2E test is added to the README's Testing Resources table.

### Open questions (resolved)

**Q: Should the startup PR detection path have this guardrail?**
A: No. Startup PR detection (Path 5) and after-completion PR detection (Path 4) handle entities whose merge hooks already fired when the PR was created. These paths just detect that the PR merged and do the terminal advancement/archival. No hooks needed.

**Q: Should idle hooks or post-completion hooks also get guardrails?**
A: Out of scope. The incident was specifically about merge hooks being skipped. If other hook types get skipped, that's a separate issue.

### Staff review findings (independent reviewer)

**Design: PASS** — single-execution-point consolidation is correct, all merge paths identified, guardrail wording handles no-mods fallback.

**Test plan: INSUFFICIENT → ADDRESSED** — Original test plan only covered "hook fires." Reviewer identified missing coverage:
1. ~~No-mods fallback~~ → Added to AC6 (run without mods, verify local merge completes)
2. ~~PR-creating hook path~~ → Out of scope for this task; pr-merge mod already has its own E2E test path
3. Hook failure handling → Out of scope; document as future work

**Gap: ADDRESSED** — Guardrail wording said "check `_mods/*.md`" but hooks are discovered at startup and stored in memory. Updated AC7 to clarify the guardrail references the in-memory registry.

## Stage Report: ideation

- [x] All merge code paths in the FO template identified
  Five paths mapped: gate approve+terminal+worktree, gate approve+terminal+no-worktree, Merge and Cleanup section, after-completion PR detection, startup PR detection. Only the first three need the guardrail.
- [x] Guardrail wording proposed (bold ALL-CAPS pattern)
  MERGE HOOK GUARDRAIL wording drafted, matching existing GATE APPROVAL and GATE IDLE guardrail style.
- [x] Placement determined with rationale
  Single placement in Merge and Cleanup section, with consolidation to eliminate the duplicate inline instruction in the gate approval path. One hook execution point instead of two.
- [x] Acceptance criteria defined
  Five criteria covering: guardrail existence and style, single execution point, gate path delegation, explicit blocking semantics, and PR-created stop condition.

### Summary

Mapped all five merge-related code paths in the FO template. The root cause of the 073 incident was that merge hook instructions existed in two places (gate approval path and Merge and Cleanup section), making it easy to skip one and jump to local merge. The proposed fix consolidates to a single hook execution point in Merge and Cleanup with a bold ALL-CAPS guardrail, and rewrites the gate approval path to delegate to Merge and Cleanup instead of having its own inline hook step.

## Stage Report: implementation

- [x] MERGE HOOK GUARDRAIL added to Merge and Cleanup section
  Bold ALL-CAPS guardrail added at top of Merge and Cleanup in `templates/first-officer.md:144`, matching GATE APPROVAL and GATE IDLE guardrail style.
- [x] Gate approval path delegates to Merge and Cleanup (no inline hook instruction)
  Replaced 2-step inline merge hook logic at line 113-116 with single delegation: "Fall through to Merge and Cleanup."
- [x] E2E test script created at tests/test-merge-hook-guardrail.sh
  Test has 8 static template checks (Phase 1), hook-fires-at-merge-time dynamic test (Phases 2-4), and no-mods fallback test (Phases 5-7).
- [x] Test added to README Testing Resources table
  Added row to `docs/plans/README.md` Testing Resources table.
- [x] Commission test harness passes (no regression)
  All 65 checks pass: `scripts/test-commission.sh` run in worktree with zero failures.
- [x] All changes committed to worktree branch
  Committed to `ensign/077-merge-guardrail` as `5136c1b`.

### Summary

Added bold MERGE HOOK GUARDRAIL to the Merge and Cleanup section of the first-officer template, consolidating merge hook execution to a single point. Removed the inline merge hook instruction from the gate approval path so it delegates to Merge and Cleanup. The guardrail references the in-memory hook registry (discovered at startup), blocks git merge/archival/status advancement until hooks complete, and handles the PR-created stop condition. Created E2E test with fixture, static guardrail validation, and two dynamic test cases (with-hook and no-mods fallback). Commission test harness passes with all 65 checks green.

## Stage Report: validation

- [x] AC1: MERGE HOOK GUARDRAIL exists in Merge and Cleanup (bold ALL-CAPS)
  `templates/first-officer.md:144` — bold ALL-CAPS guardrail matching GATE APPROVAL and GATE IDLE style.
- [x] AC2: All merge paths funnel through single hook execution point
  Gate approval path no longer has inline hook instructions; all paths delegate to Merge and Cleanup.
- [x] AC3: Gate approval path delegates to Merge and Cleanup (no inline hook instruction)
  Line 115: "Fall through to `## Merge and Cleanup` — the merge hook guardrail there handles hook execution, PR detection, and merge."
- [x] AC4: Guardrail states: no git merge, no archival, no status advancement until hooks complete
  Line 144: "Do NOT proceed to `git merge`, archival, or status advancement until all merge hooks have completed"
- [x] AC5: Guardrail addresses PR-created case: if hook set pr, stop — no local merge
  Line 144: "If a merge hook created a PR (set the `pr` field), do NOT perform a local merge — report to the captain that the PR is pending and stop."
- [x] AC6: E2E test at tests/test-merge-hook-guardrail.sh with test mod + no-mods fallback
  Test script present with 8 static checks (Phase 1), hook-fires dynamic test (Phases 2-4), and no-mods fallback (Phases 5-7). Awk section extraction fixed in commit 9853264 — flag-based approach now captures full Merge and Cleanup section. All 8 static checks pass.
- [x] AC7: Guardrail wording references in-memory hook registry, not filesystem scan
  Line 144: "from the in-memory hook registry (discovered at startup from `_mods/`)" — and Step 1 also says "from the in-memory hook registry".
- [x] AC8: Test added to README Testing Resources table
  `docs/plans/README.md:182` — row present with correct path and description.
- [x] Commission test harness passes
  All 65 checks pass with zero failures.
- [x] Recommendation: PASSED
  All 8 acceptance criteria verified. Template changes correct, test script fixed and passing.

### Summary

All 8 acceptance criteria verified with evidence. The template changes in `templates/first-officer.md` correctly add the MERGE HOOK GUARDRAIL to the Merge and Cleanup section, consolidate all merge paths to a single hook execution point, and handle the PR-created stop condition. The E2E test script had an awk section-extraction bug (start-end pattern collision) that was fixed by the implementer in commit 9853264 using a flag-based approach — re-verified all 8 static checks now pass. Commission test harness passes with all 65 checks green.
