# Plugin-Shipped Runtime Assets Implementation Plan

> **For Claude:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make commissioned workflows data-only by shipping `status`, mods, and core agents from the plugin instead of copying them into each workflow.

**Architecture:** The status script lives at `skills/commission/bin/status` and gains an explicit `--workflow-dir` mode so the first officer and tests can invoke it without a workflow-local copy. The first officer resolves status, mods, and plugin agents from the plugin root at runtime, while commission/refit stop materializing those assets into workflows.

**Tech Stack:** Python 3 stdlib, Markdown prompt templates, pytest, existing test helpers.

---

### Task 1: Lock In The New Commission Contract

**Files:**
- Modify: `scripts/test_commission.py`
- Modify: `skills/commission/SKILL.md`

- [ ] **Step 1: Write the failing test**

Add checks in `scripts/test_commission.py` that commissioned workflows do not contain `{dir}/status` or `{dir}/_mods/pr-merge.md`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python scripts/test_commission.py`
Expected: FAIL because commission still generates `status` and `_mods/pr-merge.md`.

- [ ] **Step 3: Write minimal implementation**

Update `skills/commission/SKILL.md` to remove generation/copy steps and update the completion checklist/output summary accordingly.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python scripts/test_commission.py`
Expected: PASS for the new contract checks.

### Task 2: Add Plugin-Resolved Status Execution

**Files:**
- Modify: `skills/commission/bin/status`
- Modify: `scripts/test_lib.py`
- Modify: `tests/test_status_script.py`

- [ ] **Step 1: Write the failing test**

Add a test that invokes the plugin-shipped status script with an explicit workflow directory and expects the same output as the current local-script mode.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_status_script.py -q`
Expected: FAIL because the shipped status script does not yet accept explicit workflow-dir invocation.

- [ ] **Step 3: Write minimal implementation**

Teach `skills/commission/bin/status` to accept `--workflow-dir <dir>` and update shared test helpers to call the plugin-shipped script directly.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_status_script.py -q`
Expected: PASS.

### Task 3: Move First-Officer Runtime To Plugin Assets

**Files:**
- Modify: `agents/first-officer.md`
- Modify: `agents/ensign.md`
- Modify: `tests/test_gate_guardrail.py`
- Modify: `tests/test_dispatch_names.py`
- Modify: `tests/test_rejection_flow.py`
- Modify: `tests/test_scaffolding_guardrail.py`
- Modify: `tests/test_merge_hook_guardrail.py`

- [ ] **Step 1: Write the failing test**

Update runtime tests to use plugin-shipped status/mod behavior and assert first officer instructions no longer reference `{workflow_dir}/status` or `{workflow_dir}/_mods/`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_gate_guardrail.py tests/test_dispatch_names.py tests/test_rejection_flow.py tests/test_scaffolding_guardrail.py tests/test_merge_hook_guardrail.py -q`
Expected: FAIL because the plugin agent still references workflow-local runtime assets.

- [ ] **Step 3: Write minimal implementation**

Update `agents/first-officer.md` to resolve plugin-shipped status and mods, dispatch `spacedock:ensign`, and adjust the tests/fixtures to invoke that path.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_gate_guardrail.py tests/test_dispatch_names.py tests/test_rejection_flow.py tests/test_scaffolding_guardrail.py tests/test_merge_hook_guardrail.py -q`
Expected: PASS.

### Task 4: Simplify Refit And Final Verification

**Files:**
- Modify: `skills/refit/SKILL.md`
- Modify: `scripts/test_commission.py`
- Modify: `tests/test_plugin_runtime_assets.py`

- [ ] **Step 1: Write the failing test**

Add checks that refit/commission documentation no longer describe workflow-local status or `_mods/` as managed scaffolding.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python scripts/test_commission.py`
Expected: FAIL because the docs still mention local runtime asset management.

- [ ] **Step 3: Write minimal implementation**

Remove stale refit guidance for local status/mod management and align messaging with plugin-shipped runtime assets.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python scripts/test_commission.py`
Expected: PASS.

- [ ] **Step 5: Run final verification**

Run:
- `uv run python -m pytest tests/test_status_script.py -q`
- `uv run python -m pytest tests/test_plugin_runtime_assets.py -q`

Expected: all green.
