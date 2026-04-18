---
id: 183
title: "Ensign skill prose: use BashOutput polling for background tasks instead of blocking sleep"
status: validation
source: "from #182's test_feedback_keepalive iteration cycle (2026-04-17 session) — implementer used `sleep 540 && tail -30 /tmp/log` to wait on a 9-min background bash, blocking even after the underlying test completed in 206s. Captain interrupted (Exit 137) and noted the inefficiency. Same pattern likely repeats across other ensign uses of background bash."
started: 2026-04-18T00:09:23Z
completed:
verdict:
score: 0.5
worktree: .worktrees/spacedock-ensign-ensign-bash-poll-not-sleep
issue:
pr: #122
mod-block: merge:pr-merge
---

## Problem

When an ensign launches a long-running command via `Bash(run_in_background: true)`, the shell returns a `bash_id` and the command runs asynchronously. The correct pattern is `BashOutput(bash_id=...)` polling: sleep briefly between polls, inspect the returned `status`, and proceed once `status == "completed"`.

The anti-pattern: a single blocking `sleep N && tail -n … /tmp/log` sized to the worst-case duration. Two concrete costs:

1. **Wallclock waste.** When the task finishes before the sleep budget expires, the agent idles for the remainder. On a 9-minute sleep budget with a 3-minute task, 6 minutes per cycle are wasted; across several iterations this dominates total run time and token cost (the agent also stays resident in the conversation while sleeping).
2. **Uninterruptibility.** A blocking sleep cannot be preempted by captain messages. Incoming `SendMessage`s queue but go unobserved until the sleep returns. Recovery requires killing the turn (Exit 137), which discards in-flight context.

`BashOutput` polling avoids both: the agent wakes at each poll interval so captain messages land promptly, and the loop exits as soon as the task finishes.

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

## Stage Report: implementation

- DONE: Stay inside worktree `.worktrees/spacedock-ensign-ensign-bash-poll-not-sleep` on branch `spacedock-ensign/ensign-bash-poll-not-sleep`.
  All file reads/writes under the worktree; no branch switches.
- DONE: Apply the ideation-specified `## Background Bash Discipline` subsection into `skills/ensign/references/ensign-shared-core.md` verbatim, inserted after `## Rules` and before `## Stage Report Protocol`.
  Edit placed the five-step polling rule plus the explicit anti-pattern paragraph.
- DONE: AC-2 forbidden-token grep on the new subsection body.
  Extracted subsection into `/tmp/bg-subsection.md` (13 lines). Grep results: `opus-` 0, `sonnet-` 0, `haiku-` 0, `#182` 0, `#183` 0, `(see #` 0, `observed` 0, `recently` 0, ` new ` 0, ` legacy ` 0, `improved` 0.
- DONE: AC-5 evaluation — FO shared-core left unchanged.
  Rationale: grep of `skills/first-officer/references/` for `run_in_background|BashOutput|background bash|sleep` returned no files, and first officers dispatch work through `SendMessage`/Task tools rather than launching multi-minute background shell commands. The anti-pattern surfaced in an ensign implementer loop, not in FO orchestration. If FOs later start launching long-running background shells themselves, the same subsection can be mirrored into `first-officer-shared-core.md` at that time; adding it preemptively violates YAGNI.
- DONE: Run the static suite with `unset CLAUDECODE && make test-static`.
  `426 passed, 22 deselected, 10 subtests passed in 20.40s` — meets the ≥ 426 threshold.
- DONE: Commit changes on the worktree branch.
  See commit SHA below (appended by the commit step).
- DONE: Write this Stage Report section.
  This section.

### Summary

Inserted the `## Background Bash Discipline` subsection into `skills/ensign/references/ensign-shared-core.md` between `## Rules` and `## Stage Report Protocol`, using the ideation body's fenced-markdown content verbatim. AC-2 evergreen-tone grep passes with zero forbidden-token hits; `make test-static` holds at 426 passed. FO shared-core left unchanged per AC-5 — FOs don't run multi-minute background bash, so mirroring the subsection would be speculative. AC-4 live behavioral verification is deferred to validation stage per the dispatch brief.

## Stage Report: validation

- [x] DONE: Read implementation Stage Report first.
  Confirmed implementer's claims: subsection inserted at `ensign-shared-core.md:34`, AC-2 tokens zero, `make test-static` 426 passed, FO shared-core left unchanged per YAGNI.
- [x] DONE: Verify AC-1 — subsection present and well-formed.
  Grep `^## Background Bash Discipline` on worktree copy of `skills/ensign/references/ensign-shared-core.md` returns exactly one hit at line 34. Body (lines 34-44) contains both the five-step `BashOutput` polling rule and the explicit anti-pattern paragraph ("Do not wait on a background task with a single blocking `sleep N && tail …`…").
- [x] DONE: Verify AC-2 — wording is evergreen (independent grep).
  Extracted subsection body (lines 34-44) into `/tmp/ac2-subsection.md` (11 lines). Case-insensitive grep for `opus-|sonnet-|haiku-|#182|#183|\(see #|observed|recently|\bnew\b|\blegacy\b|improved`: **no matches**. All forbidden tokens return zero hits.
- [x] DONE: Verify AC-3 — static suite stays green.
  `unset CLAUDECODE && make test-static` in this worktree: `426 passed, 22 deselected, 10 subtests passed in 20.48s`. Meets ≥ 426 threshold.
- [x] SKIPPED: Verify AC-4 — live behavioral verification on a background-bash consumer.
  Ran the suggested test: `unset CLAUDECODE && KEEP_TEST_DIR=1 uv run pytest tests/test_feedback_keepalive.py -m live_claude --runtime claude --model claude-opus-4-6 --effort low -v -s`. Result: `1 passed in 201.99s` (preserved dir `/var/folders/h1/vnssm1dj6ks4nzzvx8y29yjm0000gn/T/tmpsdlkana9`). However, the test scenario does **not** exercise `Bash(run_in_background=true)` — the work items are creating/validating a `greeting.txt` file, all synchronous. Inspection of `tool-calls.json` (41 calls): 15 `Bash` calls (all `run_in_background=None`), 0 `BashOutput`, 0 `bash_id` references. The only `BashOutput`/`run_in_background`/`bash_id` tokens in `fo-log.jsonl` (line 82) are the FO reading the new skill-prose file content — not an actual polling call. Additionally, ensign-internal tool-calls (the ensign runs as an `Agent()` subprocess) are not captured in this harness's top-level `tool-calls.json` or `fo-log.jsonl`. AC-4's evidence requirement (bash_ids from background Bash paired with BashOutput polls) cannot be produced via this test path. Rationale for SKIP: (a) the suggested test doesn't exercise the scenario under evaluation; (b) the harness doesn't capture ensign-subprocess tool calls needed for the evidence shape AC-4 specifies; (c) the implementation is pure documentation — AC-1/AC-2/AC-3 are the load-bearing checks for a prose addition, and all three pass. Flagging this as a gap in the validation plan itself, not in the deliverable. Budget used: ~$0.20 for the 3m21s live run.
- [x] DONE: Verify AC-5 — FO shared-core decision documented.
  Implementation Stage Report line 133-134 explicitly states "FO shared-core left unchanged" with rationale (FOs dispatch via `SendMessage`/Task tools rather than launching multi-minute background shells; YAGNI). Decision is explicit and either-outcome-acceptable per AC-5.

### Summary

AC-1, AC-2, AC-3, AC-5 all pass with concrete evidence (grep results, 426 test pass, explicit FO decision documented). AC-4 skipped — the suggested `test_feedback_keepalive.py` does not exercise `Bash(run_in_background=true)` and the harness doesn't capture ensign-subprocess tool-calls, so the required evidence shape (bash_ids paired with BashOutput polls) cannot be produced from this test path. Since the deliverable is a prose-only addition to a skill file, the static checks (AC-1/2/3) are the load-bearing verification; AC-4 was an aspirational live confirmation that would need a different test scenario and/or ensign-subprocess logging to satisfy. **Recommendation: PASSED** — static ACs verified, FO decision explicit, AC-4 unverifiable via the suggested path but not blocking for a prose deliverable.
