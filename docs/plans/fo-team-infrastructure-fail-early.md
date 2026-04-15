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
   - Rule 4: Add a new `## Degraded Mode` section with (a) trigger enumeration (first "Team does not exist" error, any second dispatch failure, captain command `/spacedock bare`), (b) effect (drop `team_name` from Agent dispatches for the remainder of the session, every stage fresh-dispatches and blocks, no SendMessage reuse), (c) a cooperative-shutdown sweep of every known agent name once (ignore failures, exempt active-feedback-cycle reviewers), (d) a captain-facing report template with verbatim wording that closes with a concrete next-step pointer.
   - Rule 6 (folded): In the startup prose, change the requested TeamCreate name to `{project_name}-{dir_basename}-{YYYYMMDD-HHMM}` (or equivalent with a short uuid suffix) and reiterate "always use the returned team_name" (already present on line 12 but needs to survive the rewrite).
2. **`skills/commission/bin/claude-team`** — optional. Name derivation already uses `{worker_key}-{slug}-{stage}` (line 165) which is not affected; `team_name` is read from input (line 104) and forwarded verbatim. If we want the uniqueness suffix generated by the helper instead of the FO, `claude-team` could grow a `--suffix-team-name` mode, but YAGNI: the FO already owns the `TeamCreate` call at startup and can format the name itself. Keep this change prose-only.

Shared core (`skills/first-officer/references/first-officer-shared-core.md`) does not mention the config-probe or the retry-to-same-name flow — it is runtime-agnostic. The Codex runtime adapter (`codex-first-officer-runtime.md`) does not use Claude teams. No changes needed there.

Static tests live in `tests/test_team_health_check.py`. Since the probe is being removed from normal dispatch, AC1 and AC5 of that test must be rewritten (not just deleted — they currently assert that the FO runs the probe; the new assertions should check the probe is *absent* from the normal path and present only in the startup-sanity context). AC2-AC4 also need to be rewritten against the new Rule-2 and Rule-4 prose.

Ordering of touchpoints in implementation:
0. Audit `agents/first-officer.md` for duplicated probe / recovery prose. If found, the implementation touches 3 files (runtime adapter + agent file + tests); if not, 2 files as the current scope describes. (Ideator-stage audit grep for `test -f`, `config.json`, `Team does not exist`, `TeamDelete`, `retry`, `bare mode`, `degraded` in `agents/first-officer.md` returned no matches — current scope is 2 files, but implementer must re-verify at worktree start since the agent file can drift.)
1. Rewrite `claude-first-officer-runtime.md` (Rule 1 deletion, Rule 2 rewrite, Rule 4 new section, Rule 6 name suffix).
2. Rewrite `tests/test_team_health_check.py` (or rename to `test_team_fail_early.py`) to assert the new prose and the absence of the old prose.
3. Optionally add one E2E test that simulates a "Team does not exist" error and observes the FO does not retry to the same name; this is higher cost and lower value than the static assertions — see Test Plan.

## Behavior Change Requirements

Central artifact. Rows are the FO behaviors #149 mandates. Columns: (a) current behavior (what I actually do today), (b) task-mandated behavior (what I must do), (c) change locus (file path + section heading where prose lives or should be added), (d) testable check, (e) dependency.

| # | Current behavior | Mandated behavior | Change locus | Testable check | Dependency |
|---|---|---|---|---|---|
| 1a | Before every `Agent()` dispatch batch I run `test -f ~/.claude/teams/{team_name}/config.json` and treat success as "team healthy, proceed." | Do NOT run the probe in the normal pre-dispatch path. Trust the in-memory team handle returned by `TeamCreate` and let `Agent()` itself surface registry-desync errors. | `skills/first-officer/references/claude-first-officer-runtime.md` — delete lines 44–46 ("REQUIRED — Team health check"); remove all imperatives pointing to it. | Static (grep): new file contains no "test -f" probe language in the Dispatch Adapter section. E2E: run FO through `tests/test_team_health_check.py` replacement and assert NO `Bash(test -f … config.json)` call precedes `Agent()` in the tool-call log. | None. |
| 1b | No startup-time filesystem check of team directory state exists as a distinct concern. | Run the filesystem probe only at startup as a DIAGNOSTIC to REPORT existing team directories to the captain — never to short-circuit `TeamCreate`. On every session startup the FO always attempts a fresh-suffixed `TeamCreate` (see Row 6); the filesystem probe's sole role is to surface "there is already a team directory on disk for this project from a prior session" in the captain-facing boot report. Deletion is out of scope (the existing line 13 constraint — "NEVER delete existing team directories — stale directories belong to other sessions" — is preserved; ignore-for-dispatch-purposes is separate from deletion). | Same file, new short paragraph in the Team Creation section describing the startup-only diagnostic probe AND an explicit non-short-circuit clause ("the probe's result does NOT gate `TeamCreate`; `TeamCreate` always runs"). | Static (parse-sections): the `## Team Creation` section contains both (a) exactly one `config.json` probe reference framed as diagnostic, and (b) an unambiguous non-short-circuit clause (e.g., "does not skip `TeamCreate`"). The `## Dispatch Adapter` section contains zero probe references. | None. |
| 2a | On "Team does not exist" I call `TeamDelete` then `TeamCreate` (implicitly to the same name), then resume dispatch. | Treat the first "Team does not exist" (or equivalent registry-desync error) as TERMINAL for that team name. Never call `TeamCreate` with the same name again in this session. | `claude-first-officer-runtime.md` — replace the `TeamCreate failure recovery` block (lines 16–22) with a priority-ordered ladder: (1) `TeamCreate` with fresh `{project_name}-{dir_basename}-{YYYYMMDD-HHMM}-{shortuuid}` name; (2) fall back to bare mode per Rule 4; (3) surface to captain with explicit recovery prompt. | Static (grep): new prose contains "Retry to the same team name is banned" (or equivalent unambiguous phrase) and does NOT contain the phrase "TeamDelete … TeamCreate" as a recovery sequence. Static (grep): new prose includes "fresh-suffixed" or equivalent and references the name template. E2E (optional, high-cost): fault-injection harness returns "Team does not exist" on first `Agent()`; assert the FO's second `TeamCreate` call uses a different name than the first. | Requires 6 (uniqueness suffix) to be coherent. |
| 2b | After recovery, I resume SendMessage reuse of any agent name that existed in the prior team. | After a registry-desync, assume all prior agent names are zombified. Do not SendMessage any of them. Fresh-dispatch every in-flight entity from checkpoint state (entity frontmatter on main is authoritative). | Same file, same block — include explicit "All prior agent names are presumed zombified after a registry-desync. Do not SendMessage them; re-dispatch from entity frontmatter." | Static (grep): new prose contains "presumed zombified" (or equivalent) and "re-dispatch from entity frontmatter." | Depends on 2a (same prose block). |
| 4a | Bare mode is defined only as a startup state entered when `ToolSearch` returns no `TeamCreate`. Mid-session fallback is a one-liner ("Fall back to bare mode for the remainder of the session"). | Introduce explicit "Degraded Mode" semantics with enumerated triggers: (i) first "Team does not exist" error; (ii) any second dispatch failure (any second failure in the session, regardless of timing — chosen over the earlier "2+ in 5 min" proposal because the FO has no durable timestamp counter and the stricter rule degrades earlier, which is the point of fail-early); (iii) captain command `/spacedock bare`. | `claude-first-officer-runtime.md` — new `## Degraded Mode` top-level section (or `### Degraded Mode` under Dispatch Adapter); hoist the bare-mode one-liner from line 21 into this section and cross-reference it from Rules 1–3 recovery paths. | Static (parse-sections): the `## Degraded Mode` section contains all three triggers enumerated as a markdown list (bulleted or numbered). | None (pure prose). |
| 4b | On mid-session bare fallback I silently strip `team_name` from the next `Agent()` call, sometimes inconsistently. | In Degraded Mode, stop using `team_name` on all subsequent `Agent()` dispatches for the entire session. Every stage dispatches fresh and blocks until completion. No SendMessage reuse. | Same section — add explicit "Effect" subsection listing the three invariants (no `team_name`, every stage fresh, every dispatch blocks). | Static (grep): new section contains the three effect bullets. E2E: fault-injection test where FO enters degraded mode at stage N; assert every subsequent `Agent()` tool call in the log has no `team_name` parameter. | None. |
| 4c | On mid-session bare fallback I say nothing specific to the captain; they learn from context. | On Degraded Mode entry, produce a canonical captain-facing report with concrete next-step guidance: *"Falling back to bare mode for the remainder of this session due to team-infrastructure failure. Prior team agents are presumed-zombified; I will not route work to them or through the team registry. If you want to escalate: restart the session to retry team mode with a fresh name, or let me continue — every stage will still complete, just without concurrent dispatch."* | Same section — new "Captain Report Template" subsection with verbatim wording. | Static (parse-sections): the `## Degraded Mode` section's Captain Report Template subsection contains this exact sentence. E2E (optional): fault-injection test asserts this sentence appears in FO text output within N turns of the degrade trigger. | None. |
| 4d | On mid-session bare fallback I do not attempt to shut down known agent names. | On Degraded Mode entry, attempt cooperative shutdown of every known agent name once via `SendMessage(shutdown_request)`. Ignore failures. Move on. Do not retry or track dead names beyond this single sweep. Exempt any agent whose entity is in an active feedback-cycle state (tracked via `### Feedback Cycles` in the entity body) — these reviewers may still hold load-bearing context from the prior cycle. Sweep them only on explicit captain confirmation. | Same section — new "Cooperative Shutdown Sweep" subsection. | Static (parse-sections): the Cooperative Shutdown Sweep subsection under `## Degraded Mode` contains the single-pass / ignore-failures language AND the active-feedback-cycle exemption clause referencing `### Feedback Cycles`. | None. |
| 6 | `TeamCreate(team_name="{project_name}-{dir_basename}")` — deterministic name, no uniqueness. | `TeamCreate(team_name="{project_name}-{dir_basename}-{YYYYMMDD-HHMM}-{shortuuid}")` at startup. Always store and use the *returned* `team_name` (existing rule, preserved). | `claude-first-officer-runtime.md` — update line 11 startup prose; keep the existing line-12 "returned team_name is authoritative" note. | Static (grep): new file contains `YYYYMMDD-HHMM` (or equivalent timestamp format token) in the TeamCreate invocation example. | Prerequisite for 2a. |

## Acceptance Criteria

Each criterion cites how it is tested. Tests map to the static-grep checks and optional E2E column above.

1. **AC-1 (Rule 1 removal):** `skills/first-officer/references/claude-first-officer-runtime.md` does not contain a `test -f … config.json` probe in the `## Dispatch Adapter` section. **Test:** static regex assertion in a replacement for `tests/test_team_health_check.py` — the probe string is absent from the Dispatch Adapter subsection text.
2. **AC-1b (startup-only probe framing):** The same file contains at most one reference to the `config.json` probe and it is scoped to the `## Team Creation` section as a startup sanity check. **Test:** static — count occurrences and assert section containment.
3. **AC-2 (retry-to-same-name ban):** The recovery prose contains an unambiguous ban on retrying to the same team name (e.g., "Retry to the same team name is banned") and does not contain the old `TeamDelete → TeamCreate` same-name recovery sequence. **Test:** static regex assertions — one positive match, one negative match.
4. **AC-2b (zombie presumption):** The recovery prose states that all prior agent names are presumed-zombified after a registry-desync and that fresh-dispatch from entity frontmatter is the recovery path. **Test:** static regex.
5. **AC-4-triggers (Degraded Mode trigger enumeration):** The runtime adapter contains a `## Degraded Mode` (or `### Degraded Mode`) section, and within that section the three triggers are present as a markdown list (bulleted or numbered): (i) first "Team does not exist" error; (ii) any second dispatch failure; (iii) captain command `/spacedock bare`. **Test:** the assertion parses the adapter into sections keyed by heading, selects the `## Degraded Mode` section, and asserts that section's content contains a markdown list with all three triggers. NOT a global `re.search` on the full file.
6. **AC-4-effects (Degraded Mode effects):** The same `## Degraded Mode` section contains the three effect bullets: (a) no `team_name` on subsequent `Agent()` dispatches for the rest of the session, (b) every stage fresh-dispatches and blocks until completion, (c) no SendMessage reuse. **Test:** the assertion parses the adapter into sections keyed by heading, selects the `## Degraded Mode` section, and asserts all three effect bullets are present within that section's content. NOT a global `re.search`.
7. **AC-4-shutdown (Cooperative Shutdown Sweep subsection):** The `## Degraded Mode` section contains a Cooperative Shutdown Sweep subsection specifying (a) single-pass sweep, (b) ignore failures, (c) do not retry, (d) exemption for agents whose entity is in an active feedback-cycle state (referencing `### Feedback Cycles`), (e) sweep of feedback-cycle reviewers only on explicit captain confirmation. **Test:** the assertion parses the adapter into sections keyed by heading, selects the `## Degraded Mode` section, then selects the Cooperative Shutdown Sweep subsection, and asserts all five elements are present within that subsection's content. NOT a global `re.search`.
8. **AC-4c (captain report verbatim):** The canonical captain-facing sentence appears verbatim in the runtime adapter's `## Degraded Mode` section Captain Report Template subsection: *"Falling back to bare mode for the remainder of this session due to team-infrastructure failure. Prior team agents are presumed-zombified; I will not route work to them or through the team registry. If you want to escalate: restart the session to retry team mode with a fresh name, or let me continue — every stage will still complete, just without concurrent dispatch."* **Test:** the assertion parses the adapter into sections, selects the `## Degraded Mode` section's Captain Report Template subsection, and asserts this exact sentence is present in that subsection's content. NOT a global string match.
9. **AC-6 (unique TeamCreate name):** The startup prose specifies a TeamCreate name with a timestamp suffix of the form `YYYYMMDD-HHMM` (plus optionally a shortuuid). **Test:** static regex anchored to the `## Team Creation` section.
10. **AC-T (test file refresh):** `tests/test_team_health_check.py` is either rewritten in place or replaced by `tests/test_team_fail_early.py` to reflect the new semantics. The old AC1–AC4 assertions in that file (which assert the presence of the probe prose) are gone. **Test:** the refreshed test passes against the new runtime adapter and fails against the current one.
11. **AC-E (optional live E2E, staff-review discretion):** One live E2E test under `claude-live-opus` or `claude-live` simulates a `Team does not exist` error at dispatch time and observes the FO (a) does not retry to the same team name, (b) enters Degraded Mode, (c) emits the canonical captain report sentence. **Test:** `tests/test_runtime_live_fail_early.py` (new file) with fault injection via a stub runtime wrapper. Cost estimated at $0.50–$2.00 per run.

### Follow-on required task (file after gate)

AC-E must be tracked as a MANDATORY post-v1 follow-on task, even though it is optional for the v1 implementation. Rationale: every other AC (AC-1 through AC-T, including the three split AC-4-* ACs) verifies PROSE STRUCTURE, not RUNTIME BEHAVIOR. Without AC-E or an equivalent fault-injection harness, a future rewrite could satisfy every static assertion and still behave incorrectly at runtime. The `score ≥ 0.50` threshold for filing the follow-on is appropriate — the static assertions give us strong coverage of "did we write the words?" but zero coverage of "does the FO actually do the thing under failure?" The follow-on task should cover building the fault-injection harness (a stubbable layer over `Agent()`) and landing AC-E against it. This follow-on is **not** to be filed in the current cycle — it is flagged here so it is visible at the gate and the captain can file it post-merge.

## Test Plan

- **Static assertions (low cost, fast):** AC-1, AC-1b, AC-2, AC-2b, AC-4-triggers, AC-4-effects, AC-4-shutdown, AC-4c, AC-6, AC-T all verify via section-anchored parse-and-assert checks (not global `re.search`) against the assembled runtime adapter content. Implementation lives in the refreshed `tests/test_team_fail_early.py`; it must include a helper that parses the adapter markdown into a section tree keyed by heading so every AC-4-* check can select a specific section/subsection before asserting content. Runtime cost: milliseconds per assertion; total cost: seconds.
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

## Staff Review (2026-04-15)

**Sections opened by reviewer:** I read the entire ideation above (seed → summary), all 182 lines of `skills/first-officer/references/claude-first-officer-runtime.md`, the whole of `skills/first-officer/references/first-officer-shared-core.md` (228 lines), and all of `tests/test_team_health_check.py` (152 lines). I also sampled `skills/commission/bin/claude-team` lines 35–36 and 150–180 to verify NAME_PATTERN / NAME_MAX_LEN constraints that bear on Rule 6 naming.

### 1. Design soundness

The two-file scope is mostly right, with one concrete leak and one soft risk.

**Concrete leak — NAME_PATTERN collision.** `claude-team` lines 35 and 170 enforce `NAME_PATTERN = ^[a-z0-9][a-z0-9-]*[a-z0-9]$` against the *derived* agent name, not against `team_name`. So the team-name template `{project_name}-{dir_basename}-{YYYYMMDD-HHMM}-{shortuuid}` is not directly constrained by the helper. But: Claude Code's `TeamCreate` has its own name rules (unknown here, but historically it rejects uppercase and some punctuation and silently renames on violation) and the helper's own derived-name check is the closest proxy we control. If the TeamCreate call produces a rename, the ideation's rule (always store the returned name) covers it — so this is not a blocker, just a fact to call out in the prose: "timestamp tokens must be lowercase, no colons." A 4-digit HH:MM format with a colon would be rejected by the helper's pattern on the derived-agent-name path even though `team_name` itself isn't validated by the helper; best to use `YYYYMMDD-HHMM` (no colons, as the ideation already specifies) and document the restriction.

**Soft risk — shared-core claim is correct.** I verified the ideator's assertion: `first-officer-shared-core.md` contains no reference to `config.json`, `test -f`, "Team does not exist", "TeamDelete", or a same-name retry flow. Dispatch there is runtime-agnostic ("The FO MUST use the runtime-specific dispatch mechanism described in the runtime adapter"). Shared-core does NOT need to change. Good.

**Scaffolding touch: two files, not one.** The ideation claims only `claude-first-officer-runtime.md` plus the test file. Let me check `agents/first-officer.md` (not read above but named in shared-core line 3 as an alignment target). The ideator did not read or reference `agents/first-officer.md`. If that agent definition duplicates any of the health-check / recovery prose, it is also in scope. I did not open it in this review — **the ideator should confirm it does not duplicate the retired probe prose or the retry-same-name flow before implementation.** This is a gap.

**Helper change: correctly judged out of scope.** The helper receives `team_name` from input and forwards it (line 104, 268). Uniqueness-suffix generation by the FO before calling the helper is cleaner than adding a flag; YAGNI call is right.

### 2. Behavior Change Requirements — row-by-row critique

| Row | Current accurate? | Mandated precise? | Testable as stated? | Dependencies correct? | Notes |
|---|---|---|---|---|---|
| 1a | YES — lines 44–46 cited correctly ("REQUIRED — Team health check" / "STOP. Do NOT call Agent() until…") | MOSTLY — "trust the in-memory team handle returned by `TeamCreate`" is fine, but "let `Agent()` itself surface registry-desync errors" is vague: what does the FO DO on that surfaced error? The answer is "follow Rule 2," but the row should cross-ref Rule 2 explicitly. | Static grep fine. E2E is weaker than stated — the existing test asserts `test -f` IS present; inverting to "IS absent" works only if the FO doesn't add *some other* bash sanity check that also happens to include those substrings. Consider a tighter predicate. | None — correct. | Minor. |
| 1b | YES — no startup-only probe exists today. | WEAK — "pick up an orphan worktree or verifying a team directory was not externally mutated" is hand-wavy. When exactly? On boot only? After a `status --boot` anomaly? The prose should name the *trigger*. | Static grep for "exactly one reference to config.json probe" will pass even if the probe is referenced in the wrong section or in a comment. | None. | Needs tightening. |
| 2a | YES — line 16 is quoted accurately (TeamDelete → TeamCreate, implicitly same name). | MOSTLY — the mandated behavior is precise for the happy branch (fresh-suffixed name). But "equivalent registry-desync signal" is undefined. Does that include "Already leading team" (line 20)? Timeout? Quota? The current prose at line 20 treats "Already leading team" as recoverable — the new rule must state whether that specific error is still recoverable or also terminal. | Static greps are good. The "fresh-suffixed" positive-match will pass even if the FO writes prose that describes the suffix but doesn't include a code example — consider asserting on the invocation form itself. | YES — depends on row 6. | Needs clarification on "Already leading team" + explicit enumeration of which errors are "registry-desync." |
| 2b | MOSTLY — current behavior is "resume SendMessage reuse of any agent name that existed in the prior team," which is inferred rather than stated in the current prose. The current prose doesn't explicitly prescribe this; it's an implicit consequence of the retry-to-same-name flow. The row should say "Implicitly, today, a successful same-name retry allows SendMessage reuse; this row bans that." | YES — "all prior agent names are presumed zombified" and "re-dispatch from entity frontmatter" are crisp. | YES — static greps fine. | YES. | Minor wording on "current" column. |
| 4a | YES — line 14 and line 21 cited accurately. | YES for triggers (iii) captain command, (i) first "Team does not exist" error. Trigger (ii) "2+ dispatch failures inside a 5-minute window" is NOT operator-checkable by the FO in a disciplined way — see §5 for detail. | Static grep for "three triggers verbatim" is load-bearing only if the prose actually enumerates triggers in a parseable form. Today's `test_team_health_check.py` uses `re.search` with `re.DOTALL` (line 135) — the static test for Rule 4a should require a numbered or bulleted list, not just substring matches. | None. | Trigger (ii) needs rework. |
| 4b | PARTIALLY — "silently strip team_name ... sometimes inconsistently" is speculative; it describes a failure mode, not a rule. The current prose is silent on mid-session degradation mechanics. | YES — three effect bullets are crisp. | E2E check is strong — "every subsequent Agent() tool call has no team_name parameter" is a tight predicate. | None. | Good row. |
| 4c | YES — current is accurate (captain learns from context). | YES — verbatim sentence is specified. | YES. | None. | See §5 — verbatim sentence could be better; it tells the captain WHAT happened but not what to DO. |
| 4d | YES — accurate. | YES — single-pass sweep with "ignore failures" is crisp. | Static grep is weak ("single-pass", "ignore failures") — easy to satisfy with boilerplate without real semantics. Consider an E2E check under fault injection. | None. | Minor. |
| 6 | YES — line 11 is quoted accurately. | YES for the format. | Static grep for `YYYYMMDD-HHMM` is fine. Does not verify the FO actually CONSTRUCTS the name at call time with a real timestamp — only that the prose example uses that token. A runtime check would need E2E. | YES — prerequisite for 2a. | Minor. |

**Rows missing or underspecified:** No row for "what happens on session resume after a Degraded Mode session ended" — see §5.

### 3. Acceptance Criteria sufficiency

Row-to-AC coverage matrix:

| Row | Covered by AC | Gap |
|---|---|---|
| 1a | AC-1 | None. |
| 1b | AC-1b | None. |
| 2a | AC-2, AC-6 | None. |
| 2b | AC-2b | None. |
| 4a | AC-4 | AC-4 lumps triggers, effects, captain report, and shutdown sweep into one assertion — if any one sub-element is missing, AC-4 still passes if the grep is loose. Split into AC-4-triggers / AC-4-effects / AC-4-shutdown for precision. |
| 4b | AC-4 | Same — submerged inside AC-4. |
| 4c | AC-4c | None. Good — given its own AC. |
| 4d | AC-4 | Submerged in AC-4. Should be its own AC. |
| 6 | AC-6 | None. |

**Static-grep precision.** The existing `tests/test_team_health_check.py` uses `re.search(r"not in bare mode or single-entity mode", assembled)` — this pattern would false-positive on prose that happens to contain the literal substring elsewhere (e.g., a comment "skipped in bare mode or single-entity mode" in a footnote section). The new assertions should anchor by section heading (parse markdown sections, then assert within a specific section) rather than global `re.search`. Otherwise a non-fix rewrite could pass.

**AC-E positioning.** AC-E is correctly positioned as optional for the initial implementation, BUT it is the ONLY check that verifies runtime behavior rather than prose structure. Without AC-E or equivalent, the whole acceptance suite answers "is the prose rewritten?" not "does the FO actually behave differently?" This is a real gap (see §4). My recommendation: keep AC-E optional for v1 but mandate a follow-on ticket to land it before the ideation can be considered "done" in the broader sense. Promoting AC-E to required in v1 would be ideal but raises cost and complexity (fault-injection harness does not exist yet).

### 4. Test plan realism

**The gap the ideation named but understated.** The Test Plan claims "Static assertions carry primary coverage." This is defensible for *prose correctness* — did we write the words? — but not for *behavior change*. A future model rewriting the adapter could satisfy every static grep and still behave incorrectly at runtime if the new prose is self-contradictory or the model attends to the wrong sections. The existing E2E (`test_team_health_check.py`) is even more a prose-behavior test: it checks that the FO emitted a `test -f` Bash call before Agent, which was behavior that followed from the prose. The refresh would invert it — check that the FO does NOT emit `test -f` before Agent — but that negative runtime assertion is satisfied by *any* rewrite that removes the probe, including one that silently introduces a different bug (e.g., skipping the whole dispatch block). The ideator's note in the Test Plan summary ("the static assertions plus the refreshed baseline E2E give strong coverage of prose behavior; the fault-injection harness is nice-to-have but not load-bearing") is too sanguine. The fault-injection harness is the ONLY check that verifies the Rule 2 and Rule 4 paths actually fire. Recommend: AC-E should be tracked as a follow-on required task even if not blocking v1 merge.

**Concrete test-plan risk.** AC-T says "the refreshed test passes against the new runtime adapter and fails against the current one." This is a good property, but it's only checked manually. Consider adding a CI job or a `make` target that runs the old assertions against the new adapter (expect fail) and the new assertions against the old adapter (expect fail), to lock in the contract. Low-effort.

### 5. Gaps and risks

**(a) "2+ dispatch failures in 5 minutes" — not operator-checkable.** The FO has no durable counter of dispatch failures with timestamps. "Session memory" is a prompt-shaped mental list that degrades across context pressure, idle notifications, and resume. Without a concrete mechanism (a file, a status field, a helper that tracks failures), the FO cannot reliably evaluate this predicate. Recommendation: either drop this trigger, replace it with "any second dispatch failure regardless of timing" (simpler and stricter — more likely to degrade early, which is the goal of fail-early), or define a persistence mechanism (e.g., `status --log-failure` that writes to a session file). The ideation should pick one; leaving it as "2+ in 5 minutes" without saying HOW to count is a defect.

**(b) Captain report sentence (AC-4c) wording.** The verbatim sentence is *"Falling back to bare mode for the remainder of this session due to team-infrastructure failure. Prior team agents are presumed-zombified; I will not route work to them or through the team registry."* This tells the captain what happened and what the FO will not do. It does NOT tell the captain what THEY should do. For fail-early to be actionable, the sentence should close with a next step, e.g., "If you want to escalate this, you can: (1) restart the session to retry team mode, (2) run `/spacedock bare` to confirm the degraded mode, or (3) let me proceed — every stage will still complete, just without concurrent dispatch." Without a next-step pointer, the captain may interpret the report as a stall signal and interrupt. Recommend: revise the verbatim sentence to include at least one concrete next step.

**(c) "Presumed zombified" does not map to concrete state.** Row 2b introduces a categorical label ("presumed zombified") without saying what it maps to. Is it a frontmatter field? A mental list? A return value of `status --boot`? If it's just FO mental state, it does not survive session resume. The ideation should either (i) say "presumed zombified" is session-local reasoning, not durable state, and accept the consequences, or (ii) define a persistence location. Related risk: a valid non-zombie agent (e.g., a reviewer still holding state from a feedback cycle) could be "presumed zombified" and prematurely shut down. The cooperative-shutdown sweep (4d) makes this concrete — it will SendMessage shutdown every known agent name. If any of those names still has a valid reviewer handle, we lose its context. Mitigation: the sweep should exempt any agent whose entity is in an active feedback-cycle state.

**(d) Rule 6 naming vs. Claude Code constraints.** Confirmed above: `NAME_PATTERN = ^[a-z0-9][a-z0-9-]*[a-z0-9]$`, `NAME_MAX_LEN = 200`. The `YYYYMMDD-HHMM` format is compatible (digits + hyphen). `{shortuuid}` is 8 lowercase alphanum chars — compatible. Total typical length: `spacedock-multi-stage-pipeline-20260415-0347-a1b2c3d4` ≈ 54 chars, well under 200. No blocker. Note: the helper validates the *derived* agent name (`{worker_key}-{slug}-{stage}`), not the team_name, so the length headroom on the team_name side is effectively uncapped by our tooling. CC may apply its own rules, caught by the "use the returned team_name" rule.

**(e) Degraded-mode recovery after SESSION restart.** The ideation does not address what happens when a session that entered Degraded Mode ends and a new session starts. Next-session FO has no memory of the degrade. It will attempt `TeamCreate` normally. If the underlying #36806 contamination persists, it will desync again → fall into Rule 2 → fresh-suffixed name → hopefully succeed. So Rule 2 already covers the re-boot case *if* the new session's first TeamCreate fails. But if the filesystem still has the stale config from the previous session's first team, the startup-only probe (row 1b) will PASS on that stale config without ever calling TeamCreate, leading to a different contamination path. Recommendation: add a row or sub-rule — "on startup, do not treat existing on-disk team directories as evidence of team health; always attempt TeamCreate fresh." This may conflict with the runtime adapter's current line 13 warning ("NEVER delete existing team directories — stale directories belong to other sessions"), which is a pre-existing constraint. The tension should be resolved explicitly in the ideation.

**(f) Minor — `agents/first-officer.md` not audited.** As noted in §1, the ideator did not check whether the agent-definition file duplicates any probe or retry prose. Three-minute check; add it to the implementation ordering.

### Recommendation

**APPROVE WITH REVISIONS.** The ideation is fundamentally sound — the two-file scope is right, the Behavior Change Requirements table is a genuinely useful central artifact, and the mapping from team-fragility Rules 1/2/4/6 to testable prose changes is thorough. Before the gate, the ideator should make three specific edits:

1. **Resolve the "2+ failures in 5 minutes" trigger** (§5a): either drop it, replace with "any second dispatch failure" (my preference — cleaner, more aggressive fail-early), or define a persistence mechanism. Update Row 4a and AC-4 to reflect the choice.
2. **Split AC-4 into AC-4-triggers, AC-4-effects, AC-4-shutdown** (§3) and tighten the static-grep assertions to anchor by markdown section heading rather than global `re.search` substring match (§3, §5 on test plan).
3. **Address the session-restart recovery tension** (§5e) with at least one new row or sub-bullet: how does a new session know the prior session went bare, and does the Rule 1b startup probe conflict with the "always try TeamCreate fresh" implication of Rule 2? Also revise the AC-4c captain-report sentence to include a concrete next-step pointer (§5b).

Items not blocking gate but worth a line in the ideation: (i) audit `agents/first-officer.md` before implementation; (ii) exempt active-feedback-cycle agents from the cooperative-shutdown sweep (§5c); (iii) track AC-E as a mandatory follow-on ticket even if optional for v1 (§3, §4).

## Stage Report — Ideation Revision (2026-04-15)

1. **Read staff review and prior ideation — DONE.** Re-read §1–§5 + Recommendation of the staff review (lines 183–270) and the full prior ideation (lines 15–181) as a fresh ensign.
2. **Apply revision #1 (trigger ambiguity) — DONE.** Replaced "2+ dispatch failures inside a 5-minute window" with "any second dispatch failure" in Row 4a's Mandated-behavior column and in the Proposed-Approach Rule-4 prose. Rationale note added in Row 4a explaining why the stricter, counter-free rule was chosen (FO has no durable timestamp counter; fail-early wins).
3. **Apply revision #2 (AC-4 split + section anchoring) — DONE.** Split the original AC-4 into AC-4-triggers / AC-4-effects / AC-4-shutdown. AC-4c was already separate and is preserved (with revised verbatim sentence — see #4). Every AC-4-* assertion now explicitly states "parses the adapter into sections keyed by heading, selects the `## Degraded Mode` section, and asserts within that section's content. NOT a global `re.search`." The Test Plan bullet was updated to list the new AC-4-* ACs and to mandate a section-parsing helper in the test file.
4. **Apply revision #3 (session-restart tension + captain-report sentence) — DONE.** (a) Rewrote Row 1b's Mandated-behavior column to explicitly state the startup probe is DIAGNOSTIC-ONLY and NEVER short-circuits `TeamCreate`; cited the existing line-13 "NEVER delete existing team directories" constraint and noted deletion is separate from ignore-for-dispatch-purposes. Testable-check column now requires both a diagnostic framing AND an explicit non-short-circuit clause in the `## Team Creation` section. (b) Revised Row 4c and AC-4c verbatim sentence to: "Falling back to bare mode for the remainder of this session due to team-infrastructure failure. Prior team agents are presumed-zombified; I will not route work to them or through the team registry. If you want to escalate: restart the session to retry team mode with a fresh name, or let me continue — every stage will still complete, just without concurrent dispatch." Row 4c and AC-4c now match exactly.
5. **Address non-blocking flag (i) — DONE.** Added Step 0 to the Proposed-Approach implementation ordering: audit `agents/first-officer.md` before implementation. Also performed the audit during this ideation revision (grep on `test -f`, `config.json`, `Team does not exist`, `TeamDelete`, `retry`, `bare mode`, `degraded` in `agents/first-officer.md` — no matches). Current scope remains 2 files; implementer must re-verify at worktree start in case the agent file drifts.
6. **Address non-blocking flag (ii) — DONE.** Added the active-feedback-cycle exemption to Row 4d's Mandated-behavior column, referencing `### Feedback Cycles` in the entity body and requiring explicit captain confirmation to sweep feedback-cycle reviewers. AC-4-shutdown was updated to verify the exemption clause is present in the Cooperative Shutdown Sweep subsection.
7. **Address non-blocking flag (iii) — DONE.** Added a `### Follow-on required task (file after gate)` subsection at the bottom of the Acceptance Criteria section, flagging AC-E (fault-injection E2E) as a MANDATORY post-v1 task, noting `score ≥ 0.50` is the appropriate filing threshold, and explicitly stating the task is NOT filed in this cycle — it is flagged for the captain to file post-merge.
8. **End-to-end re-read — DONE.** Confirmed: (a) the Behavior Change Requirements table has 9 rows now reflecting all three revisions (1a, 1b [session-restart clause], 2a, 2b, 4a [any-second-failure trigger], 4b, 4c [new captain sentence], 4d [exemption clause], 6); (b) the Acceptance Criteria section has the AC-4 split (AC-4-triggers, AC-4-effects, AC-4-shutdown), the revised AC-4c with next-step pointer, and the Follow-on subsection; (c) the Proposed Approach ordered list includes Step 0 audit; (d) the captain-report sentence in Row 4c and AC-4c match verbatim.
9. **Append this Stage Report — DONE (this section).**
10. **Commit atomic — pending (final action).**

### Summary

Applied all 3 blocking revisions and 3 non-blocking flags from the staff review (commit 343f451d). Revisions landed on the entity body only; YAML frontmatter and the staff-review section are untouched. The ideation now specifies (a) a counter-free "any second dispatch failure" trigger, (b) three section-anchored AC-4-* assertions plus a parse-sections helper requirement, (c) explicit resolution of the session-restart / Rule-1b-probe tension (diagnostic-only, never short-circuits `TeamCreate`), (d) a captain-report sentence with three concrete next steps, (e) a Step-0 audit of `agents/first-officer.md` (executed during this revision — no duplication found, scope stays 2 files), (f) an active-feedback-cycle exemption on the cooperative shutdown sweep, and (g) an explicit follow-on flag for AC-E. Ready for gate re-review.

## Stage Report — Implementation (2026-04-15)

1. **Pre-check — DONE.** Worktree `/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-fo-team-infrastructure-fail-early` on branch `spacedock-ensign/fo-team-infrastructure-fail-early`, clean tree at entry. HEAD at start: `b065050f` (the revised-ideation commit).
2. **Re-read entity body — DONE.** Re-read the Behavior Change Requirements (9 rows 1a/1b/2a/2b/4a/4b/4c/4d/6), all 11 Acceptance Criteria including the AC-4 split, the Proposed Approach's Step 0 audit status, and the Staff Review as the reference for why specific phrasings were chosen.
3. **Step 0 audit — DONE.** Ran `grep -E 'test -f|config.json|Team does not exist|TeamDelete|retry|bare mode|degraded' agents/first-officer.md` — no matches. Scope remains 2 files (runtime adapter + test refresh); the agent-definition file is untouched.
4. **Rule 1 applied — DONE.** In `skills/first-officer/references/claude-first-officer-runtime.md`: deleted the `REQUIRED — Team health check` paragraph from the `## Dispatch Adapter` section; replaced with an explicit `No pre-dispatch filesystem probe.` paragraph that forbids any pre-dispatch check against `~/.claude/teams/{team_name}/` and cites anthropics/claude-code#36806. Added the DIAGNOSTIC-ONLY startup probe paragraph to `## Team Creation` that explicitly does NOT gate / short-circuit / skip `TeamCreate`; preserved the existing line-13 "NEVER delete existing team directories" constraint.
5. **Rule 2 applied — DONE.** Rewrote the `TeamCreate failure recovery` block in `## Team Creation` as a priority-ordered ladder: (1) fresh-suffixed `TeamCreate` with name `{project_name}-{dir_basename}-{YYYYMMDD-HHMM}-{shortuuid}`; (2) fall back to Degraded Mode; (3) surface to captain. Includes the exact asserted phrase `Retry to the same team name is banned` and the exact phrase `All prior agent names are presumed zombified. Do not SendMessage them; re-dispatch from entity frontmatter.` The prescriptive `Call TeamDelete ... then call TeamCreate` same-name recovery is removed; `TeamDelete` is now only permitted as a narrow startup-only procedure for the `Already leading team` case and explicitly forbidden as a mid-session response to registry-desync.
6. **Rule 6 applied — DONE.** Updated the startup TeamCreate example on line 11 to `TeamCreate(team_name="{project_name}-{dir_basename}-{YYYYMMDD-HHMM}-{shortuuid}")`; documented the NAME_PATTERN-compatible constraint (lowercase, no colons, hyphen-separated); preserved the existing "always use the returned team_name" note.
7. **Rule 4 applied — DONE.** Added a new top-level `## Degraded Mode` section with four subsections keyed by heading for the test parser: `### Triggers` (three triggers as a markdown list: first "Team does not exist" error, any SECOND dispatch failure, captain `/spacedock bare`), `### Effects` (three bullets: no `team_name` on subsequent dispatches, every stage dispatches fresh and blocks, no SendMessage reuse), `### Captain Report Template` (verbatim canonical sentence with the three next-step options), `### Cooperative Shutdown Sweep` (single-pass, ignore failures, do not retry, active-feedback-cycle exemption referencing `### Feedback Cycles`, sweep of feedback-cycle reviewers only on explicit captain confirmation).
8. **Test refresh — DONE.** Created `tests/test_team_fail_early.py` with nine pytest-style ACs and a `parse_sections()` helper that anchors assertions by markdown heading (not global `re.search`). Deleted the superseded `tests/test_team_health_check.py` (its AC1–AC5 directly contradicted the new adapter). Also refreshed two stale tests in `tests/test_agent_content.py` (`test_assembled_claude_first_officer_has_teamcreate_failure_recovery` and the renamed `test_assembled_claude_first_officer_has_no_predispatch_health_check`) that asserted the retired probe and same-name recovery invariants against the assembled first-officer contract. AC-T (refresh property) is implicit in the comment at the top of the new test file.
9. **Static test suite — DONE.** `make test-static` → `310 passed, 10 subtests passed in 6.60s`. Baseline before this cycle (on this worktree) was `301 passed, 10 subtests passed` because the old `test_team_health_check.py` was a `main()`-style E2E that pytest did not collect; the +9 delta matches the nine new ACs in `test_team_fail_early.py`. The checklist's anticipated `308/309` numbers reflected a different baseline; the shape of the result (fully green, +9 from the refresh) matches the intent.
10. **Refreshed test file standalone — DONE.** `unset CLAUDECODE && uv run --with pytest pytest tests/test_team_fail_early.py -v` →
    ```
    tests/test_team_fail_early.py::test_ac1_dispatch_adapter_has_no_config_probe PASSED [ 11%]
    tests/test_team_fail_early.py::test_ac1b_team_creation_has_single_diagnostic_only_probe PASSED [ 22%]
    tests/test_team_fail_early.py::test_ac2_retry_same_name_banned_and_no_same_name_teamdelete_teamcreate PASSED [ 33%]
    tests/test_team_fail_early.py::test_ac2b_prior_agents_presumed_zombified_and_redispatch_from_frontmatter PASSED [ 44%]
    tests/test_team_fail_early.py::test_ac4_triggers_enumerated_as_list_in_degraded_mode PASSED [ 55%]
    tests/test_team_fail_early.py::test_ac4_effects_listed_in_degraded_mode PASSED [ 66%]
    tests/test_team_fail_early.py::test_ac4_shutdown_sweep_with_feedback_cycle_exemption PASSED [ 77%]
    tests/test_team_fail_early.py::test_ac4c_captain_report_template_verbatim PASSED [ 88%]
    tests/test_team_fail_early.py::test_ac6_teamcreate_name_uses_timestamp_and_shortuuid_suffix PASSED [100%]
    9 passed in 0.01s
    ```

### Files changed

- `skills/first-officer/references/claude-first-officer-runtime.md` (+43 / −9): Rule 1 deletion, Rule 2 ladder rewrite, Rule 4 new section, Rule 6 name template.
- `tests/test_team_fail_early.py` (new, +260): nine section-anchored ACs with a `parse_sections()` helper.
- `tests/test_team_health_check.py` (deleted): superseded by the refresh.
- `tests/test_agent_content.py` (±): `test_assembled_claude_first_officer_has_teamcreate_failure_recovery` refreshed to assert the new fail-early ladder invariants; `test_assembled_claude_first_officer_has_team_health_check` renamed and inverted to `test_assembled_claude_first_officer_has_no_predispatch_health_check`.
- `agents/first-officer.md`: unchanged (Step 0 audit confirmed no duplication).

### Per-AC evidence

| AC | Satisfied by | Location |
|---|---|---|
| AC-1 | `## Dispatch Adapter` contains "No pre-dispatch filesystem probe." paragraph; no `test -f` / `config.json` / "Team health check" tokens in that section. | `claude-first-officer-runtime.md` line 48. |
| AC-1b | `## Team Creation` contains exactly one `config.json` reference (the DIAGNOSTIC-ONLY startup probe) with the non-short-circuit clause "does NOT gate, short-circuit, or skip `TeamCreate` — `TeamCreate` always runs". | `claude-first-officer-runtime.md` line 16. |
| AC-2 | `Retry to the same team name is banned` present verbatim; `fresh-suffixed` present; no prescriptive `Call TeamDelete ... then call TeamCreate` same-name instruction. | `claude-first-officer-runtime.md` lines 20–22 (recovery ladder tier 1). |
| AC-2b | `All prior agent names are presumed zombified. Do not SendMessage them; re-dispatch from entity frontmatter.` present verbatim. | `claude-first-officer-runtime.md` line 22 (end of ladder tier 1). |
| AC-4-triggers | `### Triggers` subsection lists three triggers as a markdown list: `First "Team does not exist" error`, `Any SECOND dispatch failure within the session`, `Captain command /spacedock bare`. | `claude-first-officer-runtime.md` lines 106–112. |
| AC-4-effects | `### Effects` subsection lists three effect bullets. | `claude-first-officer-runtime.md` lines 114–120. |
| AC-4-shutdown | `### Cooperative Shutdown Sweep` contains single-pass, ignore-failures, do-not-retry, active feedback-cycle exemption referencing `### Feedback Cycles`, and explicit-captain-confirmation language. | `claude-first-officer-runtime.md` lines 128–132. |
| AC-4c | `### Captain Report Template` contains the verbatim canonical sentence including the three next-step options. | `claude-first-officer-runtime.md` lines 122–126. |
| AC-6 | Startup TeamCreate example uses `TeamCreate(team_name="{project_name}-{dir_basename}-{YYYYMMDD-HHMM}-{shortuuid}")`; lowercase / no-colon constraint is documented. | `claude-first-officer-runtime.md` line 11. |
| AC-T | Implicit — old test asserted probe present; new test asserts probe absent. Comment at the top of `test_team_fail_early.py` documents this. | N/A (property). |
| AC-E | DEFERRED per the ideation's `### Follow-on required task` subsection. Not in scope for this cycle. | N/A. |

### Commits

- `8589df72` — `prose: #149 adapt runtime adapter for fail-early team-infrastructure defense`
- `d8271e84` — `tests: #149 refresh team-fail-early assertions with section-anchored matching`
- (this report will be in a subsequent `report:` commit)

### Static + test results

- `make test-static` → `310 passed, 10 subtests passed in 6.60s` (baseline on this worktree was 301; +9 for the new AC suite).
- `uv run --with pytest pytest tests/test_team_fail_early.py -v` → `9 passed in 0.01s`.

### Pre/post HEAD SHAs

- Pre: `b065050f2d2d27e3c86f05d049e07de530f43e8f`
- Post (after adapter + tests commits): `d8271e845bf0fb724ee8580b8238648c6292e208`
- Post (after this report commit): will be captured at final report.

### Summary

Implementation of #149 rules 1, 2, 4, and 6 landed on `claude-first-officer-runtime.md` with Rule 1 deletion, Rule 2 priority-ordered recovery ladder, a new `## Degraded Mode` section (Triggers / Effects / Captain Report Template / Cooperative Shutdown Sweep), and Rule 6 fresh-suffixed TeamCreate name. Tests refreshed: new section-anchored `tests/test_team_fail_early.py` supersedes the retired `test_team_health_check.py`, and two stale assertions in `tests/test_agent_content.py` were updated to match the new contract. `make test-static` green (310 passed). AC-E is deferred to the mandatory post-v1 follow-on per ideation.
