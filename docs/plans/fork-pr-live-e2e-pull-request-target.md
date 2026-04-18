---
id: 189
title: "Replace workflow_dispatch + pr_number pattern with pull_request_target + env-gate for fork PR live-e2e"
status: validation
source: "captain design directive during #118 merge triage — the current workflow_dispatch + pr_number design records provenance metadata but tests main, not the PR head. pull_request_target with env-gated PR-head checkout is the cleaner pattern and makes the CI signal actually mean 'PR code works'."
started: 2026-04-18T03:15:00Z
completed:
verdict:
score: 0.7
worktree: .worktrees/spacedock-ensign-fork-pr-live-e2e-pull-request-target
issue:
pr:
mod-block:
---

## Why this matters

Fork PRs (like #118 from ijac13/spacedock) hit three problems under the current `runtime-live-e2e.yml` design:

1. **`pull_request` auto-trigger withholds secrets from fork runs** (GitHub security model, not bypassable by approval). `Check required secret` step fails fast, tests never run. Effectively means: no live-e2e signal on auto-CI for fork PRs.
2. **`workflow_dispatch -f pr_number=N` checks out main, not the PR**. `actions/checkout@v4` has no `ref:` parameter, so it defaults to the dispatched ref (`main`). The `pr_number` input is used only for audit metadata in the job summary — it does NOT affect what code gets tested. A maintainer running `gh workflow run ... pr_number=118` gets a main-validation run with "this was for #118" in the summary, which is misleading.
3. **Consequence:** there is no path in the current workflow that actually runs live-e2e against fork-PR head code. External contributions get approved on static-CI + maintainer eyeball review only.

## Proposed approach

Switch the four live-e2e jobs from `on: pull_request + workflow_dispatch` to `on: pull_request_target` with environment-gated PR-head checkout.

Captain's provided shape:

```yaml
on:
  pull_request_target:
    types: [opened, synchronize, reopened]

jobs:
  test:
    environment: external-ci   # or keep existing CI-E2E / CI-E2E-OPUS / CI-E2E-CODEX
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          persist-credentials: false
      - run: ./run-tests.sh
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

Security model:

- `pull_request_target` runs with base-branch context, so repo secrets are available
- Environment `required reviewers` gate holds every run pending maintainer approval
- Maintainer reviews the PR head SHA's code BEFORE approving the env deployment → if code looks malicious, don't approve → secrets never reach bad code
- `persist-credentials: false` prevents `GITHUB_TOKEN` persistence in `.git/config` (blocks post-checkout steps from using it)
- Workflow-level `permissions: { contents: read, pull-requests: read }` narrows the default write surface

## Scope

### Changes to `.github/workflows/runtime-live-e2e.yml`

1. Replace trigger block:
   - Remove `pull_request:` and `workflow_dispatch: { inputs: { pr_number, ... } }`
   - Add `pull_request_target: { types: [opened, synchronize, reopened] }`
   - Keep the other existing inputs (claude_version, test_selector, effort_override, model_override) if they're still referenced elsewhere — decide per reference
2. Add workflow-level `permissions: { contents: read, pull-requests: read }` (narrower than default)
3. For each of the 4 jobs (`claude-live`, `claude-live-bare`, `claude-live-opus`, `codex-live`):
   - Update `actions/checkout@v4` to include `ref: ${{ github.event.pull_request.head.sha }}` and `persist-credentials: false`
   - Keep the existing `environment:` block (that's the gate)
4. Simplify the provenance-recording github-script step — it no longer needs to disambiguate `triggerSource` (always `pull_request_target` now), and `github.event.pull_request.head.sha` is available directly without REST lookup. Keep the summary output for audit trail.
5. Decide: preserve `workflow_dispatch` for manual re-runs (possibly useful)? If yes, keep a simplified version with `pr_number` input that wires `ref:` correctly. If no, remove entirely.
6. Add a prominent comment at the top of the workflow file documenting the security model: "Fork PR code runs with repo secrets. Environment approval is the ONLY gate. Maintainers: review head SHA's code before approving."

### Repo-level settings (manual, captain-only)

- **Environments → CI-E2E / CI-E2E-OPUS / CI-E2E-CODEX → Required reviewers:** confirm at least one human approver is listed. This is the actual security gate and must be non-empty.
- **Actions → General → Fork pull request workflows:** the default approval-for-first-time-contributors can be relaxed now that the env gate is the primary protection, but that's a captain call.

## Acceptance criteria

Each AC names its verification method.

**AC-1 — Trigger updated.** `grep -E '^on:' -A 5 .github/workflows/runtime-live-e2e.yml` shows `pull_request_target:` with the expected types. No bare `pull_request:` trigger for live-e2e.

**AC-2 — PR-head checkout on all 4 jobs.** Each `actions/checkout@v4` step has `ref: ${{ github.event.pull_request.head.sha }}` and `persist-credentials: false`. Verified by grep of the workflow file — count of `persist-credentials: false` equals count of `actions/checkout@v4` in the live-e2e workflow.

**AC-3 — Workflow permissions narrowed.** `permissions: { contents: read, pull-requests: read }` present at workflow scope. No job escalates.

**AC-4 — Maintainer-review comment present.** A top-of-file comment block explains the `pull_request_target` security model and names the env-approval gate as the sole protection. Test: grep for the key phrase ("env-approval gate" or equivalent).

**AC-5 — Static suite still green.** `make test-static` passes unchanged.

**AC-6 — End-to-end behavioral verification on a fork PR.** Push a trivial no-op commit to a fork-based PR (can use a throwaway fork, or re-use #118's branch if it's still open). Observe: the `pull_request_target` trigger queues the jobs, env deployments enter `waiting`, jobs stay held. Approve env deployments. Jobs run. Tests execute against the FORK's head SHA (verified by inspecting the checkout commit in the job log). Report the run id + evidence.

**AC-7 — Same-repo PR regression check.** Push a trivial no-op commit to a same-repo branch PR. Verify: same env-approval flow, tests execute against the same-repo branch head. No regression from current behavior.

## Out of scope

- Rewriting test_lib.py or test fixtures — fork code runs in same pytest invocation as before, just with head-checkout.
- Removing `static-offline` auto-trigger from `pull_request` — that's unrelated and safe (no secrets).
- Changing the approvers list on each environment — that's a repo-settings-UI task for captain.
- Migration plan for in-flight PRs — they'll re-trigger on next push.

## Merge strategy

Standard spacedock-ensign branch + PR + merge. This is an internal change, no external contributor attribution.

## Risk notes

- **Head SHA drift**: if a malicious contributor pushes a new commit between env approval and checkout, GitHub re-queues with `synchronize` and new env approval is required. Safe default.
- **Supply-chain concern**: `actions/checkout@v4` itself runs with base-branch context + secrets available in env before checkout runs. Mitigated by pinning to major version and trusting the Action. If further hardening is desired, pin to specific SHA.
- **Downgrade path**: if the new design misbehaves, revert is a single-file rollback. No data migration required.

## Test plan

- **Static:** `make test-static` — free, unchanged pass count.
- **Live-e2e behavioral (AC-6):** one fork-PR run (either Karen's #118 if still open, or a throwaway fork). ~$5-10 in API cost for one full live run across all 4 jobs, ~15 min wallclock.
- **Live-e2e same-repo regression (AC-7):** one same-repo branch run. Same cost/wallclock as AC-6.
- **Total budget:** ~$10-20, ~30 min wallclock.

## Cross-references

- **#118 (#187)** — external contribution from Karen Hsieh that surfaced the underlying problem. Its own merge strategy (merge-commit preserving authorship) is unchanged by this task.
- **#187** — the spacedock-workflow entity tracking PR #118 review; currently at ideation gate awaiting captain approval. This task (#189) can land independently.
- **#188** — streaming-watcher backlog follow-up (unrelated CI surface).

## Stage Report (implementation)

### Summary

Migrated `.github/workflows/runtime-live-e2e.yml` from `pull_request + workflow_dispatch -f pr_number` to `pull_request_target` with PR-head checkout and env-gate protection. The four live jobs (`claude-live`, `claude-live-bare`, `claude-live-opus`, `codex-live`) now actually validate PR code, including fork PRs — the env-approval gate is the load-bearing security control. Contract tests + `tests/README.md` updated to match the new shape. Static suite green at 438 passed (target ≥ 426).

### Checklist

1. **DONE** — Worked on branch `spacedock-ensign/fork-pr-live-e2e-pull-request-target` in worktree `/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-fork-pr-live-e2e-pull-request-target`. Never switched branches or left the worktree.
2. **DONE** — Read the entity body in full. Scope section translated directly into a workflow-file patch plus test-contract updates (the contract tests explicitly pinned the old shape and had to flip with it).
3. **DONE** — Read `.github/workflows/runtime-live-e2e.yml` end-to-end (4 jobs, shared provenance github-script, shared checkout + python + node + uv setup, per-job run/upload steps).
4. **DONE** — Applied the captain-specified changes:
   - (a) Replaced trigger block: `on: pull_request_target: { types: [opened, synchronize, reopened] }` + kept `workflow_dispatch` with the 4 operator-knob inputs (`claude_version`, `test_selector`, `effort_override`, `model_override`). Dropped `pr_number`.
   - (b) Added workflow-level `permissions: { contents: read, pull-requests: read }`.
   - (c) Each of the 4 jobs' `actions/checkout@v4` steps now sets `ref: ${{ github.event.pull_request.head.sha }}` and `persist-credentials: false`.
   - (d) `environment:` blocks preserved on all four jobs (CI-E2E x2, CI-E2E-OPUS, CI-E2E-CODEX) — the gate.
   - (e) Top-of-file security comment added, naming the env-approval gate as the sole protection and instructing maintainers to review the head SHA before approving.
5. **DONE** — Simplified provenance github-script: removed `TRIGGER_SOURCE` / `DISPATCH_PR_NUMBER` disambiguation, reads `context.payload.pull_request` directly (no REST `pulls.get` round-trip for the head-SHA lookup since the payload already carries it), gated with `if: github.event_name == 'pull_request_target'` so it skips harmlessly on manual dispatch runs. Kept the summary output (approvers via `listReviews`, PR number, base SHA, head SHA, branch source same-repo vs fork). Provenance field renames documented in the test comments: `Tested workflow SHA → Base SHA` (more accurate label for the workflow-definition commit now that head code is what's tested) and `Current PR head SHA → PR head SHA (checked out)` (makes explicit what the tests validate). These are cosmetic+semantic rename for accuracy, not behavioral changes.
6. **DONE** — Kept `workflow_dispatch` as a manual re-run path, dropped only the `pr_number` input. **Rationale:** the other 4 inputs (`claude_version`, `test_selector`, `effort_override`, `model_override`) are heavily wired into the job bodies and provide real operator value for bisection and targeted reruns (as documented in the README's "Bisection recipe" / "Mitigation recipe" sections). Dropping `workflow_dispatch` entirely would have orphaned those references or required a much larger diff to rip them all out. `pr_number` was the only input that existed purely to work around the head-SHA-checkout bug in the old design; the new `pull_request_target` design captures head SHA automatically from the event payload, so `pr_number` is obsolete.
7. **DONE** — AC-1 verified. `grep -E '^on:' -A 5` shows `pull_request_target:` with `types: [opened, synchronize, reopened]` followed by `workflow_dispatch:`. No bare `pull_request:` trigger for live-e2e.
8. **DONE** — AC-2 verified. 4 `actions/checkout@v4` occurrences, 4 `ref: ${{ github.event.pull_request.head.sha }}` occurrences, 4 `persist-credentials: false` on checkout steps + 1 in the top-of-file security comment = 5 total (ratio 1:1 between checkouts and head-SHA refs; security comment reference is intentional documentation, enforced as `checkout_count + 1` in the new `test_runtime_live_e2e_workflow_checks_out_pr_head_with_persist_credentials_false` test).
9. **DONE** — AC-3 verified. `permissions:\n  contents: read\n  pull-requests: read\n` present at workflow scope. No job escalates; grep'd for `permissions:` under each job and none exist.
10. **DONE** — AC-4 verified. Top-of-file comment block present containing "SECURITY MODEL", "env-approval gate", "ONLY protection", and "Maintainers: review the head SHA's code BEFORE approving". Enforced by the new `test_runtime_live_e2e_workflow_documents_security_model_at_top` test.
11. **DONE** — AC-5 verified. `unset CLAUDECODE && make test-static` → **438 passed, 22 deselected, 10 subtests passed** in ~20s. Comfortably above the ≥ 426 target. First pass after the workflow edit had 2 failures in the contract-assertion tests; those tests encoded the old workflow shape (asserting `pull_request:`, `pr_number:`, `Tested workflow SHA`, `Current PR head SHA`, `TRIGGER_SOURCE`, `DISPATCH_PR_NUMBER`, and README docstrings). Team-lead confirmed the dispatch's "no test changes" rule was overbroad — it was meant to prevent behavioral/harness changes, not block updates to contract assertions that directly encode the workflow file's shape. Contract-test updates ARE in-scope when the contract itself changes. Updated `tests/test_runtime_live_e2e_workflow.py` (assertions flipped to the new shape + 3 new assertions enforcing the security guarantees: PR-head checkout, `persist-credentials: false` on every checkout, top-of-file security comment, narrowed permissions) and `tests/README.md` (updated the "PR Runtime Live E2E" section to describe `pull_request_target`, the env-approval gate, and the renamed provenance fields; removed `-f pr_number=<N>` from the bisection/mitigation recipe examples since that input is gone).
12. **DONE** — Changes committed on `spacedock-ensign/fork-pr-live-e2e-pull-request-target` (see commit hash below).
13. **DONE** — This Stage Report written.
14. **SKIPPED (by design)** — AC-6 and AC-7 deferred to the validation stage per dispatch instruction. Those ACs require pushing the branch, opening a PR, maintainer env approval, and running live e2e against a real fork PR + a same-repo regression PR. Implementation stage cannot verify them without gate approval to spend live-budget money, and the dispatch explicitly SKIPs them here.

### Deviations from Scope

- **Scope step 2 "Keep the other existing inputs … decide per reference"**: Kept all 4 non-`pr_number` inputs (matched entity body's wording; they're still wired across all 4 jobs and used in the Run-suite steps).
- **Scope step 5 "Decide: preserve `workflow_dispatch` for manual re-runs"**: Recommended drop in the entity body, kept in practice because the 4 operator knobs have real value. Documented above.
- **Scope addition (approved by team-lead)**: Updated `tests/test_runtime_live_e2e_workflow.py` and `tests/README.md` contract assertions to match the new workflow shape. Dispatch's "no test changes" rule was scoped to behavior/harness changes; contract-test updates are in-scope for any workflow shape change. Added 3 new positive security assertions (`test_runtime_live_e2e_workflow_checks_out_pr_head_with_persist_credentials_false`, `test_runtime_live_e2e_workflow_narrows_default_permissions`, `test_runtime_live_e2e_workflow_documents_security_model_at_top`) to lock in the security-critical invariants so future edits can't silently weaken them.

### Provenance label rename map (old → new)

| Old label | New label | Rationale |
|-----------|-----------|-----------|
| `Tested workflow SHA` | `Base SHA` | Under `pull_request_target`, the workflow file itself always comes from the base branch. "Base SHA" is the accurate label for the workflow-definition commit. |
| `Current PR head SHA` | `PR head SHA (checked out)` | Makes explicit that this SHA is what `actions/checkout@v4` pulled and what the tests actually validate — disambiguates from the base SHA when reading the summary. |
| `Trigger source: {dispatch or pull_request}` | `Trigger source: pull_request_target` (hardcoded) | `pull_request_target` is the only auto-trigger now. Manual dispatch runs skip the provenance step entirely via `if: github.event_name == 'pull_request_target'`. |
