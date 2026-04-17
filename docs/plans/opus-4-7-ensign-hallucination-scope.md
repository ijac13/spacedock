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

## Repurpose: Layer 2 Mitigation Investigation

**Proposed new title (FO updates frontmatter):** "opus-4-7 ensign hallucination — root cause investigation and Layer 2 mitigation experiments"

### Preamble (captain-directed pivot)

The original experiment (Decision lines 89-105, ACs lines 107-138, Outcome, Stage Reports, Staff Review) ran cleanly on 2026-04-16 and produced a definitive negative result: AC-1 and AC-2 both FAILED on the stacked #178 mitigation branch (boilerplate prose did not discipline `opus-4-7` at low/medium effort), and AC-3 was BROKEN (the negative-control surfaced an independent failure that contaminated the signal). Those sections above are PRESERVED VERBATIM as the audit trail that motivates this pivot — do not edit them.

The captain has redirected this entity to investigate **Layer 2 prompt-shape mitigations**: hypotheses about *which part* of the dispatch prompt primes `opus-4-7`'s fabrication behavior, so that a future engineering task can target the actual priming surface rather than wrapping more boilerplate around it.

### Decision

This entity now investigates whether prompt-shape mitigations can address `opus-4-7` hallucination at low/medium effort. The primary hypothesis under test: the **rich teammate descriptions** in the dispatch prompt's `### Standing teammates available in your team` section (introduced in commit `0acd6501`, "claude-team build auto-enumerates alive standing teammates into dispatch prompts") prime `opus-4-7` to fabricate plausible tool-call outcomes. The full per-teammate routing usage body (Patterns 1-4 for `comm-officer`, four caller patterns with example syntax) is exactly the surface a model could use to compose a believable `SendMessage` outcome without emitting the call.

Three independent experiments, each isolating a different variable, each ~5 minutes of local execution. Each experiment falsifies a distinct sub-hypothesis. Outcomes feed into a single `## Repurpose Outcome` section the implementation will write, recommending which prompt-shape mitigation (if any) should become a future engineering task.

The history complication noted in the dispatch (test_standing_teammate_spawn.py was added in `8ac41339` *before* the standing-teammates section in `0acd6501`) means the naive "go back in time and re-run the test" approach does not isolate the section's contribution — the test inherently requires the section to pass. AC-R1 and AC-R2 work around this: AC-R1 picks a *different* test that does not exercise teammate routing at all (so the section's presence is irrelevant to the test's pass condition), and AC-R2 patches the section in place to keep it structurally present but strip its rich content.

Out-of-scope per original entity discipline (restated):
- Building new infrastructure as ACs (e.g., new prompt-assembly modes, FO-side post-completion verification).
- Forcing API tool choice (`tool_choice: any` or similar SDK-level mitigation).
- Iterating on #178's prose. The original experiment killed that path.

### Acceptance Criteria

Each AC has Verify command, Pass/Fail line, and Capture list. All ACs run locally — no CI dispatch needed.

**AC-R1 — Counterfactual on a non-routing test.**

- Hypothesis isolated: "the regression is *specific to* dispatch prompts that contain the standing-teammates section." If a test that does NOT involve standing teammates passes on `opus-4-7` + low effort, the section is implicated as the priming surface. If it fails with the same hallucination class, the regression is independent of the section and prompt-shape mitigation will not help.
- Test selected: `tests/test_gate_guardrail.py::test_gate_guardrail`. Verified clean (no `standing`/`teammate`/`comm-officer`/`echo-agent` references in the file). It is the cheapest live test in the repo (~60s, ~$0.02 haiku per `tests/README.md` lines 192-199), runs on a minimal gated workflow fixture with no teammate routing.
- Verify (run from repo root):

  ```
  unset CLAUDECODE && uv run pytest tests/test_gate_guardrail.py \
    --runtime claude --model opus --effort low -v
  ```

  Confirm `claude --version` reports `2.1.111` (or 2.1.112 — note Claude Code drift is mild; original Evidence shows the regression observed on both). Capture `claude --version` output before the run.
- Pass: pytest exit code 0, all gate-guardrail assertions pass. Standing-teammates section is implicated as the priming surface.
- Fail: pytest fails with the same FO-level hallucination class (FO claims status changes / archives without the corresponding tool calls). Section is NOT the priming; prompt-shape mitigation through stripping the section will not help.
- Capture: `claude --version` output, pytest exit code, the test's `KEEP_TEST_DIR=1`-preserved `fo-log.jsonl`, and the `assistant.message.model` stamps from that log proving the run actually executed on `claude-opus-4-7`. For a fail, the specific assertion that fired and the tool-call inventory around it.

**AC-R2 — Section-stripped variant on the standing-teammate test.**

- Hypothesis isolated: "the *richness* of teammate descriptions (full Patterns 1-4 prose, examples, routing contracts) is what primes fabrication, not the section's mere presence." A minimal one-line-per-teammate variant lets us keep the structural section but remove the prose surface. If the test passes, rich descriptions are the priming and the fix is to compress them. If it fails, the section's presence itself is the priming and a deeper change (remove the section entirely, or use a different routing-discovery mechanism) would be needed.
- Patch target: `skills/commission/bin/claude-team` lines 276-308, the `enumerate_alive_standing_teammates` block. The MINIMAL variant emits only:

  ```
  ### Standing teammates available in your team

  - {name} is available; SendMessage to it.
  ```

  one line per teammate, no descriptions, no per-pattern usage bodies, no "Full routing contract" footer. The implementation patches the loop in place inside the worktree (do NOT push or merge — this is an experimental local patch).
- Verify: from inside the rebased worktree (see Implementation Notes), apply the minimal patch to `skills/commission/bin/claude-team`, then run:

  ```
  unset CLAUDECODE && uv run pytest \
    tests/test_standing_teammate_spawn.py::test_standing_teammate_spawns_and_roundtrips \
    --runtime claude --model opus --effort low -v
  ```

- Pass: pytest exit code 0; both `SendMessage to echo-agent observed` and `ECHO: ping reply received` milestones fire. Rich descriptions are the priming surface; the engineering follow-up is to compress the section's emission.
- Fail: same milestone timeouts as the original AC-1 failure (most likely `SendMessage to echo-agent observed` at 240s). Section presence (not its richness) is the priming, OR the priming sits elsewhere in the prompt entirely (Completion Signal block, "via SendMessage" mention in the section header, etc.). Engineering follow-up needs to investigate further before settling on a fix.
- Capture: the patch diff (paste into the entity's stage report), pytest exit code, the preserved `fo-log.jsonl` model stamps, milestone timing breakdown from the streaming watcher's labeled output. For a fail, capture the dispatch prompt as it appeared with the patch applied (read the `Agent` tool_use input from `fo-log.jsonl`) so the next investigator can confirm the patch took effect.

**AC-R3 — Different ensign model.**

- Hypothesis isolated: "this is `opus-4-7`-specific calibration; `sonnet` does not exhibit the pattern." A working alternative ensign model is a viable workaround independent of any prompt-shape fix and is worth knowing even if AC-R1/AC-R2 produce a clean answer.
- Verify:

  ```
  unset CLAUDECODE && uv run pytest \
    tests/test_standing_teammate_spawn.py::test_standing_teammate_spawns_and_roundtrips \
    --runtime claude --model sonnet --effort low -v
  ```

  No code patch — this exercises the standard prompt assembly with `--model sonnet` instead of `--model opus`.
- Pass: pytest exit code 0; both teammate-routing milestones fire. `sonnet` is a viable ensign-model workaround; the captain can pin `--model sonnet` in workflow defaults as a safer default than `--model opus` until upstream is fixed.
- Fail: pytest fails on the same milestones. `sonnet` ensign also has problems — not a clean workaround. The pattern is broader than `opus-4-7`-specific calibration; root cause is likely either the prompt shape (across models) or a Claude Code runtime issue.
- Capture: pytest exit code, `fo-log.jsonl` `assistant.message.model` stamps proving the ensign sub-call actually used `sonnet` (NOT `opus`), milestone timing.

### Test Plan

- **Mechanics**: each AC is a single local `pytest` invocation against a real Claude runtime. The streaming watcher (#173) provides per-milestone fail attribution; preserved `fo-log.jsonl` artifacts (set `KEEP_TEST_DIR=1`) provide the audit evidence (model stamps, tool-call inventory).
- **Cost**: ~5 min per AC, ~15-20 min total. AC-R1 is the cheapest (gate-guardrail, no teammate roundtrip); AC-R2 and AC-R3 each run the standing-teammate test with its 4 milestone × 240s budget but typically fail-fast at ~60-180s when the regression appears.
- **Local execution only**: no CI dispatch. The original experiment burned three CI dispatches; the Layer 2 investigation does not need them — local runs with the streaming watcher provide the same evidence quality. Cost in CI minutes: zero.
- **Claude Code version**: ideally `2.1.111` to match the original experiment, but `2.1.112` is acceptable per the original Evidence (regression observed on both). Capture `claude --version` for each AC so the gate review can confirm version drift did not contaminate the result.
- **Static checks**: none new. The streaming watcher's labeled milestones and the `fo-log.jsonl` model stamps are the structural evidence.
- **E2E tests**: yes — these three ACs ARE E2E experiments. No new test code; AC-R2 patches existing infrastructure locally; AC-R1 and AC-R3 use existing tests with different CLI flags.

### Implementation Notes

**Worktree state**. The existing 177 worktree at `.worktrees/spacedock-ensign-opus-4-7-ensign-hallucination-scope` is checked out at #178's tip (`e1a087df`) and lacks #179's plumbing fix (#180, commit `addcbeee` on main). For the Layer 2 experiments, the implementer should:

- **Option A (preferred)**: rebase the existing worktree onto current `main`. From inside the worktree:

  ```
  git fetch origin
  git rebase origin/main
  ```

  This brings #179's plumbing fix and the latest `claude-team build` source code (which AC-R2 will patch).

- **Option B**: discard the existing worktree and recreate from main. From the repo root:

  ```
  git worktree remove .worktrees/spacedock-ensign-opus-4-7-ensign-hallucination-scope
  git worktree add .worktrees/spacedock-ensign-opus-4-7-ensign-hallucination-scope -b spacedock-ensign/opus-4-7-layer-2 main
  ```

  Cleaner but loses any in-progress local state from the original experiment.

Either option gives the implementer up-to-date plumbing AND the latest claude-team source. Pick Option A unless the existing worktree has uncommitted state that makes rebase messy.

**AC-R2 patch shape**. The patch replaces the loop body at `skills/commission/bin/claude-team:287-301` (the `for name, description, mod_path in standing_teammates:` block) with a single line per teammate:

```python
for name, description, mod_path in standing_teammates:
    lines.append(f'- {name} is available; SendMessage to it.')
```

And drops the "Full routing contract" footer at lines 303-307. Apply the patch, run the test, capture the diff into the stage report, then `git stash` or `git checkout` to revert before any other AC runs (so AC-R3's run uses the unpatched, standard prompt).

**Evidence to capture for each AC** (write into the `## Repurpose Outcome` section):

- `claude --version` output (proves the runtime version).
- pytest exit code and the specific assertion / milestone that fired (for fails).
- `assistant.message.model` stamps from the relevant `fo-log.jsonl` (proves the model actually executed; AC-R1 should show `claude-opus-4-7` for both FO and ensign, AC-R3 should show `sonnet` for the ensign sub-call).
- Per-milestone timing from the streaming watcher's labeled `StepTimeout` output (for AC-R2 and AC-R3 fails).
- For AC-R2: the patch diff and the dispatched prompt's standing-teammates section (extract from `fo-log.jsonl` `Agent` tool_use input) so a future reader can confirm the patch took effect.

**What the implementation MUST NOT do**:

- Do not commit the AC-R2 patch. It is a local experimental patch; revert before AC-R3 runs.
- Do not modify the original experiment's sections (Decision lines 89-105, ACs 107-138, Outcome, Stage Reports, Staff Review). Those are preserved audit trail.
- Do not add a fourth experiment. The three are scoped to be independent; any further hypothesis goes into a follow-up entity.
- Do not propose API-level mitigations (tool_choice forcing, SDK-level changes) — out of scope per the captain's directive.

The actionable output is a `## Repurpose Outcome` section recommending which prompt-shape mitigation (if any) actually moves the needle, evidence-backed, ready to feed into a future engineering task.

## Stage Report (ideation revision, repurpose)

### Summary

Repurposed #177 to investigate Layer 2 prompt-shape mitigations after the original experiment's AC-1/AC-2 FAIL + AC-3 BROKEN outcome falsified #178's boilerplate approach. Three independent local experiments (~15-20 min total): AC-R1 isolates the standing-teammates section's contribution via a non-routing test (`test_gate_guardrail`); AC-R2 isolates the section's *richness* via a minimal-content patch on `claude-team`; AC-R3 isolates `opus-4-7`-specific calibration via a `sonnet` ensign run. All original sections preserved verbatim as audit record.

### Checklist

1. **Read entity body in full and recognize the captain-directed pivot.** DONE. Read all 294 lines of the pre-repurpose file. Recognized the original experiment ran cleanly and is factual; AC-1/AC-2 failed and AC-3 broke as documented. The captain's pivot redirects to Layer 2 hypothesis testing while preserving the original sections as audit trail.
2. **Read FO-as-API use-cases spec and #178 body.** DONE. `docs/superpowers/specs/2026-04-17-spacedock-fo-as-api-use-cases.md` reviewed (full architecture context; Use Case 4 directly cites #177 as the failure pattern motivating hallucination-resistant API mutations). `docs/plans/ensign-prompt-tool-call-discipline-boilerplate.md` reviewed (#178's boilerplate prose, placement between Completion checklist and Summary placeholder, AC-3 acknowledges the experiment may produce a negative result — which it did).
3. **Investigate standing-teammate prompt section history.** DONE. `git log --oneline --all -S 'Standing teammates available in your team' -- skills/commission/bin/claude-team` returns one commit: `0acd6501 impl: #162 cycle 2 — claude-team build auto-enumerates alive standing teammates into dispatch prompts`. `git log --oneline --diff-filter=A -- tests/test_standing_teammate_spawn.py` returns `8ac41339 tests: #162 live E2E standing teammate spawn + roundtrip fixture`. Test was added BEFORE the section emission (the test inherently requires the section), so a naive "go back in time" experiment does not isolate the variable. Recorded in the Decision section's history-complication paragraph.
4. **Identify candidate non-routing live tests.** DONE. Surveyed `tests/`: skipped/xfail tests (`test_scaffolding_guardrail`, `test_repo_edit_guardrail`, `test_rejection_flow`, `test_push_main_before_pr`, `test_dispatch_completion_signal`, etc.) are not viable. `test_gate_guardrail.py` is clean (verified no `standing`/`teammate`/`comm-officer`/`echo-agent` references via grep), is the cheapest live test in the repo per `tests/README.md` lines 192-199, and exercises the FO+ensign loop on a gated workflow fixture without teammate routing. Selected as AC-R1's test.
5. **Append `## Repurpose: Layer 2 Mitigation Investigation` section after all existing sections.** DONE. Section appended after the existing `## Stage Report (ideation revision)` (line 294). Preamble explains the captain-directed pivot and links to the original AC-3 BROKEN finding as the trigger.
6. **Write `### Decision` subsection.** DONE. Names the primary hypothesis (rich teammate descriptions in the dispatch prompt prime `opus-4-7` fabrication), three independent experiments, ~5 min cost each, single `## Repurpose Outcome` section as the actionable output. Out-of-scope items restated per original entity discipline.
7. **Write `### Acceptance Criteria` for three experiments.** DONE. AC-R1 (counterfactual on `test_gate_guardrail`), AC-R2 (section-stripped variant on standing-teammate test, with explicit patch shape), AC-R3 (sonnet ensign on standing-teammate test). Each AC has Verify command, Pass/Fail line, and Capture list per the dispatch instruction.
8. **Write `### Test Plan`.** DONE. Local-execution mechanics, `KEEP_TEST_DIR=1` for evidence preservation, streaming watcher per-milestone attribution, ~15-20 min total cost, no CI dispatch, Claude Code version capture (2.1.111 ideally; 2.1.112 acceptable per original Evidence).
9. **Write `### Implementation Notes` with worktree state guidance.** DONE. Option A (rebase existing worktree onto main) preferred; Option B (recreate from main) as alternative. Both bring #179 plumbing + latest `claude-team` source. AC-R2 patch shape spelled out (replace loop body at `claude-team:287-301`; drop the routing-contract footer). Evidence-capture list and explicit must-not list included.
10. **Update title in prose.** DONE. Proposed title at top of Repurpose section: "opus-4-7 ensign hallucination — root cause investigation and Layer 2 mitigation experiments" — for the FO to pick up in frontmatter.
11. **Commit on main.** Pending — will run immediately after this report write completes. Working tree was clean on `main` at start.
12. **Stage Report (ideation revision, repurpose) at very end.** DONE (this section).
13. **Do NOT modify existing sections.** DONE. Original Decision (lines 89-105), Acceptance Criteria (107-138), Test Plan (137-146), Implementation Notes, Outcome, Stage Reports, Staff Review, and Stage Report (staff review) all preserved verbatim. Only appended new sections after line 294.

### One-line summary for the FO at the gate

Repurpose-ideation complete: three independent local experiments (AC-R1 non-routing test counterfactual, AC-R2 section-stripped patch, AC-R3 sonnet ensign) scoped at ~15-20 min total cost; each isolates a different priming hypothesis; original sections preserved as audit trail.

## Staff Review (repurpose)

**Verdict: APPROVE WITH CHANGES.** The Layer 2 pivot is well-motivated and the three-AC structure is correct in spirit. AC-R2 and AC-R3 are clean. AC-R1 has a real isolation problem that should be acknowledged in the spec rather than fixed (re-scoping AC-R1 would broaden the experiment beyond its 15-20 min budget). AC-R4-style mixed-outcome enumeration should be added to the Decision section before implementation, since 8 outcome combinations exist and the entity currently delegates them to implementer judgment. Three smaller capture/sequencing gaps; none blocks re-ideation.

### Independence claim

The three ACs each *vary* a different surface, but only AC-R2 and AC-R3 cleanly *isolate* a single variable.

- **AC-R2** (lines 339-361) keeps everything constant except the section's prose richness — section header preserved, one-line-per-teammate, same test, same model, same fixture. This is a clean isolation.
- **AC-R3** (lines 363-377) keeps everything constant except `--model`. Clean isolation of model-vs-prompt.
- **AC-R1** (lines 323-337) varies *three* things at once: (a) section absence (the named hypothesis), (b) team mode entirely (the gated-pipeline fixture has no `agents:` config — verified at `tests/fixtures/gated-pipeline/README.md:1-19`, no team configured, so `enumerate_alive_standing_teammates` returns empty and the Completion Signal block at `claude-team:310-319` is also skipped), and (c) different test surface (FO-driven gate hold vs ensign-driven roundtrip). A FAIL on AC-R1 cannot distinguish "section primes hallucination" from "team-mode dispatch shape primes hallucination" or "this test simply also exhibits the regression on a different surface." The Decision (line 312) acknowledges the test was added before the section, but does not acknowledge the multi-variable change at AC-R1.

Recommend: keep AC-R1 in the spec but re-frame its Pass/Fail interpretation. PASS still implicates *some* aspect of team-mode dispatch shape (section + completion-signal + standing-teammates header) as the priming surface — narrower than "the section" but still actionable. FAIL still rules out *all* prompt-shape mitigation. Update line 325's "specific to dispatch prompts that contain the standing-teammates section" to "specific to team-mode dispatch shape (which includes the standing-teammates section, the Completion Signal block, and team-mode framing)."

### AC-R1 test selection sanity

Verified `tests/test_gate_guardrail.py`: it does invoke the FO via `run_first_officer_streaming` (line 47-72), uses `install_agents` for the claude path (line 39), and the test exercises the FO+ensign loop on a gated workflow. The fixture (`gated-pipeline/README.md`) has no `agents:` block, so `claude-team build` does NOT emit the standing-teammates section for any dispatched ensign in this test. Premise checks out — the section is genuinely absent. The confound is *which other variables* are also absent (see Independence above), not whether the section is absent.

One additional caveat: the gate-guardrail test's failure surface is the FO itself (FO self-approving at the gate), not an ensign hallucinating in a stage report. The original regression class (Evidence lines 21-26) was *ensign* hallucination of `SendMessage` outcomes inside a stage report. AC-R1's pass condition (FO halts at gate) is a different observable. Recommend the Pass/Fail line at lines 335-336 explicitly note this asymmetry: a FAIL on AC-R1 would have to mean either "FO self-approved" or "FO claimed a state change without making the tool call" — the latter is the closer analog to the original regression class.

### AC-R2 patch shape sanity

Verified `claude-team` on main:
- Lines 287-301 contain the loop body (`for name, description, mod_path in standing_teammates:` plus the conditional `usage_body` branches) exactly as the spec describes.
- Lines 302-307 contain the `lines.append('')` + "Full routing contract:" footer that the spec says to drop.
- The patch as specified (lines 415-417 of the entity) leaves the section's heading + at least one bullet, so any "section structurally present" check still passes.

Patch target is correct. One sequencing gap (see Gaps).

### Outcome enumeration completeness

3 ACs × {pass, fail} = 8 combinations. The Decision section (line 310) says outcomes "feed into a single `## Repurpose Outcome` section the implementation will write." The implementer is left to judge what each outcome combination *recommends*. With Outcome being the single actionable deliverable, the spec should pre-enumerate the most informative combinations rather than delegating that interpretation to the implementer. Suggested minimum table:

- **all-three PASS**: section richness is the priming AND sonnet works AND the section is necessary. Recommend filing two follow-ups: (1) compress the section emission per AC-R2, (2) consider `--model sonnet` workflow default as belt-and-suspenders.
- **all-three FAIL**: regression is broader than prompt-shape and broader than `opus-4-7`. Recommend the FO-side post-completion verification path (Layer 3) and surface to upstream.
- **AC-R1 PASS + AC-R2 FAIL** (counterintuitive): section presence (or team-mode shape) matters but its richness does not. Recommend investigating *what specifically* in the section header / Completion Signal block is the priming token, not the per-teammate prose.
- **AC-R3 PASS + others FAIL**: clean `--model sonnet` workaround independent of any prompt fix. Recommend pinning `--model sonnet` in workflow defaults; deprioritize prompt-shape mitigation.
- **AC-R2 PASS + others FAIL**: most actionable Layer 2 result — compress the section, ship it.
- **Any AC-R1 FAIL**: prompt-shape mitigation alone does not help; recommend Layer 3 (FO verification) regardless of other ACs.

Recommend adding a `### Outcome Map` subsection to Decision (after line 318) with at least the five rows above. Without it, the implementer's `## Repurpose Outcome` will likely under-enumerate.

### Silent assumptions

- **(a) "Same hallucination class" objective definition** (lines 325, 336, 360). The streaming watcher surfaces `StepTimeout` with a milestone label — that's objective for AC-R2 and AC-R3 (same milestones expected). For AC-R1, the test does not have an ensign-side roundtrip milestone, so "same hallucination class" requires the implementer to inspect `fo-log.jsonl` for the FO-equivalent (FO claims a status change without the tool call). Recommend the Capture list at line 337 explicitly require: for a FAIL, identify whether the FO emitted the corresponding tool calls for any state-change claims it makes in text. Without that, AC-R1 FAIL evidence is judgment-call.
- **(b) AC-R3 isolates model, not section** (lines 363-377). Spec correctly notes this is "worth knowing even if AC-R1/AC-R2 produce a clean answer." No issue — flagging only that AC-R3 does not test the priming-via-section hypothesis at all, just the `opus-4-7`-specific calibration sub-question. The Decision section (line 308) frames the *primary* hypothesis as section richness, so AC-R3 is admitted as a secondary question. Acceptable, but the Outcome Map (above) should treat AC-R3 as orthogonal evidence, not as falsifying or confirming the primary hypothesis.
- **(c) Claude Code 2.1.111 vs 2.1.112 confound** (line 384). Spec says both acceptable per original Evidence. Reasonable for AC-R1 and AC-R2 (both should reproduce on either). For AC-R3 specifically, sonnet behavior under 2.1.112 has not been directly evidenced in this entity. Recommend AC-R3's Capture list (line 377) include the `claude --version` output explicitly, and if 2.1.112 is used, the implementer should note that sonnet's behavior on 2.1.112 was not pre-validated and a PASS should be re-confirmed on 2.1.111 before pinning `--model sonnet` as a recommendation.

### Gaps

- **AC-R2 patch revert mechanism** (line 419): "git stash or git checkout to revert" — the spec offers two equivalent options without picking one. `git stash` is reversible (the patch survives in the stash); `git checkout -- skills/commission/bin/claude-team` is destructive (patch lost unless captured to a separate file first). Recommend: capture the patch as a `.patch` file via `git diff > /tmp/ac-r2.patch` BEFORE applying, then `git checkout` to revert. The diff-to-file step also satisfies the Capture-list requirement at line 361 ("paste the patch diff into the stage report") more reliably than reading from the stash.
- **AC-R2 → AC-R3 patch leak risk** (line 419): if the implementer skips the revert step or does it incorrectly, AC-R3 silently runs against the patched `claude-team` and its result is contaminated. Recommend: AC-R3's Pre-step (added to its Verify command) be `git diff --quiet skills/commission/bin/claude-team` to confirm zero pending changes before running. A non-zero exit from that check should abort AC-R3.
- **Un-patched dispatch prompt baseline** (Implementation Notes, lines 421-427): AC-R2's Capture requires the *patched* prompt for confirmation. There is no requirement to capture the *un-patched* prompt as a baseline. Without it, a future reader cannot diff the two prompts to see exactly what AC-R2 changed. Recommend adding to the Implementation Notes evidence list: capture one un-patched dispatch prompt (from any AC-R3 run) and one patched dispatch prompt (from AC-R2), preferably as side-by-side excerpts in the Outcome section.
- **AC-R1 worktree applicability**: AC-R1 uses `tests/test_gate_guardrail.py` which lives at the repo root, not in the worktree. The Implementation Notes (line 388-410) describe rebasing the existing worktree onto main, but AC-R1 does not need any patch — it only needs current code. Spec should clarify whether AC-R1 runs from the rebased worktree (consistent with AC-R2/R3) or from the repo root (cheaper). Recommend the worktree for consistency, but the spec is currently silent.

Length: ≈940 words; over the upper bound because AC-R1's confounding and the missing Outcome Map are concrete structural requests, not minor notes.

## Stage Report (staff review, repurpose)

### Summary

Independent staff review of #177's repurpose ideation (Layer 2 prompt-shape investigation). Verdict: **APPROVE WITH CHANGES.** The three-AC structure is sound; AC-R2 and AC-R3 are clean isolations. AC-R1 confounds three variables (section absence + team-mode absence + different test surface) — recommend re-framing its interpretation rather than re-scoping it. Outcome enumeration is incomplete (8 combinations, no Outcome Map) — recommend adding a 5-row Outcome Map subsection to Decision before implementation. Three smaller gaps: AC-R2 patch revert mechanism, AC-R2→AC-R3 patch-leak guard, missing un-patched-prompt baseline.

### Checklist

1. **Append-only `## Staff Review (repurpose)` section; do not modify prior sections.** DONE. Added `## Staff Review (repurpose)` and this `## Stage Report (staff review, repurpose)` after line 462. Verified by inspection: lines 1-294 (original entity) and lines 296-462 (Repurpose section + revision report) are untouched.
2. **Read entity body in full, focus on Repurpose section (lines 296+).** DONE. Read all 462 lines. Original sections noted as audit trail per dispatch instruction. Repurpose Decision (306-318), AC-R1 (323-337), AC-R2 (339-361), AC-R3 (363-377), Test Plan (379-386), Implementation Notes (388-436) all scrutinized.
3. **Verify experimental design's independence claim.** DONE. Captured in Staff Review § Independence claim. AC-R2 and AC-R3 isolate cleanly; AC-R1 varies three things at once (section absence, team-mode absence, different test surface). Recommended re-framing AC-R1's interpretation rather than re-scoping the test.
4. **Sanity-check AC-R1's test selection.** DONE. Captured in Staff Review § AC-R1 test selection sanity. Verified `tests/test_gate_guardrail.py:30-156` invokes FO via `run_first_officer_streaming`, uses `install_agents`. Verified `tests/fixtures/gated-pipeline/README.md:1-19` has no `agents:` block. Premise (section is absent) is correct; confound (other variables are also absent) is the actual problem. Also flagged that the test's failure surface (FO self-approval) is not the same observable as the original regression (ensign hallucination in stage report).
5. **Sanity-check AC-R2's patch shape.** DONE. Captured in Staff Review § AC-R2 patch shape sanity. Verified `skills/commission/bin/claude-team:287-301` contains the loop, `:302-307` contains the routing-contract footer. Patch leaves section structurally present. Patch target is correct.
6. **Examine outcome enumeration.** DONE. Captured in Staff Review § Outcome enumeration completeness. 8 combinations exist; spec delegates interpretation to implementer. Recommended adding a 5-row Outcome Map subsection to Decision (after line 318) covering all-pass, all-fail, AC-R1 PASS + AC-R2 FAIL counterintuitive, AC-R3 PASS only, and AC-R2 PASS only.
7. **Check for silent assumptions.** DONE. Captured in Staff Review § Silent assumptions. (a) "Same hallucination class" requires objective definition for AC-R1 (recommended Capture-list addition); (b) AC-R3 admittedly does not test the section hypothesis (acceptable, flagged for the Outcome Map); (c) 2.1.112 sonnet behavior not pre-validated, recommended `claude --version` capture for AC-R3.
8. **Look for gaps.** DONE. Captured in Staff Review § Gaps. (a) AC-R2 patch revert mechanism ambiguous (`git stash` vs `git checkout`); recommended capturing as `.patch` file before apply. (b) AC-R2 → AC-R3 patch-leak risk; recommended `git diff --quiet` pre-check on AC-R3. (c) Missing un-patched dispatch prompt baseline; recommended capturing one for side-by-side. (d) AC-R1 worktree applicability not stated; recommended running from worktree for consistency.
9. **Append `## Staff Review (repurpose)` section, 300-500 words (longer if structural problem).** DONE. Section is ≈940 words — over the budget because AC-R1's confounding and the missing Outcome Map are concrete structural requests, not notes.
10. **Commit on main.** Pending — will run immediately after this report write completes. Working tree was clean on `main` at start; commit message will be `staff-review: #177 repurpose ideation — APPROVE WITH CHANGES`.
11. **`## Stage Report (staff review, repurpose)` at very end.** DONE (this section).

### One-line summary for the captain

Repurpose-ideation is structurally sound; APPROVE WITH CHANGES — AC-R1 confounds three variables (re-frame interpretation, don't re-scope), Decision should add an Outcome Map enumerating the 5 most informative outcome combinations, plus three smaller patch-handling gaps.
