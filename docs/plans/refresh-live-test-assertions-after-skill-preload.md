---
id: 154
title: "Refresh live-test assertions against post-#085 skill-preloading scaffolding (test_commission and peers)"
status: ideation
source: "PR #94 (#148 pytest migration) cycle-5 CI — pytest-parallel surfaced previously-masked content-drift failures across 8 claude live tests + 1 codex live test"
started: 2026-04-15T05:18:01Z
completed:
verdict:
score: 0.70
worktree:
issue:
pr:
---

The #148 pytest migration surfaced a class of test failures that had been masked by the pre-migration Makefile's `&&` short-circuit. The failures are deterministic (identical counts across concurrency modes and models — 19/65 on `test_commission` on claude-live, claude-live-bare, and claude-live-opus), not concurrency-induced, and not caused by #148's harness. They are **pre-existing test-content drift**: the tests assert that `agents/first-officer.md` contains tokens like `TeamCreate`, `Agent(`, `Event Loop`, `initialPrompt`, `Fresh stage property`, `feedback protocol instructions`, `_archive convention`, `discovers plugin-shipped mods`, etc.

After task #085 ("agent boot via skill preloading") landed, `agents/first-officer.md` became a 15-line thin wrapper pointing at the `spacedock:first-officer` skill. The heavy content — including every token the tests look for — lives in `skills/first-officer/SKILL.md`, `references/first-officer-shared-core.md`, `references/claude-first-officer-runtime.md`, `references/codex-first-officer-runtime.md`. The tests were not updated to follow the content to its new home.

## Affected tests

Observed failing on PR #94 CI run 24435674557:

| Test | claude-live (haiku teams) | claude-live-bare (haiku bare) | claude-live-opus (opus teams) |
|------|---------------------------|-------------------------------|-------------------------------|
| `test_commission` | 19/65 | 19/65 | 19/65 |
| `test_agent_captain_interaction` | 1/4 | 1/4 | 1/4 |
| `test_output_format` | 2/11 | 1/11 | 1/11 |
| `test_reuse_dispatch` | 2/18 | 3/17 | 2/18 |
| `test_team_health_check` | 1/7 | — (bare deselects) | 1/7 |
| `test_repo_edit_guardrail` | 2/8 | — | 2/7 |
| `test_dispatch_completion_signal` | 1/5 | — | — |
| `test_checklist_e2e` | 1/9 | — | — |

Also relevant on codex-live:

| Test | codex-live |
|------|-----------|
| `test_codex_packaged_agent_e2e` | 3/25 |

Inner-check failure counts ≤ 3 on most tests suggest only a handful of assertions per test target stale content locations; the test cores themselves are intact. `test_commission` is the outlier at 19/65 — it was always the heaviest contract test.

## Problem Statement

Every failing assertion expects specific tokens to live in `agents/first-officer.md`. After #085, those tokens live in the skill file and references. The tests need to:

1. Identify which assertions target content that moved into the skill layer
2. Update the assertions to read the correct file(s) or the assembled contract (first-officer wrapper + skill content + referenced files)
3. Delete assertions that are genuinely obsolete (if any)

No change to the actual first-officer behavior is required. This is a test-content-refresh pass.

## Desired Outcome

Each failing test passes against the current scaffolding, OR its failing assertions are deliberately deleted with a one-line rationale in a comment. The pytest-marker skip/xfail decorators added on #148 cycle 6 are removed as each test is unblocked. After all tests refresh, `make test-live-claude` / `make test-live-claude-bare` / `make test-live-codex` go green.

## Out of Scope

- No change to first-officer runtime behavior
- No change to commission generation logic
- No change to the #148 pytest harness or marker scheme
- Codex-specific `test_codex_packaged_agent_e2e` failures may have a different root cause (codex doesn't share the skill-preload architecture) — investigate separately within this task or spin off

## Prior Art

- Task #085 — agent boot via skill preloading (scaffolding refactor)
- Task #088 — restore initialPrompt (partial acknowledgment that #085 stripped content)
- Task #148 — pytest migration (exposed the drift)

## Acceptance criteria (provisional — finalize in ideation)

- Each test in the affected-tests table above passes on `make test-live-claude` (or `test-live-claude-bare`) under CI conditions
- The `@pytest.mark.xfail` / `@pytest.mark.skip` markers that will be added on #148 cycle 6 are all removed
- No new assertions lie about where content lives — assertions target the file that actually contains the tokens
- `test_commission`'s 19 failures addressed explicitly — either the assertions move to target the skill / references, or they are deleted with rationale
