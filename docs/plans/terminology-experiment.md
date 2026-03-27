---
id: 058
title: Experiment — nautical terminology vs business English performance comparison
status: backlog
source: CL
started:
completed:
verdict:
score:
worktree:
---

Does the Star Trek / nautical terminology (captain, first officer, ensign, commission, refit) help or hurt agent performance compared to plain business English (user, orchestrator, worker, setup, upgrade)?

## Hypothesis

The metaphor may aid agent role adherence (an "ensign" knows its place in the hierarchy better than a "worker"), or it may confuse models that over-index on the fiction. We don't know — need to measure.

## Design

1. **Pick a benchmark** — a reproducible task set that exercises the full pipeline (commission → dispatch → stage work → gate → merge). Candidates:
   - The existing commission test harness (batch mode, 65 checks)
   - The checklist E2E test (full first-officer → ensign cycle)
   - A new purpose-built benchmark with scoring dimensions (adherence to role, quality of output, protocol compliance, error rate)

2. **Create a variant** — fork the templates with nautical terminology replaced by business English:
   - captain → user / operator
   - first officer → orchestrator / coordinator
   - ensign → worker / executor
   - lieutenant → specialist
   - commission → setup / initialize
   - refit → upgrade / update
   - bridge / conn → dashboard

3. **Run both variants** — same tasks, same seed entities, same model, same parameters. Multiple runs for statistical significance.

4. **Measure** — compare on:
   - Protocol compliance (does the agent follow its role boundaries?)
   - Gate adherence (does the orchestrator self-approve?)
   - Task quality (do stage reports meet checklist items?)
   - Error rate (crashes, wrong file edits, frontmatter corruption)
   - Token usage (does one variant produce more verbose output?)

## Prerequisites

- Decide on the benchmark before building the variant
- The benchmark needs to be deterministic enough to compare across runs
- Budget: each run costs ~$1-2, need at least 5 runs per variant = ~$10-20 total
