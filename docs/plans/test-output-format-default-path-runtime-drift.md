---
id: 195
title: "test_output_format default-path runtime drift (entity ID + verdict mentions)"
status: backlog
source: "PR #131 CI (#154 cycle-1 pre-merge) — after #154 lifted the misattributed `pending #154` xfail, `test_output_format` still fails live on 2/11 checks against claude-live, claude-live-bare, claude-live-opus"
started:
completed:
verdict:
score: 0.55
worktree:
issue:
pr:
mod-block:
---

## Problem

`tests/test_output_format.py` Phase 3 (default output format, entity starts at backlog) runs the FO against `output-format-default` fixture and captures `log_default.fo_texts()`. Two assertions fail:

- **`default output mentions entity ID (001)`** (line 98) — `"001" in default_output` fails — FO output does not mention the entity ID when the fixture has no `## Output Format` section and should fall back to default.
- **`default output mentions verdict`** (line 100) — regex `PASSED|REJECTED` misses.

Phase 1 static checks and Phase 2 custom-format checks PASS; the drift is specifically in the default-path FO output.

## Candidate root causes

1. Default FO output format may have changed post-#085 — the shared-core / claude-runtime "fall back" path no longer emits entity ID + verdict in the terminal message.
2. The FO might be terminating the single-entity flow before the final output line in default-path budget.
3. `read_entity_frontmatter` shows entity reaches `status: done` (passes), so the workflow completes — but the terminal output may be structured differently now.

## Out of scope for #154

#154 was test-assertion-refresh against skill-preload content homes. The Phase-3 failures here are FO runtime behavior on the default fall-back output format, not a content-home drift. Refresh pass confirmed Phase-1 static checks are correct.

## Acceptance criteria (provisional)

- `test_output_format` passes ≥10/11 on `make test-live-claude` (all three claude variants)
- Root cause documented (default output format change, budget cap, or assertion specificity) and fix lands in the right layer (FO runtime, test assertion, or fixture)
