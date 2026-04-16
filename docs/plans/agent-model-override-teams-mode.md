---
id: 171
title: "Agent(model=...) in teams mode does not propagate to subagent runtime model"
status: backlog
source: "CI failure on PR #105 (tighten-hedging) — test_per_stage_model_haiku_propagates. Verified against PR #100 artifacts: same bug, different severity."
started:
completed:
verdict:
score: 0.7
worktree:
issue:
pr:
---

## Problem Statement

`Agent(model="haiku")` in teams mode does not reliably set the subagent's runtime model. The subagent inherits the captain's model instead. This was observed in CI on two separate PRs:

- **PR #100** (2026-04-15, `claude-opus-4-6`): `Agent(model=haiku)` emitted. Runtime: 27 opus messages, 3 haiku messages (10% propagation). Test passed only because the assertion checks for *any* haiku messages, not *all*.
- **PR #105** (2026-04-16, `claude-opus-4-7`): identical `Agent(model=haiku)` call. Runtime: 34 opus messages, 0 haiku messages (0% propagation). Test failed.

The `claude-team build` helper correctly resolves `stages.defaults.model: haiku` and emits `"model": "haiku"` in its output. The FO correctly passes `model=haiku` to the `Agent()` tool call. The bug is downstream in Claude Code's teams-mode agent spawning — the `model` parameter is silently ignored or overridden.

In bare mode (no `team_name`), `Agent(model="haiku")` works correctly — `claude-live-bare` passed on both PRs.

## Evidence

- PR #105 CI artifacts: `/tmp/ci-logs-105/spacedock-test-ctpikw13/fo-log.jsonl` — all 34 assistant turns are `claude-opus-4-7`. The `Agent()` tool_use entry shows `model=haiku` in the input.
- PR #100 CI artifacts: `/tmp/ci-logs-100/spacedock-test-_zwiz4fc/fo-log.jsonl` — 27 `claude-opus-4-6` + 3 `claude-haiku-4-5-20251001`. Same `Agent(model=haiku)` in the tool_use.
- Local verification: `claude-team build` against the `per-stage-model` fixture emits `"model": "haiku"` on stdout.

## Correlation with model cutover

Failure severity increased when the default opus pointer rotated from `claude-opus-4-6` to `claude-opus-4-7` between 2026-04-15 and 2026-04-16 (Claude Code 2.1.110 → 2.1.111 default-alias flip, verified by the 2026-04-16 session bisection). The bug existed under `4-6` (10% propagation) but was masked by the weak assertion; under `4-7` propagation dropped to 0%. The cutover amplified the bug rather than introducing it.

## Distinction from the standing-teammate opus-4-7 regression

The 2.1.110 → 2.1.111 default-alias flip also affects `test_standing_teammate_spawns_and_roundtrips`, but through a different mechanism. That test fails because `claude-opus-4-7` at low effort hallucinates checklist completion (per the Opus 4.7 migration guide's stricter-effort calibration), not because `Agent(model=...)` propagation breaks. Its mitigation — pin `--model claude-opus-4-6` via the `model_override` workflow input (#176) or bump effort — is orthogonal to #171's Agent-propagation bug. Resolving one does not resolve the other.

## Current mitigation

`test_per_stage_model_haiku_propagates` is xfailed with `strict=False` so CI is not blocked. The xfail reason cites this task (#171).

## Open questions for ideation

- Is this a known Claude Code issue? Should we file upstream (similar to `anthropics/claude-code#36806`)?
- Can we work around it by passing model as part of the agent prompt rather than the `Agent()` parameter?
- Should the test be restructured to verify the `Agent()` call shape (spacedock's responsibility) rather than the runtime model (Claude Code's responsibility)?
- Does this affect standing-teammate spawning too? `spawn-standing` also passes `model=` to `Agent()` in teams mode.

## Out of Scope

- Fixing Claude Code's `Agent()` model propagation — that is a platform issue.
- Changing the `claude-team build` helper's model resolution — it already works correctly.
- Bare-mode model propagation — that path works.
