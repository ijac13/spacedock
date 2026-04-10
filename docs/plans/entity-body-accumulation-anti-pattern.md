---
id: 125
title: "Entity body accumulation anti-pattern — stage reports shouldn't append forever"
status: ideation
source: "FO diagnosis after both 116 cycle-2 and cycle-3 impl ensigns died from context overflow driven by entity-body reads"
score: 0.85
worktree:
started: 2026-04-10T21:25:50Z
completed:
verdict:
issue:
pr:
---

Stage reports currently accumulate in the entity body of the task file itself. Each implementation cycle, validation cycle, feedback rejection, and re-implementation appends more content — ideation reports, stage reports, feedback cycles sections, addenda, reviewer findings. After two or three cycles on a task of moderate complexity, the entity body can grow past 800 lines. Every subsequent ensign dispatched on that task has to read the entire accumulated history to understand its instructions, which blows up its context budget before it can reach the actual deliverable.

## Empirical evidence — task 116 killed two impl ensigns

During the 2026-04-10 session, task 116 `readme-and-architecture-refresh` killed two consecutive implementation ensigns by this exact mechanism:

**Cycle-2 impl ensign (kept alive across feedback):** started at ~80% context after cycle 1, died silently at 200k after writing stage report content into an ever-growing entity body. Left +43/-53 uncommitted lines of actual README changes in the worktree.

**Cycle-3 impl ensign (fresh dispatch with explicit 60% escalation warning):** peaked at **170,668 resident tokens (85.3% of 200k)** across 111 turns. Died mid-turn. Diagnostic tool-use counts from its jsonl:

| Tool target | Read count | Edit count |
|---|---|---|
| `docs/plans/readme-and-architecture-refresh.md` (entity body, 792 lines) | **25** | **9** |
| `README.md` (121 lines — the actual deliverable) | 1 | **0** |

The cycle-3 ensign read its own task body **25 times** and the README **once**. It edited the task body **9 times** and the README **zero times**. It spent all of its context on reading and editing its own instructions + accumulated history, never touching the deliverable before dying.

Notably, the cycle-3 ensign was actively trying to **prune** the entity body when it died — the uncommitted diff showed `+150/-262` lines, a net reduction. This is evidence that the right organic instinct (shrink the entity body) is already present in worker behavior; what's missing is architectural support for keeping it small from the start.

## Root cause

The entity body conflates two very different kinds of content:

1. **The spec** — stable, small: problem statement, acceptance criteria, design decisions, stage definitions, active directives from the current cycle.
2. **The execution log** — accumulating, large: ideation stage report, implementation stage reports (possibly multiple cycles), validation stage reports (possibly multiple cycles), feedback cycles section, addenda, independent reviewer findings.

Current design: both live in one markdown file. The entity body is the single source of truth for both "what to do" and "what has been done". This works for small single-cycle tasks. It catastrophically fails for tasks that go through multiple feedback cycles or substantial iteration, because every cycle adds 100–200 lines of execution log that the next cycle's ensign has to read just to find the active directives.

Secondary cause: the dispatch prompt template currently says "Read the entity file at {path} for full context". This pulls the entire 800-line blob into the ensign's context on turn 1 and again on every subsequent turn that needs to reference it.

## Design directions (ideation to choose)

Four possible fixes, in rough order of schema disruption:

### Option A — Separate stage-history file
Move completed stage reports to a companion file `{slug}-stage-history.md` alongside the entity file. The entity body retains only the spec + active current-cycle stage report. The history file is append-only and workers don't need to read it unless doing historical analysis. **Minimal schema change; rebase-safe.**

### Option B — Archive completed stage reports per cycle
When a cycle completes, move the current stage report out of the entity body into `_archive/stage-reports/{slug}-{stage}-cycle{N}.md`. The entity body gets pruned to just the spec + upcoming work. **More aggressive; requires a workflow step to perform the move at cycle boundary.**

### Option C — Stage reports never touch the entity body
Ensigns write their stage reports to standalone files from the start (`{workflow_dir}/stage-reports/{slug}-{stage}-cycle{N}.md`). The FO reads them at gate time. The entity body is permanently a short spec. **Largest schema change; cleanest separation.**

### Option D — Inline directives in dispatch prompt; entity body stays accumulating
Change FO behavior only: dispatch prompts contain the full directive list inline. Ensigns are told NOT to read the entity body; they get everything from the prompt. Stage reports still accumulate but ensigns only read+write at the very end once. **Fewest schema changes; most dispatch-template changes. Catches the symptom without fixing the underlying storage.**

Ideation should evaluate how each option interacts with refit, commission, the status tool, and the PR body template (task 118's extraction rules source the motivation lead from "entity body paragraph(s) between closing `---` and the first `##` heading" — that source will change depending on which option lands).

## Scope

- Architectural ideation choosing an option (or hybrid)
- Implementation of the chosen option
- Migration path for in-flight tasks with accumulated entity bodies (task 116 is the obvious test case)
- Update the dispatch template in `skills/first-officer/references/claude-first-officer-runtime.md` to reflect the new pattern
- Update the ensign shared core in `skills/ensign/references/ensign-shared-core.md` to reflect the new stage-report-write path
- Update `skills/commission/SKILL.md` if the workflow schema changes
- Update `skills/refit/SKILL.md` similarly
- Update workflow README templates
- Update the pr-merge mod's extraction rules (task 118) if the entity body source structure changes

## Out of scope

- Retroactively pruning all 106 archived entities' stage reports (one-time cleanup; separate task if wanted)
- Changes to frontmatter fields (tasks 122, 123 own that surface)
- The underlying context-aware-reuse rule (task 121 is orthogonal — 125 is about what the ensign reads, 121 is about when to fresh-dispatch)

## Acceptance Criteria (ideation to refine)

1. Stage reports from different cycles do not accumulate into a single ever-growing blob that every subsequent ensign must re-read. A separation mechanism is in place.
2. A fresh ensign dispatched on a mid-flight task's next cycle consumes **<10% of its context budget** from reading spec + current directives (measured: tokens consumed by Read tool calls on entity-associated files, divided by the model context window).
3. Task 116's own backlog is unblocked: either by prune-and-rescue on 116's existing 792-line entity body, or by accepting 116 shipped-as-is with partial cycle-3 recovery + a successor task for remaining work.
4. `tests/test_agent_content.py` has a static assertion that the FO dispatch template does NOT unconditionally instruct the ensign to "read the entity file body for full context".
5. Existing suites stay green: `test_agent_content.py`, `test_rejection_flow.py`, `test_merge_hook_guardrail.py`, `test_dispatch_completion_signal.py`.

## Test Plan

- Static assertion in `test_agent_content.py` for AC-4 (low cost, required).
- Unit tests for any new files/paths introduced by Option A/B/C (if chosen).
- E2E regression: modify `tests/test_rejection_flow.py` or add a new test that drives a task through 3+ feedback cycles and verifies the entity body does not grow unboundedly.
- **Ground-truth measurement**: dispatch a cycle-4 ensign on task 116 under the new pattern, record its peak resident tokens, verify <100k (ideally <60k). This is a session-live measurement, not a CI test.

## Related

- **Task 116** `readme-and-architecture-refresh` — the observed test case. Died twice from this anti-pattern. Cycle-4 dispatched via inline-directives workaround (Option D applied ad-hoc) concurrent with this task seed.
- **Task 121** `fo-context-aware-reuse` — complementary and orthogonal. 121 is about when to fresh-dispatch; 125 is about what the ensign reads when dispatched. Both matter for FO reliability.
- **Task 118** `pr-merge-mod-rich-body-template` — just landed. Its PR-body extraction rules depend on the current entity-body structure; 125's Option A/B/C may require 118's extraction rules to update in lockstep.
- **Issue #63** (local) — fuzzy prose template anti-pattern umbrella. 125 is a specific instance: the entity body is the prose spec for ensigns, and it has the same fragility as the dispatch template issue #63 calls out.
- **External FO feedback (2026-04-10)** — the experiment pipeline FO's "prose where there should be structure" meta-thesis. 125 is one of the structural fixes that thesis implies.
