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

## Problem

When an ensign launches a long-running command via `Bash(run_in_background: true)`, the shell returns a `bash_id` and the command runs asynchronously. The correct way to wait on it is `BashOutput(bash_id=...)` polling: sleep briefly between polls, inspect the returned `status`, and proceed once `status == "completed"`.

The anti-pattern: issuing a single blocking `sleep N && tail -n … /tmp/log` sized to the worst-case duration. Two concrete costs:

1. **Wallclock waste.** Whenever the task finishes before the sleep budget, the agent stays idle for the remainder. On a 9-minute sleep budget with a 3-minute task, 6 minutes per cycle are wasted; across several iterations this dominates total run time and token cost (the agent stays resident in the conversation).
2. **Uninterruptibility.** A blocking sleep inside the agent process cannot be preempted by captain messages. Incoming SendMessages queue but are not observed until the sleep returns. Recovery requires killing the turn (Exit 137), which is coarse and throws away in-flight context.

`BashOutput` polling avoids both: the agent wakes at each poll interval, so captain messages land promptly, and the loop exits as soon as the task is actually done.

## Root cause of the anti-pattern

The ensign skill prose does not mention `BashOutput` or name the polling pattern. With no guidance, the model falls back to whatever priors it has; for some model versions that prior is `sleep N && tail`. This is a documentation gap in the skill, not a tool-shape problem — both `Bash(run_in_background: true)` and `BashOutput` already exist and work.

## Proposed approach

Add a **"Background Bash Discipline"** subsection to `skills/ensign/references/ensign-shared-core.md` (the shared-core file, so both Claude and Codex ensigns see it). Evaluate in implementation whether `skills/first-officer/references/first-officer-shared-core.md` needs the same subsection for first-officer-launched background commands; if yes, mirror the wording.

The subsection must be evergreen: no model-version names, no "observed in #NNN", no temporal phrasing. It describes the pattern as steady-state operational discipline.

### Before (current state)

`ensign-shared-core.md` has no guidance about `run_in_background: true` or `BashOutput`. The "## Working" section covers assignment reading, worktree ownership, and committing before signaling completion; it says nothing about waiting on asynchronous commands.

### After (proposed wording)

Insert a new subsection in `ensign-shared-core.md`, placed after the existing `## Rules` section and before `## Stage Report Protocol`:

```markdown
## Background Bash Discipline

When you launch a command with `Bash(run_in_background: true)`, wait on it with `BashOutput` polling, not a blocking `sleep`:

1. Capture the returned `bash_id`.
2. Sleep briefly between polls — roughly 30s is a reasonable default; longer for tasks expected to run many minutes, shorter for tasks expected in under a minute.
3. Call `BashOutput(bash_id=...)` and read the `status` field.
4. If `status == "completed"`, read the final output and proceed.
5. Otherwise, repeat from step 2. Cap total wait at the task's budgeted timeout; if the cap is reached, report the timeout rather than waiting indefinitely.

Do not wait on a background task with a single blocking `sleep N && tail …`. A blocking sleep sized for the worst case wastes wallclock whenever the task finishes early, and it prevents the agent from observing incoming messages until the sleep returns. Polling avoids both problems.
```

The wording does not reference any specific task, model, or incident. It states the rule, the shape, and the reason an agent reading the skill cold would need.

## Acceptance criteria

Each criterion below names its verification method.

**AC-1 — Subsection present and well-formed.**
Test method: grep `ensign-shared-core.md` for the literal heading `## Background Bash Discipline`; confirm it exists exactly once, and the body contains both the `BashOutput` polling rule and the explicit anti-pattern statement ("Do not wait on a background task with a single blocking `sleep`…"). Static check only.

**AC-2 — Wording is evergreen.**
Test method: grep the new subsection for forbidden tokens: `opus-`, `sonnet-`, `haiku-`, `#182`, `#183`, `(see #`, `observed`, `recently`, `new`, `legacy`, `improved`. Each must return zero hits inside the subsection. Static check.

**AC-3 — Static suite stays green.**
Test method: run the existing repo-level lint/test suite (`make test` or whatever the project currently defines as the default pre-commit check). Confirm no regressions introduced by the prose addition.

**AC-4 — Live behavioral verification on a background-bash consumer.**
Test method: pick one ensign dispatch that exercises `Bash(run_in_background: true)` with a task lasting several minutes (a local `tests/test_feedback_keepalive.py` invocation is one candidate). Run once with the new shared-core prose loaded. From the parent `fo-log.jsonl` or the session transcript, confirm the ensign called `BashOutput` at least once with a `bash_id` returned from a background `Bash`, and did **not** call `Bash` with a `sleep` command whose argument exceeds 60 seconds. Wallclock should be close to actual task duration + one poll interval, not the worst-case budget. One run is sufficient for ideation-stage validation; a larger sample can be gathered later if needed.

**AC-5 — First-officer runtime evaluation documented.**
Test method: implementation stage must include a short explicit decision in the stage report: either "FO shared-core also updated with the same subsection, rationale X" or "FO shared-core left unchanged, rationale X". Either outcome is acceptable; the requirement is that the decision is explicit, not absent.

## Out of scope

- Changing the `Bash` or `BashOutput` tools themselves. This is a skill-prose task.
- Sweeping the codebase for every blocking `sleep`. Many one-off shell scripts genuinely need a fixed wait and are fine as-is. This task only targets agent orchestration prose.
- Investigating why particular model versions default to the wrong pattern. Possible model-preference drift; can inform a follow-up if it becomes load-bearing.
- Adding an automated lint that forbids `sleep N && tail` in agent output. Prose first; mechanical enforcement is a separable follow-up.

## Test plan

- **Static checks (AC-1, AC-2, AC-3):** grep-based and existing suite. Cheap, deterministic; run as part of the implementer's pre-commit. Cost: seconds.
- **Behavioral check (AC-4):** one local ensign dispatch against a background-bash test, inspecting the session transcript for the call pattern. Cost: a single pytest invocation plus a few minutes of transcript review, roughly 5–10 minutes and well under $1 in live-agent budget.
- **Evaluation note (AC-5):** text-only, no test infrastructure.
- **No CI dispatch required.** The change is prose only; its effect is observable with a single local run.
- **Total estimated cost:** ~15 minutes implementer wallclock, under $1 live-agent budget.

## Cross-references (audit trail — not for inclusion in skill prose)

- **#182** — the diagnostic-workflow entity whose implementer iteration surfaced this anti-pattern. #182 itself is being rejected for scope drift (it added a "Completion Signal Discipline" Variant A prose block to `claude-first-officer-runtime.md` that exceeded #182's scope); that Variant A has been removed and #183 does not depend on it.
- **Earlier AC-4 dependency removed:** a prior draft of this entity required "no regression on #182's Variant A discipline." That clause is obsolete — Variant A no longer exists in the runtime file — and has been dropped. The current AC-4 is scoped to the new subsection alone.

## Stage Report: ideation

- DONE: Read the current #183 entity body in full.
  Confirmed existing body, pre-rewrite, in `docs/plans/ensign-bash-poll-not-sleep.md`.
- DONE: Note the scope change (#182 rejected, Variant A removed) and re-scope AC-4.
  Grep of `skills/first-officer/references/claude-first-officer-runtime.md` for "Completion Signal Discipline|Variant A" returned zero matches; AC-4 rewritten to verify polling call pattern only, and a standalone audit note records the removed dependency.
- DONE: Refine problem statement in evergreen operational terms.
  Rewrote "Problem" and "Root cause" sections; no model-version, no "observed in #NNN", no temporal phrasing in sections that become skill prose.
- DONE: Propose targeted approach with exact before/after shape.
  "Proposed approach" names the target file (`skills/ensign/references/ensign-shared-core.md`), insertion point (after `## Rules`, before `## Stage Report Protocol`), and provides the full fenced-markdown body for the new `## Background Bash Discipline` subsection.
- DONE: Rewrite acceptance criteria with explicit test methods per criterion; keep list short.
  Five criteria (AC-1..AC-5), each with a named test method; static grep checks for shape and evergreen tone, one live behavioral check, one FO-runtime evaluation note.
- DONE: Write test plan (static + behavioral + cost estimate; live-CI judgement).
  Test plan lists static, behavioral, and evaluation costs; total ~15 min wallclock and <$1 agent budget; no CI dispatch needed.
- DONE: Preserve #182 cross-reference for audit; keep proposed skill prose evergreen.
  Cross-references moved to a tail section explicitly labeled "audit trail — not for inclusion in skill prose"; the proposed `## Background Bash Discipline` body contains no model-version names, no `(see #NNN)`, no temporal phrasing. AC-2 enforces this with a grep check.
- DONE: Commit the updated entity body on main.
  See commit SHA below (appended by the commit step).
- DONE: Append this Stage Report section.
  This section.

### Summary

Rewrote #183 for ideation stage: sharpened the problem statement, specified the target file (`ensign-shared-core.md`) and exact insertion point for the new `## Background Bash Discipline` subsection, supplied the full fenced-markdown body, and re-scoped AC-4 so it no longer depends on #182's removed Variant A prose. Acceptance criteria now include an evergreen-tone grep (AC-2) to enforce global-CLAUDE.md discipline, and the `#182` audit trail is isolated from content that would ship into the skill. Test plan is static + one live behavioral run; no CI dispatch.
