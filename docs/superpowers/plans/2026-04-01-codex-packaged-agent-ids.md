# Codex Packaged Agent IDs Implementation Plan

> **For Claude:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Spacedock-owned logical packaged worker ids to the Codex spike and split dispatch ids from filesystem-safe worker keys.

**Architecture:** Keep the Codex first officer skill/prompt based. Add a small packaged worker registry owned by Spacedock, default the Codex path to `spacedock:ensign`, and derive a safe `worker_key` for worktrees and branches so namespaced ids do not leak into git or filesystem operations.

**Tech Stack:** Markdown prompt assets, shell launcher, Python test harness, pytest-style script tests

---

## Chunk 1: Plan And Red Tests

### Task 1: Add direct tests for packaged worker ids

**Files:**
- Create: `tests/test_codex_packaged_agent_ids.py`
- Modify: `scripts/test_lib.py`
- Test: `tests/test_codex_packaged_agent_ids.py`

- [ ] **Step 1: Write the failing test**

```python
def test_packaged_agent_id_uses_safe_worker_key():
    resolved = resolve_codex_worker("spacedock:ensign")
    assert resolved["dispatch_agent_id"] == "spacedock:ensign"
    assert resolved["worker_key"] == "spacedock-ensign"
    assert resolved["prompt_path"].name == "codex-worker-prompt.md"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --with pytest python tests/test_codex_packaged_agent_ids.py`
Expected: FAIL because the Codex worker resolver does not exist yet.

- [ ] **Step 3: Add one more red test for unknown ids**

```python
def test_unknown_packaged_agent_id_is_rejected():
    with pytest.raises(ValueError):
        resolve_codex_worker("spacedock:unknown")
```

- [ ] **Step 4: Run the test file again**

Run: `uv run --with pytest python tests/test_codex_packaged_agent_ids.py`
Expected: FAIL with missing resolver symbols or equivalent.

- [ ] **Step 5: Commit**

```bash
git add tests/test_codex_packaged_agent_ids.py
git commit -m "test: add codex packaged agent id coverage"
```

### Task 2: Add an integration assertion for safe worker naming

**Files:**
- Modify: `tests/test_codex_rejection_flow.py`
- Test: `tests/test_codex_rejection_flow.py`

- [ ] **Step 1: Write the failing assertion**

Add an assertion that any created worktree path includes `spacedock-ensign` and does not include `spacedock:ensign`.

- [ ] **Step 2: Run the rejection test to verify it fails**

Run: `uv run --with pytest python tests/test_codex_rejection_flow.py`
Expected: FAIL because the current Codex path still uses the old worker naming model.

- [ ] **Step 3: Commit**

```bash
git add tests/test_codex_rejection_flow.py
git commit -m "test: assert safe codex worker naming"
```

## Chunk 2: Resolver And Prompt Wiring

### Task 3: Add the packaged worker resolver

**Files:**
- Modify: `scripts/test_lib.py`
- Create: `references/codex-packaged-agents.json`
- Test: `tests/test_codex_packaged_agent_ids.py`

- [ ] **Step 1: Add a packaged worker registry file**

Create a registry that maps:

```json
{
  "spacedock:ensign": {
    "prompt_path": "references/codex-worker-prompt.md",
    "worker_key": "spacedock-ensign"
  }
}
```

- [ ] **Step 2: Implement a minimal resolver in `scripts/test_lib.py`**

Add a helper that:
- accepts a logical id
- loads the registry
- returns `dispatch_agent_id`, `prompt_path`, and `worker_key`
- rejects unknown ids

- [ ] **Step 3: Run the unit test to verify it passes**

Run: `uv run --with pytest python tests/test_codex_packaged_agent_ids.py`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add references/codex-packaged-agents.json scripts/test_lib.py tests/test_codex_packaged_agent_ids.py
git commit -m "feat: add codex packaged worker resolver"
```

### Task 4: Update Codex FO prompt and launcher assumptions

**Files:**
- Modify: `references/codex-first-officer-prompt.md`
- Modify: `references/codex-worker-prompt.md`
- Modify: `scripts/run_codex_first_officer.sh`
- Test: `tests/test_codex_rejection_flow.py`
- Test: `tests/test_codex_gate_guardrail.py`

- [ ] **Step 1: Update the FO prompt**

Change the prompt so it explicitly:
- defaults to `spacedock:ensign`
- resolves packaged worker ids before spawn
- distinguishes `dispatch_agent_id` from `worker_key`
- uses `worker_key` for worktree and branch naming

- [ ] **Step 2: Update the worker prompt**

Tell the worker that the assignment may include a logical packaged id and that reporting should preserve that id.

- [ ] **Step 3: Update the launcher only if needed**

Keep the launcher FO-only. Only add extra prompt context if the FO prompt needs the packaged registry path.

- [ ] **Step 4: Run the rejection test**

Run: `uv run --with pytest python tests/test_codex_rejection_flow.py`
Expected: PASS

- [ ] **Step 5: Run the gate test**

Run: `uv run --with pytest python tests/test_codex_gate_guardrail.py`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add references/codex-first-officer-prompt.md references/codex-worker-prompt.md scripts/run_codex_first_officer.sh
git commit -m "feat: wire packaged codex worker ids"
```

## Chunk 3: Verification

### Task 5: Run the Codex spike verification set

**Files:**
- Test: `tests/test_codex_packaged_agent_ids.py`
- Test: `tests/test_codex_gate_guardrail.py`
- Test: `tests/test_codex_rejection_flow.py`
- Test: `tests/test_status_script.py`

- [ ] **Step 1: Run the new unit-style test**

Run: `uv run --with pytest python tests/test_codex_packaged_agent_ids.py`
Expected: PASS

- [ ] **Step 2: Run the gate test**

Run: `uv run --with pytest python tests/test_codex_gate_guardrail.py`
Expected: PASS

- [ ] **Step 3: Run the rejection test**

Run: `uv run --with pytest python tests/test_codex_rejection_flow.py`
Expected: PASS

- [ ] **Step 4: Run the stable regression check**

Run: `uv run --with pytest python -m pytest tests/test_status_script.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test: verify codex packaged worker path"
```
