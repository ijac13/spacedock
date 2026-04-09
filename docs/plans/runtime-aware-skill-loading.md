---
id: 109
title: Make skill entrypoints runtime-aware — Codex loads Codex runtime, Claude loads Claude runtime
status: ideation
source: CL diagnosis — Codex main broken, skill loads wrong runtime contract
started: 2026-04-09T18:16:42Z
completed:
verdict:
score: 0.9
worktree:
issue:
pr:
---

## Problem

`skills/first-officer/SKILL.md` and `skills/ensign/SKILL.md` unconditionally load Claude-specific runtime references (`references/claude-first-officer-runtime.md`, `references/claude-ensign-runtime.md`). When Codex runs these skills, it gets Claude Code dispatch instructions (TeamCreate, SendMessage, Agent tool) that don't exist on Codex, causing timeouts and broken dispatch.

The same mismatch exists for both first-officer and ensign skills.

## Approach: runtime split (option 2 from diagnosis)

1. Keep shared core in `references/first-officer-shared-core.md` and `references/ensign-shared-core.md` — platform-agnostic behavioral contracts
2. Make skill SKILL.md files runtime-aware: detect the platform and load the appropriate runtime reference
   - Codex: load `references/codex-first-officer-runtime.md` / `references/codex-ensign-runtime.md`
   - Claude Code: load `references/claude-first-officer-runtime.md` / `references/claude-ensign-runtime.md`
3. Align the Codex packaged worker dispatch path with the existing helper contract (resolve logical id to worker_key, build packaged bootstrap prompt, spawn_agent with fork_context=false)
4. Both first-officer and ensign skills get the same treatment — fix consistently, not just the failing path

## Open question

How does the skill detect which runtime it's on? Options:
- Environment variable (`CODEX_HOME`, `CLAUDECODE`, etc.)
- Platform-specific file presence (`.codex/` vs `.claude/`)
- Separate skill entrypoints per platform (`skills/first-officer/SKILL.md` for Claude, different path for Codex)
- The skill prompt can check which tools are available (TeamCreate exists → Claude Code)

## Acceptance criteria

1. Codex FO loads `codex-first-officer-runtime.md`, not `claude-first-officer-runtime.md`
   - Test: static content check that SKILL.md references both runtime files conditionally
   - Test: Codex E2E — verify Codex FO log does not contain Claude-specific dispatch primitives (TeamCreate, SendMessage, Agent tool)
2. Codex ensign loads `codex-ensign-runtime.md`, not `claude-ensign-runtime.md`
   - Test: static content check that SKILL.md references both runtime files conditionally
   - Test: Codex E2E — verify Codex ensign does not attempt SendMessage for completion
3. Claude Code FO still loads `claude-first-officer-runtime.md` (no regression)
   - Test: existing `test_agent_content.py` tests pass (may need updates to reflect new SKILL.md wording)
   - Test: existing Claude Code E2E tests pass unchanged
4. Claude Code ensign still loads `claude-ensign-runtime.md` (no regression)
   - Test: existing `test_agent_content.py` tests pass
   - Test: existing Claude Code E2E tests pass unchanged
5. Codex packaged-agent E2E test passes
   - Test: `test_codex_packaged_agent_e2e.py` (if it exists) or a new Codex E2E test
6. Existing Claude Code E2E tests pass
   - Test: run full E2E suite with `--runtime claude`

## Proposed approach

### Runtime detection mechanism

SKILL.md is a markdown prompt — it cannot branch with if/else. The detection must be an instruction to the agent. The recommended mechanism:

**Use `${CLAUDE_SKILL_DIR}` expansion as the detection signal.** Claude Code substitutes `${CLAUDE_SKILL_DIR}` to the skill directory's absolute path during skill invocation (Phase 2 of skill loading — see ch12-extensibility.md). Codex does NOT perform this substitution. So:

- If the agent sees a literal unexpanded `${CLAUDE_SKILL_DIR}` in the prompt, it's on Codex.
- If `${CLAUDE_SKILL_DIR}` resolved to an actual path, it's on Claude Code.

However, this is fragile — the agent may not reliably distinguish expanded vs unexpanded variable syntax in its own prompt text. A more robust approach:

**Instruct the agent to check for the `CLAUDECODE` environment variable.** This variable is set by Claude Code sessions (it's the reason tests must `unset CLAUDECODE` before launching subprocess sessions). It is never set in Codex. The check is a simple `echo $CLAUDECODE` or a Bash test.

But even simpler: **use the path structure itself.** On Claude Code, `${CLAUDE_SKILL_DIR}` expands to the real path (e.g., `/path/to/spacedock/skills/first-officer`). On Codex, the skill is loaded from `~/.agents/skills/spacedock/first-officer/SKILL.md` — but importantly, Codex reads the SKILL.md content and presents it to the model without path variable substitution.

**Recommended approach: conditional instructions in SKILL.md.** The SKILL.md tells the agent to read the shared core and guardrails (always), then detect the runtime and read the appropriate runtime reference. Detection is based on whether `${CLAUDE_SKILL_DIR}` was substituted (agent can try to read a file using the path — if it works, it's Claude Code).

Actually, the simplest reliable approach: **use two separate path patterns and let the agent try them.** But this is messy.

**Final recommendation: explicit conditional instruction.**

The SKILL.md should:
1. Always read shared-core and guardrails (using `${CLAUDE_SKILL_DIR}` for Claude, relative/bare paths for Codex)
2. Instruct the agent to determine the runtime: "If you have access to the `TeamCreate` tool or the `CLAUDECODE` environment variable is set, you are on Claude Code — read the Claude runtime. Otherwise, you are on Codex — read the Codex runtime."

This is robust because:
- `TeamCreate` is a Claude Code team tool that Codex never has
- `CLAUDECODE` env var is set by Claude Code, never by Codex
- Both signals are already used in the codebase (the Claude runtime itself probes for TeamCreate)

### Before/after for skill files

#### `skills/first-officer/SKILL.md` — Before

```markdown
Read these reference files to load the first officer operating contract:

1. Read `${CLAUDE_SKILL_DIR}/../../references/first-officer-shared-core.md`
2. Read `${CLAUDE_SKILL_DIR}/../../references/code-project-guardrails.md`
3. Read `${CLAUDE_SKILL_DIR}/../../references/claude-first-officer-runtime.md`

Then begin the Startup procedure from the shared core.
```

#### `skills/first-officer/SKILL.md` — After

```markdown
Read these reference files to load the first officer operating contract:

1. Read `${CLAUDE_SKILL_DIR}/../../references/first-officer-shared-core.md`
2. Read `${CLAUDE_SKILL_DIR}/../../references/code-project-guardrails.md`
3. Detect your runtime to load the correct runtime adapter:
   - If the environment variable `CLAUDECODE` is set (check with `echo $CLAUDECODE`), read `${CLAUDE_SKILL_DIR}/../../references/claude-first-officer-runtime.md`
   - Otherwise, read `${CLAUDE_SKILL_DIR}/../../references/codex-first-officer-runtime.md`

Then begin the Startup procedure from the shared core.
```

#### `skills/ensign/SKILL.md` — Before

```markdown
Read these reference files to load the ensign operating contract:

1. Read `${CLAUDE_SKILL_DIR}/../../references/ensign-shared-core.md`
2. Read `${CLAUDE_SKILL_DIR}/../../references/code-project-guardrails.md`
3. Read `${CLAUDE_SKILL_DIR}/../../references/claude-ensign-runtime.md`

Then read your assignment and begin work.
```

#### `skills/ensign/SKILL.md` — After

```markdown
Read these reference files to load the ensign operating contract:

1. Read `${CLAUDE_SKILL_DIR}/../../references/ensign-shared-core.md`
2. Read `${CLAUDE_SKILL_DIR}/../../references/code-project-guardrails.md`
3. Detect your runtime to load the correct runtime adapter:
   - If the environment variable `CLAUDECODE` is set (check with `echo $CLAUDECODE`), read `${CLAUDE_SKILL_DIR}/../../references/claude-ensign-runtime.md`
   - Otherwise, read `${CLAUDE_SKILL_DIR}/../../references/codex-ensign-runtime.md`

Then read your assignment and begin work.
```

### Open issue: `${CLAUDE_SKILL_DIR}` on Codex

There is a subtlety: on Codex, `${CLAUDE_SKILL_DIR}` is not substituted. The agent will see the literal string `${CLAUDE_SKILL_DIR}/../../references/...` in the prompt. Codex agents can still resolve these paths if they know the skill directory location — and the Codex runtime references already document the skill path convention (`~/.agents/skills/{namespace}/{name}/SKILL.md`).

Two sub-options:

**Option A: Keep `${CLAUDE_SKILL_DIR}` and rely on Codex agents to resolve it.** Codex agents already know the skill lives at `~/.agents/skills/spacedock/first-officer/`, so `${CLAUDE_SKILL_DIR}/../../references/` resolves to `~/.agents/skills/spacedock/references/` which is a symlink to the real `references/` directory (set up by `prepare_codex_skill_home`). This works today because the test harness creates this symlink structure.

**Option B: Add a fallback path instruction for Codex.** After the `${CLAUDE_SKILL_DIR}` path, add: "If the path does not resolve, look for the references directory relative to your skill location at `~/.agents/skills/spacedock/references/`."

Option A is the simpler path and works with the existing test infrastructure. The Codex FO already navigates this path structure successfully for the shared-core and guardrails — the only issue is which *runtime* file it loads, not whether it can find the files.

**Recommendation: Option A.** No path changes needed — just change which runtime file name appears in the conditional.

### Files that need changes

1. `skills/first-officer/SKILL.md` — add runtime detection conditional
2. `skills/ensign/SKILL.md` — add runtime detection conditional
3. `tests/test_agent_content.py` — update `test_first_officer_skill_reads_references_directly()` to check for both runtime references and the conditional structure
4. `scripts/test_lib.py` — update `assembled_agent_content()` to accept a runtime parameter so it can assemble the correct runtime reference for each platform

### Files that do NOT need changes

- `references/first-officer-shared-core.md` — platform-agnostic, no changes
- `references/ensign-shared-core.md` — platform-agnostic, no changes
- `references/code-project-guardrails.md` — platform-agnostic, no changes
- `references/claude-first-officer-runtime.md` — content unchanged
- `references/claude-ensign-runtime.md` — content unchanged
- `references/codex-first-officer-runtime.md` — content unchanged
- `references/codex-ensign-runtime.md` — content unchanged
- `agents/first-officer.md` — unchanged (uses skill preloading)
- `agents/ensign.md` — unchanged (uses skill preloading)

### Codex packaged worker dispatch alignment

The Codex packaged worker dispatch path (`codex-first-officer-runtime.md` § Dispatch Adapter) already describes how to resolve logical ids to `worker_key`, build self-contained prompts, and `spawn_agent` with `fork_context=false`. The worker prompt instructs the spawned agent to read its skill definition from `~/.agents/skills/{namespace}/{name}/SKILL.md`. Since that SKILL.md will now have the conditional runtime detection, the Codex ensign worker will correctly load `codex-ensign-runtime.md` instead of `claude-ensign-runtime.md`.

No changes needed to the dispatch adapter itself — the fix is entirely in the SKILL.md entrypoints.

### Test plan

**Static tests (free, fast):**
1. Update `test_first_officer_skill_reads_references_directly` to verify both runtime references appear in SKILL.md and that the conditional structure is present
2. Add `test_ensign_skill_reads_references_directly` (parallel test for ensign)
3. Add `test_skill_runtime_detection_uses_claudecode_env` — verify both SKILL.md files reference `CLAUDECODE` as the detection mechanism

**Assembled content tests (free, fast):**
4. Update `assembled_agent_content()` to accept `runtime="claude"|"codex"` parameter, defaulting to `"claude"` for backward compatibility
5. Existing `test_assembled_claude_first_officer_*` tests pass unchanged (they use the default claude runtime)
6. Add `test_assembled_codex_first_officer_has_dispatch_adapter` — verify Codex-assembled FO content includes `spawn_agent`, `fork_context=false`, and does NOT include `TeamCreate`

**E2E tests (costs money, slower):**
7. Existing Claude Code E2E tests pass unchanged — regression check
8. Codex E2E test — run the first officer on Codex and verify the log does not contain Claude-specific dispatch primitives

E2E tests are proportional to risk: the change is small (2 SKILL.md files, conditional on a well-known env var), so existing E2E tests should catch regressions. A targeted Codex E2E test is warranted because the whole point of this task is fixing the Codex path.

## Stage Report: ideation

- [x] Review current skill entrypoints and reference loading
  Reviewed `skills/first-officer/SKILL.md` and `skills/ensign/SKILL.md` — both unconditionally load `claude-*-runtime.md` using `${CLAUDE_SKILL_DIR}` paths.
- [x] Review Codex vs Claude runtime references
  Read all four runtime files. Claude runtime uses TeamCreate/SendMessage/Agent tool. Codex runtime uses spawn_agent with fork_context=false. The behavioral contracts are fundamentally different dispatch models.
- [x] Research runtime detection mechanism
  Recommended: check `CLAUDECODE` environment variable. Set by Claude Code sessions, never by Codex. Simple, reliable, already used in the test infrastructure for the same purpose.
- [x] Propose approach with exact before/after wording
  Provided exact before/after for both `skills/first-officer/SKILL.md` and `skills/ensign/SKILL.md`. The change adds a conditional step 3 that checks `CLAUDECODE` to select the runtime file.
- [x] Identify all files that need changes
  4 files: `skills/first-officer/SKILL.md`, `skills/ensign/SKILL.md`, `tests/test_agent_content.py`, `scripts/test_lib.py`. Reference files and agent wrappers are unchanged.
- [x] Define acceptance criteria with test plan
  6 acceptance criteria with specific test methods. 8 tests total: 3 static, 3 assembled-content, 2 E2E.
- [x] Address Codex packaged worker dispatch alignment
  No dispatch adapter changes needed. The fix is entirely in SKILL.md entrypoints. Codex workers will pick up the correct runtime through the same conditional when they read their own SKILL.md.

### Summary

The fix is small and focused: change 2 lines in 2 SKILL.md files (replacing unconditional `claude-*-runtime.md` loads with a conditional that checks `CLAUDECODE` env var), plus test updates. The shared core, guardrails, runtime references, and agent wrappers are all unchanged. The `CLAUDECODE` env var detection is the simplest reliable mechanism — it's already a known platform signal used throughout the test infrastructure.

## Diagnosis context

CL's diagnosis (session that seeded this entity) identified the concrete failure path: when the Codex FO invokes `spacedock:first-officer`, it reads `skills/first-officer/SKILL.md` which unconditionally loads `claude-first-officer-runtime.md`. That runtime instructs the FO to use `TeamCreate`, `SendMessage`, and the `Agent` tool — none of which exist on Codex. The result is timeouts and broken dispatch. The same pattern repeats for ensign workers: the Codex worker bootstrap prompt tells the ensign to invoke `spacedock:ensign`, which reads `skills/ensign/SKILL.md`, which loads `claude-ensign-runtime.md` containing `SendMessage` completion signals.

Two options were considered:
- **Option 1 (minimal fix):** Hardcode the correct runtime file in the Codex invocation prompt or test harness, bypassing the skill entrypoint.
- **Option 2 (proper runtime split):** Make the SKILL.md itself runtime-aware so both platforms get the correct runtime automatically.

Option 2 was chosen because the mismatch exists for both FO and ensign skills, and a minimal fix would leave the same bug latent for any future Codex invocation that goes through the skill system.

### Additional observation from failing run

In the failing Codex packaged-agent run, the FO not only loaded the wrong runtime — it also spawned a worker with a handwritten validation prompt rather than the packaged bootstrap shape encoded in `build_codex_worker_bootstrap_prompt()`. This is a secondary symptom: loading the Claude runtime gave the FO Claude-style dispatch instructions (Agent tool), so it improvised a Codex-compatible dispatch rather than following the Codex runtime's `spawn_agent(fork_context=false)` pattern. Once the correct Codex runtime loads, the FO should follow the documented `spawn_agent` dispatch pattern. The Codex E2E test (AC5) will verify this.

### Resolved open questions

- **`references/codex-ensign-runtime.md` exists** — confirmed in the repo (989 bytes, last modified Apr 8). No new reference files need to be created.
- **Entity 107 (team agents lose skills)** is a separate known issue: dispatched ensigns in Claude Code team mode silently lose their skill frontmatter. That bug affects the Claude path (ensigns rely on dispatch prompts, not skill loading). It does not affect this task's Codex fix, but it means the ensign SKILL.md change only helps Codex and bare-mode Claude dispatch, not team-mode dispatch.

### Implementation approach

The implementation follows a two-step verification strategy:
1. Apply the runtime-aware SKILL.md changes (the production fix).
2. Rerun the Codex E2E (`test_codex_packaged_agent_e2e.py`) to verify both runtime loading AND dispatch path behavior correct themselves. If dispatch still fails despite correct runtime loading, the dispatch adapter may need a separate fix — but the evidence so far suggests the handwritten-prompt symptom is a consequence of loading the wrong runtime, not an independent bug.

Test-harness changes (`scripts/test_lib.py`, `tests/test_agent_content.py`) are verification infrastructure, not part of the production fix. They are listed separately in the implementation plan.
