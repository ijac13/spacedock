---
id: 065
title: Clarify implementation vs validation boundaries for experimental tasks
status: ideation
source: CL
started: 2026-03-28T00:25:00Z
completed:
verdict:
score:
worktree:
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
2. README `validation` stage definition explicitly states the validator checks what was produced and does not produce the deliverable itself
3. FO validation instructions distinguish "run existing tests to verify" from "run experiments to produce results"
4. FO validation instructions state that a missing or incomplete deliverable is itself a REJECTED finding
5. Validator template requires no changes (or changes are justified against the current wording)
6. Edge cases (experimental, research, test-suite tasks) are covered by the proposed wording without special-case rules

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
