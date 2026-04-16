---
id: "163"
title: "Kilocode support — Kilo as a Spacedock runtime"
status: implementation
source:
started: 2026-04-16T06:05:42Z
completed:
verdict:
score:
worktree:
issue:
pr:
---

Add support for Kilo (kilo.ai) as a third Spacedock runtime alongside Claude Code and Codex.

## Problem Statement

Spacedock currently supports:
- Claude Code (via claude-first-officer-runtime.md)
- Codex (via codex-first-officer-runtime.md)

Kilo is another AI coding assistant that uses subagents. Adding it expands supported execution environments.

## Proposed Approach

1. **Runtime detection**: detect Kilo via environment variables
2. **Runtime adapter**: create `kilo-first-officer-runtime.md` following existing adapter patterns
3. **Dispatch mechanism**: implement worker spawning via Kilo's `task` tool
4. **Entity lifecycle**: map stages (backlog → ideation → implementation → validation → done) to Kilo's execution model

## Ideation Research

### 1. Kilo Capability Research

**What is Kilo?**
Kilo (kilo.ai) is an AI coding assistant built on the OpenCode open-source core. It supports subagents, parallel execution, custom agents, and runs across CLI, VS Code, JetBrains, and Cloud Agents.

**Environment Variables for Kilo Runtime Detection:**
- `KILO_CONFIG` — path to additional config file
- `KILO_CONFIG_DIR` — extra directory scanned for agents/commands/plugins
- `KILO_CONFIG_CONTENT` — inline JSON config string
- `KILO_DISABLE_PROJECT_CONFIG` — skip project-level config discovery
- `KILO_PERMISSION` — JSON string merged into permission field

Detection pattern: Check for any `KILO_*` environment variable prefix, or existence of `kilo.json`/`kilo.jsonc` config in project root or `~/.config/kilo/`.

**Tools Kilo Provides:**
- `task` tool — spawns subagents (built-in: `general`, `explore`; custom via config)
- Custom agents defined in `kilo.jsonc` or `.kilo/` directory
- Agent modes: `subagent`, `primary`, `all`

**Agent Lifecycle:**
- Subagents run in isolated sessions with separate conversation history
- Parent agent coordinates via `task` tool and receives summary on completion
- Parallel subagents supported — multiple subagents can run concurrently

**Completion Reporting:**
- Subagent returns a summary to the parent agent
- No built-in team message-passing like Claude Code's `SendMessage`
- More similar to Codex's direct handle model

### 2. Spacedock Runtime Requirements (extracted from adapters)

From `first-officer-shared-core.md`:
1. **Workflow discovery** — find project root and workflow directory
2. **Status script** — execute `status` for entity state management
3. **Entity dispatch** — read entity, stage definition, build checklist
4. **Worker spawning** — runtime-specific dispatch mechanism
5. **Completion handling** — parse stage report, verify checklist
6. **Reuse logic** — reuse existing workers when conditions pass
7. **Gate handling** — present reviews to human, handle approval/rejection
8. **Merge hooks** — run registered hooks at terminal stage

From `claude-first-officer-runtime.md`:
- Team creation via `TeamCreate` (if teams available)
- `Agent()` for dispatch, `SendMessage` for reuse
- Context budget checking via `claude-team`

From `codex-first-officer-runtime.md`:
- Direct handle dispatch via `spawn_agent`
- `send_input` for reuse, `wait_agent` for completion
- Explicit shutdown required

### 3. Gap Analysis: Kilo vs Requirements (CORRECTED)

| Requirement | Kilo Capability | Gap/Missing |
|-------------|------------------|--------------|
| Workflow discovery | Same git/FS access | None |
| Status script | Same `status` tool | None |
| Worker spawning | `task` tool + Agent Manager | **Pattern diff**: parent→subagent, not FO→worker |
| Completion detection | Subagent returns summary | **Pattern diff**: no wait_agent equivalent |
| Reuse logic | Agent Manager tabs (manual) | **Pattern diff**: tab-switching vs message-passing |
| Team creation | Agent Manager | **Pattern diff**: tabs vs team model |
| Concurrent dispatch | Parallel subagents supported | None! |
| Gate handling | Parent presents to human | Partial — needs custom flow |

**Correction (2026-04-16) — FIRST-HAND TEST:**

```
Test: Spawn subagent, then try to send_message to it after completion
Result: "none available" — subagent handle expires immediately

Conclusion: Subagents are NOT addressable after completion.
- task_id provided at spawn
- After subagent returns, handle is gone
- No SendMessage equivalent
- No wait_agent equivalent
```

**Source code verification:**
- Kilo (`packages/opencode/src/tool/task.ts:180`): `Effect.runPromise(run(params, ctx))` — blocking
- OpenCode (upstream): same blocking pattern
- This limitation is inherited from OpenCode, NOT Kilo-specific

**Runtime detection in this session:**
- `KILO=1` — primary detection env var
- `KILOCODE_VERSION=7.2.10`, `KILO_PID`, `KILOCODE_FEATURE=cli` also set

### 4. E2E Test Strategy

**Current test infrastructure** (from `tests/README.md`):
- `--runtime` option accepts `claude` or `codex`
- `run_first_officer()` for Claude, `run_codex_first_officer()` for Codex
- Fixtures under `tests/fixtures/`

**To add Kilo runtime:**
1. Add `--runtime kilo` to `tests/conftest.py`
2. Create `run_kilo_first_officer(runner, workflow_dir, ...)` in `test_lib.py`
3. Add `@pytest.mark.live_kilo` marker (parallel to `live_claude`, `live_codex`)
4. Create fixture under `tests/fixtures/kilo-spike/` for basic dispatch test
5. Follow Codex pattern: Kilo FO invoked via skill (likely `kilo:first-officer`)

**Test verification for `kilo-first-officer-runtime.md`:**
- Runtime detection test (environment variable check)
- Basic workflow execution (backlog → done)
- Entity dispatch via `task` tool
- Stage report parsing
- Merge hook execution (if feasible without persistent handles)

### 5. Implementation Plan

**Numbered steps:**

1. **Create runtime detection in FO skill**
   - Detect Kilo via `KILO_*` env vars or config file existence
   - Load `kilo-first-officer-runtime.md` when detected

2. **Create `kilo-first-officer-runtime.md`**
   - Define entry surface (skill-based like Codex)
   - Map worker resolution (subagent names vs logical IDs)
   - Implement dispatch adapter using `task` tool
   - Define completion shape (subagent return handling)
   - Add reuse handling (or document non-reuse due to handle limitations)
   - Define merge and cleanup flow
   - Add bounded stop rules for single-entity mode

3. **Add Kilo to test infrastructure**
   - Update `tests/conftest.py` with `--runtime kilo` option
   - Add `run_kilo_first_officer()` to `test_lib.py`
   - Add `@pytest.mark.live_kilo` marker support
   - Add Kilo to Makefile test targets

4. **Create E2E test fixtures**
   - Create `tests/fixtures/kilo-spike/` (minimal workflow)
   - Test basic dispatch and completion

5. **Verify and iterate**
   - Run static tests
   - Run live Kilo tests
   - Fix gaps based on test results

**Acceptance Criteria with Concrete Verifiers:**

| Criterion | Verifier |
|-----------|----------|
| Runtime detection works | FO detects Kilo env and loads adapter |
| FO dispatches entities to Kilo subagents | E2E test shows `task` tool called with entity work |
| Basic workflow execution completes | Entity reaches terminal stage under Kilo |
| Merge hooks fire correctly | Terminal stage triggers merge hook (if handle model supports) |
| Single-entity mode works | Entity completes via `kilo exec` style invocation |
| Tests run under `--runtime kilo` | `pytest --runtime kilo` executes Kilo-specific tests |

**Risks:**
- `task` tool dispatch may not map cleanly to FO→worker pattern
- Subagent handle persistence not supported — reuse may be impossible
- No team abstraction means concurrent dispatch limited to parallel `task` calls
- Context budget API unknown — may need workarounds

### Impact Analysis: Spacedock Usability

| Spacedock Feature | Impact | Severity |
|-----------------|-------|----------|
| **Worker reuse** (per #96) | Broken - cannot message completed subagent | High |
| **Feedback bounce** | Broken - needs fresh dispatch each cycle | High |
| **Standing teammates** | Broken - cannot keep alive across session | High |
| **Concurrent dispatch** | Partial - task blocks, but parallel `task` calls possible | Medium |
| **Single-entity mode** | ✅ Works - aligns with blocking behavior | None |

**Mitigation:** Kilo runtime must FRESH-DISPATCH for every stage. No reuse. This is acceptable for single-entity bounded runs but increases per-entity cost in multi-stage workflows.

**Workaround:** Use deterministic stage ordering (backlog → ideation → done) without feedback cycles to minimize dispatches.

## Completion Checklist

- [x] Research Kilo (kilo.ai) capabilities — understand the runtime
- [x] Extract Spacedock runtime requirements from existing adapters
- [x] Gap analysis: Kilo vs requirements
- [x] E2E test strategy designed
- [x] Implementation plan written to entity body
- [x] Runtime adapter created (`kilo-first-officer-runtime.md` at skill path)
- [ ] Test infrastructure updated for Kilo
- [ ] E2E tests pass under Kilo runtime