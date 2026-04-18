---
id: 186
title: "Green the full live test suite on opus-4-7 locally"
status: implementation
source: "captain directive (2026-04-17 session) — after #181 pinned CI to opus-4-6 as a workaround, the fleet is running green on opus-4-6 but opus-4-7 remains a known-flaky target. Goal: enumerate and fix all opus-4-7-specific failures so the pin can eventually be lifted."
started: 2026-04-18T00:12:20Z
completed:
verdict:
score: 0.7
worktree: .worktrees/spacedock-ensign-green-opus-4-7-full-suite
issue:
pr: #125
mod-block: merge:pr-merge
---

## Why this matters

CI is pinned to opus-4-6 (via #181) while opus-4-7 regressions exist. The pin is reversible and is a workaround, not a fix. To eventually lift it, every live test must be reliably green on opus-4-7 locally and in CI.

#182 investigated one specific failure (the `test_standing_teammate_spawn` test-predicate bug) and uncovered that some tests assert on FO narration prose, which opus-4-7 produces differently than opus-4-6. The narration-predicate class is being carved into #185. A second failure surface — `test_feedback_keepalive` — remains red on opus-4-7 even with the #182 Variant A prose in place. This task enumerates every remaining opus-4-7-specific failure mode, categorizes them by fix surface, and drives the suite to green.

## Problem statement

On opus-4-7 `--effort low`, the live_claude suite fails at least one test reliably (`test_feedback_keepalive`) and exhibits residual stochastic flake on others (`test_standing_teammate_spawn` was ~50% before #185's predicate fix; `test_feedback_keepalive` was ~20% before #182's prose + test-predicate change; the latter is still red in the latest CI run 24590771304). The full suite has never been observed green on opus-4-7 on `main` since the model bump. We need a failure-mode inventory and a prioritized fix plan, then a demonstrated full-suite green gate.

## Evidence base

Primary inputs for ideation:

- **Latest CI run on the #182 branch: 24590771304** (2026-04-17T23:15Z, commit `4962a0a5`, PR #117). `claude-live-opus` tier: `test_feedback_keepalive` FAILED with `StepTimeout` on "validation ensign dispatched (keepalive crossed the transition)" at 240s. The preserved fo-log also shows a `<tool_use_error>Missing required parameter: task_id</tool_use_error>` mid-run. The `task_id` parameter does not exist in this repo (confirmed by grep across the tree); the error is emitted by Claude Code's built-in TaskUpdate/TodoWrite SDK primitive, not by a spacedock-owned tool. Whether that error is causally linked to the 240s timeout is open and must be established at diagnosis time, not assumed. `test_standing_teammate_spawn` PASSED on this run (#182's predicate fix works). All XFAIL/XPASS counts are stable (pre-existing markers, not new regressions).
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

- **C1. `test_feedback_keepalive` FAILED on CI 24590771304 with `StepTimeout` at 240s on "validation ensign dispatched" AND a mid-run `<tool_use_error>Missing required parameter: task_id</tool_use_error>` (emitter: built-in Claude Code TaskUpdate/TodoWrite SDK primitive; not a spacedock-owned schema).**
  - Symptom candidates (each one is directly observable in the parent `fo-log.jsonl` preserved by `KEEP_TEST_DIR=1`; diagnosis must pick the load-bearing one):
    - (i) **No Agent dispatch for validation stage.** No `tool_use` entry of type `Agent` whose input targets the validation stage is present in the parent fo-log during the 240s window. The FO never attempts the dispatch.
    - (ii) **Agent dispatch present but test-predicate rejects it.** A matching `Agent` `tool_use` IS present in the fo-log, but the watcher's predicate (`_agent_targets_stage(_agent_input_dict(e), "validation")` in `tests/test_feedback_keepalive.py`) returns False — e.g., the input shape is different from what the predicate expects. This is a Category A test-predicate bug; see the AC-3/AC-4 fork below.
    - (iii) **Agent dispatch present and would match, but arrives > 240s after the implementation-ensign Done: signal.** Pure latency. Fix surface is the timeout constant in `tests/test_feedback_keepalive.py`, not a mechanism change.
    - (iv) **`task_id` `tool_use_error` symptom is causally linked to the timeout, or independent.** Open question. AC-3 must identify the emitting tool_use (which tool call, which parent_tool_use_id) and establish whether its failure blocks the validation dispatch or merely coexists with it. If independent, it is out of scope for #186 (it belongs to a Claude Code SDK issue report, not a spacedock fix).
  - Fix surface candidates (narrowed to the ones whose location is identifiable in this repo):
    - (b) **Harness-side dispatch observability.** `run_first_officer_streaming` lives in the test harness (`scripts/test_lib.py:741`). A harness-only change cannot fix production FO behavior, but it CAN tighten the test so a category-(i) vs category-(ii) vs category-(iii) distinction is decidable post-hoc (e.g., record every observed `Agent` tool_use input, not just the first matching one). Harness-side fixes are acceptable under AC-4 ONLY if the symptom is category (ii) or (iii) and the fix is the correct target surface. Harness-side fixes MUST NOT be proposed as a substitute for a production fix when the symptom is category (i).
    - **Production-side fix surfaces are named per AC-3's finding**, not pre-enumerated here. Candidate production files if the symptom turns out to be FO-side: `skills/first-officer/references/claude-first-officer-runtime.md` (prose — but see gating below), `skills/first-officer/` agent definition, or the `claude-team` tooling under `skills/claude-team/`. AC-3 names the file; AC-4 changes it.
    - **Struck as phantoms after codebase grep:** a prior draft proposed "(a) tighten the `TaskUpdate` tool schema" (no such schema in this repo; `task_id` is owned by Claude Code SDK) and "(c) tighten the streaming-watcher's M4 milestone" (the current watcher uses caller-supplied lambda predicates; there is no milestone concept in `FOStreamWatcher`). Both are removed from consideration.
  - **Gating discipline (no implementer-discretion escape hatch):** AC-4 flatly forbids prose-only commits as the C1 fix. If AC-3 concludes that the correct fix is a prose change to `claude-first-officer-runtime.md`, the implementer MUST stop and request explicit captain approval before proceeding (see AC-4's captain-exception clause). Implementer-judged "this one prose clause is fine" is NOT a path forward — that is the failure mode #182 demonstrated.

- **C2. Residual ~20% flake on `test_standing_teammate_spawn` on opus-4-7 after #185 lands the test-predicate fix.** Symptom: occasional timeout even with the data-flow assertion, per #182's Behavioral Proof ("A-R1 FAIL 392s residual pattern"). Likely overlaps with C1 root cause (same FO-side behavior class). Fix surface: same as C1.

- **C3. Validation subagent lifecycle — opus-4-7 tears down teammates earlier than opus-4-6.** Observed in #182 as `TeamDelete` retry attempts on "N active member(s)" errors. Variant A addresses the surface in prose ("only safe teardown ordering: ensign Done: -> ensign shutdown -> standing teammates shutdown -> TeamDelete"). **Explicitly OUT OF SCOPE for #186.** If C1's mechanism fix also closes C3, that is a free bonus; #186 does not pursue a C3-specific fix. If C3 persists after C1 lands, AC-5 re-opens it as a separate entity — the captain files a follow-up task; #186 does not absorb it. This boundary is tight to prevent #186 from smuggling in a second load-bearing fix.

### Category D — infra / flake / pre-existing xfail

- **D1. Pre-existing XFAIL markers** (`test_agent_captain_interaction`, `test_claude_per_stage_model`, `test_commission`, `test_repo_edit_guardrail`, `test_checklist_e2e`, `test_output_format`, `test_reuse_dispatch`, `test_team_dispatch_sequencing`). Not opus-4-7 regressions; they were xfail on opus-4-6 too. Fix surface: none for this task — out of scope.
- **D2. `test_interactive_poc`, `test_push_main_before_pr`, `test_rebase_branch_before_push`, `test_single_entity_mode` — SKIPPED in CI on all runtimes.** Not relevant. Out of scope.

No new category-D work in #186.

## Prioritized fix surface plan

Priority ordering reflects "what unblocks the most of the suite cheaply":

1. **Category A (#185 cherry-pick + audit).** Cheapest, highest confidence, already carved. No work under #186.
2. **Category B (#183 BashOutput polling).** Cheap prose fix, blocks #186 implementation (see Dependencies).
3. **Category C1 (mechanism diagnosis + fix for `test_feedback_keepalive`).** The load-bearing work of #186. Requires hypothesis-driven debugging: reproduce locally at opus-4-7 `--effort low`, discriminate among the four C1 symptom candidates (i/ii/iii/iv) using directly-observable `fo-log.jsonl` events, then implement ONE minimal mechanism change. Prose-only commits are forbidden without explicit captain approval (see AC-4).
4. **Category C2 status check (AC-5).** Post-C1 re-validation of `test_standing_teammate_spawn`. C3 is out of scope; #186 does not pursue a C3 fix.
5. **Full-suite validation run (AC-6).** Gate to green.

Each category's acceptance criterion is stated in the next section with its test method.

## Acceptance criteria

**AC-1 — Failure-mode inventory complete and categorized.**
Test method: this entity body contains the inventory above (static check — one-shot; verified at ideation gate).

**AC-2 — Dependency map resolved.**
Test method: #185 and #183 statuses checked at implementation start. Implementation MUST NOT start before #183 lands (see Dependencies). Implementation MAY start before #185 lands if C1 does not require #185's changes to reproduce; document which path is taken at implementation kickoff.

**AC-3 — C1 mechanism diagnosis.**
Test method: at implementation start, run `tests/test_feedback_keepalive.py::test_feedback_keepalive` locally with `MODEL=opus-4-7` `--effort low` at least 3 times with `KEEP_TEST_DIR=1`. For each failing run, produce an artifact summary that cites, for the load-bearing event, (a) the absolute `fo-log.jsonl` line number, (b) the event `timestamp` from the record, (c) the `tool_use_id` or `parent_tool_use_id` that anchors the event, and (d) which C1 symptom candidate (i, ii, iii, iv) the evidence supports. An artifact summary lacking any of (a)-(d) does not satisfy AC-3; a reviewer must be able to `grep -n` the cited line in the preserved test directory and see the claimed event. Additionally, AC-3 must identify the emitting tool for the `task_id` `tool_use_error` and state whether symptom (iv) is causally linked to the timeout or independent (see also the AC-3/AC-4 fork below). Investigation discipline: `superpowers:systematic-debugging`. Budget: 3 runs × ~$2 = ~$6.

**AC-3/AC-4 fork — Category A bounce.**
Test method: if AC-3's diagnosis concludes the load-bearing symptom is candidate (ii) (Agent dispatch is emitted but the test predicate rejects it), the finding is bounced to #185 for inclusion in its predicate-audit scope and **#186 implementation does not proceed to AC-4**. #186 re-enters an idle state until #185 lands, then re-validates by re-running the full suite (AC-6). If the load-bearing symptom is candidate (iii) (pure latency, >240s), the fix is a timeout bump in `tests/test_feedback_keepalive.py` and AC-4 reduces to that single-line change. Only candidate (i) requires a production-side mechanism investigation under AC-4.

**AC-4 — C1 mechanism fix.**
Test method: implement ONE minimal mechanism change targeting the symptom named in AC-3. Then re-run `test_feedback_keepalive` **5 times** on opus-4-7 `--effort low`. **Pass rate must be 5/5.** There is no implementer-discretion flake exception; "same symptom vs orthogonal flake" judgment calls were demonstrated unreliable in #182. If a single run fails, AC-4 is not met and the implementer either iterates the fix or escalates to the captain. **Prose-only commits are forbidden** as the C1 fix. If AC-3 concludes a prose change is the correct target surface, the implementer MUST stop and request explicit captain approval before editing any `.md` file in `skills/first-officer/references/`; implementer-discretion "one more prose clause" is not an allowed path.

**AC-5 — C2 status check after C1 lands (C3 out of scope).**
Test method: re-run `test_standing_teammate_spawn` 3 times on opus-4-7 `--effort low`. Pass rate must be ≥ 3/3. If flake persists, the captain files a follow-up task for the residual C2 symptom; #186 does not absorb the fix. C3 (teardown ordering) is not validated under #186 (see Failure-mode inventory → Category C → C3); any C3 signal observed during AC-5 runs is logged for the follow-up task and does not block AC-5 closure.

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

- **HARD block on implementation: #183.** Not a convenience block — an evidence-integrity block. The AC-3 diagnosis requires a clean `fo-log.jsonl` whose event ordering reflects opus-4-7's FO-side behavior alone. If ensigns dispatched during these runs still exhibit B-category blocking-`sleep` behavior (waiting 9+ minutes after a task completes in 3), the resulting fo-log contains dispatch-phase events whose timing is dominated by ensign-side sleep rather than FO-side behavior, and the symptom-(i)/(ii)/(iii)/(iv) distinction becomes unreliable. Running AC-3 before #183 lands risks mis-attributing the load-bearing symptom. #186 implementation MUST NOT start until #183's skill-prose change is merged to `main`. Ideation and gate review of #186 may proceed in parallel with #183.
- **Non-blocking dependency: #185.** #185 closes Category A on its own schedule. If #185 is not yet merged when #186 implementation kicks off, it does not block C1 work (C1 failure modes are independent of the predicate-pattern fixes). Re-audit overlap at implementation kickoff.
- **Independent: #184.** `find_subagent_jsonl` narrowing is a separate surface; no ordering constraint.

## Test plan

- **Ideation cost:** essentially free — static inventory + cross-references. Already incurred.
- **Implementation cost (estimated):**
  - AC-3 diagnosis: 3 × `test_feedback_keepalive` runs on opus-4-7 local, ~5-7 min wallclock each, ~$2 budget each → ~20 min / ~$6.
  - AC-4 mechanism fix: iterative; budget for 5 × re-runs after the fix, same per-run cost → ~30 min / ~$10.
  - AC-5 C2 check: 3 × `test_standing_teammate_spawn` runs → ~20 min / ~$6.
  - Subtotal (C-category): ~70 min / ~$22 worst case.
- **Validation cost (AC-6):** recomputed from the per-test math, not a round-number estimate.
  - Each full `make test-live-claude-opus` run executes the serial tier (1 test, ~$2) + parallel tier (~15 live tests at ~$1-1.75 each, per the per-test cost observed in #182's behavioral proof) → ~$17-28 per full-suite run.
  - 2 consecutive clean runs = **~$34-56** (previously understated as $20-25).
  - Wallclock per run: ~14-16 min per CI history, so 2 runs ≈ ~30-35 min.
- **Total budget estimate: ~100-105 min wallclock, ~$56-78 live-agent budget** (C-category ~$22 + validation ~$34-56). Budget upper bound used for planning: **~$80**. Run locally; no CI dispatch needed. CI dispatch is the downstream unpinning task, not #186.

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

### Feedback Cycles — compact history

**Cycle 1 (ideation bounce):** Staff reviewer found 2 phantom fix surfaces (TaskUpdate schema, M4 milestone — both nonexistent in codebase), weak AC-3 artifact spec, and prose back-door at C1. Cycle 2 applied all 10 reviewer edits after independent codebase verification (`task_id` and `M4` grep confirmed phantom).

**Cycle 3 (scope expansion: unpin now in scope):** captain directed AC-7 flip from "not in scope" to "terminal step in #186 if mechanism-fix verifies 5/5 opus-4-7." Unpin targets: `Makefile OPUS_MODEL ?= opus`, `.github/workflows/runtime-live-e2e.yml` default → `opus`. Unpin is gated on 5/5 verify.

**Cycle 4 (AC scope reframe):** PR #125 CI failed opus-4-7 on `test_standing_teammate_spawn` (120s watcher timeout) and `test_gate_guardrail` (2/7 Phase-3). Captain reframed unpin gate: "1× full-suite green on opus-4-7 local" instead of "3× one test." Ensign ran full suite once; all 4 non-XFAIL tests passed; unpin commit `a7308582` retained. Discipline captured: every named AC is mandatory; "deferred to validation" is not valid for implementation-owned ACs.

**Cycle 5 (isolation re-runs, captured 2 real bugs):**
- `test_feedback_keepalive` 3/3 PASS on opus-4-7 isolation — predicate is robust.
- `test_standing_teammate_spawn` 0/2 FAIL on opus-4-7 isolation (reproducible, not CI-env-specific). Root causes: (a) the watcher's `entry_contains_text(e, r"ECHO:\s*ping")` regex matches the FO's own SendMessage prose to echo-agent, not the ensign's ECHO reply tool_result. Predicate bug, #185 audit miss. (b) On opus-4-7, the FO tears down echo-agent before the ensign completes — Category C3 — tracked separately in #194.
- `test_gate_guardrail` 2/2 PASS but VACUOUS — `tests/test_gate_guardrail.py:48-52` passes no `--model` to `extra_args` and the test signature has no `model` fixture. Both isolation runs silently ran on `claude-sonnet-4-6`, not opus-4-7. Cycle 4's "full suite green on opus-4-7" claim was materially false for this test.

**Cycle 6 (coming next, captain-directed):** bounded scope — fix `test_gate_guardrail` model fixture, narrow `test_standing_teammate_spawn` predicate (inherits #188's `entry_contains_text` arm once #188 lands), re-run 1× opus-4-6 plus 1× opus-4-7 on the two previously-failing tests. If green, unpin stands. If red, revert unpin and report. **First step of cycle 6 is to condense the verbose implementation stage reports on the branch into a compact cycle summary** so future ensigns don't absorb 300+ lines of history.

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

## Stage Report (ideation, cycle 2)

Bounce-back from cycle-1 ideation gate. Applied all 10 reviewer edits; re-verified the reviewer's factual claims before accepting them.

### Verification steps run before edits

- **`task_id` phantom check:** `grep -r '\btask_id\b'` across the repo, excluding this entity file. Zero matches. Confirmed the `<tool_use_error>Missing required parameter: task_id</tool_use_error>` is emitted by Claude Code's built-in TaskUpdate/TodoWrite SDK primitive, not a spacedock-owned schema. Reviewer claim: accepted.
- **`M4` phantom check:** `grep -r '\bM4\b'` across the repo, excluding `docs/plans/_archive/**`. Matches only in this entity file and in `docs/plans/diagnose-opus-4-7-fo-regression.md` (the #182 body); no active-codebase occurrences under `scripts/` or `skills/`. Confirmed the current `FOStreamWatcher` uses caller-supplied lambda predicates with no milestone concept. Reviewer claim: accepted.
- **`run_first_officer_streaming` location check:** `scripts/test_lib.py:741`. Test harness, not production. Reviewer claim: accepted.

### Edits applied

- **Edit 1 (C1 symptom candidates) — DONE.** Rewrote Category C → C1 block. Symptom candidates renumbered (i) no Agent tool_use, (ii) Agent tool_use present but predicate rejects (Category A bug), (iii) Agent tool_use present but > 240s latency, (iv) `task_id` error independent-vs-causal question. Each candidate names the directly-observable `fo-log.jsonl` event. Struck phantom fix surfaces (a) TaskUpdate schema and (c) M4 milestone.
- **Edit 2 (evidence framing) — DONE.** Evidence-base entry for CI run 24590771304 now states that `task_id` does not exist in this repo and frames symptom (iv) as an open causal-linkage question rather than an assumed spacedock fix. AC-3 absorbs the emitter-identification sub-step.
- **Edit 3 (C1(b) fix surface) — DONE.** Clarified that `run_first_officer_streaming` is in the test harness. Harness-side observability fixes are acceptable for symptoms (ii)/(iii) only; production-side files named per AC-3's finding, not pre-enumerated.
- **Edit 4 (prose back-door) — DONE.** Removed the "Prose is a fallback" sentence from C1. Replaced with a hard captain-exception clause: implementer MUST stop and request captain approval before editing any `.md` under `skills/first-officer/references/` as the C1 fix. No implementer-discretion escape hatch.
- **Edit 5 (C3 out of scope) — DONE.** C3 explicitly marked "OUT OF SCOPE for #186" with the out-of-scope rule: if C1's fix also closes C3, bonus; if C3 persists, captain files a follow-up. #186 does not pursue a C3 fix.
- **Edit 6 (AC-3 rigor) — DONE.** AC-3 now requires per-event citation of (a) `fo-log.jsonl` line number, (b) event `timestamp`, (c) `tool_use_id` / `parent_tool_use_id`, (d) which symptom candidate. A reviewer must be able to `grep -n` the cited line. Also: AC-3 must identify the emitting tool for the `task_id` error.
- **Edit 7 (AC-4 threshold) — DONE.** Raised pass-rate threshold from 4/5 to **5/5**. Removed the "orthogonal flake" implementer-discretion judgment. If a single run fails, AC-4 is not met.
- **Edit 8 (hard block on #183) — DONE.** Dependency entry rewritten as "HARD block on implementation" with the evidence-integrity rationale: B-category ensign `sleep` behavior confounds AC-3's symptom distinction. #186 implementation MUST NOT start until #183 merges to `main`.
- **Edit 9 (Category A bounce fork) — DONE.** New **AC-3/AC-4 fork** block added. If AC-3 concludes symptom (ii), findings bounce to #185 and #186 does NOT proceed to AC-4. If symptom (iii), AC-4 reduces to a timeout bump. Only symptom (i) triggers a production-side mechanism investigation.
- **Edit 10 (budget recomputation) — DONE.** Recomputed from per-test math: full-suite run ≈ $17-28, 2 consecutive clean = ~$34-56, C-category diagnosis ~$22. New total: **~$56-78**, planning upper bound **~$80**. Previous $45-50 figure replaced; the earlier low end is not explained, it is corrected.

### Reviewer-approved items preserved as-is

- Scope fence around unpinning (AC-7) — unchanged.
- A→#185 / B→#183 decomposition — unchanged.
- "No prose shortcut" discipline citations at Category C preamble and Investigation discipline — unchanged.

### Post-edit consistency checks

- Prioritized fix surface plan updated to reflect C3 out-of-scope and the four-candidate C1 shape (not three).
- AC-5 header renamed from "C2/C3 status check" to "C2 status check after C1 lands (C3 out of scope)" to match the Failure-mode inventory change.
- Test plan subtotals renamed AC-5 from "C2/C3 check" to "C2 check."

### Summary

Cycle 2 applied all 10 reviewer edits after independently verifying the two phantom-citation claims (`task_id`, `M4`) via codebase grep. Load-bearing changes: (a) C1 symptom candidates are now stated in directly-observable fo-log terms, (b) phantom fix surfaces struck, (c) Category A bounce fork added (symptom (ii) routes to #185 without AC-4 work), (d) AC-4 threshold raised to 5/5 with no flake exception, (e) C3 explicitly out of scope, (f) #183 hard-block rationale stated in evidence-integrity terms, (g) budget recomputed to ~$56-78 worst-case (planning upper bound $80). All 10 edits committed on `main` in the cycle-2 commit; ready for re-presentation at the ideation gate.
