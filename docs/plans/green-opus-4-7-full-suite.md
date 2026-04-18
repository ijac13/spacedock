---
id: 186
title: "Green the full live test suite on opus-4-7 locally"
status: ideation
source: "captain directive (2026-04-17 session) — after #181 pinned CI to opus-4-6 as a workaround, the fleet is running green on opus-4-6 but opus-4-7 remains a known-flaky target. Goal: enumerate and fix all opus-4-7-specific failures so the pin can eventually be lifted."
started: 2026-04-18T00:12:20Z
completed:
verdict:
score: 0.7
worktree:
issue:
pr:
mod-block:
---

## Why this matters

CI is pinned to opus-4-6 (via #181) while opus-4-7 regressions exist. The pin is reversible and is a workaround, not a fix. To eventually lift it, every live test must be reliably green on opus-4-7 locally and in CI.

#182 investigated one specific failure (the `test_standing_teammate_spawn` test-predicate bug) and uncovered that some tests assert on FO narration prose, which opus-4-7 produces differently than opus-4-6. The narration-predicate class is being carved into #185. A second failure surface — `test_feedback_keepalive` — remains red on opus-4-7 even with the #182 Variant A prose in place. This task enumerates every remaining opus-4-7-specific failure mode, categorizes them by fix surface, and drives the suite to green.

## Problem statement

On opus-4-7 `--effort low`, the live_claude suite fails at least one test reliably (`test_feedback_keepalive`) and exhibits residual stochastic flake on others (`test_standing_teammate_spawn` was ~50% before #185's predicate fix; `test_feedback_keepalive` was ~20% before #182's prose + test-predicate change; the latter is still red in the latest CI run 24590771304). The full suite has never been observed green on opus-4-7 on `main` since the model bump. We need a failure-mode inventory and a prioritized fix plan, then a demonstrated full-suite green gate.

## Evidence base

Primary inputs for ideation:

- **Latest CI run on the #182 branch: 24590771304** (2026-04-17T23:15Z, commit `4962a0a5`, PR #117). `claude-live-opus` tier: `test_feedback_keepalive` FAILED with `StepTimeout` on "validation ensign dispatched (keepalive crossed the transition)" at 240s. The preserved fo-log shows a `<tool_use_error>Missing required parameter: task_id</tool_use_error>` mid-run — the FO on opus-4-7 emitted a malformed TaskUpdate call. `test_standing_teammate_spawn` PASSED (#182's predicate fix works). All XFAIL/XPASS counts are stable (these are pre-existing xfail markers, not new regressions).
- **#182 commit trail** (`94a416b0` through `e40ff353`): root cause attribution + Variant A prose (`## Ensign Completion Signal Discipline` in `claude-first-officer-runtime.md`) + test-side data-flow polling for `### Feedback Cycles`. Variant A raised opus-4-7 pass rate on `test_standing_teammate_spawn` from 0-30% to 80% (4/5), but the residual 20% flake was not resolved by prose alone.
- **#182 commit `e806a23a`** ("FO-impatience prose-fix attempted, resisted by opus-4-7, no prose commit") — direct evidence that FO-side prose discipline alone has diminishing returns on opus-4-7 for at least one failure mode.
- **Session debrief 5f8a88c6** — "opus-4-7 diagnosis flipped from ensign-side to test-narration-bug + FO-discipline gaps."

Secondary inputs:

- **#183** — BashOutput polling discipline (ensign-side skill prose). Still in ideation.
- **#185** — test-predicate cherry-pick + `test_gate_guardrail.py` audit. Still in ideation.
- **#184** — `find_subagent_jsonl` narrowing (unrelated to opus-4-7; independent).

## Failure-mode inventory

Enumerated from the evidence above. Each entry: (failure mode) — (symptom) — (fix surface) — (status / owner if already carved).

### Category A — test-construct bugs (predicate asserts on FO narration)

- **A1. `test_standing_teammate_spawn` predicate matched FO narration, not data flow.** Symptom: timeout waiting for a narration pattern opus-4-7 produces less verbosely than opus-4-6. Fix surface: test code (data-flow assertion on archived entity body). **Status: carved to #185** (cherry-pick of #182's commits `9c59d143` + `ab238078`).
- **A2. Audit `tests/test_gate_guardrail.py` for the same pattern.** Symptom: same brittle-predicate pattern suspected; concrete offenders at `test_gate_guardrail.py:55,64` use `entry_contains_text` on FO narration. Fix surface: test code. **Status: carved to #185** (audit scope).
- **A3. Audit remaining `entry_contains_text(...)` callers across `tests/` for narration-class predicates.** Fix surface: test code. **Status: carved to #185** (audit scope, covers this).

This category is already owned by #185. No new work under #186 unless #185 closes without covering a specific caller; revisit at #186 implementation time.

### Category B — ensign-side behavior (background-bash discipline)

- **B1. Ensigns using `Bash(run_in_background: true)` then blocking `sleep N && tail` instead of `BashOutput` polling.** Symptom: wallclock waste; uninterruptible turns that cannot observe captain messages. Known-observed on opus-4-7 during #182 iteration. Fix surface: `skills/ensign/references/ensign-shared-core.md` prose. **Status: carved to #183.**

This category is owned by #183 for ensign-side; evaluate in #183's AC-5 whether the FO shared-core also needs the subsection. No new work under #186 on this surface.

### Category C — FO-side behavior that prose alone has not resolved

These are the failure modes where #182's prose (Variant A in `claude-first-officer-runtime.md`) did **not** close the gap on opus-4-7. Per #182 commit `e806a23a`, "opus-4-7 resists" at least one discipline clause. The global CLAUDE.md rule forbids piling on more prose as a mitigation. A real mechanism fix is required, OR a diagnosis that distinguishes "needs prose with different shape" from "needs mechanism."

- **C1. `test_feedback_keepalive` FAILED on CI 24590771304 with `StepTimeout` at 240s on "validation ensign dispatched" AND a mid-run `<tool_use_error>Missing required parameter: task_id</tool_use_error>`.**
  - Symptom candidates (to be discriminated in implementation): (i) opus-4-7 FO emits a malformed TaskUpdate (missing `task_id`) which breaks the subagent's ability to signal completion, cascading into keepalive-transition timeout; (ii) opus-4-7 FO tears down the implementation ensign before receiving its Done: message — the #182 Variant A "Ensign Completion Signal Discipline" subsection targets this but does not fully land on opus-4-7; (iii) opus-4-7 FO narrates a validation dispatch but does not actually emit the Agent tool_use (streaming-watcher sees no matching event).
  - Fix surface candidates: **mechanism** preferred. Options include: (a) tighten the `TaskUpdate` tool schema's error handling so the FO gets a more actionable retry signal rather than silently stalling; (b) wire a small check into `run_first_officer_streaming` that injects a structured reminder-event if no Agent-dispatch is seen within N seconds of a known stage transition; (c) tighten the streaming-watcher's M4 milestone to tolerate opus-4-7's tool-call ordering. Prose is a fallback, and only if evergreen and covering a shape #182's Variant A did not cover.
  - **Gating discipline:** no "prose mitigation" commits in this category. Any prose edit must be evergreen per global CLAUDE.md rules and must be accompanied by a reproducible before/after pass-rate delta (opus-4-7 3/3 or 5/5) demonstrating the mechanism change (not a reshuffle of words) closes the gap.

- **C2. Residual ~20% flake on `test_standing_teammate_spawn` on opus-4-7 after #185 lands the test-predicate fix.** Symptom: occasional timeout even with the data-flow assertion, per #182's Behavioral Proof ("A-R1 FAIL 392s residual pattern"). Likely overlaps with C1 root cause (same FO-side behavior class). Fix surface: same as C1.

- **C3. Validation subagent lifecycle — opus-4-7 tears down teammates earlier than opus-4-6.** Observed in #182 as `TeamDelete` retry attempts on "N active member(s)" errors. Variant A addresses the surface in prose ("only safe teardown ordering: ensign Done: -> ensign shutdown -> standing teammates shutdown -> TeamDelete"), but C1 suggests the prose is not wholly sufficient. Fix surface: likely a `claude-team` tooling guard (shutdown orchestration) rather than more prose. Revisit at implementation time to see whether C1's mechanism fix also closes C3.

### Category D — infra / flake / pre-existing xfail

- **D1. Pre-existing XFAIL markers** (`test_agent_captain_interaction`, `test_claude_per_stage_model`, `test_commission`, `test_repo_edit_guardrail`, `test_checklist_e2e`, `test_output_format`, `test_reuse_dispatch`, `test_team_dispatch_sequencing`). Not opus-4-7 regressions; they were xfail on opus-4-6 too. Fix surface: none for this task — out of scope.
- **D2. `test_interactive_poc`, `test_push_main_before_pr`, `test_rebase_branch_before_push`, `test_single_entity_mode` — SKIPPED in CI on all runtimes.** Not relevant. Out of scope.

No new category-D work in #186.

## Prioritized fix surface plan

Priority ordering reflects "what unblocks the most of the suite cheaply":

1. **Category A (#185 cherry-pick + audit).** Cheapest, highest confidence, already carved. No work under #186.
2. **Category B (#183 BashOutput polling).** Cheap prose fix, blocks #186 implementation (see Dependencies).
3. **Category C1 (mechanism diagnosis + fix for `test_feedback_keepalive`).** The load-bearing work of #186. Requires hypothesis-driven debugging: reproduce locally at opus-4-7 `--effort low`, instrument the FO stream to distinguish the three C1 symptom candidates, then implement ONE minimal mechanism change. No prose-only commits.
4. **Category C2/C3 (revisit after C1 lands).** Likely closed by the same mechanism fix.
5. **Full-suite validation run.** Gate to green.

Each category's acceptance criterion is stated in the next section with its test method.

## Acceptance criteria

**AC-1 — Failure-mode inventory complete and categorized.**
Test method: this entity body contains the inventory above (static check — one-shot; verified at ideation gate).

**AC-2 — Dependency map resolved.**
Test method: #185 and #183 statuses checked at implementation start. Implementation MUST NOT start before #183 lands (see Dependencies). Implementation MAY start before #185 lands if C1 does not require #185's changes to reproduce; document which path is taken at implementation kickoff.

**AC-3 — C1 mechanism diagnosis.**
Test method: at implementation start, run `tests/test_feedback_keepalive.py::test_feedback_keepalive` locally with `MODEL=opus-4-7` `--effort low` at least 3 times with `KEEP_TEST_DIR=1`. Produce a per-run artifact summary (fo-log highlights, tool_use sequence around the 240s timeout window) and identify ONE of the three C1 symptom candidates (i/ii/iii) as the load-bearing one. Investigation discipline: `superpowers:systematic-debugging`. Budget: 3 runs × ~$2 = ~$6.

**AC-4 — C1 mechanism fix.**
Test method: implement ONE minimal mechanism change targeting the symptom named in AC-3. Then re-run `test_feedback_keepalive` 5 times on opus-4-7 `--effort low`. Pass rate must be ≥ 4/5 (80%), with the one permissible failure not reproducing the same timeout/tool_error symptom. No prose-only commits satisfy AC-4.

**AC-5 — C2/C3 status check after C1 lands.**
Test method: re-run `test_standing_teammate_spawn` 3 times on opus-4-7 `--effort low`. Pass rate must be ≥ 3/3. If flake persists, re-open C2/C3 as separate failure modes with updated symptom evidence; do not gate #186 on resolving them here (but do gate unpinning CI, which is the downstream task).

**AC-6 — Full-suite greening.**
Test method: `make test-live-claude-opus OPUS_MODEL=opus` (serial + parallel tiers) run locally. Acceptance: **2 consecutive clean runs**, where "clean" means all non-XFAIL/non-SKIP tests pass. Two consecutive passes are the minimum evidence that the suite is reliable, not a single lucky run.

**AC-7 — Unpinning CI is explicitly NOT in scope.**
Test method: grep the entity body and commit messages for any change to `.github/workflows/` or the `make` target's default model; confirm zero changes. Unpinning is a separate follow-up task filed by the captain after #186 lands clean.

## Investigation discipline

Apply `superpowers:systematic-debugging` for Category C work. Do NOT:

- Stack multiple fixes at once. Phase 3 rule: one hypothesis, one minimal test.
- Write prose mitigations as a shortcut (learned from #182 rejection; enforced by global CLAUDE.md).
- Inflate scope into broader "FO architecture" investigation — #186 targets measurable test greening, not a redesign.

Do:

- Reproduce before investigating.
- Capture all artifacts (`KEEP_TEST_DIR=1`, preserved test directories, parent fo-log, stats-fo.txt).
- Compare against opus-4-6 baseline when the symptom is ambiguous.

## Dependencies

- **Blocks implementation: #183.** Implementation of #186 runs many local `make test-live-claude-opus` invocations; each requires dispatched ensigns that use background bash. Until #183 lands, each iteration burns wallclock on blocking `sleep N && tail` waits. Ideation and gate review of #186 can proceed in parallel with #183; implementation MUST wait.
- **Non-blocking dependency: #185.** #185 closes Category A on its own schedule. If #185 is not yet merged when #186 implementation kicks off, it does not block C1 work (C1 failure modes are independent of the predicate-pattern fixes). Re-audit overlap at implementation kickoff.
- **Independent: #184.** `find_subagent_jsonl` narrowing is a separate surface; no ordering constraint.

## Test plan

- **Ideation cost:** essentially free — static inventory + cross-references. Already incurred.
- **Implementation cost (estimated):**
  - AC-3 diagnosis: 3 × `test_feedback_keepalive` runs on opus-4-7 local, ~5-7 min wallclock each, ~$2 budget each → ~20 min / ~$6.
  - AC-4 mechanism fix: iterative; budget for 5 × re-runs after the fix, same per-run cost → ~30 min / ~$10.
  - AC-5 C2/C3 check: 3 × `test_standing_teammate_spawn` runs → ~20 min / ~$6.
  - Subtotal (C-category): ~70 min / ~$22 worst case.
- **Validation cost (AC-6):**
  - Each `make test-live-claude-opus` run: ~14-16 min wallclock (per CI history), ~$8-12 budget (serial tier is one test file, parallel tier is ~15 tests × ~$0.50-1.00 each).
  - 2 consecutive clean runs: ~30 min / ~$20-25 worst case.
- **Total budget estimate: ~100 min wallclock, ~$45-50 live-agent budget.** Run locally; no CI dispatch needed. CI dispatch is the downstream unpinning task, not #186.

- **Pass-rate threshold choice (AC-6):** 2 consecutive clean full-suite runs. Rationale: a single run can pass stochastically even with latent flake; two consecutive runs give ~4× the sample at low added cost. More than 2 is diminishing returns — #186's goal is "green enough to consider unpinning," and the unpinning task will run its own CI-side multi-run validation before flipping the pin.

## Out of scope

- Changing the CI pin — belongs to a follow-up task after #186 closes clean.
- Codex-side tests — this task targets `live_claude` tier only.
- Infrastructure changes outside test code and the skill-prose / mechanism surfaces already identified.
- XFAIL/SKIP cleanup — pre-existing markers, not opus-4-7 regressions.
- Re-litigating #182's Variant A prose — it stays as-is unless the C1 diagnosis reveals a different prose shape is needed (in which case it must still be evergreen).

## Cross-references

- #181 — CI pin to opus-4-6 (the workaround this task eventually unblocks the removal of)
- #182 — prior diagnosis; source of Variant A prose + test-predicate data-flow fix
- #183 — BashOutput polling discipline (blocks implementation)
- #184 — claude-team narrowing cherry-pick (unrelated surface; can land anytime)
- #185 — test-predicate cherry-pick + audit (addresses Category A)
- CI run 24590771304 — latest #182 branch full-suite run showing the C1 failure pattern

## Stage Report (ideation)

- **DONE — Read the seed entity body in full.** Confirmed seed body captured the pre-ideation framing; rewrote with inventory + acceptance criteria.
- **DONE — Pull latest #182 CI artifacts.** `gh run list --workflow="Runtime Live E2E" --limit 10` identified run 24590771304 as the most recent #182-branch run. `gh run view 24590771304 --log-failed` extracted the `test_feedback_keepalive` StepTimeout + `<tool_use_error>Missing required parameter: task_id</tool_use_error>` evidence. Full artifact download not needed — log excerpts sufficed for inventory-stage work.
- **DONE — Read #182's Diagnosis Outcome section (AC-4 attribution).** Read the #182 entity in full. Noted that the formal "Diagnosis Outcome" section was not written as a standalone block — the attribution is distributed across commits `94a416b0`, `e806a23a`, and `e40ff353`. Evidence extracted from commit messages and folded into the Category C inventory.
- **DONE — Enumerate failure modes categorized (a/b/c/d).** Inventory in `## Failure-mode inventory`: Category A (test-construct, owned by #185), Category B (ensign-side, owned by #183), Category C (FO-side mechanism, owned by #186), Category D (pre-existing XFAIL/SKIP, out of scope).
- **DONE — Per-category fix surface + acceptance criteria.** Section `## Prioritized fix surface plan` + `## Acceptance criteria` (AC-1 through AC-7). Each AC names its test method.
- **DONE — Implementation vs validation scope.** Implementation scope: C1 mechanism diagnosis + fix, with AC-3/AC-4 run counts. Validation scope: full-suite serial + parallel on opus-4-7, AC-6 requires 2 consecutive clean runs.
- **DONE — Note implementation blocked on #183.** Called out in `## Dependencies`; AC-2 enforces the check at implementation start.
- **DONE — Test plan with cost + wallclock estimate.** Section `## Test plan`: ~100 min wallclock, ~$45-50 budget, purely local. CI dispatch explicitly not required.
- **DONE — Commit updated body on main.** See commit SHA below.
- **DONE — Append this Stage Report.** This section.

### Summary

Fleshed out #186 for ideation: enumerated every known opus-4-7 failure mode against CI run 24590771304 + #182's commit trail, categorized them by fix surface (A: test-construct → #185; B: ensign-side → #183; C: FO-side mechanism → #186; D: pre-existing xfail, out of scope). Acceptance criteria are AC-1 through AC-7, each with a named test method; the load-bearing work is C1 (`test_feedback_keepalive` mechanism fix, explicitly forbidden from being a prose-only change). Implementation is blocked on #183 landing. Validation gate is 2 consecutive clean full-suite runs on opus-4-7 locally; unpinning CI is an explicit follow-up, not part of #186. Budget estimate: ~100 min wallclock, ~$45-50 live-agent budget.
