---
id: 180
title: "Fix extra_args plumbing so workflow model_override reaches claude -p in live tests"
status: done
source: "from #177 implementation outcome (AC-3 BROKEN, 2026-04-17 session) — workflow input model_override=claude-opus-4-6 was silently dropped because tests/test_standing_teammate_spawn.py:72 hardcodes --model opus and ignores pytest's --model CLI option"
started: 2026-04-17T02:47:24Z
completed: 2026-04-17T03:15:47Z
verdict: REJECTED
score: 0.7
worktree: 
issue:
pr:
mod-block:
---

## Why this matters

This task is the critical-path unblocker for the opus-4-7 cluster (#177, #178, #172):

- **#177** can't conclude its experiment until AC-3 (opus-4-6 negative control) actually runs on opus-4-6. Without that control, we cannot distinguish "boilerplate didn't fix opus-4-7" from "test broken on the stacked branch."
- **#178** can't merge until #177 either confirms the boilerplate works (currently falsified at low/medium per #177's AC-1/AC-2) or we have a clean recommendation in hand.
- **#172** can't reach Layer-3-green CI until claude-live-opus stops failing — which requires either #178 (currently falsified) or pinning opus-4-6 in CI workflow defaults — which requires this plumbing fix to land first so the pin can be proven to work.

## The bug

`tests/test_standing_teammate_spawn.py` at line 72 (and likely other live tests in the same file or neighbors) hardcodes:

```python
extra_args=["--model", "opus", "--effort", effort, "--max-budget-usd", "2.00"]
```

`tests/conftest.py:25,107` already exposes a `--model` pytest CLI option that propagates from `runtime-live-e2e.yml`'s `model_override` workflow input. The plumbing exists; the live test just doesn't consume it.

Result: any CI dispatch with `model_override=claude-opus-4-6` is silently downgraded to `--model opus`, which under Claude Code 2.1.111+ resolves to `claude-opus-4-7`. The model_override workflow input is currently a no-op for this test.

## Proposed fix

Replace the hardcoded `--model opus` in `tests/test_standing_teammate_spawn.py` `extra_args` lists with the value of pytest's `--model` option (defaulting to `opus` if unset, to preserve current behavior). Audit other live tests in `tests/` for the same hardcoding pattern and apply the same fix.

Once landed, re-dispatch #177's AC-3 and confirm the run's `fo-log.jsonl` `assistant.message.model` stamps show `claude-opus-4-6`.

## Out of Scope

- Changing the default model. The fix preserves `--model opus` as the default; only `model_override` cases change behavior.
- Investigating WHY opus-4-7 hallucinates (that's #177's surface).
- Deciding whether to pin opus-4-6 in CI (that's a follow-up after this lands and #177 re-runs cleanly).

## Cross-references

- #177 (opus-4-7 ensign hallucination scope) — this fix unblocks #177's AC-3 negative control
- #178 (tool-call-discipline boilerplate) — disposition depends on #177's clean rerun
- #172 (lazy-spawn) — merge waits on either #178 shipping or opus-4-6 pin landing, both downstream of this fix
- #176 (model_override workflow input) — this is the documented "extra_args plumbing follow-up" referenced in #176's design

## Test plan (for ideation to expand)

- Static test verifying any live test with `extra_args` containing `--model` sources from pytest's `--model` option.
- Re-dispatch of #177's AC-3 after the fix lands, with model stamp verification, as the live integration test.

## Stage Report (implementation)

### Headline

**No code change required — the bug described in this entity's spec is already fixed in the codebase.** The fix landed earlier as commit `44f09373` ("fix: #179 plumb model fixture into extra_args in test_standing_teammate_spawn.py") on `origin/spacedock-ensign/fix-extra-args-model-plumbing`, and is present on `main` and on this worktree's branch base. All other live tests that build `extra_args` lists with `--model` already source the value from the `model` pytest fixture as well. #180 appears to have been filed against a stale view of the code (likely from #177's AC-3 BROKEN session, before #179 had landed or been observed).

This report documents verification of the present state and surfaces the duplicate-fix conclusion to the validator and FO. **No commit was made on the worktree branch** because there is nothing to change. Strange things are afoot at the Circle K — flagging per CLAUDE.md Rule #1.

### Checklist

1. **DONE** — Read entity body in full (`/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-model-override-plumbing-fix/docs/plans/model-override-plumbing-fix.md`). Spec is in 'The bug' (line 24) and 'Proposed fix' (line 36).

2. **FAILED (bug not present)** — `grep -n 'extra_args' tests/test_standing_teammate_spawn.py` from worktree root returned a single match:
   ```
   72:        extra_args=["--model", model, "--effort", effort, "--max-budget-usd", "2.00"],
   ```
   The literal at line 72 is `"--model", model` (variable) — NOT the hardcoded `"--model", "opus"` claimed by the spec. The spec is stale relative to the present code state. Per `git log -- tests/test_standing_teammate_spawn.py`, the parameterization landed in commit `44f09373` ("fix: #179 plumb model fixture into extra_args in test_standing_teammate_spawn.py"), present on `main` and on this worktree's branch base.

3. **DONE** — `grep -n 'addoption\|--model\|model.*default' tests/conftest.py | head -10` returned:
   ```
   21:def pytest_addoption(parser):
   22:    parser.addoption("--runtime", action="store", default="claude",
   25:    parser.addoption("--model", action="store", default="haiku",
   27:    parser.addoption("--effort", action="store", default="low",
   29:    parser.addoption("--budget", action="store", type=float, default=None,
   31:    parser.addoption("--team-mode", action="store", default="auto",
   107:    return request.config.getoption("--model")
   ```
   - `tests/conftest.py:25` registers `--model` pytest CLI option (default `haiku`, NOT `opus`).
   - `tests/conftest.py:106-107` defines `model` fixture: `return request.config.getoption("--model")`.
   - The exact accessor is the `model` pytest fixture (function-scoped). All live tests that need the model receive it via this fixture.

4. **DONE** — `grep -rn -- '--model.*opus' tests/ | head -20` returned only documentation/comment hits, NO source code with the bug pattern:
   ```
   tests/README.md:166:- `make test-live-claude-opus` is the same shape with `--model opus --effort low` overrides.
   tests/README.md:286:| `model_override` | Override the `--model` flag for Claude jobs. ... | `claude-opus-4-6` |
   tests/README.md:306:When a Claude Code version flips a model alias in a way that breaks a test ...
   ```
   Zero `.py` files contain a hardcoded `--model opus` in an extra_args list. A complementary audit on the broader pattern `extra_args.*--model` across `tests/*.py` identified 12 production live tests, all of which already source `--model` from the `model` fixture (or, in the `test_checklist_e2e.py` / `test_commission.py` cases, a `model_for_run` local that wraps the same fixture with an opus default for that single test's documented historical reasons). No file requires a fix.

   Full inventory of `extra_args` callsites with `--model`:
   - `tests/test_agent_captain_interaction.py:100` — uses fixture `model`
   - `tests/test_checklist_e2e.py:77,100` — uses local `model_for_run` (wraps `model`)
   - `tests/test_claude_per_stage_model.py:63` — uses fixture `model`
   - `tests/test_dispatch_completion_signal.py:59` — uses fixture `model`
   - `tests/test_feedback_keepalive.py:171` — uses fixture `model`
   - `tests/test_push_main_before_pr.py:125` — uses fixture `model`
   - `tests/test_rebase_branch_before_push.py:161` — uses fixture `model`
   - `tests/test_rejection_flow.py:186` — uses fixture `model`
   - `tests/test_repo_edit_guardrail.py:81` — uses fixture `model`
   - `tests/test_scaffolding_guardrail.py:80` — uses fixture `model`
   - `tests/test_standing_teammate_spawn.py:72` — uses fixture `model`
   - Plus `tests/test_merge_hook_guardrail.py:175,257`, `test_reuse_dispatch.py:67`, `test_team_dispatch_sequencing.py:54`, `test_single_entity_team_skip.py:45` — all use fixture `model`.

5. **SKIPPED** — Implementation step not performed because the file already contains the correct wiring at line 72 (`extra_args=["--model", model, ...]`). Making any "fix" here would either be a no-op edit or a regression. Per CLAUDE.md ("YOU MUST make the SMALLEST reasonable changes" + "Do NOT modify YAML frontmatter"), the right action is to do nothing to source code and surface the duplicate finding.

6. **SKIPPED** — Per step 4, no other file contains the bug pattern. All other live tests already source `--model` from the `model` fixture. Same rationale as step 5.

7. **DONE** — `unset CLAUDECODE && make test-static` from worktree root, full final pytest line:
   ```
   426 passed, 22 deselected, 10 subtests passed in 20.29s
   ```
   Zero failures. Note: the count is 426 (not 422 as in the prompt's example) because the worktree base includes #177's added tests on top of #172. No regression introduced (no edit was made).

8. **DONE** — `unset CLAUDECODE && uv run pytest tests/test_standing_teammate_spawn.py --collect-only -q --model opus 2>&1 | tail -10` output:
   ```
   tests/test_standing_teammate_spawn.py::test_standing_teammate_spawns_and_roundtrips

   1 test collected in 0.01s
   ```
   Test collects cleanly with `--model opus` passed through. Note that conftest's default for `--model` is `haiku` (not `opus`), so passing `--model opus` here exercises the override path — the test would receive `model="opus"` via the fixture.

9. **DONE** — Wiring chain trace by code-reading (no execution required since the code is unchanged from main):
   - **Step A — Workflow → CI:** `runtime-live-e2e.yml` `model_override` workflow input is forwarded to pytest as `--model <value>` (per #176's design and `tests/README.md:286`).
   - **Step B — pytest CLI → option:** `tests/conftest.py:21,25` `pytest_addoption` registers `--model` with default `haiku`.
   - **Step C — option → fixture:** `tests/conftest.py:105-107`:
     ```python
     @pytest.fixture
     def model(request):
         return request.config.getoption("--model")
     ```
   - **Step D — fixture → test:** `tests/test_standing_teammate_spawn.py:34` declares `model` as a fixture parameter on `test_standing_teammate_spawns_and_roundtrips`. Pytest injects the value at call time.
   - **Step E — test → extra_args:** `tests/test_standing_teammate_spawn.py:72`:
     ```python
     extra_args=["--model", model, "--effort", effort, "--max-budget-usd", "2.00"],
     ```
   - **Step F — extra_args → subprocess:** `scripts/test_lib.py:760-769` (`run_first_officer_streaming`):
     ```python
     cmd = [
         "claude", "-p", prompt,
         "--plugin-dir", str(runner.repo_root),
         "--agent", agent_id,
         "--permission-mode", "bypassPermissions",
         "--verbose",
         "--output-format", "stream-json",
     ]
     if extra_args:
         cmd.extend(extra_args)
     ```
     `subprocess.Popen(cmd, ...)` at line 775 invokes the `claude -p ... --model <value>` subprocess.

   The full chain is intact. Workflow `model_override=claude-opus-4-6` → pytest `--model claude-opus-4-6` → fixture `model="claude-opus-4-6"` → `extra_args=["--model", "claude-opus-4-6", ...]` → `claude -p ... --model claude-opus-4-6`. The model_override value reaches the `claude` subprocess.

10. **DONE** — This Stage Report section.

11. **SKIPPED (no commit)** — No source files were modified, so no commit was made on the worktree branch. Committing an unchanged tree (or a no-op edit) would either fail (`nothing to commit`) or pollute history. The branch HEAD remains at `b11b92e3 fast-track: #180 backlog -> implementation (skip ideation gate; spec is in body)`. If FO/Validator wants a no-op marker commit anyway (e.g., `chore: #180 verified — already fixed by #179, no code change required`), that decision belongs to FO at the merge boundary and I'm flagging it here rather than fabricating one.

### Files changed

None. The only edit on this branch in this stage is this Stage Report appended to `docs/plans/model-override-plumbing-fix.md` (the entity body itself, NOT YAML frontmatter — frontmatter is untouched).

### Summary for validator

#180's spec is stale: the bug it describes was already fixed by #179 (commit `44f09373`), present on main and on this worktree's base. All 12 live tests with `extra_args` lists containing `--model` source the value from pytest's `model` fixture; no file contains a hardcoded `--model opus`. Wiring chain (workflow input → pytest `--model` → `model` fixture → `extra_args` → `claude -p`) verified by code-reading. Static suite green at `426 passed, 22 deselected, 10 subtests passed in 20.29s`. No commit made because there is nothing to change. Recommend: validator confirms by re-running steps 2 and 4; FO either closes #180 as duplicate of #179, or re-dispatches #177 AC-3 directly against this branch (or main) to confirm the live integration path now stamps `claude-opus-4-6` correctly.
