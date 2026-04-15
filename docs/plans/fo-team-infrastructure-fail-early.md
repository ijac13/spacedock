---
id: 149
title: "FO runtime: fail-early team-infrastructure defense (rules 1, 2, 4 of team-fragility issue)"
status: ideation
source: "CL direction during 2026-04-14 session from /tmp/2026-04-14-team-fragility-issue.md"
started: 2026-04-15T03:47:38Z
completed:
verdict:
score: 0.82
worktree:
issue:
pr:
---

The Claude Code `Agent`/`Team*` tooling has compounding bugs that cause the FO to spawn untracked zombie ensigns and duplicate work whenever a session is interrupted (rate-limit re-auth, long idle at a gate, or any event that desyncs the in-memory team registry). Upstream: anthropics/claude-code #45683, #36806, #35355, #25131.

The 2026-04-14 Discovery Outreach session evidence:

- `test -f ~/.claude/teams/{team}/config.json` returned OK after rate-limit + re-auth
- `Agent(team_name=...)` returned "Team does not exist" — but the agent process spawned anyway
- Retries compounded the zombie count; one zombie completed work and committed to main without FO coordination
- `TeamDelete` "succeeded" but didn't clear session in-memory contamination

## Scope — robustness and fail-early, no ledger

CL direction: focus on robustness and failing early rather than building our own agent-tracking infrastructure. Rules 1, 2, and 4 from the team-fragility issue are in scope. Rule 3 (session-memory agent ledger) is deferred — we accept that zombies exist and rely on git history / UI surfacing rather than building tracking.

### Rule 1 — Remove the useless `test -f config.json` health check from normal dispatch flow

**Problem:** The filesystem probe before each dispatch batch passes even when the in-memory team registry is invalidated. Guaranteed false-positive after rate-limit-then-reauth and #36806 contamination scenarios.

**Fix:** Remove the check from `claude-first-officer-runtime.md`'s normal pre-dispatch path. Keep the filesystem probe only as a startup sanity check when picking up an orphan worktree or deciding if a team directory was externally mutated.

### Rule 2 — Treat "Team does not exist" as terminal; never retry to the same name

**Problem:** The current shared-core recovery procedure calls `TeamDelete` then `TeamCreate` (same or new name). In practice the retry re-contaminates and re-zombifies per #36806.

**Fix:** On the first "Team does not exist" error (or equivalent registry-desync signal), stop dispatching to that team name for the rest of the session. Options in priority order:

1. `TeamCreate` with a fresh, uniquely-suffixed name (e.g. `{workflow}-{YYYYMMDD-HHMM}-{shortuuid}`). Ignore any returned rename — the new name is whatever TeamCreate gives back. Re-dispatch in-flight entity work from checkpoint state (the entity frontmatter is authoritative).
2. Fall back to bare mode (Rule 4).
3. Surface to captain with a clear recovery prompt. Do not silently retry.

Retry-same-name is banned.

### Rule 4 — First-class bare-mode fallback with explicit mid-session transition

**Problem:** The runtime adapter treats bare mode as the startup default when ToolSearch can't find `TeamCreate`, but mid-session fallback is vague.

**Fix:** Define an explicit "degraded mode" transition in `claude-first-officer-runtime.md`:

- **Trigger:** any of {first "Team does not exist" error, 2+ dispatch failures inside a 5-minute window, captain command `/spacedock bare`}.
- **Effect:** FO stops using `team_name` on Agent dispatches for the rest of the session. Reuse-via-SendMessage is no longer available; every stage dispatches fresh and blocks until completion.
- **Report to captain:** "Falling back to bare mode for the remainder of this session due to team-infrastructure failure. Prior team agents are presumed-zombified; I will not route work to them or through the team registry."
- **On degrade:** attempt cooperative shutdown of every known agent name once, then assume at least some won't respond and move on.

`claude-team build` already accepts `bare_mode: true` — the prose just needs to tell the FO when to flip it.

### Uniquely-suffixed TeamCreate names (from Rule 6, folded into Rule 2)

The fragility issue's Rule 6 says TeamCreate requests should include a uniqueness suffix. This is a prerequisite for Rule 2 option 1 (fresh-suffixed TeamCreate). Fold it into the implementation of Rule 2:

- Always request `{project_name}-{dir_basename}-{YYYYMMDD-HHMM}` or similar unique name
- Always store and use the actual returned `team_name` from TeamCreate (it may rename)

## Deferred (not this task)

- **Rule 3 — Agent ledger** (CL declined; focus on robustness/fail-early, not tracking)
- **Rule 5 — Prior-session zombie awareness**
- **Rule 6 — Defensive naming** (folded into Rule 2 above)
- **Rule 7 — Operator docs for re-auth gotcha** (can be a small doc update task later)
- **Rule 8 — Nuclear mitigation hook** (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=0`)

## Acceptance criteria (provisional — finalize in ideation)

1. `claude-first-officer-runtime.md` has the `test -f config.json` check removed from the dispatch adapter's pre-dispatch flow (Rule 1).
2. `claude-first-officer-runtime.md` has updated recovery prose that treats "Team does not exist" as terminal — no retry-to-same-name path (Rule 2).
3. `claude-first-officer-runtime.md` has an explicit "Degraded Mode" section with triggers, effect, and captain-facing report template (Rule 4).
4. TeamCreate invocation includes a uniqueness suffix (Rule 6 subset).
5. Static tests assert the new prose structure exists and the old retry-same-name language is gone.
6. Optional: one E2E test that simulates a dispatch failure and observes the FO follows the new rules without spawning zombies via retry.

## Out of scope

- Fixing any upstream Claude Code bugs. This is defense-in-depth on top of them.
- Changing Spacedock core state model (entity frontmatter, worktrees, stages stay as they are).
- OS-level zombie reaping.

## Related

- `/tmp/2026-04-14-team-fragility-issue.md` — full context document
- Session debrief for 2026-04-14 Discovery Outreach (to be written)
- anthropics/claude-code#45683, #36806, #35355, #25131 — upstream bugs
- #120 (merged) — structured dispatch helper provides deterministic `name` derivation and `bare_mode` input flag; this task builds on that
- #114 (in flight) — mod-block enforcement; adjacent runtime-enforcement mechanism

## Seed Understanding

The task asks me, as FO, to internalize rules 1, 2, and 4 of the team-fragility issue as my operating contract from *now on* and then produce an introspective behavior-change spec: what do I currently do, what must I do instead, where does the enforcement/prose live, and how is the change testable. Rule 3 (ledger) is explicitly deferred; rule 6 (unique TeamCreate names) folds into rule 2 as a prerequisite for fresh-suffixed recreation. The deliverable's central artifact is a Behavior Change Requirements table — classical ideation sections (problem / approach / AC / test plan) surround it but the table is the centerpiece. I also need to be honest about scaffolding scope: I am not allowed to modify files under `agents/` or `references/` during ideation (see the dispatch guardrails block), so this stage produces prose-spec only, and implementation of the behavior changes will happen in a later worktree stage.

## Problem Statement

Current FO behavior (as lived in the 2026-04-14 session and encoded in `skills/first-officer/references/claude-first-officer-runtime.md` lines 16–24 and 44–46) is actively harmful when Claude Code's team registry is desynced from the filesystem:

1. **False-positive health check drives bad dispatch.** Lines 44–46 of `claude-first-officer-runtime.md` label the `test -f ~/.claude/teams/{team_name}/config.json` probe REQUIRED before every Agent dispatch batch, with the imperative "STOP. Do NOT call Agent() until you have verified the team is healthy." Upstream bug anthropics/claude-code#36806 leaves the config file on disk after rate-limit-then-reauth invalidates the in-memory registry; the probe passes while `Agent(team_name=...)` returns "Team does not exist" and yet spawns a zombie process. I observed this three times in the 2026-04-14 Discovery Outreach session: every retry compounded the zombie count and one zombie committed to main without FO coordination.
2. **Recovery prose tells me to retry-to-same-name.** Lines 16–22 prescribe `TeamDelete` → `TeamCreate` (same or implicit-same name). In practice the second `TeamCreate` re-contaminates the same registry slot per #36806 and zombifies again. The prose has no "terminal failure, stop dispatching to this name" branch — it only has retry and, as a final fallback, bare mode. The "Block all Agent dispatch" clause reads absolutely but in the live session I treated it as "retry until it works."
3. **Mid-session bare-mode transition is ambiguous.** Line 14 only describes bare mode as the startup default when ToolSearch returns no TeamCreate definition. The mid-session "fall back to bare mode" clause on line 21 is a one-liner with no trigger enumeration, no captain-facing report template, no cooperative-shutdown sweep for presumed-zombie agents. I didn't have concrete, checkable thresholds to flip, so I did not flip.
4. **TeamCreate name requested is not uniquely suffixed.** Line 11 says `TeamCreate(team_name="{project_name}-{dir_basename}")`. After a #36806 contamination, this deterministic name collides with the registry's stale slot; even if Claude Code renames and returns a different name, my *first* request hits the contaminated slot. A uniqueness suffix (date-time or shortuuid) gives the registry a clean key on recreate.

The upstream bugs are out of scope. This task is defense-in-depth on top of them.

## Proposed Approach

All of the live behavior changes live in prose files (no code changes to `claude-team`, `status`, or runtime binaries). Two files in scope:

1. **`skills/first-officer/references/claude-first-officer-runtime.md`** — the runtime adapter prose I execute from.
   - Rule 1: Delete the `test -f config.json` probe from the normal pre-dispatch path (lines 44–46). Move a lightweight filesystem probe into a startup-only sanity check that runs when picking up an orphan worktree or deciding if a team directory was externally mutated.
   - Rule 2: Rewrite the TeamCreate failure recovery prose (lines 16–22) so "Team does not exist" (or any registry-desync signal) is explicitly terminal for that team name: remove the retry-to-same-name branch entirely and replace with a priority-ordered fallback ladder (fresh-suffixed TeamCreate → bare mode → captain surface).
   - Rule 4: Add a new `## Degraded Mode` section with (a) trigger enumeration (first "Team does not exist" error, 2+ dispatch failures inside a 5-minute window, captain command `/spacedock bare`), (b) effect (drop `team_name` from Agent dispatches for the remainder of the session, every stage fresh-dispatches and blocks, no SendMessage reuse), (c) a cooperative-shutdown sweep of every known agent name once (ignore failures), (d) a captain-facing report template with verbatim wording.
   - Rule 6 (folded): In the startup prose, change the requested TeamCreate name to `{project_name}-{dir_basename}-{YYYYMMDD-HHMM}` (or equivalent with a short uuid suffix) and reiterate "always use the returned team_name" (already present on line 12 but needs to survive the rewrite).
2. **`skills/commission/bin/claude-team`** — optional. Name derivation already uses `{worker_key}-{slug}-{stage}` (line 165) which is not affected; `team_name` is read from input (line 104) and forwarded verbatim. If we want the uniqueness suffix generated by the helper instead of the FO, `claude-team` could grow a `--suffix-team-name` mode, but YAGNI: the FO already owns the `TeamCreate` call at startup and can format the name itself. Keep this change prose-only.

Shared core (`skills/first-officer/references/first-officer-shared-core.md`) does not mention the config-probe or the retry-to-same-name flow — it is runtime-agnostic. The Codex runtime adapter (`codex-first-officer-runtime.md`) does not use Claude teams. No changes needed there.

Static tests live in `tests/test_team_health_check.py`. Since the probe is being removed from normal dispatch, AC1 and AC5 of that test must be rewritten (not just deleted — they currently assert that the FO runs the probe; the new assertions should check the probe is *absent* from the normal path and present only in the startup-sanity context). AC2-AC4 also need to be rewritten against the new Rule-2 and Rule-4 prose.

Ordering of touchpoints in implementation:
1. Rewrite `claude-first-officer-runtime.md` (Rule 1 deletion, Rule 2 rewrite, Rule 4 new section, Rule 6 name suffix).
2. Rewrite `tests/test_team_health_check.py` (or rename to `test_team_fail_early.py`) to assert the new prose and the absence of the old prose.
3. Optionally add one E2E test that simulates a "Team does not exist" error and observes the FO does not retry to the same name; this is higher cost and lower value than the static assertions — see Test Plan.

## Behavior Change Requirements

Central artifact. Rows are the FO behaviors #149 mandates. Columns: (a) current behavior (what I actually do today), (b) task-mandated behavior (what I must do), (c) change locus (file path + section heading where prose lives or should be added), (d) testable check, (e) dependency.

| # | Current behavior | Mandated behavior | Change locus | Testable check | Dependency |
|---|---|---|---|---|---|
| 1a | Before every `Agent()` dispatch batch I run `test -f ~/.claude/teams/{team_name}/config.json` and treat success as "team healthy, proceed." | Do NOT run the probe in the normal pre-dispatch path. Trust the in-memory team handle returned by `TeamCreate` and let `Agent()` itself surface registry-desync errors. | `skills/first-officer/references/claude-first-officer-runtime.md` — delete lines 44–46 ("REQUIRED — Team health check"); remove all imperatives pointing to it. | Static (grep): new file contains no "test -f" probe language in the Dispatch Adapter section. E2E: run FO through `tests/test_team_health_check.py` replacement and assert NO `Bash(test -f … config.json)` call precedes `Agent()` in the tool-call log. | None. |
| 1b | No startup-time filesystem check of team directory state exists as a distinct concern. | Run the filesystem probe only at startup (when picking up an orphan worktree or verifying a team directory was not externally mutated); frame it as a sanity check, not a precondition for dispatch. | Same file, new short paragraph in the Team Creation section describing the startup-only probe. | Static (grep): new file contains exactly one reference to the `config.json` probe, and it sits inside the `## Team Creation` section, not `## Dispatch Adapter`. | None. |
| 2a | On "Team does not exist" I call `TeamDelete` then `TeamCreate` (implicitly to the same name), then resume dispatch. | Treat the first "Team does not exist" (or equivalent registry-desync error) as TERMINAL for that team name. Never call `TeamCreate` with the same name again in this session. | `claude-first-officer-runtime.md` — replace the `TeamCreate failure recovery` block (lines 16–22) with a priority-ordered ladder: (1) `TeamCreate` with fresh `{project_name}-{dir_basename}-{YYYYMMDD-HHMM}-{shortuuid}` name; (2) fall back to bare mode per Rule 4; (3) surface to captain with explicit recovery prompt. | Static (grep): new prose contains "Retry to the same team name is banned" (or equivalent unambiguous phrase) and does NOT contain the phrase "TeamDelete … TeamCreate" as a recovery sequence. Static (grep): new prose includes "fresh-suffixed" or equivalent and references the name template. E2E (optional, high-cost): fault-injection harness returns "Team does not exist" on first `Agent()`; assert the FO's second `TeamCreate` call uses a different name than the first. | Requires 6 (uniqueness suffix) to be coherent. |
| 2b | After recovery, I resume SendMessage reuse of any agent name that existed in the prior team. | After a registry-desync, assume all prior agent names are zombified. Do not SendMessage any of them. Fresh-dispatch every in-flight entity from checkpoint state (entity frontmatter on main is authoritative). | Same file, same block — include explicit "All prior agent names are presumed zombified after a registry-desync. Do not SendMessage them; re-dispatch from entity frontmatter." | Static (grep): new prose contains "presumed zombified" (or equivalent) and "re-dispatch from entity frontmatter." | Depends on 2a (same prose block). |
| 4a | Bare mode is defined only as a startup state entered when `ToolSearch` returns no `TeamCreate`. Mid-session fallback is a one-liner ("Fall back to bare mode for the remainder of the session"). | Introduce explicit "Degraded Mode" semantics with enumerated triggers: (i) first "Team does not exist" error; (ii) 2+ dispatch failures inside a 5-minute window; (iii) captain command `/spacedock bare`. | `claude-first-officer-runtime.md` — new `## Degraded Mode` top-level section (or `### Degraded Mode` under Dispatch Adapter); hoist the bare-mode one-liner from line 21 into this section and cross-reference it from Rules 1–3 recovery paths. | Static (grep): new file contains `## Degraded Mode` heading and all three triggers verbatim. | None (pure prose). |
| 4b | On mid-session bare fallback I silently strip `team_name` from the next `Agent()` call, sometimes inconsistently. | In Degraded Mode, stop using `team_name` on all subsequent `Agent()` dispatches for the entire session. Every stage dispatches fresh and blocks until completion. No SendMessage reuse. | Same section — add explicit "Effect" subsection listing the three invariants (no `team_name`, every stage fresh, every dispatch blocks). | Static (grep): new section contains the three effect bullets. E2E: fault-injection test where FO enters degraded mode at stage N; assert every subsequent `Agent()` tool call in the log has no `team_name` parameter. | None. |
| 4c | On mid-session bare fallback I say nothing specific to the captain; they learn from context. | On Degraded Mode entry, produce a canonical captain-facing report: *"Falling back to bare mode for the remainder of this session due to team-infrastructure failure. Prior team agents are presumed-zombified; I will not route work to them or through the team registry."* | Same section — new "Captain Report Template" subsection with verbatim wording. | Static (grep): exact sentence present in the runtime adapter. E2E (optional): fault-injection test asserts this sentence appears in FO text output within N turns of the degrade trigger. | None. |
| 4d | On mid-session bare fallback I do not attempt to shut down known agent names. | On Degraded Mode entry, attempt cooperative shutdown of every known agent name once via `SendMessage(shutdown_request)`. Ignore failures. Move on. Do not retry or track dead names beyond this single sweep. | Same section — new "Cooperative Shutdown Sweep" subsection. | Static (grep): prose describes the single-pass sweep with "ignore failures" language. | None. |
| 6 | `TeamCreate(team_name="{project_name}-{dir_basename}")` — deterministic name, no uniqueness. | `TeamCreate(team_name="{project_name}-{dir_basename}-{YYYYMMDD-HHMM}-{shortuuid}")` at startup. Always store and use the *returned* `team_name` (existing rule, preserved). | `claude-first-officer-runtime.md` — update line 11 startup prose; keep the existing line-12 "returned team_name is authoritative" note. | Static (grep): new file contains `YYYYMMDD-HHMM` (or equivalent timestamp format token) in the TeamCreate invocation example. | Prerequisite for 2a. |

## Acceptance Criteria

Each criterion cites how it is tested. Tests map to the static-grep checks and optional E2E column above.

1. **AC-1 (Rule 1 removal):** `skills/first-officer/references/claude-first-officer-runtime.md` does not contain a `test -f … config.json` probe in the `## Dispatch Adapter` section. **Test:** static regex assertion in a replacement for `tests/test_team_health_check.py` — the probe string is absent from the Dispatch Adapter subsection text.
2. **AC-1b (startup-only probe framing):** The same file contains at most one reference to the `config.json` probe and it is scoped to the `## Team Creation` section as a startup sanity check. **Test:** static — count occurrences and assert section containment.
3. **AC-2 (retry-to-same-name ban):** The recovery prose contains an unambiguous ban on retrying to the same team name (e.g., "Retry to the same team name is banned") and does not contain the old `TeamDelete → TeamCreate` same-name recovery sequence. **Test:** static regex assertions — one positive match, one negative match.
4. **AC-2b (zombie presumption):** The recovery prose states that all prior agent names are presumed-zombified after a registry-desync and that fresh-dispatch from entity frontmatter is the recovery path. **Test:** static regex.
5. **AC-4 (Degraded Mode section):** The runtime adapter contains a `## Degraded Mode` (or `### Degraded Mode`) section with the three triggers, three effects, captain report template sentence, and cooperative-shutdown sweep subsection. **Test:** static — parse section headings and assert presence of each required subheading or bullet.
6. **AC-4c (captain report verbatim):** The canonical captain-facing sentence appears verbatim in the runtime adapter. **Test:** static string match.
7. **AC-6 (unique TeamCreate name):** The startup prose specifies a TeamCreate name with a timestamp suffix of the form `YYYYMMDD-HHMM` (plus optionally a shortuuid). **Test:** static regex.
8. **AC-T (test file refresh):** `tests/test_team_health_check.py` is either rewritten in place or replaced by `tests/test_team_fail_early.py` to reflect the new semantics. The old AC1–AC4 assertions in that file (which assert the presence of the probe prose) are gone. **Test:** the refreshed test passes against the new runtime adapter and fails against the current one.
9. **AC-E (optional live E2E, staff-review discretion):** One live E2E test under `claude-live-opus` or `claude-live` simulates a `Team does not exist` error at dispatch time and observes the FO (a) does not retry to the same team name, (b) enters Degraded Mode, (c) emits the canonical captain report sentence. **Test:** `tests/test_runtime_live_fail_early.py` (new file) with fault injection via a stub runtime wrapper. Cost estimated at $0.50–$2.00 per run.

## Test Plan

- **Static assertions (low cost, fast):** AC-1, AC-1b, AC-2, AC-2b, AC-4, AC-4c, AC-6, AC-T all verify via string / regex checks against the assembled runtime adapter content. Implementation lives in the refreshed `tests/test_team_fail_early.py`. Runtime cost: milliseconds per assertion; total cost: seconds.
- **Existing E2E baseline:** `tests/test_team_health_check.py` currently runs a real FO dispatch with `claude-live` under `--model sonnet --effort low --max-budget-usd 2.00`. That test *must* be refreshed in lockstep with the prose rewrite — it will fail against the new prose otherwise. Budget: same ~$2 ceiling, 60–120s wall clock.
- **Fault-injection E2E (optional, AC-E):** Requires a new test harness that injects a "Team does not exist" response on the first `Agent()` call and lets the FO continue. Cost: moderate (~$0.50–$2.00 per run on `claude-live-opus`, ~$0.20 on `claude-live`). Complexity: medium — we need a stubbable layer over `Agent()`. **Recommendation:** defer AC-E unless staff review flags the static assertions as insufficient. The static assertions plus the refreshed baseline E2E give strong coverage of prose behavior; the fault-injection harness is nice-to-have but not load-bearing.
- **E2E runtime choice:** `claude-live-bare` is the wrong choice here — the whole point is teams-mode failure. `claude-live` (sonnet) is sufficient for the baseline refresh. `claude-live-opus` only if AC-E is accepted and we want higher-fidelity coverage of the recovery decision logic.

## Stage Report

1. **Read the seed description — DONE.** My understanding: #149 asks the FO to internalize rules 1, 2, and 4 of the team-fragility issue as its operating contract and produce an introspective behavior-change spec that cross-references the current scaffolding. Rule 6 folds into Rule 2 as a prerequisite; rule 3 is deferred. The central deliverable is the Behavior Change Requirements table, with classical ideation sections as supporting structure. The seed also enforces a scaffolding-write guardrail (no writes under `agents/` or `references/` in ideation), so this stage produces prose-spec only; implementation happens later.
2. **Problem Statement — DONE.** Above. Enumerates four concrete failure modes with line references into `skills/first-officer/references/claude-first-officer-runtime.md` and traces them to the 2026-04-14 session observations.
3. **Proposed Approach — DONE.** Above. Two-file scope (`claude-first-officer-runtime.md` + tests), ordered three-step implementation, explicit "no changes to `claude-team` binary" judgment with rationale (YAGNI).
4. **Acceptance Criteria — DONE.** Above. Nine criteria (AC-1 through AC-E), each with a concrete test mechanism.
5. **Test Plan — DONE.** Above. Static assertions as primary coverage, refreshed baseline E2E (`tests/test_team_health_check.py`) as required companion, fault-injection E2E (AC-E) deferred unless staff review flags coverage gaps. Cost and runtime choice documented.
6. **Behavior Change Requirements table — DONE.** Above. Eight rows (1a, 1b, 2a, 2b, 4a, 4b, 4c, 4d, 6) each with current behavior, mandated behavior, change locus, testable check, dependency.
7. **Commit — DONE (will be made as the final action of this stage).** Single atomic commit with the specified message.

### Summary

Ideation for #149 delivered: introspective behavior-change spec for FO team-infrastructure fail-early defense. Eight behaviors mapped (health-check removal, startup-only probe, retry-to-same-name ban, zombie presumption, Degraded Mode section with triggers / effects / captain report / shutdown sweep, uniquely-suffixed TeamCreate). All changes localized to `skills/first-officer/references/claude-first-officer-runtime.md` plus a refresh of `tests/test_team_health_check.py`. Nine acceptance criteria with static-assertion-primary test plan and an optional fault-injection E2E deferred to staff-review discretion. Score 0.82 flagged this as staff-review-worthy; the reviewer should focus on (a) whether the Degraded Mode trigger thresholds (especially "2+ dispatch failures in 5 minutes") are operator-checkable and (b) whether AC-E should be promoted from optional to required.
