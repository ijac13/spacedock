---
id: 154
title: "Refresh live-test assertions against post-#085 skill-preloading scaffolding (test_commission and peers)"
status: implementation
source: "PR #94 (#148 pytest migration) cycle-5 CI — pytest-parallel surfaced previously-masked content-drift failures across 8 claude live tests + 1 codex live test"
started: 2026-04-15T05:18:01Z
completed:
verdict:
score: 0.70
worktree: .worktrees/spacedock-ensign-refresh-live-test-assertions-after-skill-preload
issue:
pr: #131
mod-block: merge:pr-merge
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

## Scope corrections (from ideation refinement)

Two corrections to the provisional draft above, verified by direct codebase inspection:

1. **`test_team_health_check` does not exist.** No file named `test_team_health_check.py` is under `tests/`, and no test function by that name exists. The closest match is `tests/test_team_fail_early.py`, but that file is NOT marked `xfail` for #154 — it already reads from `skills/first-officer/references/claude-first-officer-runtime.md` directly (line 21) and is presumed passing. The affected-tests table entry for `test_team_health_check` is dropped from scope. Actual #154-tagged test count: **7**, confirmed by `grep -rln "pending #154" tests/`.
2. **`test_codex_packaged_agent_e2e` is out of scope.** Its `xfail` marker cites #161 (codex reused-wait text drift), not #154 — separate root cause per the dispatch prompt's caveat. No assertions in it target the content locations #085 moved. Dropped from #154 entirely; handled by #161.

The seven in-scope tests (each currently `xfail` with `reason="pending #154"`):

- `tests/test_commission.py::test_commission`
- `tests/test_agent_captain_interaction.py::test_agent_captain_interaction`
- `tests/test_output_format.py::test_output_format`
- `tests/test_reuse_dispatch.py::test_reuse_dispatch`
- `tests/test_repo_edit_guardrail.py::test_repo_edit_guardrail`
- `tests/test_dispatch_completion_signal.py::test_dispatch_completion_signal`
- `tests/test_checklist_e2e.py::test_checklist_e2e`

## Content-home mapping (post-#085)

The references live under `skills/first-officer/references/`, not top-level `references/` as the task prompt suggested. Verified paths:

- `agents/first-officer.md` — 15-line wrapper; contains only `name:` frontmatter, `DISPATCHER` keyword, boot instructions
- `skills/first-officer/SKILL.md` — skill entry point
- `skills/first-officer/references/first-officer-shared-core.md` — runtime-neutral core: FO Write Scope, Output Format rules, feedback-to, _archive, reuse conditions, dispatch-fresh, subagent_type guardrail, self-approve guardrail, `mods/*.md` discovery
- `skills/first-officer/references/claude-first-officer-runtime.md` — Claude adapter: `TeamCreate`, `Agent(`, `Event Loop`, `Fresh` property, `name=.*{stage}` dispatch-name pattern, fall back wording
- `skills/first-officer/references/codex-first-officer-runtime.md` — Codex adapter: `Fresh`, `feedback-to`, `_archive`, `mods/*.md`
- `skills/first-officer/references/code-project-guardrails.md` — FO Write Scope enforcement & cross-ref

Per-token residence confirmed by grep:

| Token asserted by test | Lives in (post-#085) |
|---|---|
| `DISPATCHER` | `agents/first-officer.md` (wrapper) |
| `TeamCreate` | `claude-first-officer-runtime.md` |
| `Agent(` | `claude-first-officer-runtime.md` |
| `Event Loop` | `claude-first-officer-runtime.md` |
| `initialPrompt` | NOT PRESENT anywhere — resurface or delete (see per-test notes) |
| `MUST use the Agent tool` | NOT PRESENT literally — assertion wording must shift |
| `subagent_type` guard | `first-officer-shared-core.md`, `claude-first-officer-runtime.md` |
| `Report.*ONCE` | NOT PRESENT literally — assertion wording must shift |
| `self-approve` guard | `first-officer-shared-core.md`, `claude-first-officer-runtime.md` |
| `Fresh` stage property | `claude-first-officer-runtime.md`, `codex-first-officer-runtime.md` |
| `feedback-to` | shared-core + both runtimes |
| `_archive` | shared-core + `codex-first-officer-runtime.md` |
| `mods/*.md` | shared-core + both runtimes |
| `## FO Write Scope` + allow/prohibit lists | `first-officer-shared-core.md` (cross-referenced by `code-project-guardrails.md`) |
| `Output Format` + `fall back` | shared-core + claude runtime |
| `dispatch fresh` | `first-officer-shared-core.md` |
| `name=.*{stage}` dispatch-name | `claude-first-officer-runtime.md` |
| `stages` frontmatter read step | shared-core + claude runtime |

The three tokens flagged "NOT PRESENT literally" (`initialPrompt`, `MUST use the Agent tool`, `Report.*ONCE`) need a judgement call at implementation time: either restore the exact wording to shared-core (if the guarantee is still binding) or delete the assertion with a one-line rationale comment citing the equivalent-in-spirit assertion that already passes.

## Per-test refresh mapping

| Test | Current source of truth | Strategy | Notes |
|---|---|---|---|
| `test_commission` | `fo_path = t.repo_root / "agents" / "first-officer.md"` (line 26) + raw `fo_text = fo_path.read_text()` across 5 sections | **Assembled-contract swap**: replace `fo_text = fo_path.read_text()` with `fo_text = assembled_agent_content(t, "first-officer")`. Keep `fo_path` only for existence check (line 74). Preserve frontmatter-scoped checks on `fo_head20`: those must still read the wrapper, so use `fo_path.read_text()` for `fo_head20` specifically (lines 138-142). All other `fo_text` references shift to assembled. For `initialPrompt`, `MUST use the Agent tool`, `Report.*ONCE`: delete each with a one-line `# removed: token superseded by <equivalent> in assembled contract` comment, OR re-add the token to shared-core if still binding (author's call at impl time). | Heaviest refactor. 19 inner failures maps to the 5 `[First-Officer *]` check groups. |
| `test_agent_captain_interaction` | Live dispatch test. Grep shows no direct read of `agents/first-officer.md`. The 1/4 failure is likely in SendMessage-target validation or token drift in captured output | **Dispatch-log assertion check, not content swap**: verify whether Phase 3's `fo_sm_calls` / shutdown-pattern regex is the failing assertion. If so, the "skill-preload content drift" framing is wrong for this test — the failing behavior is runtime-dispatch output, not content presence. At impl time, run the test once, identify the single inner-failure string, and either (a) refresh the regex or (b) reclassify this test out of #154. Static fallback: if any assertion does grep FO content, swap to `assembled_agent_content`. | 1/4 suggests a single runtime-output assertion drifted. May partially deflect to a sibling task. |
| `test_output_format` | Already uses `assembled_agent_content(t, "first-officer")` at line 33 | **Already correct; investigate drift**: the 1-2/11 inner failures are not about content home. Both `"Output Format"` and `"fall back"` tokens exist in shared-core (line 47) and claude runtime (line 109). Run the test once at impl time, log which `t.check` call fails, and fix the target assertion (likely runtime output format in Phase 2/3, not static content). | Could be a no-op from #154's perspective — verify at impl time. |
| `test_reuse_dispatch` | Already reads `skills/first-officer/references/first-officer-shared-core.md` and `claude-first-officer-runtime.md` directly + `assembled_agent_content` at lines 147-149 | **Already correct path-wise; investigate runtime drift**: 2-3/17-18 inner failures are likely runtime-behavior drift (Phase 3 validation of reuse vs fresh dispatch), not stale content paths. At impl time, identify which t.check fires and address locally (may be token wording in shared-core or a runtime adapter tweak). | Near-no-op for path refresh. |
| `test_repo_edit_guardrail` | Uses `assembled_agent_content(t, "first-officer")` at line 49. Lines 50-68 check `## FO Write Scope` section and cross-ref | **Already correct; verify FO Write Scope presence**: grep confirms `## FO Write Scope` exists in shared-core. 2/8 inner failures are almost certainly the runtime-behavior checks (Phase 4 code-edit guardrail), not static assertions. Minimal static fix; defer behavioral fixes to a sibling task if out-of-scope for #154. | Verify at impl time which inner check fires. |
| `test_dispatch_completion_signal` | Live dispatch test. Grep shows no static content read | **No content-home swap needed**: this is a pure runtime test validating FO exit code and ensign-dispatch signaling. The 1/5 failure is runtime behavior, not content drift. **Recommend reclassifying out of #154's scope** — the `xfail` marker may have been auto-added in #148 cycle 6 without verifying the root cause. Drop xfail and rerun; if it still fails, open a fresh task. | Probably mis-tagged as #154. |
| `test_checklist_e2e` | Live dispatch test. Grep shows no static content read from FO agent file | **No content-home swap needed**: like `test_dispatch_completion_signal`, this validates runtime checklist protocol in dispatch output. 1/9 inner failure is a dispatch-prompt-format check (lines 113-129). **Likely mis-tagged as #154**; recommend reclassification after trial run. | Probably mis-tagged. |

**Strategy summary**: 3 tests (commission, output_format, repo_edit_guardrail) are genuine static-content-drift candidates; `assembled_agent_content` is the primary tool. 2 tests (reuse_dispatch, agent_captain_interaction) are partly static and partly runtime. 2 tests (dispatch_completion_signal, checklist_e2e) appear mis-tagged — their failure mode is runtime behavior, not content drift; impl phase should validate and reclassify.

## Acceptance criteria

**AC-1 — `test_commission` passes ≥63/65 checks on `make test-live-claude` with the `#154` xfail marker removed.**
Verified by: `uv run pytest tests/test_commission.py::test_commission -m live_claude -v` under `LIVE_CLAUDE=1`, observing 0 `xfail` and `pass` (or ≤2 non-#154 inner failures attributable to unrelated drift, documented in a follow-up task).

**AC-2 — `test_agent_captain_interaction` passes 4/4 checks on `make test-live-claude` with the `#154` xfail marker removed or reclassified.**
Verified by: `uv run pytest tests/test_agent_captain_interaction.py -m live_claude -v`. If the single inner failure is runtime behavior drift (not content home), AC is met by reclassifying the xfail to a new task ID.

**AC-3 — `test_output_format` passes ≥10/11 checks with `#154` xfail removed.**
Verified by: `uv run pytest tests/test_output_format.py -m live_claude -v`. Phase-1 static checks (lines 34-43) must all pass against `assembled_agent_content`.

**AC-4 — `test_reuse_dispatch` passes ≥16/18 checks with `#154` xfail removed.**
Verified by: `uv run pytest tests/test_reuse_dispatch.py -m live_claude -v`. The static checks at lines 147-171 (shared-core + runtime paths) must all pass; remaining variance is runtime behavior.

**AC-5 — `test_repo_edit_guardrail` passes ≥7/8 checks with `#154` xfail removed.**
Verified by: `uv run pytest tests/test_repo_edit_guardrail.py -m live_claude -v`. Phase-1 FO Write Scope static checks (lines 50-68) must all pass.

**AC-6 — `test_dispatch_completion_signal` and `test_checklist_e2e` xfail markers for `#154` are either removed (if passing) or reclassified to a different task-id with a one-line comment stating the real root cause.**
Verified by: `grep -rln "pending #154" tests/` returning at most the 5 genuinely content-drifted tests after impl, with the two reclassified tests carrying a distinct task reference.

**AC-7 — No `@pytest.mark.xfail` or `@pytest.mark.skip` marker in `tests/` cites `#154` after merge, except deletions replaced by `#161`-or-other task IDs.**
Verified by: `grep -rln "pending #154" tests/` returns empty (or returns only reclassified entries pointing at new task IDs).

**AC-8 — No assertion misrepresents a content home. Every `read_text` / `file_contains` / `in fo_text` call in the seven in-scope tests either (a) reads the wrapper for wrapper-scoped checks, (b) reads the assembled contract via `assembled_agent_content` for behavioral checks, or (c) reads a specific reference file by absolute skill-relative path.**
Verified by: static review of the diff in PR; `grep -n "agents/first-officer.md" tests/test_{commission,agent_captain_interaction,output_format,reuse_dispatch,repo_edit_guardrail,dispatch_completion_signal,checklist_e2e}.py` — each remaining match must be either an existence check (`fo_path.is_file()`) or a deliberate wrapper-scoped frontmatter check.

**AC-9 — Three "literally absent" tokens (`initialPrompt`, `MUST use the Agent tool`, `Report.*ONCE`) are each resolved: either re-added to shared-core if still a binding guarantee, or the asserting line is deleted with a one-line rationale comment citing the superseding assertion.**
Verified by: `grep -rn 'initialPrompt\|MUST use the Agent tool\|Report.*ONCE' skills/first-officer/ tests/test_commission.py` — each token either appears in the skill layer or does not appear in the assertion list; no orphan assertions remain.

**AC-10 — `make test-live-claude` exits 0 against a Claude Haiku runtime, and `make test-live-claude-bare` exits 0 (or each remaining red test has a distinct task-id-cited xfail).**
Verified by: CI run on the implementation PR; local spot-check by CL.

## Test plan

### Cost estimate

- **Static verification (free, ~30s)**: For each of the 7 tests, `uv run pytest ... --collect-only` + a dry `assembled_agent_content` invocation (offline) validates that the assertion refresh targets existing tokens. No Claude API calls.
- **Live spot-check (per test, ~60-180s)**: Each in-scope test carries `@pytest.mark.live_claude`; running the full file under `LIVE_CLAUDE=1` costs ~$0.10-$1.00 per invocation depending on model and fixture scope. Haiku is the default per `test_commission`'s model fallback logic.
- **Full suite**: `make test-live-claude` runs the 7 tests in parallel (pytest-xdist per #148). Estimated wall time 5-10 min; estimated cost ~$3-$8 on Haiku. Opus run of `test_commission` alone ~$5-$15.

### Cheapest-shape-that-proves-it per test

| Test | Cheapest validation |
|---|---|
| `test_commission` | Static: run the Phase-1/2 static checks (file-existence + `assembled_agent_content` token grep) offline by temporarily skipping the `subprocess.run(['claude', ...])` block. Live: one Haiku run (~$0.30) proves the full flow. |
| `test_agent_captain_interaction` | Live-only — depends on FO dispatch. Haiku, ~60s, ~$0.20. |
| `test_output_format` | Static Phase-1 checks (lines 30-43) prove the content-home refresh. Live Phase-2/3 runs (~$0.50) are needed for runtime-output assertions. |
| `test_reuse_dispatch` | Static checks on shared-core + runtime (lines 147-171) prove the path refresh offline. Live phase (~$1) validates reuse behavior. |
| `test_repo_edit_guardrail` | Static Phase-1 `## FO Write Scope` check (line 50) proves the refresh offline. Live phase (~$0.50) validates guardrail behavior. |
| `test_dispatch_completion_signal` | Live-only. Haiku, ~$0.20. Expected: no assertion refresh needed — re-run and reclassify if fails. |
| `test_checklist_e2e` | Live-only. Haiku, ~$0.30. Expected: same as above. |

**Spot-check budget**: $5 on Haiku is sufficient to validate per-test refresh lands. Opus run optional for `test_commission` as final sign-off.

### E2E coverage rationale

Static checks cover the content-home-refresh intent. Live dispatch is required for the three "behavioral" failures (AC-2, AC-6 tests) because they validate runtime FO behavior, not stored content. The #148 xfail markers were added without distinguishing static-content drift from runtime drift; the ideation-refined ACs above separate them explicitly so impl can land the static-content fix (cheap, deterministic) and defer runtime behavior to sibling tasks if they surface.

### Out of scope (confirmed)

- No scaffolding changes under `skills/`, `references/`, or `agents/` (per dispatch prompt)
- No YAML frontmatter changes in this entity
- `test_codex_packaged_agent_e2e` — handled by #161
- `test_team_health_check` — does not exist; dropped
- First-officer runtime behavior — sibling tasks if runtime-drift surfaces

## Stage Report

1. **Convert AC block to #193 entity-level format** — **DONE**. Replaced the provisional 4-bullet AC list with 10 `**AC-N — {end-state property}**` items, each followed by `Verified by:` referencing a concrete `pytest` invocation, grep check, or CI signal. Each AC names a post-merge repo property, not a stage action.
2. **Per-test mapping table** — **DONE**. Added a 7-row table naming the current source-of-truth file for each test's assertions, a 1-line strategy per test (path-swap / assembled-contract grep / reclassify), and a strategy summary. Corrected two errors in the provisional draft: `test_team_health_check` does not exist (dropped); `test_codex_packaged_agent_e2e`'s `xfail` cites #161, not #154 (dropped). The task prompt's reference paths (`references/first-officer-shared-core.md`) were wrong — actual home is `skills/first-officer/references/`; corrected throughout. Three tokens asserted by `test_commission` (`initialPrompt`, `MUST use the Agent tool`, `Report.*ONCE`) are not literally present in any skill file — AC-9 calls for impl-time resolution (restore-or-delete-with-rationale).
3. **Test plan refined** — **DONE**. Cost estimate: ~$3-$8 Haiku for full `make test-live-claude`; ~$5 spot-check budget for iterating. Per-test cheapest-validation-shape table specifies which checks are static (free) and which require live dispatch. E2E rationale explains why 3 tests need live FO runs and why the other 4 can be validated statically first.

### Summary

Refined #154 from a provisional 4-bullet draft to a gate-ready spec under #193's AC-vs-checklist discipline. Dropped 2 out-of-scope tests (`test_team_health_check` doesn't exist; `test_codex_packaged_agent_e2e` belongs to #161). Verified content homes post-#085 and built a per-test strategy table distinguishing genuine static-content-drift (3 tests), partial (2 tests), and mis-tagged (2 tests) failures. 10 entity-level ACs defined with concrete verification commands; test plan budgets ~$5 on Haiku for spot-checking. Impl phase should land static-content swaps to `assembled_agent_content` first (cheap, deterministic), then run live tests and reclassify runtime-drift failures to sibling tasks.
