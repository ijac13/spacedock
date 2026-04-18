---
id: 189
title: "Replace workflow_dispatch + pr_number pattern with pull_request_target + env-gate for fork PR live-e2e"
status: ideation
source: "captain design directive during #118 merge triage — the current workflow_dispatch + pr_number design records provenance metadata but tests main, not the PR head. pull_request_target with env-gated PR-head checkout is the cleaner pattern and makes the CI signal actually mean 'PR code works'."
started: 2026-04-18T03:15:00Z
completed:
verdict:
score: 0.7
worktree:
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
