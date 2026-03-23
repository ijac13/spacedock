---
title: More Deterministic Test Harness
status: ideation
source: commission seed
started:
completed:
verdict:
score: 0.82
---

The current test harness (`claude -p` with batch mode) produces non-deterministic output — each run generates slightly different README prose, status script implementations, and first-officer phrasing. This makes regression testing difficult: you can check structural properties (files exist, frontmatter valid, columns present) but not whether a fix actually changed the output.

## Problem Areas

- No way to diff test runs meaningfully
- Can't tell if a skill change improved or regressed output quality
- Validation is heuristic (grep for sections) rather than structural
- No stored baseline to compare against
- Model version, temperature, and prompt caching all affect output

## Directions to Explore

- Structural assertions: parse YAML frontmatter, verify stage count, check required README sections via AST rather than grep
- Golden file testing: store a blessed output, diff structurally (ignore prose, compare schema)
- Deterministic seed: fix model temperature to 0, pin model version in test metadata
- Checksums on invariant portions: frontmatter schema shape, stage names, approval gates should be byte-identical across runs
- Test artifact storage: capture source skill SHA, model version, prompt hash alongside each test run for reproducibility
