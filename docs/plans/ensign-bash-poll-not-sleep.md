---
id: 183
title: "Ensign skill prose: use BashOutput polling for background tasks instead of blocking sleep"
status: ideation
source: "from #182's test_feedback_keepalive iteration cycle (2026-04-17 session) — implementer used `sleep 540 && tail -30 /tmp/log` to wait on a 9-min background bash, blocking even after the underlying test completed in 206s. Captain interrupted (Exit 137) and noted the inefficiency. Same pattern likely repeats across other ensign uses of background bash."
started: 2026-04-18T00:09:23Z
completed:
verdict:
score: 0.5
worktree:
issue:
pr:
mod-block:
---

## Why this matters

When an ensign launches a long-running command via `Bash(run_in_background: true)`, it gets a task ID and the command runs asynchronously. The correct pattern to wait on it is `BashOutput(bash_id=...)` polling — small sleep, check status, repeat until `status == "completed"`, then read the result.

The observed (anti-)pattern: agents use `sleep 540 && tail -30 /tmp/log` — a single blocking sleep for the worst-case duration, followed by reading the log. This wastes time whenever the underlying task completes faster than the sleep budget. In #182's case, opus-4-7 implementer did this for 5+ test runs at 9-min sleeps each; multiple tests completed in 2-3 min, leaving the agent idle for 6-7 min of unnecessary wallclock per run. Across 6 runs the waste accumulates to roughly 30+ minutes plus the API token cost of staying resident.

Beyond efficiency, blocking sleeps are uninterruptible — captain SendMessages queue but cannot wake the agent until the sleep returns. In #182 the captain killed an in-flight sleep with Exit 137 to recover control. With BashOutput polling, captain messages are seen between polls.

## The bug

The ensign skill (`agents/ensign.md`) and first-officer skill prose (`skills/first-officer/`) do not document the BashOutput polling pattern for background tasks. Agents fall back to whichever pattern the model has stronger priors for — currently `sleep N && tail` for many opus-4-7 instances.

## Proposed fix

Add a "Background Bash Discipline" subsection to the ensign skill (and possibly to the first-officer runtime adapters for FO use) that:

1. **States the rule explicitly:** "When you launch `Bash(run_in_background: true)`, wait on it using `BashOutput(bash_id=...)` polling, NOT a blocking `sleep N`."
2. **Specifies the polling shape:** "Sleep ~30s between polls. Read `BashOutput`'s `status` field. When `status == 'completed'`, read the final output and proceed. Cap total wait at the originally-budgeted timeout."
3. **Explains why:** "Blocking sleeps waste time when the task completes early, and they make the agent uninterruptible by captain messages."
4. **Cites the failure pattern:** cross-reference #182 / #183 for the observed waste.

## Acceptance criteria

1. **Prose addition is surgical** to the ensign skill (and optionally first-officer runtime adapter), defining the BashOutput polling pattern with explicit anti-pattern note.
2. **Static suite stays green** (no test regression from the prose addition).
3. **Local verification on a target test that uses background bash** — pick any one of #182's test runs (e.g., `test_feedback_keepalive` on opus-4-7), instrument the implementer's behavior, confirm the agent uses BashOutput polling instead of `sleep N && tail`. Verify wallclock per run is reduced from the sleep-budget worst case to actual-test-duration + small polling overhead.
4. **No regression on the discipline already shipped in #182's Variant A** — the Ensign Completion Signal Discipline subsection added there must remain intact and effective.

## Out of Scope

- Changing the BashOutput tool itself (this is a skill-prose-discipline task, not a tool change).
- Replacing all blocking sleeps everywhere in the codebase (only the agent-orchestration patterns matter; one-off shell scripts that genuinely need a fixed wait are fine).
- Investigating why opus-4-7 specifically defaults to the wrong pattern (possible model-preference drift; out of scope here, can inform a follow-up).

## Cross-references

- #182 — the cycle where this pattern was observed (test_feedback_keepalive iteration, R1-R6, sleep-540-then-tail anti-pattern, captain interrupt on R7)
- The Ensign Completion Signal Discipline subsection added to `claude-first-officer-runtime.md` in #182's Variant A — same skill file is the candidate location for the new subsection

## Test plan

- Static: confirm the prose additions parse cleanly (no markdown errors, no broken cross-references).
- Behavioral: re-run a `test_feedback_keepalive` cycle on opus-4-7 with the new prose loaded; verify ensign uses BashOutput polling. Compare wallclock vs the pre-prose sleep-540 pattern.
- Cost: ~5 min of local pytest + a few minutes of prose drafting. No CI dispatch needed.
