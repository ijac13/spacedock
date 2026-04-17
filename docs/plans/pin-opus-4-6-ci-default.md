---
id: 181
title: "Pin --model claude-opus-4-6 in CI workflow defaults (until upstream opus-4-7 regression resolves)"
status: validation
source: "from #177 + #178 cluster — opus-4-7 regression at low/medium effort makes claude-live-opus CI job unreliable. #178's boilerplate mitigation falsified by #177. This is the temporary unblocker for #172 PR #107 and any other PR whose CI runs hit opus-4-7 default. Reversible — pinning is a workflow-default change, not a code change; explicit model_override still works."
started: 2026-04-17T03:56:01Z
completed:
verdict:
score: 0.6
worktree: .worktrees/spacedock-ensign-pin-opus-4-6-ci-default
issue:
pr:
mod-block: merge:pr-merge
---

## Why this matters

172's PR #107 has 4/5 jobs green; the 5th (claude-live-opus) fails on opus-4-7 (the regression #177 is investigating). #177's #178-boilerplate mitigation was falsified at low/medium effort. The cleanest unblocker for 172 — and any other PR sitting in the same cluster — is to pin `claude-live-opus`'s effective model to `claude-opus-4-6` until upstream resolves the opus-4-7 hallucination.

This is reversible: it's a workflow-default change, not a code or test change. Explicit `model_override` workflow input still works for anyone who wants to test opus-4-7 directly.

## The change

Edit `.github/workflows/runtime-live-e2e.yml`:
- Locate the `claude-live-opus` job's model resolution (the input default or the env var that resolves to `--model opus`).
- Change the default from `opus` (which now resolves to `claude-opus-4-7` under Claude Code 2.1.111+) to `claude-opus-4-6` explicitly.
- Preserve `model_override` workflow input handling so future testers can override back to `opus` or any other value.

The `model_override` plumbing into `claude -p` already works end-to-end (verified by #179's fix; confirmed by #180's audit).

## Acceptance criteria

1. **Workflow YAML edit is surgical.** Only the `claude-live-opus` job's default model resolution changes. Other jobs (`claude-live`, `claude-live-bare`, `codex-live`, `static-offline`) untouched.
2. **Static suite passes.** `make test-static` from the worktree root, ≥ 422 passed (current main baseline).
3. **The pin is documented in the workflow file.** Inline comment explains why pinning, links to #177 + this entity.
4. **Verification: dispatch one CI run on the worktree branch with no model_override input.** The `claude-live-opus` job should now run on `claude-opus-4-6` (verify via `gh run download` + grep `assistant.message.model` from the run's `fo-log.jsonl`).

## Test plan

- Static: `make test-static` from worktree root.
- Live: one CI dispatch on the worktree branch via `gh workflow run runtime-live-e2e.yml --ref spacedock-ensign/pin-opus-4-6-ci-default -f claude_version=2.1.111` (no model_override). Capture run URL, claude-live-opus job conclusion, and model stamps from fo-log.jsonl.
- Total cost: ~5 min CI minutes (one focused dispatch).

## Out of Scope

- Any change to the `--model` default in test files (test_standing_teammate_spawn.py and friends) — those already correctly read pytest's `--model` option per #179.
- Pinning `claude-live` or any non-opus job (only opus is broken).
- Reverting the pin once upstream fixes opus-4-7 — that's a future task triggered by upstream signal.
- Long-term decision on whether opus-4-6 should be the *permanent* default — this is a temporary pin pending upstream.

## Cross-references

- #177 — root cause investigation (now repurposed to Layer 2 mitigation experiments)
- #178 — falsified low/medium-effort boilerplate mitigation (likely won't ship in current form)
- #172 — direct beneficiary; PR #107 will reach 5/5 green CI once this lands and 172 rebases
- #179 — landed the model_override plumbing that makes this pin work end-to-end
- #180 — closed REJECTED-duplicate (audit confirming #179 covers all live tests)
