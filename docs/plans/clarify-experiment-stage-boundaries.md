---
id: 065
title: Clarify implementation vs validation boundaries for experimental tasks
status: implementation
source: CL
started: 2026-03-28T00:25:00Z
completed:
verdict:
score:
worktree: .worktrees/ensign-065-stage-boundaries
---

Experimental tasks (like 058 terminology-experiment) blur the line between implementation and validation. The implementer builds infrastructure (harness, scripts, fixtures), but the experiment results are the actual deliverable. When the validator is told to "run the experiment," it ends up doing implementation work — producing the deliverable rather than verifying it.

In 058, the validator found and fixed harness bugs (token counting, team name collision, relative paths), then ran experiments and produced findings. This violated the independence principle that the validator agent type was designed to enforce (task 061).

## What needs clarifying

1. **README stage definitions** — implementation produces the deliverable (code, experiment results, analysis). Validation verifies the deliverable is sound. Current wording focuses on "write the code" which doesn't obviously cover "run the experiment and report results."

2. **FO validation dispatch** — the FO writes the validator's dispatch prompt. The dispatch should reinforce "verify the deliverable, don't produce it." The 058 dispatch explicitly said "RUN the experiment" which overrode the validator's built-in constraints.

## Scope

Changes to README stage definitions and/or FO template validation instructions. Possibly validator template if wording needs tightening. No infrastructure changes.

## Analysis

### Problem 1: README `implementation` stage definition is too narrow

Current wording (README.md lines 93-98):

> A task moves to implementation once its design is approved. The work here is to **write the code**, create the files, or make whatever changes the task describes.

The phrase "write the code, create the files" implies the deliverable is always source code or file artifacts. For experimental tasks, the deliverable includes the results of running the experiment — not just the infrastructure to run it. The implementer in 058 built the harness and templates but never ran the benchmark or produced findings. That left a gap the validator filled.

Similarly, for research tasks, the deliverable might be a document with analysis and conclusions. For test-suite tasks, the deliverable is working tests with passing results. The current wording doesn't clearly cover these cases.

### Problem 2: README `validation` stage definition doesn't draw the boundary explicitly

Current wording (README.md lines 100-111):

> The work here is to verify the implementation meets the acceptance criteria defined in ideation.

This is correct in principle but doesn't explicitly state: "The validator verifies existing deliverables; it does not produce them." The absence of this negative constraint means there's no guard against a dispatch prompt that tells the validator to produce the deliverable (which is what happened in 058).

### Problem 3: FO validation dispatch instructions conflate "run tests" with "produce results"

Current FO validation instructions (first-officer.md line 44):

> You are a validator. You read and judge — you do NOT write code or fix bugs. Determine what work was done in the previous stage. For code changes, check the README for a Testing Resources section — run applicable tests and include results (test failure means recommend REJECTED). For analysis or research, verify correctness and completeness against acceptance criteria. Adapt validation to what was actually produced. If you find issues, describe them precisely in your stage report with a REJECTED recommendation. If an implementer messages you with fixes, re-run tests and update your stage report, then send your updated completion message to the first officer.

This has two issues:
1. It says "run applicable tests" which is fine — running existing tests to verify is validation work. But it doesn't distinguish this from "run the experiment to produce results," which is implementation work.
2. The sentence "For analysis or research, verify correctness and completeness against acceptance criteria" is the right idea but it's too brief. It doesn't say "the analysis or research should already exist as a deliverable from implementation."

### Problem 4: Validator template is fine as-is

The validator template (validator.md) already says:

> You verify that implementation work meets acceptance criteria. You NEVER modify implementation code — you read, test, judge, and may write test cases.

And:

> Do NOT modify implementation code. If you find bugs, describe them precisely so an implementer can fix them.

This is sufficient. The validator template correctly frames validation as verifying existing work. The problem in 058 was not the validator template — it was the FO's dispatch prompt that explicitly told the validator to "RUN the experiment," which overrode the template's framing. The fix belongs in the FO's validation instructions (which the FO inserts into every validator dispatch prompt) and in the README stage definitions (which the FO copies verbatim into dispatch prompts).

## Proposed Changes

### Change 1: README `implementation` stage — broaden "deliverable" language

Current:
```
### `implementation`

A task moves to implementation once its design is approved. The work here is to write the code, create the files, or make whatever changes the task describes.

- **Inputs:** The fleshed-out task body from ideation with approach and acceptance criteria
- **Outputs:** Working code or artifacts committed to the repo, with a summary of what was built and where
- **Good:** Minimal changes that satisfy acceptance criteria, clean code, tests where appropriate
- **Bad:** Over-engineering, unrelated refactoring, skipping tests, ignoring edge cases identified in ideation
```

Proposed:
```
### `implementation`

A task moves to implementation once its design is approved. The work here is to produce the deliverable: write code, run experiments, generate analysis, or make whatever changes the task describes. Implementation is complete when the deliverable exists and is ready for independent verification.

- **Inputs:** The fleshed-out task body from ideation with approach and acceptance criteria
- **Outputs:** The deliverable committed to the repo (code, experiment results, analysis, test suites — whatever the task specifies), with a summary of what was produced and where
- **Good:** Minimal changes that satisfy acceptance criteria, clean code, tests where appropriate, deliverable is self-contained and verifiable
- **Bad:** Over-engineering, unrelated refactoring, skipping tests, ignoring edge cases identified in ideation, leaving the deliverable incomplete for validation to finish
```

Key changes:
- "write the code" becomes "produce the deliverable" with examples that include experiments and analysis
- Outputs broadened from "working code or artifacts" to explicitly include experiment results, analysis, test suites
- Added "deliverable is self-contained and verifiable" to Good criteria
- Added "leaving the deliverable incomplete for validation to finish" to Bad criteria
- Added closing sentence: implementation is complete when the deliverable exists and is ready for independent verification

### Change 2: README `validation` stage — add explicit boundary statement

Current:
```
### `validation`

A task moves to validation after implementation is complete. The work here is to verify the implementation meets the acceptance criteria defined in ideation.
```

Proposed:
```
### `validation`

A task moves to validation after implementation is complete. The work here is to verify the deliverable meets the acceptance criteria defined in ideation. The validator checks what was produced — it does not produce the deliverable itself.
```

Key change: One sentence added to draw the boundary explicitly. This sentence will appear in every validator's dispatch prompt (since the FO copies the stage definition verbatim).

### Change 3: FO validation instructions — reinforce boundary, distinguish "run tests" from "produce results"

Current (first-officer.md line 44):
```
**Validation instructions** (insert when dispatching a validation stage): You are a validator. You read and judge — you do NOT write code or fix bugs. Determine what work was done in the previous stage. For code changes, check the README for a Testing Resources section — run applicable tests and include results (test failure means recommend REJECTED). For analysis or research, verify correctness and completeness against acceptance criteria. Adapt validation to what was actually produced. If you find issues, describe them precisely in your stage report with a REJECTED recommendation. If an implementer messages you with fixes, re-run tests and update your stage report, then send your updated completion message to the first officer.
```

Proposed:
```
**Validation instructions** (insert when dispatching a validation stage): You are a validator. You read and judge — you do NOT produce the deliverable, write code, or fix bugs. The deliverable should already exist from the implementation stage. Determine what was produced in the previous stage. For code changes, check the README for a Testing Resources section — run applicable tests and include results (test failure means recommend REJECTED). For experiment results or analysis, verify that the results exist, the methodology was followed, and the conclusions are supported by the data — do not re-run experiments to produce new results. Adapt validation to what was actually produced. If the deliverable is missing or incomplete, that is itself a REJECTED finding. If you find issues, describe them precisely in your stage report with a REJECTED recommendation. If an implementer messages you with fixes, re-run tests and update your stage report, then send your updated completion message to the first officer.
```

Key changes:
- "you do NOT write code or fix bugs" becomes "you do NOT produce the deliverable, write code, or fix bugs"
- Added: "The deliverable should already exist from the implementation stage."
- "Determine what work was done" becomes "Determine what was produced"
- Added specific guidance for experiments/analysis: "verify that the results exist, the methodology was followed, and the conclusions are supported by the data — do not re-run experiments to produce new results"
- Added: "If the deliverable is missing or incomplete, that is itself a REJECTED finding."

### Change 4: Validator template — no changes needed

The validator template already correctly frames validation as verifying existing work. The problem was in the dispatch prompt (controlled by the FO template), not the agent template. Adding redundant boundary language to the validator template would be belt-and-suspenders with diminishing returns — the FO's validation instructions are the effective control point because they're inserted into every dispatch prompt.

## Edge Cases

### Experimental tasks (e.g., 058 terminology-experiment)
- **Implementation** builds the harness AND runs the experiment, producing results.
- **Validation** checks: did the experiment follow the methodology? Are the results plausible? Do the statistical tests match the design? Are there obvious errors in the data?
- The proposed wording handles this: "run experiments" is in the implementation outputs, and "verify that the results exist, the methodology was followed, and the conclusions are supported by the data" is in the validation instructions.

### Research tasks (deliverable is a document)
- **Implementation** produces the research document with analysis and conclusions.
- **Validation** checks: does the document address the problem statement? Are claims supported by evidence? Is the analysis complete per the acceptance criteria?
- The proposed wording handles this: "generate analysis" is in the implementation examples, and the validation stage says "checks what was produced — it does not produce the deliverable itself."

### Test-suite tasks (deliverable IS a test suite)
- **Implementation** writes the test suite and runs it, producing pass/fail results.
- **Validation** checks: do the tests cover the acceptance criteria? Are they testing real behavior (not mocked behavior)? Do they pass when run independently?
- This is the trickiest edge case. The validator running existing tests is clearly validation work. The validator writing NEW tests could be either — the validator template already permits creating test files ("You MAY create or modify test files to verify acceptance criteria"). The boundary: the validator can write supplementary tests to verify claims, but it doesn't write the test suite that IS the deliverable. The proposed wording handles this because the test suite is the deliverable, and "does not produce the deliverable itself" applies.

### Tasks where the implementer's infrastructure is broken
- In 058, the validator found and fixed harness bugs before running the experiment. Under the proposed wording, the validator would instead report "harness is broken, cannot verify results, REJECTED" and the implementer would fix the harness.
- This is the correct behavior — it maintains the independence principle. The validator shouldn't be fixing infrastructure it's supposed to be testing.

## Expanded scope: Feedback agent pattern and `feedback-to` stage property

### The coupling problem

The FO dispatch logic (step 4) currently says: "default to `validator` when the stage has `fresh: true`." This couples two orthogonal concerns:
- **Context freshness** (`fresh: true`) — should the agent start without prior context?
- **Agent behavior** (validator vs ensign) — should the agent verify or produce?

Non-development workflows might want `fresh: true` without a validator (e.g., "second opinion" stage).

### Proposed: `feedback-to: {stage_name}` stage property

Add `feedback-to` to the README stages block to explicitly declare feedback relationships:

```yaml
- name: implementation
  worktree: true
- name: validation
  worktree: true
  fresh: true
  feedback-to: implementation
  gate: true
```

This makes the pairing explicit. The FO reads `feedback-to` and knows: (1) this is a feedback stage, (2) on rejection, bounce findings back to the named stage's agent. The pattern generalizes beyond validation:

- **Review** stage — reviewer checks work, bounces findings to author
- **Validation** stage — validator tests implementation, bounces failures to implementer
- **Approval** stage — approver evaluates proposal, bounces objections to proposer

### Agent type defaults (revised dispatch logic)

FO step 4 becomes:
- Stage has `agent:` property → use that (always wins)
- Stage has `feedback-to:` but no `agent:` → default to `validator`
- Otherwise → default to `ensign`

`fresh: true` is purely about context freshness — no longer drives agent type.

### Generalized rejection flow

The FO's `## Validation Rejection Flow` becomes a general `## Feedback Rejection Flow`:
1. Feedback stage gets REJECTED at gate
2. FO reads `feedback-to: {target_stage}` from stages block
3. FO dispatches (or re-engages) an agent for the target stage with findings
4. Target agent fixes, signals feedback agent
5. Feedback agent re-checks, reports to FO
6. FO presents at gate — same cycle limit (3) applies

### Star Trek role mapping — lieutenant as feedback role

In the hierarchy: ensign does work, the commanding officer provides feedback. The feedback agent maps to **lieutenant** — the officer who reviews the ensign's work and bounces it back. This reframes the validator as a type of lieutenant (the feedback role in the hierarchy), not a separate concept.

- **Ensign** — does the work (implementation, production)
- **Lieutenant** — provides feedback (review, validation, approval)
- **First officer** — orchestrates the bounce between them

This connects to task 064 (capability modules) which is already rethinking the lieutenant role. The pr-lieutenant was awkward as a stage agent, but "lieutenant" as a feedback role fits naturally.

### Open questions (for next brainstorm session)

1. Should `feedback-to` imply `fresh: true`? (Lean: no — keep explicit, but could be a sensible default)
2. Does the validator template rename to lieutenant? Or is validator a specialization of lieutenant?
3. How does this interact with task 064's capability modules — are feedback agents a capability or a core concept?
4. Should `feedback-to` support chaining (e.g., approval → review → implementation)?

## Brainstorm: Open questions deep dive

### Q1: Should `feedback-to` imply `fresh: true`?

**Recommendation: No. Keep them orthogonal. Do not imply `fresh: true`.**

The initial lean was correct, but the reasoning deserves more depth.

**Why feedback stages usually want fresh context:** The independence principle — a validator shouldn't be contaminated by the implementer's reasoning. If the validator sees the implementation thought process, it's primed to agree rather than challenge. This is the *typical* case for validation stages.

**Cases where a feedback stage wouldn't want fresh context:**

1. **Iterative review stages.** Imagine a writing pipeline: `draft → review → revision → final-review`. The `review` stage has `feedback-to: draft`. If the reviewer has been working with the author through prior stages, that accumulated context is valuable — they understand the intent, the audience, the constraints. Fresh context would force them to re-derive all of that from the document alone.

2. **Approval stages.** An `approval` stage with `feedback-to: implementation` might be the captain reviewing work. The captain doesn't need fresh context — they've been watching the whole process. (Granted, the captain isn't an agent, but a human-delegated approval agent might carry context.)

3. **Multi-round feedback within a stage.** During the validation rejection flow, the validator already persists across fix cycles (the FO keeps it alive). If `feedback-to` implied `fresh: true`, this would create a contradiction: the property says "fresh" but the rejection flow says "keep the validator alive."

**The coupling problem restated:** `fresh: true` is about *epistemological independence* — the agent shouldn't have prior context that biases its judgment. `feedback-to` is about *workflow topology* — this stage's output feeds back to another stage on rejection. These are correlated (validation wants both) but not identical (review might want feedback-to without fresh, and a "second opinion" stage might want fresh without feedback-to).

**Practical implication for the FO dispatch logic:** The current rule "default to `validator` when `fresh: true`" should become "default to `validator` when `feedback-to` is set." The `fresh` property continues to control context isolation independently. A stage can have `feedback-to` without `fresh` (reviewer with accumulated context) or `fresh` without `feedback-to` (independent second opinion that doesn't feed back anywhere).

### Q2: Validator/lieutenant naming — rename, specialize, or keep separate?

**Recommendation: Keep `validator` as the template name. Do not rename to `lieutenant`. `Lieutenant` is a conceptual role in the hierarchy, not a template.**

Here's the reasoning:

**The Star Trek hierarchy mapping is useful as a mental model but breaks down as a naming scheme.** In the entity, the mapping is: ensign = worker, lieutenant = feedback provider, first officer = orchestrator. This is a clean conceptual hierarchy. But as template names, it creates problems:

1. **"Lieutenant" is too generic for a template name.** A validator has specific behavior: it reads, tests, judges, doesn't modify implementation code, produces a Recommendation section. A "reviewer" (another feedback role) might have different behavior: it reads for clarity, style, and correctness, but doesn't run tests and might suggest edits. Calling both "lieutenant" erases the behavioral distinction.

2. **The validator template works well as-is.** It already has the right framing: "You verify that implementation work meets acceptance criteria. You NEVER modify implementation code." Renaming it to "lieutenant" would lose this specificity without gaining anything.

3. **Task 064 is actively rethinking what "lieutenant" means.** The pr-lieutenant is being decomposed into capability modules. If we simultaneously redefine "lieutenant" as the feedback role, we're loading the term with two different semantic histories — the old "stage agent that also provides hooks" and the new "feedback provider in the hierarchy." This invites confusion.

**Better framing:** `Lieutenant` describes a *role category* (feedback provider), and `validator` is a *specialization* of that role. Future feedback templates — `reviewer`, `approver`, etc. — would also be lieutenant-role agents. But their template names should describe their specific behavior, not their position in a hierarchy.

**What this means for the FO dispatch logic:** The FO's step 4 becomes:
- Stage has `agent:` → use that
- Stage has `feedback-to:` but no `agent:` → default to `validator`
- Otherwise → default to `ensign`

The validator is the *default* feedback agent, but `agent: reviewer` could override it for a stage that needs a different feedback flavor. No renaming needed.

**What about the Star Trek framing in documentation?** It's fine as explanatory prose (e.g., in the spec or a design document explaining the role hierarchy). It just shouldn't drive template filenames.

### Q3: Interaction with task 064 — capability modules

**Recommendation: Feedback agents are a core concept, not a capability. They complement capability modules rather than conflicting.**

Task 064's core insight: capabilities like PR management are *cross-cutting lifecycle behaviors* — they hook into startup, merge, and potentially dispatch/gate. They don't belong in a single stage. The pr-lieutenant was awkward because it tried to be both a stage agent and a lifecycle hook provider.

Task 065's feedback-to pattern is fundamentally different: it's about *stage topology* — how stages relate to each other in the workflow graph. When validation rejects, findings flow back to implementation. This is intrinsic to the workflow structure, not a cross-cutting behavior that can be enabled/disabled.

**Where they interact cleanly:**

1. **Capability modules replace the hook-providing role of lieutenants.** Lifecycle behaviors (startup hooks, merge hooks) move to `_capabilities/`. This is task 064's domain.

2. **`feedback-to` replaces the implicit coupling between `fresh: true` and agent type.** Workflow topology (which stage feeds back to which) is declared in the README stages block. This is task 065's domain.

3. **The validator template stays as a core agent template.** It's not a capability module — it's an agent type, like `ensign`. Capabilities hook into the FO's lifecycle; agent types are dispatched to do stage work.

**Where they could conflict:**

The `agent:` stage property has dual roles today:
- Task 064 says: `agent:` was used for hook-providing lieutenants, which is being replaced by capabilities. The `agent:` property remains for "non-default worker agents" (e.g., a hypothetical `data-scientist` ensign variant).
- Task 065 says: the FO defaults to `validator` when `feedback-to` is set, but `agent:` can override.

These are compatible. After task 064, `agent:` no longer serves a hook-discovery role. It purely selects which agent template to dispatch for stage work. Task 065's `feedback-to` tells the FO this is a feedback stage, and `agent:` (if present) overrides the default `validator` with an alternative feedback agent.

**Synthesis:** The two tasks divide cleanly along the lifecycle-vs-topology boundary:
- **Task 064 (capabilities):** Cross-cutting lifecycle behaviors. Modular. Enable/disable per workflow.
- **Task 065 (feedback-to):** Stage relationships in the workflow graph. Structural. Declared in README stages block.

No changes needed to either task to make them compatible. The only coordination point is ensuring the FO dispatch logic (step 4) correctly prioritizes: `agent:` > `feedback-to` default > `ensign` default.

### Q4: Should `feedback-to` support chaining?

**Recommendation: YAGNI. Do not support chaining in the initial implementation.**

The question is whether a chain like `implementation → review → approval` needs `approval` to have `feedback-to: review` and `review` to have `feedback-to: implementation`, so rejection cascades back through the chain.

**Why it seems appealing:** Some workflows have layered quality gates. Code goes through peer review, then tech lead approval, then security review. Each layer might reject for different reasons, and the rejection should go back to the right fixer.

**Why it's YAGNI:**

1. **The current rejection flow already handles the common case.** Validation rejects → implementer fixes → validator re-checks. This is a two-party bounce, not a chain. Adding a third link (approval rejects → reviewer re-reviews → reviewer re-sends to approval) adds complexity without a demonstrated need.

2. **Chaining introduces ambiguity about where to bounce.** If `approval` rejects, should it bounce to `review` (the stage it has `feedback-to` pointing at) or to `implementation` (the stage that actually produces the code)? The answer depends on *what* was rejected — a code bug should go to the implementer, a review inadequacy should go to the reviewer. This requires the rejection to carry routing information, which is a significant increase in complexity.

3. **The FO can already handle multi-stage rejection manually.** If approval finds a code bug, the captain can reject at the approval gate and say "send this back to implementation." The FO's existing rejection flow handles this — it doesn't need to be automated through chain declarations.

4. **No real workflow in the current system needs it.** Spacedock workflows today have at most implementation → validation. Adding review or approval stages is hypothetical. Building chaining support for hypothetical stages violates YAGNI.

**If it ever becomes needed:** The `feedback-to` property already points at a single stage name. Chaining would mean each feedback stage points at its own target, and the FO follows the chain. The data model supports it — each stage has its own `feedback-to`, and the FO reads the rejected stage's `feedback-to` to know where to bounce. This could be added later without changing the property format. But build it when there's a real workflow that needs it, not now.

### Q5: Review of proposed wording changes (Changes 1-3)

**Change 1 (README implementation stage) — Good, one minor gap.**

The proposed wording correctly broadens from "write the code" to "produce the deliverable" and lists examples (code, experiments, analysis, test suites). The closing sentence "Implementation is complete when the deliverable exists and is ready for independent verification" is a strong boundary marker.

**Gap:** The "Bad" criteria list adds "leaving the deliverable incomplete for validation to finish" but doesn't address the reverse problem: over-producing. An implementer might run an experiment AND interpret the results AND draw conclusions, when the acceptance criteria only asked for raw results. This isn't strictly a boundary problem (it's more about scope creep), and the existing "Over-engineering" bullet probably covers it. No wording change needed, but worth noting.

**Change 2 (README validation stage) — Good, sufficient.**

Adding "The validator checks what was produced — it does not produce the deliverable itself" is the right fix. It's one clear sentence that flows into every validator dispatch prompt via the FO's stage definition copy.

**Potential improvement:** Consider whether the sentence should also clarify "checking" vs "extending." The validator can run existing tests (checking), write supplementary tests (extending for verification purposes), but not write the test suite that IS the deliverable. The validator template already permits writing test files, so this distinction is important. However, the validator template handles this adequately — the README sentence doesn't need to duplicate it.

**Change 3 (FO validation instructions) — Good, strongest improvement.**

The specific guidance for experiments ("verify that the results exist, the methodology was followed, and the conclusions are supported by the data — do not re-run experiments to produce new results") directly addresses the 058 failure. The "missing deliverable = REJECTED" rule is the most valuable addition — it prevents the validator from compensating for incomplete implementation.

**One subtle gap:** The phrase "For code changes, check the README for a Testing Resources section — run applicable tests" could be read as "run ALL tests," which might be excessive for a targeted change. But this is an existing issue in the current wording, not something introduced by the proposed changes. Not in scope for this task.

**Overall assessment:** The three proposed changes are sufficient to address the core problem. They correctly identify the three control points (README implementation definition, README validation definition, FO dispatch instructions) and make targeted wording changes at each. No structural changes are needed — the fixes are all in prose that flows into dispatch prompts.

## Acceptance Criteria

1. README `implementation` stage definition uses "produce the deliverable" language that covers code, experiments, analysis, and test suites — not just "write the code"
2. README `validation` stage definition explicitly states the feedback agent checks what was produced and does not produce the deliverable itself
3. FO feedback instructions (replacing validation-specific instructions) distinguish "run the deliverable to verify behavior" from "produce new deliverable content"
4. FO feedback instructions state that a missing or incomplete deliverable is itself a REJECTED finding
5. Validator template dropped — feedback protocol is FO-injected dispatch instructions, not a separate agent type
6. Edge cases (experimental, research, test-suite tasks) are covered by the proposed wording without special-case rules
7. Commission Confirm Design presents stage behavior in human-readable language (approval gates, rejection flow) — not implementation vocabulary (`worktree`, `gate`, `fresh`)
8. Commission infers implementation properties (`worktree`, `fresh`) from workflow design without exposing them to the user

## Stage Report: ideation

- [x] Current stage definitions analyzed — what's ambiguous about the implementation/validation boundary
  README implementation says "write the code" which doesn't cover experiments/analysis; validation lacks an explicit "don't produce the deliverable" boundary statement
- [x] FO validation dispatch instructions analyzed — where the boundary gets violated
  FO inserts validation instructions into every dispatch prompt; current wording doesn't distinguish "run tests to verify" from "run experiments to produce results," and lacks guidance for missing deliverables
- [x] Proposed wording changes for README stage definitions
  Implementation: "produce the deliverable" with examples (code, experiments, analysis, test suites). Validation: added "checks what was produced — does not produce the deliverable itself"
- [x] Proposed wording changes for FO template validation instructions
  Added "do NOT produce the deliverable," experiment-specific guidance ("verify results exist, methodology followed, conclusions supported — do not re-run"), and "missing deliverable = REJECTED"
- [x] Validator template assessed — changes needed or not, with rationale
  No changes needed. Validator template already correctly frames role as verifying existing work. The problem was the FO dispatch prompt overriding the template, not the template itself.
- [x] Edge cases considered — experimental tasks, research tasks, test-suite tasks
  Four edge cases analyzed: experiments (run = implementation, verify results = validation), research docs (produce = implementation, check claims = validation), test suites (write the suite = implementation, run supplementary checks = validation), broken infrastructure (report REJECTED, don't fix)
- [x] Acceptance criteria written — testable conditions for "done"
  Six criteria covering README changes, FO instruction changes, validator template assessment, and edge case coverage

### Summary

Analyzed the implementation/validation boundary problem through the lens of task 058 (where the validator produced experiment results instead of verifying them) and task 061 (which established the independence principle). The root cause is twofold: README stage definitions use code-centric language ("write the code") that doesn't cover non-code deliverables, and the FO validation instructions don't explicitly distinguish running tests to verify from running experiments to produce results. Proposed specific wording changes to the README implementation stage (broaden to "produce the deliverable"), the README validation stage (add boundary statement), and the FO validation instructions (experiment-specific guidance, missing-deliverable handling). The validator template needs no changes — the fix belongs in the stage definitions and FO instructions that flow into dispatch prompts.

## Stage Report: ideation (brainstorm)

- [x] `feedback-to` and `fresh: true` relationship — recommendation with rationale
  Keep orthogonal. `fresh` = epistemological independence, `feedback-to` = workflow topology. Three cases identified where feedback stages wouldn't want fresh context (iterative review, approval, multi-round rejection flow contradiction).
- [x] Validator/lieutenant naming analysis — rename, specialize, or keep separate, with reasoning
  Keep `validator` as the template name. `Lieutenant` is a conceptual role category (feedback provider), not a template. Renaming would lose behavioral specificity, collide with task 064's semantic history, and wouldn't improve the FO dispatch logic.
- [x] Interaction with task 064 capability modules — conflict or complement, with synthesis
  Complement, not conflict. Clean division: task 064 handles cross-cutting lifecycle behaviors (capabilities), task 065 handles stage topology (feedback-to). The `agent:` property serves both without ambiguity after task 064 removes its hook-discovery role.
- [x] `feedback-to` chaining — YAGNI or real need, with examples
  YAGNI. Current two-party bounce handles the common case. Chaining introduces routing ambiguity (which stage to bounce to depends on rejection reason). Data model already supports future chaining without format changes if needed.
- [x] Review of proposed wording changes (Changes 1-3) — gaps or improvements identified
  All three changes are sufficient. One minor gap noted (over-producing in implementation, covered by existing "over-engineering" bullet). One subtle gap in validation instructions ("run applicable tests" could mean "run ALL tests") but that's pre-existing, not introduced by the changes.

### Summary

Deep-dived the four open questions from the expanded scope section. Key recommendations: (1) `feedback-to` and `fresh: true` must remain orthogonal properties — coupling them creates contradictions with the rejection flow and prevents legitimate use cases like iterative review; (2) keep `validator` as the template name, use `lieutenant` only as conceptual framing for the feedback role category; (3) tasks 064 and 065 divide cleanly along lifecycle-vs-topology lines with no conflicts; (4) chaining is YAGNI — the data model supports it later if needed but no current workflow requires it. The three proposed wording changes from the initial ideation are sufficient with no significant gaps.

## Brainstorm 2: Stress-testing the recommendations

### Q1 revisited: `feedback-to` and `fresh: true` — the default question

The prior brainstorm correctly recommends keeping them orthogonal. But there is a pragmatic concern that was under-explored: **what does the typical README stages block look like after these changes?**

Current (Spacedock's own workflow):
```yaml
- name: validation
  worktree: true
  fresh: true
  gate: true
```

Proposed with `feedback-to`:
```yaml
- name: validation
  worktree: true
  fresh: true
  feedback-to: implementation
  gate: true
```

That is four properties on a single stage. Every standard dev workflow will have this same four-property validation stage. If `feedback-to: implementation` is the overwhelmingly common pattern for validation stages, there is a usability argument for a shorthand — not that `feedback-to` *implies* `fresh`, but that there should be a way to declare the standard validation pattern without four properties every time.

**However, this is a commission UX problem, not a schema problem.** The commission skill already generates the stages block. It can emit the four properties when the user selects a validation stage. The schema should stay explicit (all four properties visible), because the README is the source of truth that agents read. Implicit defaults in the schema create a gap between what agents read and what the workflow author intended. The commission can make it easy to produce; the schema should make it unambiguous to read.

**One more case against implying `fresh`: the `feedback-to` property names a stage, not a behavior.** If `feedback-to` implied `fresh`, then adding `feedback-to` to an existing non-fresh stage would silently change its context isolation behavior. That is a spooky action-at-a-distance problem. A workflow author who adds `feedback-to: draft` to a review stage (wanting the bounce-back flow) would accidentally get fresh context isolation they did not ask for. Explicit is better.

**Final recommendation: confirmed. No implication. The commission handles the common case by generating both properties together.**

### Q2 revisited: Validator/lieutenant naming — what "lieutenant" actually means now

The prior brainstorm says "lieutenant is a role category, not a template." This is correct but raises a question: **what is the term "lieutenant" for, concretely?** If it is not a template name, not a filename, not an `agent:` value, and not a `subagent_type` — where does it appear in the system?

Three possibilities:

1. **Documentation only.** "Lieutenant" appears in the spec, design docs, and conceptual explanations of the role hierarchy. It never appears in code, filenames, or configuration. This is the cleanest option — the term serves a pedagogical purpose ("feedback agents are like lieutenants in the chain of command") without creating any naming artifacts that could conflict with task 064.

2. **Role category tag.** Templates could declare a `role:` field in their frontmatter (e.g., `role: lieutenant` in the validator template, `role: ensign` in the ensign template). The FO could read this to know "this is a feedback agent" without relying on the template name. But this is over-engineering — the FO already knows a stage is a feedback stage from `feedback-to`. It does not need the agent template to confirm this. The `feedback-to` property is the authority on whether a stage provides feedback, not the agent template's self-description.

3. **Redefine for task 064.** Task 064 says the pr-lieutenant is being replaced by capability modules. If "lieutenant" is freed from its "stage agent that provides hooks" meaning, it could be re-adopted as the feedback role name. But task 064 is not removing the *term* lieutenant from the codebase — it is removing the `pr-lieutenant` specifically. The term "lieutenant" still carries the baggage of "agent that provides lifecycle hooks." Reusing it for "feedback provider" within the same version cycle will confuse anyone reading the git history.

**Recommendation: Option 1 — documentation only.** "Lieutenant" is a conceptual term in the Star Trek metaphor. It does not appear in filenames, configuration, or template frontmatter. The validator template stays named `validator`. Future feedback templates (reviewer, approver) are named for their behavior, not their rank.

This also resolves a subtle inconsistency in the Star Trek framing itself: in Star Trek, a lieutenant outranks an ensign and can give orders. In the Spacedock model, the feedback agent (validator) cannot give orders — it can only recommend REJECTED and provide findings. The ensign (implementer) decides how to fix. The FO decides whether to bounce. The hierarchy metaphor is imperfect, and leaning on it too hard for naming would create false expectations about authority.

### Q3 revisited: Task 064 interaction — the dispatch step 4 convergence

The prior brainstorm identifies the convergence point: FO dispatch step 4 must prioritize `agent:` > `feedback-to` default > `ensign` default. Let me trace through the concrete scenario to verify this works after both tasks land.

**Current FO step 4 (today):**
```
If stage has `agent:` → use that
If stage has `fresh: true` → default to `validator`
Otherwise → default to `ensign`
```

**After task 064 only (capabilities, no feedback-to):**
The `agent:` property is still present but no longer serves hook discovery. The step stays functionally the same, but the *reason* for `agent:` changes — it is purely for non-default worker agents.

**After task 065 only (feedback-to, no capabilities):**
```
If stage has `agent:` → use that
If stage has `feedback-to:` → default to `validator`
Otherwise → default to `ensign`
```
The `fresh: true` → `validator` coupling breaks. A stage with `fresh: true` but no `feedback-to` gets an ensign (fresh ensign — second opinion pattern). A stage with `feedback-to` but no `fresh` gets a validator (warm validator — iterative review pattern).

**After both tasks land:**
Same as "after task 065 only" — task 064 changes where hooks live, not how agent types are selected. The dispatch step 4 logic is purely task 065's domain.

**Potential sequencing issue:** If task 064 lands first, it will update the FO template's step 4 wording. If task 065 lands second, it needs to modify the same section. This is a merge conflict risk, but both tasks are in ideation — the implementation order is not yet decided. The recommendation is: implement task 065's dispatch change (the `feedback-to` logic) in whichever task lands second, or do both in a single implementation if they are sequenced.

**One genuine conflict to flag:** Task 064's acceptance criterion 3 says "FO template startup step 3 discovers hooks by scanning `{workflow_dir}/_capabilities/*.md` (not agent files)." This removes the FO's step 4 from scanning agent files for hooks. But step 4 currently serves two purposes: (a) hook discovery (going away with capabilities) and (b) agent type selection (staying with `feedback-to`). The FO template rewrite needs to cleanly separate these. The current step 4 does both in one sentence: "If the stage has an `agent` property..., use that value." After both tasks, step 4 should *only* do agent type selection. Hook discovery is step 3 (capabilities). This is a wording change, not a logic change — but it needs to be done deliberately.

### Q4 revisited: Chaining — confirming YAGNI with a concrete stress test

The prior brainstorm says YAGNI. Let me stress-test with the most plausible near-term workflow that might want chaining: a documentation pipeline.

```yaml
stages:
  states:
    - name: draft
    - name: technical-review
      feedback-to: draft
      fresh: true
      gate: true
    - name: editorial-review
      feedback-to: draft
      gate: true
    - name: published
      terminal: true
```

Here, both `technical-review` and `editorial-review` feed back to `draft`. This is not chaining — both point at the same target. The FO handles each independently: technical review rejects → bounce to draft author. Editorial review rejects → bounce to draft author (possibly a different agent instance, possibly the same).

Now consider: what if editorial review catches a *technical* issue? Under this topology, it bounces to the draft author, who might not be able to fix a technical issue. The "correct" behavior would be to bounce back to technical review first. But this is a *routing decision*, not a topology declaration. The FO (or the captain) should make this call at rejection time based on the findings, not based on a pre-declared chain.

This confirms the YAGNI assessment: the edge cases where chaining seems needed are actually routing decisions that should be made dynamically. Pre-declaring chains would over-constrain the FO and create situations where the "correct" bounce target depends on the rejection reason, not the stage topology.

**One additional observation:** `feedback-to` pointing at a non-adjacent stage is interesting but unproblematic. In the docs pipeline above, `editorial-review` has `feedback-to: draft`, skipping `technical-review`. The FO reads this literally: on rejection, bounce findings to the draft stage's agent. The entity does not go back *through* technical review — it goes directly to draft. Stage progression handles the re-traversal if needed (after the draft author fixes and completes, the entity would need to re-enter technical review before reaching editorial review again). This works naturally with the existing stage progression — `feedback-to` controls where rejection findings go, not the re-traversal path.

### Q5 revisited: Proposed wording changes — one additional gap

The prior brainstorm identified all the major points. One additional gap worth noting in Change 3 (FO validation instructions):

The proposed wording says "For experiment results or analysis, verify that the results exist, the methodology was followed, and the conclusions are supported by the data." This is excellent for experiments with results-as-deliverable. But there is a middle category: **tasks where the deliverable is code, but acceptance criteria require running the code to verify behavior** (e.g., "the CLI produces correct output for these inputs").

In this case, the validator *should* run the code — that is verification, not production. The proposed wording handles this through the "For code changes" clause: "run applicable tests and include results." But if there are no formal tests (just manual verification commands), the validator might interpret the experiment clause ("do not re-run experiments to produce new results") as prohibiting them from running the code at all.

**Suggested micro-fix to Change 3:** After "For experiment results or analysis, verify that the results exist..." add: "Running the deliverable to verify its behavior (e.g., executing a CLI tool, loading a web page, triggering a pipeline) is verification work, not production work." This draws the line clearly: *running* code to check it works = validation. *Running experiments* to produce findings = implementation.

This is a one-sentence addition. The rest of Change 3 is solid.

### Star Trek role mapping — does it hold up?

The entity proposes: ensign = worker, lieutenant = feedback, first officer = orchestrator.

**Where it holds up:**
- Ensign as the worker is well-established and intuitive. Nobody questions this.
- First officer as the orchestrator is the entire FO template's identity. Solid.
- "Lieutenant provides feedback" maps well to the validator's actual behavior — reviewing work and reporting up.

**Where it creaks:**
- In Star Trek, lieutenants are senior to ensigns and command them. In Spacedock, the validator has no authority over the ensign. The FO mediates all communication. The validator recommends; the FO (and captain) decide. This is more like a peer review than a chain-of-command relationship.
- The captain (human) in Star Trek gives orders. In Spacedock, the captain approves at gates but does not write dispatch prompts — the FO does. The captain's role is closer to a product owner who approves PRs than a Star Trek captain who commands the ship.
- The term "lieutenant" in the current codebase means "stage agent with lifecycle hooks" (pr-lieutenant). Redefining it as "feedback provider" requires the old meaning to be fully retired first. Task 064 does this, but until 064 lands, using "lieutenant" for feedback creates semantic collision.

**Net assessment:** The Star Trek framing is useful for explaining the system to newcomers but should not drive design decisions. It is a *metaphor*, not an *architecture*. When the metaphor and the design diverge (as with lieutenant authority), the design wins. The framing section in the entity is fine as explanatory prose but should include a note that the mapping is approximate — the actual authority model is: captain approves, FO orchestrates, all agents are peers dispatched by the FO.

## Stage Report: ideation (brainstorm 2)

- [x] `feedback-to` and `fresh: true` relationship — recommendation with rationale
  Confirmed: keep orthogonal. Added two new arguments: (1) the common four-property validation stage is a commission UX problem, not a schema problem — commission generates the boilerplate, schema stays explicit; (2) `feedback-to` implying `fresh` creates spooky action-at-a-distance when adding feedback-to to an existing non-fresh stage.
- [x] Validator/lieutenant naming analysis — rename, specialize, or keep separate, with reasoning
  Confirmed: keep `validator` as template name. Deepened analysis to three concrete options for what "lieutenant" means going forward. Recommendation is documentation-only — the term appears in conceptual explanations, never in filenames/config/frontmatter. Also noted the Star Trek authority metaphor is imperfect (lieutenant cannot give orders to ensign in Spacedock, unlike Star Trek).
- [x] Interaction with task 064 capability modules — conflict or complement, with synthesis
  Confirmed complement. Traced through the concrete FO step 4 evolution across four scenarios (today, 064-only, 065-only, both). Identified one genuine coordination point: FO step 4 currently serves both hook discovery and agent selection in one sentence; after both tasks land, these must be cleanly separated. Flagged merge conflict risk in FO template if tasks land sequentially.
- [x] `feedback-to` chaining — YAGNI or real need, with examples
  Confirmed YAGNI. Stress-tested with a documentation pipeline (draft → technical-review → editorial-review). Demonstrated that the edge case requiring chaining is actually a routing decision (bounce target depends on rejection reason, not stage topology) that should be made dynamically by the FO/captain. Also clarified that `feedback-to` to a non-adjacent stage works naturally with existing stage progression.
- [x] Review of proposed wording changes (Changes 1-3) — gaps or improvements identified
  Identified one additional gap in Change 3: the middle category where validators need to run code to verify behavior (not produce results). Proposed a one-sentence addition to clarify that running the deliverable to check it works is verification, not production. Also reviewed the Star Trek mapping — holds up as explanatory metaphor but should note the authority model divergence.

### Summary

Stress-tested all five recommendations from the first brainstorm. All hold up under deeper scrutiny. The most substantive new finding is a micro-gap in Change 3's FO validation instructions: need one sentence clarifying that running code to verify behavior is validation work (distinct from running experiments to produce results). The `feedback-to`/`fresh` orthogonality is confirmed with two new arguments (commission handles the common case, implicit behavior change is dangerous). The lieutenant naming question is settled as documentation-only with no artifacts in code/config. Task 064 interaction is clean but has one coordination point: FO step 4 must be split into agent selection (065) and hook discovery (064) when both land. Chaining remains YAGNI — the real need is dynamic routing at rejection time, not pre-declared chains.

## Brainstorm 3: Discussion with CL — Drop the validator, simplify for non-software

CL raised three questions that shifted the direction of the task:

1. How does `feedback-to` get incorporated into the commission skill?
2. Does the implementation actually need a specialized validator agent?
3. What do non-software scenarios reveal about the feedback pattern?

### Key decision: Drop the validator template

CL's principle: **Agent specialization is for domain knowledge, not behavioral framing.** A specialized agent should exist when the README stage definition isn't enough to capture the domain expertise needed (e.g., a `legal-reviewer` for contract review). The feedback protocol itself (check-don't-produce, PASSED/REJECTED, findings) is generic infrastructure the FO should own.

Analysis of what the validator template actually provides:
- "You NEVER modify implementation code" — a constraint (injectable by FO)
- "You read, test, judge" — behavioral framing (injectable by FO)
- Recommendation section (PASSED/REJECTED) — report format (injectable by FO)
- Findings with file paths/line numbers — report format (software-specific, shouldn't be generic)

None of this requires a separate agent template. It's all dispatch-time instructions.

### Revised architecture: Three layers

1. **Feedback protocol (FO-owned, generic):** When a stage has `feedback-to`, the FO injects feedback-role instructions into an ensign's dispatch: "You are reviewing the work from {target_stage}. You check what was produced — you do not produce it yourself. If the deliverable is missing or incomplete, that is itself a REJECTED finding. Report using Recommendation and Findings format."

2. **Review criteria (README-owned, workflow-specific):** The stage definition's Outputs/Good/Bad bullets describe what to check. These are domain-specific — editorial quality for a content pipeline, clause coverage for legal review, methodology adherence for experiments.

3. **Domain expertise (agent-owned, only when needed):** The `agent:` property is reserved for real specialization — a `legal-reviewer` or `security-auditor` whose domain knowledge doesn't fit in README bullets. The feedback protocol is still injected by the FO; the specialized agent adds domain knowledge on top.

### Non-software scenarios explored

**Content pipeline** (pitch → draft → editorial-review → published): Editorial review checks thesis coherence, sourced claims, tone. The validator template's "You NEVER modify implementation code" is meaningless here. Review criteria belong entirely in the README stage definition.

**Hiring pipeline** (sourced → screening → interview → offer-review → hired): Two feedback stages with completely different review criteria. Screening evaluates candidates against role requirements. Offer-review checks whether interview assessment supports the proposed offer. Generic validator language doesn't apply to either.

**Recipe development** (concept → recipe-draft → test-cook → tasting-review → published): Tasting review checks reproducibility, clarity of instructions, match to concept. Domain-specific criteria that belong in the stage definition.

**Legal contract review** (draft → internal-review → client-review → executed): Internal review checks clause coverage, liability, policy compliance. This is a case where `agent: legal-reviewer` makes sense — the domain expertise is too deep for README bullets. But the feedback protocol (bounce to draft on rejection) is still generic.

**Pattern:** In every scenario, the feedback protocol is identical (check, report PASSED/REJECTED, bounce on rejection). The review criteria are always workflow-specific. A specialized agent is only needed when domain expertise exceeds what fits in a stage definition.

### Commission skill: User-facing presentation

CL flagged that the Confirm Design summary needs to show per-stage properties, but also that implementation terms (`worktree`, `gate`, `fresh`) leak jargon into the user experience. Non-software users shouldn't need to learn these terms.

**Resolution:** The commission presents only workflow-level decisions, not implementation vocabulary:

```
Stages: pitch → draft → editorial-review → published

Approval gates: editorial-review (you review before publishing)
On rejection: editorial-review bounces back to draft
```

The stage sequence stays clean. Behavioral properties are called out separately in plain language. The commission infers implementation details (`worktree`, `fresh`, etc.) from the workflow design and generates the full YAML frontmatter without exposing those terms to the user.

Properties the user decides on:
- **Where do I need to approve?** (maps to `gate: true`)
- **What happens when something gets rejected?** (maps to `feedback-to: {target}`)

Properties the commission infers:
- `worktree: true` — stage does substantive work beyond the entity file
- `fresh: true` — stage is a feedback stage (usually wants independent perspective)

### Change 5: Commission Confirm Design — human-readable stage behavior

Current commission Confirm Design output (SKILL.md line 134):
```
- **Stages:** pitch → draft → editorial-review → published
- **Approval gates:** editorial-review → published
```

The stage arrow chain loses all per-stage properties. And the property names themselves (`worktree`, `gate`, `fresh`, `feedback-to`) are implementation vocabulary that non-software users shouldn't need to learn.

Proposed: separate the stage sequence from behavioral properties, using plain language:

```
Stages: pitch → draft → editorial-review → published

Approval gates: editorial-review (you review before publishing)
On rejection: editorial-review bounces back to draft
```

The user decides on two things during commissioning:
- **Where do I need to approve?** → maps to `gate: true`
- **What happens when something gets rejected?** → maps to `feedback-to: {target}`

The commission infers implementation details from the workflow design without exposing them:
- `worktree: true` — stage does substantive work beyond the entity file
- `fresh: true` — feedback stage (usually wants independent perspective)

This means the commission skill's Question 2 (stage design) and Confirm Design template both need updating. The commission asks about workflow behavior in user terms, then translates to YAML properties in the generated README.

### Impact on proposed changes (Changes 1-5)

- **Change 1 (README implementation stage):** Still valid. Broadening to "produce the deliverable" is correct regardless of whether a validator template exists.
- **Change 2 (README validation stage):** Still valid. The boundary statement applies to any feedback stage, not just ones using a validator agent.
- **Change 3 (FO validation instructions):** Needs revision. Instead of being a block inserted for "validation stages," this becomes the generic feedback-role instructions inserted whenever `feedback-to` is present. The software-specific parts (file paths, line numbers, "run applicable tests") should be removed from the generic version and left to README stage definitions.
- **Change 4 (Validator template — no changes):** Superseded. The validator template is dropped entirely.
- **Change 5 (Commission Confirm Design):** Commission presents stage behavior in human-readable language, not implementation vocabulary. User decides on approval gates and rejection flow; commission infers `worktree`, `fresh`, etc.

### Open questions — resolved

1. **Transition plan:** Update in place. Spacedock is the only consumer, pre-v1, no backward compatibility concern.
2. **Findings format:** No — the commission should not help define domain-specific "specific." The generic instruction "numbered list of specific issues with enough detail to locate and address" is sufficient. Domain-specific reviewers who need more structure use a specialized agent via `agent:`.
3. **FO template wording:** Strip software-specific language from current FO validation instructions to create generic feedback protocol. The generic version: "You are reviewing the work from {target_stage}. You check what was produced — you do not produce the deliverable yourself. If the deliverable is missing or incomplete, that is itself a REJECTED finding. Running the deliverable to verify its behavior is review work; producing new deliverable content is not. Report with a Recommendation (PASSED or REJECTED) and numbered Findings."

## Stage Report: ideation (final)

- [x] Proposed changes finalized (or confirmed as-is) based on discussion with CL
  Five changes confirmed: (1) README implementation broadened to "produce the deliverable," (2) README validation adds boundary statement, (3) FO validation instructions become generic feedback protocol with software-specific language stripped, (4) validator template dropped — feedback protocol is FO-injected, (5) commission Confirm Design presents stage behavior in human-readable language. Open questions resolved: update in place, no domain-specific findings format help, generic FO wording drafted.
- [x] Acceptance criteria confirmed or updated
  Updated from 6 to 8 criteria: criteria 2-5 revised to reflect validator-drop decision, criteria 7-8 added for commission output simplification.
- [x] Open questions resolved
  Three open questions from brainstorm 3 resolved with CL approval: transition plan (in-place), findings format (keep generic), FO template wording (strip software-specific language, draft provided).

### Summary

Finalized ideation across four rounds of brainstorming and direct discussion with CL. The task evolved from targeted wording fixes (Changes 1-3) to a broader architectural shift: drop the validator template entirely, make the feedback protocol FO-owned generic infrastructure triggered by `feedback-to` stage property, and simplify the commission's user-facing presentation to hide implementation vocabulary. Five proposed changes with eight acceptance criteria are ready for implementation.

## Stage Report: implementation

- [x] README implementation stage uses "produce the deliverable" language (Change 1)
  `docs/plans/README.md` line 93: "produce the deliverable: write code, run experiments, generate analysis" with broadened Outputs, Good, and Bad criteria
- [x] README validation stage has explicit boundary statement (Change 2)
  `docs/plans/README.md` line 103: "The validator checks what was produced — it does not produce the deliverable itself"
- [x] FO validation instructions are generic feedback protocol without software-specific language (Change 3)
  `templates/first-officer.md` line 43: Feedback instructions triggered by `feedback-to`, generic wording covering all deliverable types, "missing deliverable = REJECTED" rule included
- [x] Validator template removed or deprecated (Change 4)
  `templates/validator.md` deleted via git rm. All references removed from SKILL.md (generation step 2e2, checklist, announcement, warnings) and test-rejection-flow.sh
- [x] Commission Confirm Design presents stage behavior in plain language (Change 5)
  `skills/commission/SKILL.md` Confirm Design now shows "Approval gates" with human-readable descriptions and "On rejection" with bounce targets. Implementation vocabulary (worktree, gate, fresh, feedback-to) not exposed to user
- [x] All changes committed to worktree branch
  Commit 21035b2 on ensign/065-stage-boundaries with all 6 files changed
- [x] Commission test harness passes (fix cycle)
  Updated `scripts/test-commission.sh` line 344: grep now checks for `feedback-to|feedback instructions|deliverable|produce.*deliverable` instead of removed software-specific terms. 64/64 checks pass.
- [x] Rejection flow test updated for new terminology (fix cycle)
  Updated `tests/test-rejection-flow.sh` lines 117, 183, 203, 205: replaced "validator" with "reviewer" in claude prompt, comments, and check messages. Phase 1 (fixture setup) passes: 4/4 checks.

### Summary

Implemented all five proposed changes from ideation, then fixed two test issues identified during validation. The core architectural shift: the validator template is removed entirely, and the feedback protocol becomes FO-owned generic infrastructure injected at dispatch time when a stage has `feedback-to`. Fix cycle addressed: (1) commission test harness grep updated from software-specific validation terms to generic feedback protocol terms (now 64/64 pass), (2) rejection flow test terminology updated from "validator" to "reviewer" throughout (phase 1: 4/4 pass).

## Stage Report: validation

- [x] README implementation stage uses "produce the deliverable" language covering code, experiments, analysis
  Verified at `docs/plans/README.md` line 94: "produce the deliverable: write code, run experiments, generate analysis" with broadened Outputs ("code, experiment results, analysis, test suites"), Good ("deliverable is self-contained and verifiable"), and Bad ("leaving the deliverable incomplete for validation to finish")
- [x] README validation stage explicitly states validator checks what was produced, doesn't produce the deliverable
  Verified at `docs/plans/README.md` line 103: "The validator checks what was produced — it does not produce the deliverable itself"
- [x] FO template validation instructions are generic feedback protocol (no software-specific language)
  Verified at `templates/first-officer.md` line 43: Feedback instructions triggered by `feedback-to` property, generic wording ("You are reviewing the work from {feedback-to target stage}. You check what was produced — you do not produce the deliverable yourself."), no references to "Testing Resources", "run applicable tests", or other software-specific terms. Dispatch prompt condition changed from `{if validation stage}` to `{if stage has feedback-to}`.
- [x] Validator template is removed (or deprecated) with references cleaned up
  `templates/validator.md` deleted. SKILL.md: step 2e2 (validator generation) removed, generation checklist entry removed, Phase 3 announcement line removed, lieutenant agent warnings exclusion for "validator" removed. `tests/test-rejection-flow.sh`: no longer copies `validator.md` to `.claude/agents/`. Note: deployed `.claude/agents/validator.md` still exists but is expected — deployed agents update via refit, not direct modification per agent rules.
- [x] Commission Confirm Design presents stage behavior in plain language (no worktree/gate/fresh jargon)
  Verified at `skills/commission/SKILL.md` lines 128-143: Confirm Design now shows "Approval gates: {stage_name} (you review before {next_stage_name})" and "On rejection: {gated_stage} bounces back to {target_stage}". Explicit instruction added: "Use plain language for stage behavior — do not expose implementation vocabulary like `worktree`, `gate`, `fresh`, or `feedback-to`". Commission infers `feedback-to` from `rejection_flow` derived during design.
- [ ] FAIL: Commission test harness passes
  63/64 checks pass. One failure: "first-officer has smart validation instructions" at `scripts/test-commission.sh` line 344. The check greps for `validation.*test|Testing Resources|run.*test|test.*harness` in the generated FO. The FO template intentionally no longer contains these software-specific terms — they were stripped as part of Change 3 (making feedback instructions generic). The test check needs updating to verify the new generic feedback protocol (e.g., check for `feedback-to|feedback instructions|deliverable` instead).
- [ ] SKIP: Rejection flow test passes (or is updated for new model)
  Phase 1 (fixture setup) passes: FO has "Feedback Rejection Flow", `feedback-to` dispatch logic, status script runs, entity is dispatchable. Phase 2/3 (full E2E via `claude -p` with haiku/$5) not run — requires live claude CLI invocation with budget. Test script is structurally updated for the new model (ensign-only dispatch, feedback-to checks, ensign count >= 3 for fix after rejection). Minor cosmetic issue: test still uses "validator" terminology in some comments and check messages (lines 117, 183, 203, 205).

### Recommendation

REJECTED

### Findings

1. `scripts/test-commission.sh` line 344: The check `grep -qi "validation.*test\|Testing Resources\|run.*test\|test.*harness" "$FO"` fails against the new FO template because software-specific validation terms were intentionally removed. The check should be updated to verify the generic feedback protocol instead (e.g., `feedback-to|feedback instructions|deliverable|produce.*deliverable`).
2. `tests/test-rejection-flow.sh` lines 117, 183, 203, 205: Residual "validator" terminology in comments and check messages. While cosmetic and not affecting test correctness, these are inconsistent with the architectural shift from "validator" to "feedback agent/ensign with feedback instructions." The claude -p prompt at line 117 still says "where the validator recommends REJECTED" — this should say "reviewer" or "feedback agent."

### Summary

Validated all five proposed changes against eight acceptance criteria. The core changes are well-executed: README stages broadened correctly, FO template has generic feedback protocol triggered by `feedback-to`, validator template removed with references cleaned up, commission presents plain language. Two issues found: (1) the commission test harness has one check that expects software-specific terms the template intentionally no longer contains — this is a test that needs updating, not a regression; (2) the rejection flow test has residual "validator" terminology in comments. Recommending REJECTED because the commission test harness does not pass as-is, which was an explicit acceptance criterion.
