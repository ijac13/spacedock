---
id: 203
title: "Green main for opus-4-7 — close the loop on test suite flakes"
status: backlog
source: "captain directive 2026-04-18: after multiple sessions chasing flake after flake, focus on one thing — green main for opus-4-7. Reference CI run: https://github.com/clkao/spacedock/actions/runs/24619609861/job/71987768307"
started:
completed:
verdict:
score: 0.9
worktree:
issue:
pr:
mod-block:
---

Drive the opus-4-7 test suite to green on main. Previous sessions have chased flake after flake without converging; this task is the captain-designated campaign to finish the job.

## Captain directive (ideation agenda)

CL specified the ideation stage must address these four points:

1. **Gather ground truth.** Read https://github.com/clkao/spacedock/actions/runs/24619609861/job/71987768307 carefully. Run one locally. Compare the union of failures from the remote run against the local run.
2. **Senior audit of opus-touched tests.** Have a senior staff software engineer audit all tests touched by opus-4-7 work for anti-patterns, including but not limited to: tautological tests, matching LLM narration instead of actual behavior, mocks masquerading as coverage, tests that pass because the model happened to say the right words.
3. **Focus and iterate to green.** For tests that pass the audit (real desired behavior), iterate until green. Report back any test that does not test real desired behavior — do not silently fix symptoms or rewrite a test to match a flaky outcome.
4. **PR with gated env.** Once confident, open a PR and approve only the `claude-live-opus` environment for running the live tier.

## Related prior work

- #177 — opus-4-7 ensign hallucination scope (validation stage, PASSED)
- #194 — `test_standing_teammate_spawn` ECHO roundtrip flakiness on opus-4-7
- #202 — FO behavior spec + coverage matrix (meta-spec, gates further flake triage)

Acceptance criteria and a test plan will be defined during ideation per the workflow README.
