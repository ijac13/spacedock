---
title: More Deterministic Test Harness
status: implementation
source: commission seed
started: 2026-03-23T02:05:00Z
completed:
verdict:
score: 0.82
worktree: .worktrees/pilot-deterministic-test-harness
---

The current test harness (`claude -p` with batch mode) produces non-deterministic output — each run generates slightly different README prose, status script implementations, and first-officer phrasing. This makes regression testing difficult: you can check structural properties (files exist, frontmatter valid, columns present) but not whether a fix actually changed the output.

## Problem Areas

- No way to diff test runs meaningfully
- Can't tell if a skill change improved or regressed output quality
- Validation is heuristic (grep for sections) rather than structural
- No stored baseline to compare against
- Model version, temperature, and prompt caching all affect output

## What We Learned (testflight-004/005)

We added guardrail checks to `v0/test-harness.md` (TeamCreate, Agent-tool-required, subagent_type prohibition, report-once, absolute path detection) and ran the test harness successfully. Key findings:

1. **Structural grep checks work well for guardrails.** Checking that specific strings exist in generated output is reliable — the LLM faithfully transfers template content. All 4 guardrails were present in the generated first-officer.md.

2. **The test harness catches template regressions but not runtime failures.** The generated first-officer had all guardrails, yet a testflight still showed the first-officer failing to dispatch. The template was correct; the agent ignored its own instructions. Static validation can't catch that.

3. **The batch-mode commission + grep pipeline is the practical v0 test.** `claude -p` with `--plugin-dir` runs in ~30s. Grep-based assertions cover the invariant parts. This is good enough for regression testing template changes.

## Directions to Explore

- Structural assertions: parse YAML frontmatter, verify stage count, check required README sections via AST rather than grep
- Golden file testing: store a blessed output, diff structurally (ignore prose, compare schema)
- Deterministic seed: fix model temperature to 0, pin model version in test metadata
- Checksums on invariant portions: frontmatter schema shape, stage names, approval gates should be byte-identical across runs
- Test artifact storage: capture source skill SHA, model version, prompt hash alongside each test run for reproducibility
- End-to-end runtime test: commission + launch first-officer + verify it dispatches a pilot correctly (not just generates correct files)

## Implementation Summary

Added `v0/test-commission.sh` — an executable bash script that automates the full test harness. The script:

1. Runs batch-mode commission via `claude -p` with `--plugin-dir` in a temp directory
2. Validates ~30 checks covering: file existence (6 files), status script output (header + 3 entity rows), entity frontmatter (YAML delimiters, title, status per entity), README section completeness, first-officer structure (frontmatter, dispatcher identity, startup sequence, Agent() call, event loop, pipeline path, auto-start), all 4 guardrails (Agent-tool-required, subagent_type prohibition, TeamCreate, report-once), leaked template variables, and absolute paths
3. Reports PASS/FAIL per check with a final summary
4. Cleans up on success; preserves test dir + logs on failure for inspection
5. Exits 0 on all-pass, non-zero on any failure

Updated `v0/test-harness.md` to reference the script at the top.

## Validation Report

**Verdict: PASSED**

Code review of `v0/test-commission.sh` (291 lines) against acceptance criteria:

### Checks Covered (all from test-harness.md section 3)

| Category | Checks | Result |
|----------|--------|--------|
| File existence | README, status, 3 entities, first-officer.md | PASS (6 checks) |
| Status script | Runs, produces output, has header, shows 3 entities | PASS (3 checks) |
| Entity frontmatter | Opening `---`, `title:`, `status: ideation` per entity | PASS (9 checks) |
| README completeness | 6 section keywords + 4 stage names | PASS (10 checks) |
| First-officer completeness | Frontmatter (name, tools), 6 content keywords | PASS (8 checks) |
| First-officer guardrails | Agent-tool-required, subagent_type, TeamCreate, report-once | PASS (4 checks) |
| Leaked template variables | `{variable_name}` pattern excluding `${...}` | PASS (1 check) |
| Absolute paths | `/Users/`, `/home/`, `/tmp/` in .md files and status script | PASS (2 checks) |

### Structural Requirements

- Temp directory via `mktemp -d`: PASS (line 7)
- `--plugin-dir` passed to `claude -p`: PASS (line 65)
- Cleanup on success via `trap cleanup EXIT`: PASS (lines 12-14)
- Preserves test dir on failure for inspection: PASS (lines 285-286)
- Exit 0 on success, exit 1 on failure: PASS (lines 287-289)
- `test-harness.md` references the script: PASS (lines 10-18 of test-harness.md)

### Minor Gaps (non-blocking)

1. README section checks cover 6 of ~9 documented sections (missing explicit checks for "Mission", "Approval Gates", "Pipeline State")
2. First-officer checks miss "description:" in frontmatter and "State Management" section
3. Entity frontmatter checks skip closing `---` delimiter and score field
4. Template variable regex only matches lowercase+underscore

These are minor — the script covers all critical structural checks and all 4 guardrails. The ~30 checks provide solid regression coverage for template changes.
