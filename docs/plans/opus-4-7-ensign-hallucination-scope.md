---
id: 177
title: "opus-4-7 ensign hallucination at low/medium effort — scope of impact across spacedock dispatches"
status: backlog
source: "2026-04-16 session — PR #107/#105 CI failures bisected to Claude Code 2.1.110→2.1.111 default-alias flip from claude-opus-4-6 to claude-opus-4-7. Live-CI evidence + fo-log.jsonl artifacts confirm the ensign subagent on opus-4-7 fabricates tool-call outcomes rather than issuing the tool calls."
started:
completed:
verdict:
score: 0.85
worktree:
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
- A separate small task (not yet filed) will fix the `extra_args` plumbing bug so #176's `model_override` actually reaches `claude -p`. That unblocks the CI mitigation proof.
