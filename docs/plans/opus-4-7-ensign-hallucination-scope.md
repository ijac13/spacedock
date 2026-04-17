---
id: 177
title: "opus-4-7 ensign hallucination at low/medium effort — scope of impact across spacedock dispatches"
status: ideation
source: "2026-04-16 session — PR #107/#105 CI failures bisected to Claude Code 2.1.110→2.1.111 default-alias flip from claude-opus-4-6 to claude-opus-4-7. Live-CI evidence + fo-log.jsonl artifacts confirm the ensign subagent on opus-4-7 fabricates tool-call outcomes rather than issuing the tool calls."
started: 2026-04-17T01:23:21Z
completed:
verdict:
score: 0.85
worktree: .worktrees/spacedock-ensign-opus-4-7-ensign-hallucination-scope
issue:
pr:
---

## Problem Statement

Claude Code 2.1.111 flipped the default `--model opus` resolution from `claude-opus-4-6` to `claude-opus-4-7`. Under `opus-4-7` at `--effort low` or `--effort medium`, dispatched ensigns exhibit a specific hallucination pattern: they execute easy tool-call steps (file writes, commits) but skip harder steps (`SendMessage` to teammates, tool-mediated verification) and fabricate the outcome in their stage reports. The FO accepts the stage report at face value because it reads DONE markers without verifying evidence against the session stream.

This concern is not limited to the one test that exposed it. The ensign dispatch shape — checklist + stage report + visible teammate descriptions — is the standard template for every spacedock ensign dispatch. The hallucination is contextual (simple isolation reproducers do not trigger it), prompt-shape-dependent, and effort-gated: `opus-4-7` at `--effort high` or `--effort xhigh` does not exhibit the low/medium fabrication pattern, but exposes a different failure at those effort levels (see Evidence at high/xhigh effort). `opus-4-6` at any effort does not exhibit either pattern.

## Evidence

- **Bisection**: `Claude Code 2.1.107` and `2.1.110` resolve `--model opus` to `claude-opus-4-6`; `2.1.111` resolves it to `claude-opus-4-7`. Verified via `fo-log.jsonl` `assistant.message.model` stamps across CI artifact downloads.
- **Repro in CI**: the 2026-04-16 spot-check at 2.1.111 + opus/medium failed with `StepTimeout: Step 'SendMessage to echo-agent observed' did not match within 240s`. The ensign's on-disk stage report claims `ECHO: ping` was captured; the parent `fo-log.jsonl` tool-use inventory has zero `SendMessage` entries.
- **No-repro in isolation**: a minimal 3-step task (`Write` + `Bash cat` + report stdout) executed correctly on both `opus-4-6` and `opus-4-7` at `--effort low`. The simple case does not expose the bug.
- **Scope gap**: the ensign's prompt always includes the "Standing teammates available in your team" section listing the reply format per teammate. `opus-4-7` uses that visible description to compose plausible tool-call outcomes without issuing the tool calls.

## Impact across spacedock dispatches

The pattern affects every ensign dispatched via `claude-team build` when the captain session is on `opus-4-7` at `--effort low` or `--effort medium`:

- **Validation-stage ensigns**: may rubber-stamp hallucinated implementation reports. A PR could ship broken code that "passed validation" because the validator skipped re-running tests and fabricated a PASSED recommendation. This is the highest-risk surface.
- **Implementation-stage ensigns**: may claim tests passed without running them, fabricate stdout from shell commands, or skip Write/Edit operations while reporting DONE. Observable only if CI reruns the tests or the captain audits evidence.
- **Standing-teammate routing**: any ensign told to route to `comm-officer` or a future standing teammate may skip the `SendMessage` and write its own "polished" content. Output looks like the teammate produced it.
- **FO itself** on `opus-4-7`: may skip `status --set` calls, fabricate PR numbers, or claim merges that did not happen. Observable if the captain checks git state, but silent otherwise.
- **Feedback cycles**: reviewers may claim re-verification without re-running anything. The rejection → fix → accept pattern still looks clean.

## Not affected (as far as we know)

- **Bare mode** (`claude-live-bare` passed on `2.1.111`). Smaller tool surface without `SendMessage`; needs more testing before claiming safe.
- **Codex runtime**: different model-selection path; not affected by the Claude Code default-alias flip.
- **Haiku jobs**: haiku passed on `2.1.111` CI; does not exhibit the pattern.
- **Explicit `--model claude-opus-4-6` pinning**: bypasses `opus-4-7` entirely. Confirmed locally (test passed in 2m5s) and should be confirmed in CI once the #176 plumbing bug is fixed.

## Current mitigations and gaps

- **Streaming watcher** (#173, #175): catches hallucinations when a test explicitly asserts on a tool-call shape via `w.expect(tool_use_matches(...))`. Eight tests currently have this coverage. Real-world spacedock usage (production ensigns, not tests) has no such guard.
- **Dated-model pin** (#176): bypasses `opus-4-7` via `--model claude-opus-4-6` workflow input. Currently broken by a test-level plumbing bug (tests hardcode `--model opus` in `extra_args`).
- **Effort bump to `--effort high` or `--effort xhigh`**: tested in CI (runs `24539317900` / `24539318567` on `2.1.111` + `--model opus` + effort high/xhigh). The low/medium hallucination pattern does not appear — the ensign correctly emits the `SendMessage` to the standing teammate (milestone 4 passes). However, a different failure mode surfaces at both high and xhigh: milestone 5 (`ECHO: ping reply received`) times out at 240s. The reply from `echo-agent` (on sonnet) never appears in the parent `fo-log.jsonl` within the window, even though the FO proceeds to archive the entity as completed. Effort bump removes one regression and exposes another — not a full mitigation.

## Evidence at high/xhigh effort (2026-04-16 runs)

- **`24539317900` (opus/high)**: `test_standing_teammate_spawns_and_roundtrips` failed on both `claude-live` and `claude-live-opus`. Specific error: `StepTimeout: Step 'ECHO: ping reply received' did not match within 240s`. Parent `fo-log.jsonl` shows the ensign DID emit a `SendMessage` to `echo-agent` (milestone 4 passed), but `ECHO: ping` never lands in the stream.
- **`24539318567` (opus/xhigh)**: identical failure pattern. `ECHO: ping reply received` timeout at 240s, milestone 4 clean.

Possible causes (open for investigation):

- `echo-agent` reply is routed through a subagent stream not folded into the parent `fo-log.jsonl`, so the test's parent-stream-only assertion cannot observe it.
- `echo-agent` (sonnet) takes longer than 240s to respond on the `2.1.111` runner under teammate-message scheduling.
- `echo-agent` hallucinates its own reply internally but never emits a `SendMessage` back to the ensign or the FO — an echo-agent-side variant of the `opus-4-7` hallucination pattern, tested on sonnet.
- Claude Code `2.1.111`'s teammate-message fold-in into the parent stream has a behavior change that predates or accompanies the default-alias flip.

The FO treating the entity as complete despite the missing reply suggests the test's stream-visibility expectation and the runtime's actual stream-delivery shape have diverged somewhere in the `2.1.110` → `2.1.111` window.

## Open questions for ideation

- Should production use of spacedock with Claude Code 2.1.111+ default to `--model claude-opus-4-6` or require explicit model pinning?
- Should the FO add a post-ensign-completion verification step that cross-checks the stage report's DONE claims against tool-call evidence in the stream?
- Should the ensign prompt template change — e.g., drop the "Standing teammates available" section from dispatch prompts where the ensign does not need to route — to reduce the visible context that primes hallucination?
- Is an upstream Anthropic issue warranted? The `fo-log.jsonl` artifacts are a reasonable starting reproducer even without a minimal single-agent case.
- Does the pattern hit other model families (sonnet-4-6) at low effort, or is it specific to `opus-4-7`'s effort calibration?
- Is the high/xhigh-only `ECHO: ping reply received` timeout the same underlying `opus-4-7` behavior in a different guise (echo-agent-equivalent fabrication on sonnet), a separate test-harness fold-in issue, or a Claude Code `2.1.111` runtime regression? Needs direct inspection of the high-effort `fo-log.jsonl` artifacts and comparison against the `2.1.107` baseline.

## Out of Scope

- Fixing the behavior in Claude Code or the model itself. This task covers spacedock-side mitigations and user guidance.
- Full rewrite of the ensign dispatch template. Any template changes follow after ideation resolves which changes are warranted.
- Building a minimal single-agent reproducer. The 2026-04-16 session established that isolation does not cheaply expose the pattern; the `fo-log.jsonl` CI artifacts serve as the working reproducer for now.

## Cross-references

- #171 — `Agent(model=...)` teams-mode propagation. Distinct bug (Agent-level), same surface (ensign model inheritance). Footnote in #171 explains the distinction.
- #173 — streaming watcher; the only guard currently catching this in CI.
- #174 / #176 — CI bisection and mitigation plumbing.
- #175 — test migration expanding stream-based coverage to 6 more live tests.
- #178 — tool-call-discipline boilerplate (PR #113, branch `spacedock-ensign/tool-call-discipline`). #177 is the live experiment that decides whether #178 ships or whether we fall back to pinning `--model claude-opus-4-6`.
- A separate small task (not yet filed) will fix the `extra_args` plumbing bug so #176's `model_override` actually reaches `claude -p`. That unblocks the CI mitigation proof.

## Decision

This task is a **focused live experiment**, not a hallucination-mitigation thesis. The mitigation under test is #178 (the tool-call-discipline boilerplate already shipped on branch `spacedock-ensign/tool-call-discipline`, PR #113). #177's deliverable is a yes/no on whether that boilerplate makes `opus-4-7` viable at `--effort low` and `--effort medium` for the standing-teammate roundtrip case that originally exposed the regression.

Mechanics:

- Create a worktree stacked on top of `spacedock-ensign/tool-call-discipline` (NOT `main`), so the experiment runs against the #178 mitigation as it would actually ship.
- Drive three CI runs of the smallest fail-fast test we have: `tests/test_standing_teammate_spawn.py::test_standing_teammate_spawns_and_roundtrips`, on Claude Code `2.1.111`, against the stacked worktree. Two are the variables under test (`--model opus` + `--effort low`, `--effort medium`); one is a negative control (`--model claude-opus-4-6` to prove the test still passes when the 4-7 alias is bypassed).
- Outcome maps cleanly to two paths:
  - **PASSED at both low and medium**: recommend shipping #178 and leave the default `opus` alias alone. Capture this as a debrief note that unblocks #178's merge.
  - **FAILED at either**: recommend pinning `--model claude-opus-4-6` in workflow defaults and developer docs. Cite #176 as the plumbing prerequisite and file (or note the need for) the small follow-up that fixes the `extra_args` plumbing so the pin actually reaches `claude -p` in CI.

Explicitly **not** part of this task (per Out of Scope, restated for the staff reviewer):

- No FO-side post-completion verification design. That is a larger, separate mitigation surface.
- No further changes to the dispatch-prompt template beyond what #178 already ships. We are testing #178's prose, not iterating on it.
- No work on the high/xhigh `ECHO: ping reply received` timeout. That failure mode is a different surface (likely either a parent-stream fold-in regression or an echo-agent-side issue) and warrants its own task once this experiment lands.

## Acceptance Criteria

Each AC has a specific verify command, a clear pass/fail line, and the evidence to capture.

**AC-1 — Live CI: `--model opus` + `--effort low` on stacked branch passes.**

- Verify: dispatch `runtime-live-e2e.yml` against the stacked worktree branch with `claude_version=2.1.111`, `test_selector=tests/test_standing_teammate_spawn.py::test_standing_teammate_spawns_and_roundtrips`, `effort_override=low`. Job: `claude-live-opus`.
- Pass: job result `success`. The streaming watcher milestones for `SendMessage to echo-agent observed` and `ECHO: ping reply received` both fire within their per-step timeouts. Wallclock ≈ 2-3 minutes is the *pass* expectation (matching the `claude-opus-4-6` baseline established in #176); a fail-fast `StepTimeout` at 60-180s is not directly comparable to a pass wallclock — per-milestone times from the streaming watcher are the right granularity for fail attribution.
- Fail: any milestone times out, or job result `failure`. The streaming watcher's labeled `StepTimeout` identifies which milestone the boilerplate failed to discipline.
- Capture: run URL, the `claude-live-opus` job's `assistant.message.model` stamps from `fo-log.jsonl` (proves we actually ran on `opus-4-7`), wallclock.

**AC-2 — Live CI: `--model opus` + `--effort medium` on stacked branch passes.**

- Verify: same dispatch as AC-1 with `effort_override=medium`.
- Pass / Fail / Capture: identical shape to AC-1.

**AC-3 — Negative control: `--model claude-opus-4-6` on stacked branch passes.**

- Verify: same dispatch as AC-1 with `effort_override=low` and `model_override=claude-opus-4-6` (depends on the #176-follow-up `extra_args` plumbing fix; if that plumbing is still broken at experiment time, fall back to a local run with `--model claude-opus-4-6 --effort low` against the stacked worktree and capture the local wallclock + `fo-log.jsonl` model stamps as evidence). The local fallback MUST invoke `claude --version` matching the CI dispatch's `claude_version=2.1.111` — without that pin, a Claude Code version regression could mask as a model regression and contaminate the negative-control signal.
- Pass: job (or local run) result `success`. Test passes in the expected ~2-3 minute window. Model stamps in `fo-log.jsonl` show `claude-opus-4-6`.
- Fail: if this fails, the test itself is broken on the stacked branch and AC-1 / AC-2 results cannot be trusted. Stop the experiment and surface to the captain — the test must be fixed before the experiment can run.
- Capture: run URL (or local wallclock + log path), model stamps, wallclock, and for the local-fallback path the `claude --version` output proving 2.1.111.

**AC-4 — Recommendation deliverable matches the outcome.**

- If AC-1 and AC-2 both pass: write a debrief note to `docs/plans/opus-4-7-ensign-hallucination-scope.md` (Stage Report or a dedicated `## Outcome` section) recommending #178 ships as-is, citing the three run URLs and the wallclock numbers. The note explicitly unblocks #178's merge mod-block. The recommendation covers the standing-teammate roundtrip surface only; broader confidence across the five impact surfaces enumerated in #177's Impact section requires follow-up scoping and is out of scope for this experiment.
- If AC-1 or AC-2 fails (both fail, or either fails): write the same note recommending we pin `--model claude-opus-4-6` in workflow defaults and update `tests/README.md` (or equivalent developer-facing doc) to document the pin until the upstream Claude Code regression is resolved. Cite #176 as the plumbing dependency. File a small follow-up task (or note its need) covering the workflow-default change itself, since that change is mechanically separate from this experiment.
- Mixed outcome (AC-1 PASS / AC-2 FAIL, or AC-2 PASS / AC-1 FAIL): treat as the FAIL path above. Any low/medium failure on the standard surface is shipping risk, so the recommendation is to pin `--model claude-opus-4-6` rather than ship #178 with a known effort-level gap. Note the mixed outcome explicitly in the recommendation so the next iteration of #178 can target the failing effort level.
- Verify: the recommendation note exists in the entity body, references the captured run URLs, and states one of the two paths above unambiguously.
- Pass: a future reader can determine from the entity alone which path was taken and why.

## Test Plan

- **Cost in CI minutes**: ~3 runs × ~5 min wallclock (the streaming watcher fails fast at 60-180s if the regression appears; 5 min is a generous upper bound that includes runner spin-up). Total ≈ 15 CI minutes for the experiment, plus any retries.
- **Risk level**: low. No new code beyond what #178 ships. The streaming watcher (#173, #175) provides the observability needed to attribute pass/fail to the specific milestone, so a flaky failure is distinguishable from a real regression.
- **No new code is written by this task.** All implementation lives in #178; #177 only consumes it via the stacked worktree.
- **Dependencies**:
  - Implementation stage must branch from `spacedock-ensign/tool-call-discipline` (the #178 branch), not `main`.
  - AC-3 ideally depends on the `extra_args` plumbing fix mentioned in Cross-references. If that fix is not merged at experiment time, AC-3 falls back to a local run as documented above — the experiment is not blocked on that follow-up.
- **E2E tests**: yes, this entire task IS an E2E test. The unit tests for #178 already exist on the stacked branch (`test_claude_team_spawn_standing.py` extension); #177 does not add more.
- **Static checks**: none new. Sufficiency is established by the streaming watcher's labeled milestones — pass/fail attribution is structural, not log-archaeology.

## Implementation Notes

For the implementation stage, the following mechanics matter:

- **Worktree stack**: create the worktree from the #178 branch tip, e.g.

  ```
  git worktree add .worktrees/opus-4-7-experiment -b spacedock-ensign/opus-4-7-low-medium-experiment spacedock-ensign/tool-call-discipline
  ```

  This branches the experiment off the mitigation branch so CI dispatches against the experiment branch include #178's prose.

- **If #178's branch advances during the experiment**: rebase the experiment branch onto the new tip (`git rebase spacedock-ensign/tool-call-discipline` from inside the worktree), force-push the experiment branch (`--force-with-lease`, never plain `--force`), and re-dispatch the affected CI runs. Document the rebase in the stage report so the captured run URLs are unambiguous about which #178 commit they tested.

- **CI dispatch shape** (canonical form for AC-1):

  ```
  gh workflow run runtime-live-e2e.yml \
    --ref spacedock-ensign/opus-4-7-low-medium-experiment \
    -f claude_version=2.1.111 \
    -f test_selector=tests/test_standing_teammate_spawn.py::test_standing_teammate_spawns_and_roundtrips \
    -f effort_override=low
  ```

  AC-2 swaps `effort_override=medium`. AC-3 adds `-f model_override=claude-opus-4-6` and depends on the plumbing fix; otherwise run locally inside the worktree with `make test-live-claude-opus` after editing the Makefile target's model flag (or invoke pytest directly).

- **Evidence the implementation stage MUST capture**:
  - Run URL for each CI dispatch (AC-1, AC-2, optionally AC-3).
  - Experiment branch SHA at dispatch time (`gh run view` exposes it; record inline to survive any `--force-with-lease` rebases that advance the experiment branch mid-run).
  - Model stamp from each run's `fo-log.jsonl` `assistant.message.model` field — this proves the run actually executed on `claude-opus-4-7` (or `-6` for the control). Without this, a green AC-1/AC-2 could be a false positive caused by a silent alias resolution somewhere in the stack.
  - Wallclock per run, both the streaming watcher's reported milestone times and the overall job duration.
  - For any FAILED run: the labeled `StepTimeout` message identifying which milestone fired, plus a one-paragraph attribution against the same milestone in #178's stage report (does the boilerplate visibly fail to discipline this specific tool call shape?).

- **What the implementation stage should NOT do**:
  - Do not modify #178's prose. If the boilerplate needs iteration, that is a separate task (a fail outcome on #177 + a new mitigation attempt).
  - Do not try to reproduce the high/xhigh `ECHO: ping reply received` failure here. It is a different surface; out of scope per the Decision section.
  - Do not file the workflow-default-pin change as part of this task in the FAIL path — write the recommendation note and let the captain triage filing.

## Stage Report (ideation)

### Summary

Sharpened #177 from an open-ended scoping document into a focused live experiment spec. The experiment stacks on the #178 mitigation branch, runs three CI dispatches against `tests/test_standing_teammate_spawn.py::test_standing_teammate_spawns_and_roundtrips` on Claude Code 2.1.111, and outputs a binary recommendation: PASS → ship #178; FAIL → pin `--model claude-opus-4-6`. No new code, ~15 CI minutes, observability already in place via the streaming watcher.

### Checklist

1. **Read entity body in full.** DONE. Problem Statement, Evidence, Impact, Not-affected, Current mitigations, Evidence at high/xhigh, Open questions, Out of Scope, and Cross-references all read. Substantive sections preserved unchanged per the dispatch instruction.
2. **Read #178's design.** DONE. `docs/plans/ensign-prompt-tool-call-discipline-boilerplate.md` reviewed in full. Boilerplate text and placement (between Completion checklist and Summary placeholder) confirmed. Branch `spacedock-ensign/tool-call-discipline` has three commits including stage report; PR #113 is the open mitigation.
3. **Skim #173, #175, #176 for context.** DONE. Found in `docs/plans/_archive/`. #173 shipped `FOStreamWatcher` + `run_first_officer_streaming` (PR #109). #175 migrated 6 more live tests to the streaming watcher pattern (PR #111). #176 added `model_override` workflow input (PR #110); the `extra_args` plumbing follow-up referenced in #177's Cross-references is noted as the AC-3 dependency. None of these were redesigned or duplicated.
4. **`## Decision` section.** DONE. States plainly: focused live experiment, stacked on #178 (not main), three runs, two-path outcome (PASS → ship #178; FAIL → pin `--model claude-opus-4-6` per #176 plumbing). Explicit non-goals reiterated for the staff reviewer.
5. **`## Acceptance Criteria` section.** DONE. Four ACs: AC-1 (live CI opus-4-7 + low), AC-2 (live CI opus-4-7 + medium), AC-3 (negative control on opus-4-6 with local-fallback if #176 plumbing not yet fixed), AC-4 (recommendation deliverable matching the outcome). Each AC has verify command, pass/fail line, and capture list.
6. **`## Test Plan` section.** DONE. ~3 runs × ~5 min = ~15 CI minutes. Risk: low (no new code, observability via streaming watcher already shipped). E2E: yes (this task IS the E2E test). Static checks: none new — milestone-labeled `StepTimeout` handles attribution.
7. **`## Implementation Notes` section.** DONE. Worktree command (`git worktree add ... -b spacedock-ensign/opus-4-7-low-medium-experiment spacedock-ensign/tool-call-discipline`), rebase mechanics if #178 advances mid-experiment (`--force-with-lease`, never plain force), canonical `gh workflow run` shape, evidence-capture list (run URLs, `assistant.message.model` stamps from `fo-log.jsonl`, wallclock, labeled `StepTimeout` for fails), explicit do-not list.
8. **Update existing sections only if needed for sharpening.** PARTIAL. Added one line to `## Cross-references` linking #178 explicitly as the mitigation-under-test (the existing list mentioned #173/#174/#175/#176 but not #178). Problem Statement, Evidence, Impact, Not affected, Current mitigations, Evidence at high/xhigh, Open questions, and Out of Scope sections all preserved verbatim — they are correct and load-bearing.
9. **Commit on main.** Pending — will execute after this report is written. On `main` (clean working tree at start), so the commit will be `ideation: #177 experiment spec — stack on #178, opus-4-7 low/medium live test`. Not in a worktree; the dispatch instruction's worktree-commit branch is N/A.
10. **Stage Report.** DONE (this section).

### Recommendation for the ideation gate

**PASS.** The spec is now a tight, falsifiable experiment with a clear two-path outcome and proportionate test plan. Total cost ≈ 15 CI minutes, no new code, observability already in place. The staff reviewer should focus on whether AC-3's local-run fallback is acceptable when the #176-follow-up plumbing fix is not yet merged, and whether AC-4's PASS/FAIL deliverable shape (an in-entity recommendation note) is sufficient versus requiring a separate doc edit.

## Staff Review

**Verdict: APPROVE WITH CHANGES.** The spec is structurally sound as a binary ship/pin signal for #178, and the scoping discipline (no new code, ~15 CI min, single test) is correct given the broader scoping evidence already captured in the Problem Statement / Impact / Evidence sections. Two structural gaps warrant surgical fixes before implementation; neither requires re-ideation.

### Design soundness

The experiment cleanly answers "does #178's boilerplate make opus-4-7 viable at low/medium effort for the standing-teammate roundtrip case?" — not "is opus-4-7 broadly safe." The Decision section (lines 89-105) is explicit about that narrowing, which is the right call. ACs are independent (each is one CI dispatch with one varied parameter), falsifiable (labeled `StepTimeout` attribution from the streaming watcher), and verifiable (run URL + model stamp + wallclock).

One silent assumption in the Decision (lines 96-99): treating `opus-4-7 + low` and `opus-4-7 + medium` as a unit ("PASSED at both" → ship; "FAILED at either" → pin) presupposes that hallucination behavior is monotonic across effort levels. The Evidence section (lines 21-26) only directly evidences the regression at one effort, and the high/xhigh evidence (lines 51-63) shows behavior is *non*-monotonic across effort (different failure mode at high). A mixed AC-1 PASS / AC-2 FAIL outcome is neither addressed in AC-4 (lines 130-135) nor in the Decision's two-path mapping. Recommend AC-4 explicitly cover the mixed-outcome case (likely: pin, since any low/medium failure on the standard surface is shipping risk).

### Test plan sufficiency

One test is the right scope here — not because the surface is small (it isn't; the Impact section enumerates five distinct dispatch shapes), but because the broader scoping work is already in #177's Problem/Evidence/Impact sections, and #178 is a binary mitigation question. Generalizing #178's efficacy across all five impact surfaces would require its own scoping task and is reasonably out of scope for a "should we merge PR #113" decision. The Test Plan (lines 137-146) should make this scoping logic explicit so a future reader does not over-claim from a green result — recommend a one-line note in AC-4's PASS-path deliverable that the recommendation covers the standing-teammate roundtrip surface only, and broader confidence requires follow-up.

### Ideation-flagged questions

**(a) AC-3 local-fallback acceptability (line 125).** The fallback is acceptable for the negative-control role *only if* the local run uses the same Claude Code version (2.1.111) as the CI runs. The CI-runner-vs-local-machine confound is real but secondary — what AC-3 actually controls for is "is the test broken on the stacked branch, independent of model," and that signal survives the environment change. Recommend AC-3 add an explicit note: local run must use `claude --version` matching the CI dispatch's `claude_version=2.1.111`, captured in the evidence list. Without that pin, the fallback could mask a Claude Code version-induced failure as a model-induced one.

**(b) AC-4 deliverable shape (lines 130-135).** The in-entity note is the right deliverable for the PASS path (it unblocks #178's mod-block, which is the operative action). For the FAIL path, the recommendation note alone does NOT change behavior — workflow defaults still resolve `opus` to `opus-4-7`. The current spec correctly defers the workflow-default edit ("File a small follow-up task," line 133), but the FAIL path should be explicit that until that follow-up lands, the ensign hallucination remains live in production. Recommend AC-4 FAIL path require both the in-entity note AND a filed follow-up task (or issue) with a specific title, so the captain can't mistake "recommendation written" for "behavior changed."

### Gaps

- **Mixed-outcome handling**: covered above; AC-4 needs the third path.
- **`--force-with-lease` + captured run URL** (line 160): rebasing the experiment branch loses the SHA history the run URL was tested against. The Implementation Notes evidence list (lines 174-178) requires `assistant.message.model` stamps but not the experiment-branch SHA at dispatch time. Recommend adding "experiment branch SHA at dispatch" to the capture list — `gh run view` exposes it, but recording it inline in the entity prevents post-rebase ambiguity.
- **Wallclock comparison fairness** (line 114): the "matching the `claude-opus-4-6` baseline" comparison is fine when both pass, but a fail-fast `StepTimeout` at 60-180s is not directly comparable to a 2-3 minute pass. This isn't a structural problem — the streaming watcher's per-milestone times are the right comparison granularity — but the AC-1 Pass line should clarify that "wallclock ≈ 2-3 min" is the *pass* expectation, not a fail comparison.
- **Open question #6 (line 72)** about high/xhigh `ECHO: ping reply received` is correctly out of scope per Decision line 105; flagging only that a future reader of this entity should not conflate the two failure surfaces. The Decision's explicit non-goal already handles this; no change needed.

## Stage Report (staff review)

### Summary

Independent second-opinion read on #177's ideation spec. Verdict: **APPROVE WITH CHANGES** — the experiment is structurally sound and proportionately scoped, with two surgical fixes recommended (mixed-outcome AC-4 path; AC-3 Claude Code version pin) and three smaller capture/clarification gaps. Ideation ensign's own PASS recommendation is roughly correct; the changes are additive, not blocking re-ideation.

### Checklist

1. **Staff reviewer role, append-only `## Staff Review` section.** DONE. Did not modify Decision (lines 89-105), Acceptance Criteria (107-135), Test Plan (137-146), Implementation Notes (148-183), or the ideation Stage Report. Only appended `## Staff Review` and this `## Stage Report (staff review)` section.
2. **Read entity body in full, paying attention to flagged sections.** DONE. Read all of #177; specifically scrutinized Decision, ACs, Test Plan, Implementation Notes, and the ideation ensign's two reviewer-flags (AC-3 fallback, AC-4 deliverable shape).
3. **Read #178's design.** DONE. `docs/plans/ensign-prompt-tool-call-discipline-boilerplate.md` reviewed in full — boilerplate prose, placement (between checklist and Summary placeholder), and acceptance criteria all parsed. Confirms #177's experiment tests the right artifact.
4. **Assess design soundness.** DONE. Captured in Staff Review § Design soundness. Key finding: silent assumption that low and medium hallucination behave monotonically; AC-4 lacks a mixed-outcome path.
5. **Assess test plan sufficiency.** DONE. Captured in Staff Review § Test plan sufficiency. One test is right scope for binary ship/pin signal; recommended a clarifying note that PASS recommendation covers standing-teammate roundtrip surface only.
6. **Address AC-3 fallback and AC-4 deliverable shape flags.** DONE. Captured in Staff Review § Ideation-flagged questions. AC-3 fallback acceptable with `claude_version=2.1.111` pin made explicit. AC-4 FAIL path needs filed follow-up, not just in-entity note, since the note alone does not change production behavior.
7. **Look for gaps.** DONE. Captured in Staff Review § Gaps: mixed-outcome handling (AC-4), experiment-branch SHA capture under `--force-with-lease` rebase (Implementation Notes evidence list), wallclock-comparison clarification (AC-1 Pass line), and confirmed high/xhigh failure-mode separation is already handled.
8. **Append `## Staff Review` section, 300-500 words.** DONE. Section is structured per the dispatch instruction (verdict summary; Design soundness; Test plan sufficiency; Ideation-flagged questions a/b; Gaps). Length within budget (≈540 words including verdict line, slightly over the upper bound because the mixed-outcome and AC-3 version-pin findings are concrete structural requests rather than minor notes).
9. **Commit on main.** Pending — will commit after writing this report. Working tree was clean on `main` at start; commit message will be `staff-review: #177 ideation — APPROVE WITH CHANGES`.
10. **`## Stage Report (staff review)` at very end.** DONE (this section).

### One-line summary for the captain

Ideation is structurally sound; APPROVE WITH CHANGES — two surgical fixes (AC-4 mixed-outcome path + AC-3 Claude Code version pin) and three minor capture/clarification gaps; no re-ideation needed.

## Ideation Revision (post-staff-review)

Folded the staff reviewer's APPROVE-WITH-CHANGES findings into the ideation in place:

- **Surgical Fix #1 (AC-4 mixed-outcome path)**: AC-4 now has an explicit third bullet for mixed outcomes (AC-1 PASS / AC-2 FAIL or vice versa), routed to the FAIL path (pin `--model claude-opus-4-6`) since any low/medium failure on the standard surface is shipping risk.
- **Surgical Fix #2 (AC-3 Claude Code version pin)**: AC-3's local-fallback now requires `claude --version` matching the CI dispatch's `claude_version=2.1.111`, with the version output added to the AC-3 capture list.
- **Gap #1 (experiment-branch SHA capture)**: Implementation Notes evidence list now includes the experiment-branch SHA at dispatch time, with a note that `gh run view` exposes it and recording it inline survives `--force-with-lease` rebases.
- **Gap #2 (AC-1 wallclock clarification)**: AC-1 Pass line now states that "wallclock ≈ 2-3 min" is the *pass* expectation and that fail-fast `StepTimeout` at 60-180s is not directly comparable; per-milestone times from the streaming watcher are the right granularity for fail attribution. AC-2 inherits via "identical shape to AC-1."
- **Gap #3 (AC-4 PASS-deliverable surface-scope note)**: AC-4 PASS path now states the recommendation covers the standing-teammate roundtrip surface only, and broader confidence across the five impact surfaces enumerated in the Impact section requires follow-up scoping.

The original Decision (lines 89-105), Test Plan, and Implementation Notes structure is unchanged — edits were surgical insertions/clarifications within already-flagged lines, not rewrites of unflagged sections. The `## Staff Review` and `## Stage Report (staff review)` sections are preserved verbatim as the audit record of what the reviewer found.

## Stage Report (ideation revision)

### Summary

Folded all five staff-reviewer findings into #177's ideation in place. Two surgical AC fixes (AC-4 mixed-outcome path; AC-3 version pin) and three smaller gap closures (SHA capture; wallclock clarification; PASS-path surface-scope note). Decision, Test Plan, and Implementation Notes structure unchanged; Staff Review and its Stage Report preserved as audit record. Ready to re-present at the ideation gate.

### Checklist

1. **Read entity body in full.** DONE. Read all 258 lines including Decision (89-105), ACs (107-135), Test Plan (137-146), Implementation Notes (148-183), and the Staff Review section (208-233) that drives this revision.
2. **Surgical Fix #1: AC-4 mixed-outcome path.** DONE. Added a third bullet to AC-4 covering mixed outcomes (AC-1 PASS / AC-2 FAIL or vice versa), routed to the FAIL path (pin `claude-opus-4-6`) per the staff reviewer's recommended treatment. Mixed outcome must be noted explicitly so the next iteration of #178 can target the failing effort level.
3. **Surgical Fix #2: AC-3 Claude Code version pin.** DONE. AC-3's local-fallback path now requires `claude --version` matching CI's `claude_version=2.1.111`, with the rationale (a Claude Code version regression could mask as a model regression) stated inline. The capture list now includes the version output for the local-fallback path.
4. **Gap #1: experiment-branch SHA capture.** DONE. Added a new bullet to the Implementation Notes evidence list (between run URL and model stamp) requiring the experiment branch SHA at dispatch time, with the staff reviewer's exact phrasing about `gh run view` exposing it and recording it inline to survive `--force-with-lease` rebases.
5. **Gap #2: AC-1 wallclock clarification.** DONE. AC-1 Pass line now distinguishes the 2-3 min wallclock as the *pass* expectation and notes that fail-fast `StepTimeout` at 60-180s is not directly comparable. AC-2's "identical shape to AC-1" inherits the clarification automatically.
6. **Gap #3: AC-4 PASS-deliverable surface-scope note.** DONE. AC-4 PASS path now ends with a sentence that the recommendation covers the standing-teammate roundtrip surface only, and broader confidence across the five impact surfaces enumerated in #177's Impact section requires follow-up scoping.
7. **Do not modify Staff Review or its Stage Report.** DONE. Both sections (lines 208-258 in the pre-revision file) are untouched. Verified by inspection — only AC-1, AC-3, AC-4, and the Implementation Notes evidence list were edited.
8. **Do not broaden scope.** DONE. No new ACs added; Decision, Test Plan, and unflagged sections of Implementation Notes preserved verbatim. All edits sit inside already-flagged lines.
9. **Append `## Ideation Revision (post-staff-review)` section.** DONE. Cross-references each fold-in by the staff reviewer's labels (Surgical Fix #1, #2, Gap #1, #2, #3) and confirms the original Decision/Test Plan/Implementation Notes structure is unchanged.
10. **Commit on main.** Pending — will run immediately after this report write completes. Working tree was clean on `main` at start; commit message per the dispatch: `ideation-revision: #177 fold staff-review findings — AC-4 mixed-outcome path, AC-3 version pin, SHA capture, wallclock clarification, surface-scope note`.
11. **`## Stage Report (ideation revision)` at very end.** DONE (this section).

### One-line summary for the captain

Staff-review fold-in complete: two surgical AC fixes and three gap closures applied verbatim; Decision/Test Plan/Implementation Notes structure unchanged; ready to re-present at the ideation gate.
