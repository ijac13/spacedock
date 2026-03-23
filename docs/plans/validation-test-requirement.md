---
title: Validation pilots must run the test harness
status: backlog
source: testflight-005
started:
completed:
verdict:
score: 0.72
worktree:
---

Validation pilots currently do code review only — they don't run the test harness script even when the entity changes SKILL.md or the first-officer template. The README says "Use the test harness for any entity that changes SKILL.md" but nothing in the pilot dispatch enforces this.

Additionally, the first officer itself should not run tests directly (it's a dispatcher, not a worker). Test execution should be delegated to the validation pilot or a dedicated test-runner.

Two possible fixes:
- Update the validation pilot prompt to explicitly include "run v0/test-commission.sh" as a required step
- Have the first officer dispatch a separate test-runner pilot after validation

The simpler approach (updating the pilot prompt) is likely sufficient for v0.
