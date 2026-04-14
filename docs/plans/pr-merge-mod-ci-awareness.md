---
id: 152
title: "pr-merge mod: detect CI failure on PR and route back to implementation"
status: backlog
source: "CL observation during 2026-04-14 session — validator PASSED based on local tests while PR CI could silently fail post-handoff, leaving entities stuck PR-pending"
started:
completed:
verdict:
score: 0.75
worktree:
issue:
pr:
---

## Problem

The current lifecycle for a validated entity:

1. Validator runs local tests → reports PASSED/REJECTED
2. Captain approves the validation gate
3. `pr-merge` merge hook opens a PR, sets the entity's `pr` field, returns
4. Entity sits with `status=done + pr=#N`, awaiting PR merge
5. FO event loop + `pr-merge` idle hook polls `gh pr view` — on MERGED, advance and archive

The gap: the validator's PASSED verdict is grounded only in *local* test runs. CI runs **after** the validator has signed off. If CI then goes red on the PR, nobody is accountable:

- The validator has already reported PASSED and moved on
- The captain may not be actively watching the PR
- The FO's idle poll only notices MERGED / CLOSED, not CI red

The entity can sit PR-pending indefinitely with a broken PR underneath it. Observed concretely during #114 PR #92 opus-live failure — the PR's CI failed deterministically, but nothing in the mod signaled "route back to implementation." Captain had to catch it manually and issue the reroute.

## Scope — robustness and routing, no auto-merge

Extend the `pr-merge` mod to be CI-aware on OPEN PRs. The validator stays local-scoped; the mod owns the PR lifecycle including CI.

Priorities:

1. Detect CI failures on PR-pending entities and route back to `implementation` with `feedback_context` populated
2. Preserve captain control over merging — do NOT auto-merge on CI green
3. Make the CI signal survive session resumes (startup hook also checks CI state)

## Proposed design

### Extend the `gh pr view` query

Current idle hook query (conceptually):

```
gh pr view {pr_number} --json state --jq '.state'
```

Extended query:

```
gh pr view {pr_number} --json state,statusCheckRollup
```

`statusCheckRollup` returns an array of check-run results. Reduce to a single state:

- **SUCCESS**: every check concluded `SUCCESS`, `NEUTRAL`, or `SKIPPED`
- **PENDING**: at least one check is `IN_PROGRESS`, `QUEUED`, or `WAITING_FOR_APPROVAL` (environment approval gate)
- **FAILURE**: any check concluded `FAILURE`, `CANCELLED`, `TIMED_OUT`, or `ACTION_REQUIRED`

### State machine extensions in the idle hook

| PR state | CI state | Action |
|----------|----------|--------|
| MERGED | any | Advance to done, archive, cleanup worktree (existing behavior) |
| CLOSED (not merged) | any | Report to captain, wait for direction (existing behavior) |
| OPEN | PENDING | No action (existing behavior for OPEN) |
| **OPEN** | **SUCCESS** | **No action** — captain still owns merge decision. Optional: one-time informational note to captain when first detected ("#N PR green, ready for merge") |
| **OPEN** | **FAILURE** (new) | Route entity back to `implementation` with CI failure summary as `feedback_context`. Keep `pr` field set (the PR remains open; captain may close it or fix). Report to captain. |

### Route-back-on-CI-failure procedure

When the mod detects OPEN + FAILURE on an entity:

1. Read the current entity `status`. If it is already `implementation` or the FO is mid-reroute, skip (prevent loops).
2. Write a CI failure summary into the entity body under a `## CI Failure Report` section. Fields:
   - Run URL (from `gh pr view ... --jq '.statusCheckRollup[].detailsUrl'` deduplicated)
   - Failing job name(s)
   - A short excerpt of the failing assertion (best-effort from log extraction; if the mod can't extract cheaply, reference the run URL and let the implementer investigate)
   - Timestamp and the PR head SHA at time of failure
3. Transition the entity: `status --set {slug} status=implementation mod-block=merge:pr-merge` — the `mod-block` is re-established so `status --set` refuses a premature re-terminalization before the fix lands.
4. Report to captain: "PR #{N} for {entity title} failed CI. Routed back to implementation with failure summary in the entity body. Prior PR remains open — close or update branch when the fix lands."
5. The FO's normal event loop then notices the entity is back in `implementation` state and dispatches an implementation ensign with `feedback_context` = the CI failure summary.

### Startup-hook parity

Extend the startup hook similarly. When the FO boots:

- For every entity with `pr != ""` and non-terminal status: run the same extended `gh pr view` query.
- If MERGED: advance (existing).
- If OPEN + FAILURE: trigger the route-back-on-CI-failure procedure. This catches CI failures that happened while the FO was offline.

### Loop prevention

The mod must not repeatedly reroute the same CI failure. Tracking:

- Use a `ci-fail-sha` frontmatter field on the entity (new, optional). When routing back, record the PR head SHA that failed.
- On each subsequent check, if the current PR head SHA equals `ci-fail-sha`, the mod has already rerouted for this SHA — skip.
- When a new commit is pushed to the PR branch (head SHA changes), `ci-fail-sha` becomes stale and the mod can reroute again if the new SHA also fails.
- On MERGED, clear `ci-fail-sha` along with `mod-block` and `pr`.

## Acceptance criteria

1. **AC-1: Idle hook queries statusCheckRollup.** `pr-merge.md` idle-hook prose specifies the extended `gh pr view --json state,statusCheckRollup` query.
   - Test: `test_pr_merge_template.py` — prose assertion.
2. **AC-2: CI failure routes back to implementation.** Given an entity with `status=done, pr=#N, mod-block=...` and PR CI state FAILURE, the mod's idle hook sets `status=implementation` and writes a `## CI Failure Report` section into the entity body.
   - Test: E2E `tests/test_pr_merge_ci_reroute.py` — stub `gh` responses, run the mod, assert entity state + body.
3. **AC-3: CI success does not auto-merge.** Given OPEN + SUCCESS, the mod takes no state-changing action. Optional informational note to captain is acceptable but not required by the AC.
   - Test: same fixture as AC-2, swap CI state to SUCCESS, assert no status change.
4. **AC-4: Loop prevention via ci-fail-sha.** A second invocation of the idle hook on the same failed PR (same head SHA) does not re-route and does not re-append the failure report.
   - Test: same fixture as AC-2, invoke twice, assert state is unchanged on second invocation.
5. **AC-5: Startup hook parity.** The startup hook applies the same detection and routing as the idle hook.
   - Test: prose assertion + E2E fixture with pre-existing PR CI failure, boot FO, assert entity is routed.
6. **AC-6: mod-block restored on reroute.** After a CI-triggered reroute, the entity has `mod-block=merge:pr-merge` so `status --set` refuses a bare `status=done` retry without running the hook again.
   - Test: unit test in `test_status_script.py` exercising the restored guard.
7. **AC-7: No auto-close of PR.** The mod does NOT close the failing PR automatically. Captain decides.
   - Test: E2E fixture, assert `gh pr close` was not called.

## Test plan

| Test | Harness | Assertion | Cost |
|------|---------|-----------|------|
| Prose assertions (AC-1, AC-5) | `test_pr_merge_template.py` | `pr-merge.md` contains the extended query shape and the startup-hook parity note | free |
| AC-2 reroute E2E | new `tests/test_pr_merge_ci_reroute.py` | entity state transitions correctly on failure | ~$0.30 haiku |
| AC-3 no-action on success | same fixture | no state change on SUCCESS | ~$0.30 haiku |
| AC-4 loop prevention | same fixture | second idle fire is inert | free (same run) |
| AC-6 mod-block restored | `test_status_script.py` unit | guard refuses without force | free |
| AC-7 no auto-close | same E2E fixture | `gh pr close` never invoked | free (same run) |

Total new E2E burn: roughly $0.30–0.60 (one or two runs of the new fixture). No opus required.

## Scope boundaries

**In scope:**

- Extend `mods/pr-merge.md` (plugin-shipped) with CI-aware logic on OPEN PRs
- New `ci-fail-sha` frontmatter field (add to Field Reference in the workflow `README.md` template)
- E2E test fixture with stubbed `gh pr view` responses
- Prose update in shared-core referencing the new idle/startup behavior

**Out of scope:**

- Auto-merge on CI green (captain keeps control)
- Auto-close of failing PRs (captain decides)
- Validator changes — the validator continues to report only on local tests
- Other mods — only `pr-merge` is extended
- GitHub Actions workflow changes — the mod consumes CI state; it doesn't configure CI

## Related

- #114 PR #92 opus-live failure — the canonical case study: local tests passed, CI failed deterministically, captain had to catch and reroute manually
- #149 FO team-infrastructure fail-early — adjacent robustness work, separate scope (team mechanics vs PR CI)
- `mods/pr-merge.md` — the mod this task extends

## Fast-track rationale

This should probably go through normal ideation/implementation/validation since it touches a mod plus the event-loop contract. The design above is more ideation-grade than a seed — but there are real design questions the ideation should resolve (e.g., should `ci-fail-sha` be a workflow-level convention or a mod-local concern? should the mod inspect check annotations for a shorter failure summary?). Leaving at backlog so ideation can refine.
