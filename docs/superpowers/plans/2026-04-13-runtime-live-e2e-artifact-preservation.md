# Runtime Live E2E Artifact Preservation Implementation Plan

> **For Claude:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve and upload live-test temp directories as GitHub Actions artifacts on every runtime live E2E run.

**Architecture:** Add a deterministic temp-root hook to the shared live-test harness, then point both live workflow jobs at job-specific temp roots and upload those directories with `actions/upload-artifact`. Keep default local behavior unchanged when the CI env hook is absent.

**Tech Stack:** Python test harness, GitHub Actions workflow YAML, pytest-style offline workflow checks

---

### Task 1: Add a failing helper test for deterministic temp roots

**Files:**
- Modify: `tests/test_test_lib_helpers.py`
- Modify: `scripts/test_lib.py`

- [ ] **Step 1: Write the failing test**

Add a unit test asserting `TestRunner` creates `test_dir` under `SPACEDOCK_TEST_TMP_ROOT` when that env var is set.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --with pytest python -m pytest tests/test_test_lib_helpers.py -q`
Expected: FAIL because `TestRunner` ignores `SPACEDOCK_TEST_TMP_ROOT`.

- [ ] **Step 3: Write minimal implementation**

Update `TestRunner` to use `tempfile.mkdtemp(dir=..., prefix=...)` when the env var is present.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --with pytest python -m pytest tests/test_test_lib_helpers.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_test_lib_helpers.py scripts/test_lib.py
git commit -m "test: preserve live test dirs under a configured root"
```

### Task 2: Add a failing workflow test for artifact preservation

**Files:**
- Modify: `tests/test_runtime_live_e2e_workflow.py`
- Modify: `.github/workflows/runtime-live-e2e.yml`

- [ ] **Step 1: Write the failing test**

Add assertions that each live job sets `KEEP_TEST_DIR`, sets `SPACEDOCK_TEST_TMP_ROOT`, and uploads artifacts on `if: always()`.

- [ ] **Step 2: Run test to verify it fails**

Run: `unset CLAUDECODE && uv run tests/test_runtime_live_e2e_workflow.py`
Expected: FAIL because the workflow does not yet preserve or upload live temp dirs.

- [ ] **Step 3: Write minimal implementation**

Set the env vars in both live jobs and add upload-artifact steps after the live suite commands.

- [ ] **Step 4: Run test to verify it passes**

Run: `unset CLAUDECODE && uv run tests/test_runtime_live_e2e_workflow.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_runtime_live_e2e_workflow.py .github/workflows/runtime-live-e2e.yml
git commit -m "ci: upload preserved live test dirs"
```

### Task 3: Run focused verification

**Files:**
- Modify: `tests/README.md`

- [ ] **Step 1: Update docs**

Document that live workflow runs preserve test dirs as artifacts.

- [ ] **Step 2: Run focused verification**

Run:
- `uv run --with pytest python -m pytest tests/test_test_lib_helpers.py -q`
- `unset CLAUDECODE && uv run tests/test_runtime_live_e2e_workflow.py`

Expected: both pass.

- [ ] **Step 3: Commit**

```bash
git add tests/README.md
git commit -m "docs: document live test artifact preservation"
```
