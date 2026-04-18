---
id: 186
title: "Green the full live test suite on opus-4-7 locally"
status: ideation
source: "captain directive (2026-04-17 session) — after #181 pinned CI to opus-4-6 as a workaround, the fleet is running green on opus-4-6 but opus-4-7 remains a known-flaky target. Goal: enumerate and fix all opus-4-7-specific failures so the pin can eventually be lifted."
started: 2026-04-18T00:12:20Z
completed:
verdict:
score: 0.7
worktree:
issue:
pr:
mod-block:
---

## Why this matters

CI is pinned to opus-4-6 (via #181) while opus-4-7 regressions exist. The pin is reversible and is a workaround, not a fix. To eventually lift it, every live test must be reliably green on opus-4-7 locally and in CI.

#182 investigated one specific failure (the `test_standing_teammate_spawn` test-predicate bug) and uncovered that some tests assert on FO narration prose, which opus-4-7 produces differently than opus-4-6. The narration-predicate class is being addressed in the sibling cherry-pick task (#185). Other failure classes likely exist — e.g., the "FO-impatience" flake flagged in #182's AC-4 that was deferred ("~50% residual flake" per the debrief).

## Scope

### Ideation

- Inspect the latest #182 CI run artifacts (gh run view, gh run download) to enumerate every opus-4-7 failure mode currently known. Include #182's Diagnosis Outcome section as primary input — AC-4 names specific failure modes.
- Categorize failure modes: test-construct bugs (like the narration-predicate class), ensign-side behavior (like BashOutput blocking-sleep, covered by #183), FO-side behavior (like premature teammate teardown, still needs a real fix — NOT the prose mitigation from #182), or infra/flake.
- Propose a prioritized fix list with explicit acceptance criteria per category.

### Implementation

**Blocked on #183** — #183 lands the BashOutput polling discipline that makes ensigns usable for efficient local test runs. Starting implementation before #183 lands would force this task to burn wallclock on blocking-sleep waits.

Once #183 lands: run focused local test runs on each targeted fix, verifying each category passes on opus-4-7 at `--effort low`.

### Validation

Run the full live suite on opus-4-7 locally (`make test-live-claude-opus OPUS_MODEL=opus`, serial + parallel tiers). Pass rate must be high enough to consider unpinning CI (acceptance criterion to be refined in ideation — likely "2 clean consecutive runs" or "N/N passes across M runs").

## Out of scope

- Changing the CI pin — that lives with #181's reversibility. Unpinning is a separate (future) task.
- Codex-side tests — this task targets `live_claude` tier only.
- Infrastructure changes outside test code and the skill-prose surfaces already flagged in siblings (#183, #184, #185).

## Cross-references

- #181 — CI pin to opus-4-6 (the workaround this task eventually unblocks the removal of)
- #182 — prior diagnosis; rejected for scope drift; its diagnostic content (AC-1 through AC-5) is still useful input for ideation
- #183 — BashOutput polling discipline (blocks implementation)
- #184 — claude-team narrowing cherry-pick (unrelated surface; can land anytime)
- #185 — test-predicate cherry-pick + audit (addresses one known failure class; this task covers the rest)
