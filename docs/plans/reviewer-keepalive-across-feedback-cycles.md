---
id: 141
title: Reviewer keepalive across feedback cycles
status: backlog
source: FO observation during task 140 rejection routing on 2026-04-12
score: 0.63
started:
completed:
verdict:
worktree:
issue:
pr:
---

The current feedback-routing behavior preserves the `feedback-to` target worker when possible, but it shuts down the reviewer/validator once that stage report is consumed. That matches the narrow current contract, yet it leaves reuse value on the table: after implementation addresses validation findings, the next step is often to run the same reviewer again. If the reviewer thread is still addressable and has enough context budget, keeping it alive could shorten the next cycle and reduce repeated bootstrapping.

This task should define when a completed reviewer should remain addressable across a rejection cycle and when it should still be shut down. The design must stay disciplined: keepalive is an optimization, not a license to keep every completed worker around indefinitely. The first officer still needs a clear ownership rule for which worker is the primary `feedback-to` target and which retained reviewers are optional for later reuse.

## Desired Direction

- Preserve the implementation worker as the primary `feedback-to` target exactly as today.
- Consider retaining the reviewer handle across the bounce when all of these hold:
  - the reviewer is still addressable
  - the next expected step after fixes is to re-run the same reviewer
  - context budget remains acceptable
  - there is no conflicting routing need that makes the retained reviewer misleading or expensive
- Shut the reviewer down explicitly when those checks fail or when the feedback cycle ends.

## E2E Requirement

This task needs live end-to-end evidence, not just static wording checks. The implementation must include a Codex-path E2E that proves:

1. implementation is rejected by validation
2. findings route back to implementation
3. implementation completes a follow-up fix cycle
4. the same reviewer handle is reused for the second validation pass when keepalive conditions allow it
5. the reviewer is shut down explicitly once it is no longer needed

The test should also document its specific purpose and coverage intention so future validation can tell whether it proves reviewer keepalive itself or only generic rejection routing.
