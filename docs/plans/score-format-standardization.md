---
title: Score Format Standardization
status: ideation
source: commission seed
started:
completed:
verdict:
score: 19
---

## Problem

The current scoring rubric (Edge/Fitness/Parsimony/Testability/Novelty, each 1-5, sum out of 25) is defined in the pipeline README but there is no guidance on how agents should apply it consistently. Two agents scoring the same entity could produce wildly different results because the dimension descriptions are abstract. Additionally, the spec mentions both "0-1 (normalized)" and "0-25 (sum)" as possibilities without resolving which to use.

Without standardization, scores are meaningless for prioritization — which is their entire purpose.

## Proposed Approach

1. **Keep the 1-25 integer format.** Normalized 0-1 scores are harder for agents to reason about (is 0.72 good?) and harder to sort visually in the status output. Integer sums are concrete and human-readable.

2. **Add anchor descriptions to each rubric dimension.** For each of the 5 dimensions, define what a 1, 3, and 5 looks like in concrete terms relevant to the pipeline's domain. This gives agents calibration points.

3. **Add scoring guidance to the README template** in the commission skill, so every generated pipeline gets consistent scoring instructions. The guidance should be part of the Scoring Rubric section, not a separate document.

4. **Score field format:** Plain integer in YAML frontmatter (`score: 18`), no "/25" suffix. The status script already handles this correctly.

## Acceptance Criteria

- [ ] Each rubric dimension (Edge, Fitness, Parsimony, Testability, Novelty) has anchor descriptions for scores 1, 3, and 5
- [ ] The commission skill's README template includes the anchor descriptions when a scoring rubric is generated
- [ ] The scoring guidance is specific enough that two agents scoring the same entity would produce scores within 3 points of each other
- [ ] The format is documented as integer 1-25 (not normalized) in the README template
- [ ] This pipeline's own README is updated with the standardized anchors

## Scoring Breakdown

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Edge | 4 | Consistent scoring is key to meaningful prioritization |
| Fitness | 4 | Directly impacts how well the pipeline dispatches work |
| Parsimony | 4 | Simple change — add anchor text to existing rubric |
| Testability | 4 | Can test by having two agents score the same entity |
| Novelty | 3 | Rubric anchoring is a known technique, applied to agent context |

## Open Questions (Resolved)

- **Q: Should scoring be mandatory?** A: No. The schema already marks score as optional. Some pipelines won't need prioritization.
- **Q: Should we allow custom rubric dimensions?** A: Not in v0. The 5-dimension rubric is part of the commission template. Custom dimensions can be a v1 feature.
