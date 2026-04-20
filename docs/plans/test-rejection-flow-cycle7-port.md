---
id: "210"
title: "Port test_rejection_flow (claude branch) to cycle-7 pattern — split codex branch into sibling test, un-skip #141"
status: backlog
source: "tests/README.md Tier-A hygiene list; current @pytest.mark.skip reason='pending #141 — reviewer keepalive across feedback cycles'; 297-line dual-runtime test with ensign_count>=3 milestone-counting anti-pattern flagged explicitly in README"
started:
completed:
verdict:
score: 0.50
worktree:
issue:
pr:
mod-block:
---

# Port test_rejection_flow (claude branch) to Cycle-7 Pattern Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un-skip `tests/test_rejection_flow.py` at opus-4-7 teams mode by (a) splitting the 297-line dual-runtime file into `test_rejection_flow_claude.py` (teams-mode, cycle-7-patterned) and `test_rejection_flow_codex.py` (unchanged codex branch — NOT cycle-7-ported), and (b) rewriting the claude branch to assert the #141 reviewer-keepalive contract using streaming watcher + inbox-poll keep-alive. Codex branch remains on its current structure and assertions (out of cycle-7 scope; that harness is a separate adapter).

**Architecture:** Split by runtime into two files. Claude file pins `@pytest.mark.teams_mode`, uses the cycle-7 pattern, and replaces the `ensign_count >= 3` post-hoc branch with strict per-stage assertions that correctly model the #141 reuse: `impl dispatch close → validation dispatch close → SendMessage routes findings back to implementation → impl re-dispatch close (new Agent because the completed impl was shut down after validation) → validation RE-dispatch close (via SendMessage to the kept-alive validation reviewer — the #141 contract)`. Codex file stays untouched.

**Tech Stack:** Python, pytest, `scripts/test_lib.py` (`run_first_officer_streaming`, `FOStreamWatcher`, `DispatchBudget`, `expect_dispatch_close`, `expect`), `scripts/fo_inbox_poll.py`, `tests/fixtures/rejection-flow/`.

---

## Background

`tests/test_rejection_flow.py` has three coupled problems:

1. **Dual-runtime structure** — claude and codex paths share a single test function via a `runtime` parameter. The codex branch is ~130 lines of milestone/log parsing specific to the codex adapter; the claude branch is ~40 lines using `LogParser` + `run_first_officer`. The Tier-A table in `tests/README.md` explicitly recommends splitting: *"Split claude and codex into two tests if the shared invariant doesn't fit both."* The shared invariant doesn't fit both: claude teams use `SendMessage` reuse; codex uses `send_input` on a kept-alive worker pane. The runtimes route feedback differently.

2. **`#141` — reviewer keepalive across feedback cycles.** The test's current claude-branch post-hoc is `ensign_count >= 3` (expects three Agent dispatches: impl, validation, impl-fix). But per shared-core, **after validation REJECTs and the FO routes feedback back to implementation, the RE-review should reuse the same validation reviewer via SendMessage, not a fresh Agent.** So the correct dispatch count is 3 Agents (impl, validation, impl-fix) plus 1 SendMessage to the validation reviewer to kick off re-review. The `>=3` assertion doesn't distinguish "3 Agents + SendMessage reuse" (correct) from "4 Agents" (violates #141).

3. **Gated validation under `-p`.** The `rejection-flow` fixture has `gate: true` on `backlog` (initial) AND `validation`. Under `claude -p` there's no captain to approve, so the FO correctly holds and the test hangs. Same class as the cycle-7 `reuse-pipeline` issue we solved by dropping the gate (test_gate_guardrail.py owns the gate contract).

Currently `@pytest.mark.skip` (not xfail) on both runtimes. Un-skipping requires addressing all three.

## Fixture shape

`tests/fixtures/rejection-flow/README.md`:

```yaml
stages:
  defaults:
    worktree: false
    concurrency: 2
  states:
    - name: backlog
      initial: true
      gate: true          # drop this
    - name: implementation
      worktree: true
    - name: validation
      worktree: true
      fresh: true
      feedback-to: implementation
      gate: true          # drop this
    - name: done
      terminal: true
```

**Decision: drop `gate: true` on both backlog and validation.** Matches the cycle-7 `reuse-pipeline` decision. Gate behavior is covered by `test_gate_guardrail.py` with its own fixture. The rejection flow contract is about feedback routing after REJECT, not gate handling.

## Expected FO trajectory (claude teams mode, opus-4-7, post-fix)

1. `TeamCreate(...)`
2. `Agent(..., description="... implementation")` — cycle-1 impl
3. (ensign writes buggy `math_ops.py` per fixture → commits → Done)
4. FO polls inbox → observes Done → advances to validation
5. `Agent(..., description="... validation")` — cycle-1 validation (fresh: true per stage spec)
6. (validation ensign runs tests against `math_ops.py` → finds the `a - b` bug → writes REJECTED Stage Report → Done)
7. FO polls inbox → observes Done with REJECTED verdict
8. FO enters **Feedback Rejection Flow** (shared-core line 131): reads validation's `feedback-to: implementation`, tracks cycle 1 in entity's `### Feedback Cycles` section.
9. Per shared-core, FO checks `claude-team context-budget --name {impl-ensign}`. If reuse_ok, routes findings back via `SendMessage` to the kept-alive impl ensign; else fresh-dispatches.
10. **Case A (reuse):** `SendMessage(to="spacedock-ensign-buggy-add-task-implementation", ...)` with the fix request. Impl ensign fixes `math_ops.py` → second Done.
11. **Case B (fresh):** `Agent(..., description="... implementation-fix")` — cycle-2 impl. Emits Done.
12. Either way, FO now re-runs validation. **Per #141**, since the validation reviewer was kept alive at the gate (shared-core: "keep the worker alive while waiting at the gate"), the FO reuses via `SendMessage(to="spacedock-ensign-...validation", "Re-validate: ...")`. Validation emits second Done with PASSED.
13. FO advances `validation → done`, archives entity.
14. Sentinel touched, FO exits.

## Contract assertions (claude-branch test)

1. `TeamCreate` emitted.
2. `expect_dispatch_close(ensign_name="implementation", ...)` — cycle-1 impl.
3. `expect_dispatch_close(ensign_name="validation", ...)` — cycle-1 validation.
4. `expect(REJECTED in validation Stage Report via entity file OR fo-log text)` — rejection observed.
5. **Feedback routing.** Accept either (a) `expect(SendMessage to impl ensign)` for reuse path, or (b) `expect_dispatch_close(ensign_name="implementation", ...)` for fresh cycle-2 — whichever lands first. Record which path fired.
6. **Re-validation — the #141 contract.** `expect(SendMessage to validation ensign)` for reviewer reuse. Cycle-7 pattern: the reviewer reuse is just another SendMessage event in the stream.
7. Sentinel touched; try/except `expect_exit`.
8. Post-hoc: entity status=done OR archived.
9. Post-hoc: `len(dispatch_records)` ∈ {3, 4} — either "impl + validation + impl-fix" (reuse via SendMessage) or "impl + validation + impl-fix + validation-recheck" (fresh dispatch both cycles). The #141-aligned shape is 3 Agent dispatches plus 2 SendMessages (one for feedback routing, one for re-validation).

**Note on the #141 strictness.** We do NOT want to assert `len(records) == 3` strictly because (a) we can't guarantee the FO picks reuse over fresh-dispatch every time (opus variance), and (b) the `context-budget` check is a legitimate branch. The stricter assertion is "`SendMessage` to the validation ensign was emitted at some point" — which is the reuse signal the test #141 was designed to preserve.

## File Structure

- Create: `tests/test_rejection_flow_claude.py` (~210 lines, cycle-7 patterned)
- Modify: `tests/fixtures/rejection-flow/README.md` (drop two `gate: true` lines)
- Modify: `tests/test_rejection_flow.py` — rename/move to `tests/test_rejection_flow_codex.py`, strip claude branch, keep codex branch + codex-specific helpers (~175 lines, unchanged semantics)
- Delete: `tests/test_rejection_flow.py` (superseded by the two new files)

## Task breakdown

### Task 1: Un-gate the fixture

**Files:**
- Modify: `tests/fixtures/rejection-flow/README.md`

- [ ] **Step 1: Verify no other test uses this fixture's gate behavior**

Run: `grep -rn "rejection-flow\|rejection-pipeline" tests/ | grep -v rejection_flow`
Expected: empty (only `test_rejection_flow.py` uses this fixture).

- [ ] **Step 2: Edit the fixture README**

In `tests/fixtures/rejection-flow/README.md`, delete the `      gate: true` line under both `backlog` and `validation` stages. Keep `fresh: true` and `feedback-to: implementation` on validation.

- [ ] **Step 3: Static check**

Run: `make test-static` → 475 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/rejection-flow/README.md
git commit -m "fixture: #210 drop gates on rejection-flow backlog + validation

Rejection flow contract is about feedback routing after REJECTED, not
gate handling. Under claude -p there's no captain to approve, so the
test hangs. Drop the gates; test_gate_guardrail.py owns the gate
contract with a dedicated fixture."
```

---

### Task 2: Split codex branch into its own test file

**Files:**
- Create: `tests/test_rejection_flow_codex.py`
- Modify: (will eventually delete) `tests/test_rejection_flow.py`

- [ ] **Step 1: Copy the codex branch verbatim into the new file**

Create `tests/test_rejection_flow_codex.py` containing:
- The `_codex_rejection_flow_milestones`, `_codex_rejection_follow_up_order`, `_codex_rejection_flow_stop_ready` helper functions unchanged.
- A single `@pytest.mark.live_codex`-only test function that runs only the codex branch of the original body (lines 190-296 in the original). Drop the `runtime` parameter; hard-code codex.
- Remove `@pytest.mark.live_claude` marker and all claude-branch conditionals.
- Keep the `@pytest.mark.skip(reason="pending #141 ...")` for now — un-skipping codex is a separate concern (codex has its own `send_input` reuse semantics; this plan does not touch them).

- [ ] **Step 2: Static check**

Run: `make test-static` → 475 passed (new codex-only file should collect but is skipped).

- [ ] **Step 3: Commit**

```bash
git add tests/test_rejection_flow_codex.py
git commit -m "split: #210 extract codex branch of test_rejection_flow into dedicated file

Mechanical split of the dual-runtime test into a codex-only sibling.
Codex branch body + helpers preserved verbatim; @pytest.mark.live_codex
only; runtime param removed. Skip marker retained for now — un-skipping
codex is out of scope for #210 (separate reuse semantics via send_input).

Next commit will replace tests/test_rejection_flow.py with the cycle-7
patterned claude-only test."
```

---

### Task 3: Rewrite claude branch as cycle-7 patterned test

**Files:**
- Modify: `tests/test_rejection_flow.py` — full rewrite as claude-teams-only cycle-7 test (rename the file? no: keep the original name so historical references still resolve; the codex branch was already split to a sibling file in Task 2)

- [ ] **Step 1: Overwrite `tests/test_rejection_flow.py`**

Replace the entire file content with the following cycle-7 patterned test (filename stays `test_rejection_flow.py`; after Task 2 it no longer conflicts with the codex sibling):

```python
# ABOUTME: E2E test for the validation rejection flow in the first-officer template.
# ABOUTME: Pinned to teams_mode; asserts impl + validation dispatches + SendMessage feedback routing + reviewer-reuse for re-validation (#141).

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (  # noqa: E402
    DispatchBudget,
    emit_skip_result,
    git_add_commit,
    install_agents,
    probe_claude_runtime,
    read_entity_frontmatter,
    rejection_signal_present,
    run_first_officer_streaming,
    setup_fixture,
)


PER_STAGE_OVERALL_S = 120
PER_DISPATCH_BUDGET_S = 90

SUBPROCESS_EXIT_BUDGET_S = 180


def _is_tool_use(entry: dict, name: str) -> dict | None:
    if entry.get("type") != "assistant":
        return None
    msg = entry.get("message") or {}
    for block in (msg.get("content") or []):
        if (
            isinstance(block, dict)
            and block.get("type") == "tool_use"
            and block.get("name") == name
        ):
            return block
    return None


def _is_send_message_to(entry: dict, recipient_substr: str) -> bool:
    block = _is_tool_use(entry, "SendMessage")
    if not block:
        return False
    inp = block.get("input") or {}
    return recipient_substr in str(inp.get("to", ""))


def _is_team_create(entry: dict) -> bool:
    return _is_tool_use(entry, "TeamCreate") is not None


@pytest.mark.live_claude
@pytest.mark.teams_mode
def test_rejection_flow(test_project, model, effort):
    """FO drives teams-mode rejection flow: impl -> validation REJECTED -> feedback routes back -> validation reviewer reused via SendMessage for re-review (#141)."""
    t = test_project

    if model == "claude-haiku-4-5":
        pytest.xfail(
            reason=(
                "pending haiku-teams rejection flow — haiku-4-5 drops the "
                "keep-alive Bash-probe discipline at `system init` cycle "
                "boundaries and hallucinates teardown "
                "(anthropics/claude-code#26426 class; opus-4-7 green)"
            )
        )

    print("--- Phase 1: Set up test project from fixture ---")
    fixture_dir = t.repo_root / "tests" / "fixtures" / "rejection-flow"
    setup_fixture(t, "rejection-flow", "rejection-pipeline")
    install_agents(t, include_ensign=True)

    shutil.copy2(fixture_dir / "math_ops.py", t.test_project_dir)
    tests_dir = t.test_project_dir / "tests"
    tests_dir.mkdir(exist_ok=True)
    shutil.copy2(fixture_dir / "tests" / "test_add.py", tests_dir)
    git_add_commit(t.test_project_dir, "setup: rejection flow fixture with buggy implementation")

    status_cmd = ["python3", str(t.repo_root / "skills" / "commission" / "bin" / "status"),
                  "--workflow-dir", "rejection-pipeline"]
    t.check_cmd("status script runs without errors", status_cmd, cwd=t.test_project_dir)
    status_result = subprocess.run(
        status_cmd + ["--next"], capture_output=True, text=True, cwd=t.test_project_dir,
    )
    t.check("status --next detects dispatchable entity",
            "buggy-add-task" in status_result.stdout)
    print()

    print("--- Phase 2: Run first officer (claude) ---")
    ok, reason = probe_claude_runtime(model)
    if not ok:
        emit_skip_result(
            f"live Claude runtime unavailable before FO dispatch: {reason}. "
            "This environment cannot currently prove or disprove the rejection-flow path."
        )

    abs_workflow = t.test_project_dir / "rejection-pipeline"
    prompt = f"Process all tasks through the workflow at {abs_workflow}/ to terminal completion."

    keepalive_done = t.test_project_dir / ".fo-keepalive-done"
    poll_script = t.repo_root / "scripts" / "fo_inbox_poll.py"
    seen_file = t.test_project_dir / ".fo-inbox-seen"
    headless_hint = (
        f"The spacedock plugin directory is at `{t.repo_root}`. Use it "
        f"directly; do NOT run `find / -name claude-team` — the binaries you "
        f"need are `{t.repo_root}/skills/commission/bin/status` and "
        f"`{t.repo_root}/skills/commission/bin/claude-team`.\n\n"
        f"HEADLESS INBOX-POLLING RULE. You are running in `claude -p` headless "
        f"mode. Per anthropics/claude-code#26426, inbox-delivered teammate "
        f"messages accumulate on disk at `$HOME/.claude/teams/{{team_name}}/"
        f"inboxes/team-lead.json` but are NOT surfaced to your stream. The "
        f"workaround is to surface them yourself via an external polling "
        f"script.\n\n"
        f"Until the sentinel file `{keepalive_done}` exists, every turn "
        f"MUST end with a Bash tool_use (not text) that runs the poll "
        f"script:\n\n"
        f"    python3 {poll_script} --home \"$HOME\" --pattern 'Done:' "
        f"--timeout 5 --seen-file {seen_file}\n\n"
        f"The script blocks up to 5 seconds waiting for a new inbox "
        f"message whose text contains 'Done:'. Its stdout contains the "
        f"teammate message (or is empty on timeout, in which case repeat). "
        f"Treat any 'from: spacedock-ensign-...' block with 'text: Done: "
        f"... completed {{stage}}' as the teammate's completion signal for "
        f"that stage — proceed to the next workflow step per shared-core "
        f"discipline. Never emit `SendMessage(shutdown_request)`, "
        f"`TeamDelete`, or other teardown while awaiting an ensign. Once "
        f"the workflow reaches terminal completion, you may end with text."
    )

    with run_first_officer_streaming(
        t,
        prompt,
        agent_id="spacedock:first-officer",
        extra_args=[
            "--model", model,
            "--effort", effort,
            "--max-budget-usd", "5.00",
            "--append-system-prompt", headless_hint,
        ],
        dispatch_budget=DispatchBudget(soft_s=30.0, hard_s=180.0, shutdown_grace_s=10.0),
    ) as w:
        w.expect(_is_team_create, timeout_s=PER_STAGE_OVERALL_S, label="TeamCreate emitted")
        print("[OK] TeamCreate emitted (teams mode engaged)")

        impl_record = w.expect_dispatch_close(
            overall_timeout_s=PER_STAGE_OVERALL_S,
            dispatch_budget_s=PER_DISPATCH_BUDGET_S,
            ensign_name="implementation",
            label="cycle-1 implementation dispatch close",
        )
        print(f"[OK] cycle-1 implementation dispatch closed in {impl_record.elapsed:.1f}s")

        validation_record = w.expect_dispatch_close(
            overall_timeout_s=PER_STAGE_OVERALL_S,
            dispatch_budget_s=PER_DISPATCH_BUDGET_S,
            ensign_name="validation",
            label="cycle-1 validation dispatch close",
        )
        print(f"[OK] cycle-1 validation dispatch closed in {validation_record.elapsed:.1f}s")

        # Feedback routing: FO must route back to implementation. Accept
        # either SendMessage to the impl ensign (reuse) OR a fresh Agent
        # re-dispatch of implementation. Whichever fires first is the
        # observable signal that feedback routing happened.
        w.expect(
            lambda e: (
                _is_send_message_to(e, "implementation")
                or (
                    _is_tool_use(e, "Agent") is not None
                    and "implementation" in str(((_is_tool_use(e, "Agent") or {}).get("input") or {}).get("description", ""))
                )
            ),
            timeout_s=PER_STAGE_OVERALL_S,
            label="feedback routed back to implementation (SendMessage or fresh Agent)",
        )
        print("[OK] feedback routed back to implementation")

        # The #141 contract: after the fix, FO reuses the kept-alive
        # validation reviewer via SendMessage for re-review. This is
        # the key signal the original test's `ensign_count >= 3` wasn't
        # distinguishing from "fresh validation re-dispatch".
        w.expect(
            lambda e: _is_send_message_to(e, "validation"),
            timeout_s=PER_STAGE_OVERALL_S,
            label="SendMessage to validation reviewer for re-review (#141 keepalive)",
        )
        print("[OK] validation reviewer reused via SendMessage for re-review (#141)")

        keepalive_done.touch()
        print(f"[OK] keep-alive sentinel {keepalive_done.name} touched")

        try:
            w.expect_exit(timeout_s=SUBPROCESS_EXIT_BUDGET_S)
            print("[OK] FO exited cleanly after sentinel")
        except Exception as exc:
            print(f"  NOTE: FO did not exit within {SUBPROCESS_EXIT_BUDGET_S}s post-sentinel ({type(exc).__name__}); contract assertions already passed")

    print("--- Phase 3: Validation ---")

    records = w.dispatch_records
    print(f"  dispatch records: {[(r.ensign_name, round(r.elapsed, 1)) for r in records]}")

    # Dispatch count analysis. Accept either:
    #   3 Agents (impl, validation, impl-fix) — reuse path: validation re-review via SendMessage
    #   4 Agents (impl, validation, impl-fix, validation-recheck) — fresh path
    # Per #141 the reuse path is preferred; we don't enforce it strictly
    # because the context-budget check is a legitimate branch to fresh.
    t.check(
        "FO emitted 3 or 4 ensign Agent() dispatches (impl + validation + impl-fix +/- validation-recheck)",
        len(records) in (3, 4),
    )

    print()
    print("[Rejection Signal Present]")
    entity_main = t.test_project_dir / "rejection-pipeline" / "buggy-add-task.md"
    worktrees_dir = t.test_project_dir / ".worktrees"
    t.check(
        "reviewer stage report contains REJECTED recommendation",
        rejection_signal_present("rejection-pipeline", "buggy-add-task", entity_main, worktrees_dir, "", ""),
    )

    print()
    print("[Entity Advancement]")
    entity_archive = t.test_project_dir / "rejection-pipeline" / "_archive" / "buggy-add-task.md"
    if entity_archive.is_file():
        t.pass_("entity advanced to terminal stage and was archived")
    elif entity_main.is_file():
        fm = read_entity_frontmatter(entity_main)
        status_val = fm.get("status", "")
        if status_val == "done":
            t.pass_(f"entity advanced to terminal stage (status: {status_val})")
        else:
            t.fail(f"entity did not reach terminal stage (status: {status_val!r})")
    else:
        t.fail("entity file missing from both main and _archive")

    t.finish()
```

- [ ] **Step 2: Verify the `rejection_signal_present` helper still satisfies its old signature**

`rejection_signal_present` takes `(workflow_name, slug, entity_main, worktrees_dir, worker_messages, fo_text)`. The rewrite passes empty strings for `worker_messages` and `fo_text` because the streaming watcher doesn't aggregate those; the helper's primary source is the entity's stage-report section in the main entity file or its worktree copy. Confirm via inspection that this still works (the helper falls back to entity-file stage reports as its primary signal). If it doesn't, rewrite locally to inline the `REJECTED` grep against the entity file + its worktree copy.

- [ ] **Step 3: Static check**

Run: `make test-static` → 475 passed.

- [ ] **Step 4: Run offline dispatch-budget unit tests**

Run: `uv run pytest tests/test_dispatch_budget.py -x -q` → 21 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_rejection_flow.py
git commit -m "impl: #210 rewrite test_rejection_flow (claude branch) on cycle-7 pattern

Replace run_first_officer + LogParser with run_first_officer_streaming +
FOStreamWatcher. Pin @pytest.mark.teams_mode. Un-skip (drop #141 skip).
Retain haiku xfail (anthropics/claude-code#26426 class).

Contract assertions:
- TeamCreate emitted
- cycle-1 implementation dispatch close
- cycle-1 validation dispatch close
- feedback routed to implementation (SendMessage OR fresh Agent)
- validation reviewer reused via SendMessage for re-review (#141 contract)
- entity advances to done or archived
- len(dispatch_records) in {3, 4} — accept both reuse and fresh paths

Drops the 297-line dual-runtime structure: codex branch moved to
tests/test_rejection_flow_codex.py in the prior commit.

make test-static: 475 passed. offline dispatch-budget: 21 passed."
```

---

### Task 4: Live verification at opus-4-7 teams mode

**Files:**
- (none — test-only)

- [ ] **Step 1: Prepare isolated temp dir**

Run: `mkdir -p /tmp/rejection-r1`

- [ ] **Step 2: Single live run**

Run:

```bash
cd /Users/clkao/git/spacedock/.worktrees/spacedock-ensign-opus-4-7-green-main && \
  unset CLAUDECODE && \
  KEEP_TEST_DIR=1 SPACEDOCK_TEST_TMP_ROOT=/tmp/rejection-r1 \
  CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 \
  uv run pytest tests/test_rejection_flow.py --runtime claude \
    --model opus --effort low --team-mode=teams -v
```

Expected: PASSED in 6-10 minutes (two cycles through implementation + validation + rejection + re-review).

- [ ] **Step 3: Triage on failure**

Common failure modes:
- **SendMessage to validation ensign never fires** → the FO fresh-dispatched validation instead of reusing. This would mean #141 is still live in the FO's decision logic. File a follow-up entity proposing a shared-core tightening rather than relaxing the test assertion.
- **Feedback routing never fires** → FO didn't enter the Feedback Rejection Flow. Check for `REJECTED` in the entity stage report (was the validation ensign's verdict correctly written?). If not, this is upstream of rejection-flow and might need its own investigation.
- **Total dispatch count not in {3, 4}** → log the actual value and inspect which dispatches happened. Either the FO is doing something unexpected (file a follow-up), or our shape model is wrong (adjust the accepted set with justification).

---

### Task 5: Delete the superseded split stub + stage report

Actually, there is no stub — the "rename" in Task 2 creates a new codex-only file and Task 3 rewrites `test_rejection_flow.py` in place. Nothing to delete.

**Files:**
- Modify: `docs/plans/test-rejection-flow-cycle7-port.md` (this file — add stage report + set status)

- [ ] **Step 1: Update this entity's status**

If green at opus-4-7:
```yaml
status: done
completed: "{ISO-8601 timestamp}"
verdict: PASSED
```

Add `## Stage Report: implementation` section with commit SHAs, live-run wallclock, fo-log evidence path, and a note on whether reuse-path or fresh-path fired.

- [ ] **Step 2: Commit and push**

```bash
git add docs/plans/test-rejection-flow-cycle7-port.md
git commit -m "report: #210 done — test_rejection_flow (claude) green at opus-4-7 teams"
git push origin spacedock-ensign/opus-4-7-green-main
```

---

## Acceptance criteria

1. `tests/fixtures/rejection-flow/README.md` has no `gate: true` entries.
2. `tests/test_rejection_flow_codex.py` exists; codex-only; carries `@pytest.mark.live_codex` and `@pytest.mark.skip(reason="pending #141 ...")`.
3. `tests/test_rejection_flow.py` exists; claude-teams-only; uses streaming watcher; no `run_first_officer` / `LogParser` / `CodexLogParser` imports.
4. Test carries `@pytest.mark.teams_mode`; no `@pytest.mark.skip`; inline `pytest.xfail` guard exists only for `model == "claude-haiku-4-5"`.
5. Prompt is a single line — no FO-discipline coaching.
6. `make test-static` passes at 475+ tests.
7. `uv run pytest tests/test_dispatch_budget.py` stays at 21 passed.
8. Single live run at `--model opus --effort low --team-mode=teams` under `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` passes cleanly in 6-10 minutes with all `[OK]` markers fired.
9. This entity's status advances to `done` with a stage report.

## Coordination notes

- Cycle-8 teammates don't touch any of these files.
- #141 stays open for the codex-branch reuse semantics (not addressed here).
- Sibling entities: #211 (completion-signal), #211 (checklist_e2e). Independent.

## Out of scope

- Codex-branch un-skip. Codex uses `send_input` on a persistent worker pane, which has different reuse semantics. A separate cycle-7-for-codex plan would unblock it.
- Shared-core prose changes to make the reuse path more deterministic. Current shared-core at line 138 requires the FO to check `claude-team context-budget --name {ensign-name}` before routing; if reuse_ok is false the fresh path is correct. The test accommodates both paths.
- Bare-mode rejection flow. Bare Agent() is synchronous; reviewer-reuse has no analog. Different contract; own test if required.

## Summary

Largest of the three cycle-7 ports. Splits dual-runtime test into two siblings (mechanical), then rewrites the claude side on the cycle-7 pattern with the #141 reviewer-reuse as the key assertion. Un-skips on opus-4-7; retains haiku xfail and codex skip.
