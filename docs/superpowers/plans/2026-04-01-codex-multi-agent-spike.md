# Codex Multi-Agent Prototype Spike Implementation Plan

> **For Claude:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a parallel Codex-only prototype that validates Spacedock's first-officer/worker workflow on Codex experimental multi-agent mode without changing the current Claude commission or runtime path.

**Architecture:** Keep the current Claude assets untouched. Add Codex-specific prompt assets, a thin launcher, and a Codex-specific test harness adapter that reuses existing workflow fixtures and state assertions. The spike is feasibility-first: prove that a Codex first officer can read an existing workflow, create a worktree, spawn a worker, pause at approval gates, and advance frontmatter on success.

**Tech Stack:** Codex CLI experimental multi-agent mode, shell launcher scripts, Python test harness, existing Spacedock workflow fixtures, git worktrees, Markdown/YAML workflow files

---

## File Structure

| File | Responsibility | Create/Modify |
|------|---------------|---------------|
| `references/codex-first-officer-prompt.md` | Codex-specific first-officer instructions | Create |
| `references/codex-worker-prompt.md` | Codex-specific worker instructions for one stage | Create |
| `scripts/run_codex_first_officer.sh` | Launch Codex in experimental multi-agent mode against a workflow directory | Create |
| `scripts/test_lib.py` | Add Codex launcher and Codex log parsing helpers while preserving Claude helpers | Modify |
| `tests/test_codex_gate_guardrail.py` | Codex spike smoke test for gate behavior using existing fixture | Create |
| `tests/test_codex_rejection_flow.py` | Codex spike test for multi-dispatch rejection handling | Create |
| `references/codex-tools.md` | Update with the prototype invocation path if the spike proves feasible | Modify |

## Chunk 1: Codex Runtime Prototype

### Task 1: Add Codex first-officer and worker prompt assets

**Files:**
- Create: `references/codex-first-officer-prompt.md`
- Create: `references/codex-worker-prompt.md`
- Reference: `templates/first-officer.md`
- Reference: `templates/ensign.md`
- Reference: `references/codex-tools.md`

- [ ] **Step 1: Draft the Codex first-officer prompt skeleton**

Create `references/codex-first-officer-prompt.md` with sections for:
- startup and workflow discovery
- ready-entity selection
- worktree creation and branch naming
- worker dispatch using `spawn_agent`
- approval gate handling
- frontmatter ownership rules
- completion and reporting

Keep Claude-specific concepts out of this prompt:
- no `.claude/agents/`
- no `Agent()`
- no `subagent_type`
- no team messaging assumptions

- [ ] **Step 2: Port the worker contract into a Codex-native prompt**

Create `references/codex-worker-prompt.md` that handles one entity and one stage only. The worker prompt must say:
- read the assigned entity and stage definition
- work only inside the assigned worktree
- never modify YAML frontmatter
- write a `## Stage Report`
- return a concise completion summary to the parent thread

Use the existing ensign behavior as source material, but rewrite it for Codex semantics rather than transliterating Claude syntax.

- [ ] **Step 3: Verify the prompt assets do not depend on Claude agent registration**

Run:

```bash
rg -n "\.claude/agents|Agent\(|subagent_type|SendMessage|team_name" references/codex-first-officer-prompt.md references/codex-worker-prompt.md
```

Expected: no matches

- [ ] **Step 4: Verify the prompt assets reference workflow behavior, not repo-local assumptions**

Run:

```bash
rg -n "README|status|Stage Report|worktree|approval" references/codex-first-officer-prompt.md references/codex-worker-prompt.md
```

Expected: matches for the runtime behavior sections above

- [ ] **Step 5: Commit**

```bash
git add references/codex-first-officer-prompt.md references/codex-worker-prompt.md
git commit -m "spike: add codex workflow prompt assets"
```

---

### Task 2: Add a Codex launcher for first-officer runs

**Files:**
- Create: `scripts/run_codex_first_officer.sh`
- Reference: `references/codex-first-officer-prompt.md`

- [ ] **Step 1: Create the launcher script**

Create `scripts/run_codex_first_officer.sh` with:
- `#!/bin/bash`
- `set -euo pipefail`
- arguments for workflow directory, optional model, optional reasoning effort, optional output log path
- a single Codex invocation that runs from the project root and injects the first-officer prompt

The script should:
- validate that the workflow directory contains `README.md`
- export or pass any experimental flags needed for multi-agent mode
- keep the workflow path explicit in the prompt text
- write stdout/stderr to a caller-provided log file when requested

- [ ] **Step 2: Make the script executable**

Run:

```bash
chmod +x scripts/run_codex_first_officer.sh
```

Expected: exit 0

- [ ] **Step 3: Add a usage check**

Run:

```bash
scripts/run_codex_first_officer.sh
```

Expected: non-zero exit with a short usage message

- [ ] **Step 4: Add a dry-run style smoke check against a fixture**

Run:

```bash
scripts/run_codex_first_officer.sh tests/fixtures/gated-pipeline
```

Expected: Codex starts from the fixture root or fails with a clear runtime limitation that can be captured by the spike

- [ ] **Step 5: Commit**

```bash
git add scripts/run_codex_first_officer.sh
git commit -m "spike: add codex first officer launcher"
```

---

## Chunk 2: Codex Test Harness

### Task 3: Extend the Python test library with Codex helpers

**Files:**
- Modify: `scripts/test_lib.py`

- [ ] **Step 1: Add a Codex runner beside the existing Claude runner**

Add a new helper, for example:

```python
def run_codex_first_officer(
    runner: TestRunner,
    workflow_dir: str,
    extra_args: list[str] | None = None,
    log_name: str = "codex-fo-log.txt",
) -> int:
    ...
```

This helper should:
- call `scripts/run_codex_first_officer.sh`
- run from `runner.test_project_dir`
- capture output to a log file
- preserve the current Claude helpers unchanged

- [ ] **Step 2: Add a Codex log/artifact parser**

Add a lightweight parser that does not assume Claude `stream-json` format. It only needs enough structure for the spike:
- full text output
- count of spawn events if detectable
- extracted approval/gate language if present
- optional worktree paths or entity names from output

Prefer permissive parsing over a brittle schema.

- [ ] **Step 3: Keep the reusable setup helpers untouched**

Do not break:
- `TestRunner`
- `create_test_project()`
- `setup_fixture()`

These are already runtime-agnostic and should remain reusable by both Claude and Codex tests.

- [ ] **Step 4: Run unit-style smoke checks on the updated harness**

Run:

```bash
uv run python -m pytest tests/test_status_script.py -q
```

Expected: existing status-script tests still pass

- [ ] **Step 5: Commit**

```bash
git add scripts/test_lib.py
git commit -m "spike: add codex test harness helpers"
```

---

### Task 4: Adapt the gate guardrail E2E test for Codex

**Files:**
- Create: `tests/test_codex_gate_guardrail.py`
- Reference: `tests/test_gate_guardrail.py`
- Reference: `tests/fixtures/gated-pipeline`

- [ ] **Step 1: Copy the existing gate test structure**

Create `tests/test_codex_gate_guardrail.py` using the same fixture and the same high-value assertions:
- status script runs
- entity does not advance past the gate
- entity is not archived
- first officer output indicates gate waiting/review behavior

Drop Claude-only setup and checks:
- no `install_agents()`
- no `.claude/agents/first-officer.md` assertions
- no `Agent()` log parsing assumptions

- [ ] **Step 2: Use the new Codex runner**

Replace `run_first_officer(...)` with the new Codex helper and pass the workflow path explicitly.

- [ ] **Step 3: Reframe dispatch assertions around observed behavior**

If Codex output includes reliable spawn markers, assert on them. If not, rely on stronger end-state checks:
- worktree created
- stage body updated in worktree or on main as appropriate
- entity held at gate

- [ ] **Step 4: Run the Codex gate spike test**

Run:

```bash
uv run python tests/test_codex_gate_guardrail.py
```

Expected: pass if the prototype can reach the gate; otherwise fail with a precise feasibility signal

- [ ] **Step 5: Commit**

```bash
git add tests/test_codex_gate_guardrail.py
git commit -m "spike: add codex gate guardrail test"
```

---

## Chunk 3: Multi-Dispatch Feasibility

### Task 5: Adapt the rejection-flow E2E test for Codex

**Files:**
- Create: `tests/test_codex_rejection_flow.py`
- Reference: `tests/test_rejection_flow.py`
- Reference: `tests/fixtures/rejection-flow`

- [ ] **Step 1: Copy the existing rejection-flow fixture setup**

Reuse:
- the same workflow fixture
- the same buggy implementation file
- the same test file
- the same `status --next` checks

Keep the validation goal unchanged: a rejected validation should cause a follow-up implementation dispatch.

- [ ] **Step 2: Replace Claude-only dispatch assertions**

Remove assumptions like:

```python
ensign_calls = [c for c in agent_calls if c["subagent_type"] == "ensign"]
```

Replace them with Codex-feasible checks:
- multiple worker runs inferred from output or filesystem state
- rejected review appears in entity/worktree/output
- a follow-up implementation attempt is observable after rejection

- [ ] **Step 3: Run the Codex rejection-flow spike test**

Run:

```bash
uv run python tests/test_codex_rejection_flow.py
```

Expected: pass if Codex multi-agent flow can complete implementation -> validation -> rejection -> rework, or fail with a precise breakpoint

- [ ] **Step 4: Record the exact failure mode if parity is incomplete**

If the test fails, capture which boundary broke:
- worker did not spawn
- worker edits were not applied
- gate handling stalled
- rejected feedback did not trigger a second dispatch
- worktree ownership/branch logic failed

Write this as part of the test output or a short notes block in comments at the top of the file.

- [ ] **Step 5: Commit**

```bash
git add tests/test_codex_rejection_flow.py
git commit -m "spike: add codex rejection flow test"
```

---

## Chunk 4: Decision Output

### Task 6: Document the spike result and fast-track next steps

**Files:**
- Modify: `references/codex-tools.md`

- [ ] **Step 1: Add a short "Codex prototype path" section**

If the spike proves feasible, add:
- the launcher command
- the supported scope for the prototype
- known limitations versus Claude

If the spike fails, add:
- the command used
- the exact failure boundary
- why this blocks fast-track Codex support

- [ ] **Step 2: Add a short recommendation note**

Record one of these outcomes:
- continue with a Codex-specific runtime path
- stop at prototype because multi-agent is not reliable enough
- narrow scope to gate-free or single-dispatch workflows only

- [ ] **Step 3: Verify the docs reference the parallel-path strategy**

Run:

```bash
rg -n "prototype path|parallel|Codex-specific|multi-agent" references/codex-tools.md
```

Expected: matches for the new summary text

- [ ] **Step 4: Commit**

```bash
git add references/codex-tools.md
git commit -m "docs: record codex spike findings"
```

---

## Verification Checklist

- [ ] `rg -n "\.claude/agents|Agent\(|subagent_type|SendMessage|team_name" references/codex-first-officer-prompt.md references/codex-worker-prompt.md` returns no matches
- [ ] `scripts/run_codex_first_officer.sh` has executable bit set
- [ ] `uv run python -m pytest tests/test_status_script.py -q` passes
- [ ] `uv run python tests/test_codex_gate_guardrail.py` runs and reports a clear pass/fail outcome
- [ ] `uv run python tests/test_codex_rejection_flow.py` runs and reports a clear pass/fail outcome
- [ ] No changes are required to the current Claude commission flow, `.claude/agents/` path, or existing Claude E2E tests

## Notes

- This spike intentionally does not preserve the current "self-contained generated workflow" property.
- This spike intentionally does not add a solo-operator fallback.
- If Codex multi-agent proves unreliable, the correct outcome is a documented failure boundary, not a broadened scope.
