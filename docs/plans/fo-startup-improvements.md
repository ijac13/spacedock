---
id: 074
title: First-officer startup improvements — README search and bare mode detection
status: implementation
source: CL
started: 2026-03-29T18:00:00Z
completed:
verdict:
score: 0.70
worktree: .worktrees/ensign-074-startup
---

Two improvements to the first-officer startup sequence.

## 1. README search should ignore common directories

The FO startup step 1 uses `grep -rl '^commissioned-by: spacedock@' --include='README.md' "$project_root"` to discover workflow directories. This searches everything under the project root, including:

- `node_modules/` — huge, slow, will never have workflows
- `.worktrees/` — copies of the repo, produces duplicate hits
- Other common noise: `.git/`, `vendor/`, `dist/`, `build/`

The search should exclude these directories. Observed in this session: the discovery returned 16 results including 10 from `.worktrees/` that had to be filtered out manually.

## 2. Detect TeamCreate availability and report bare mode

The FO template's startup step 3 calls `TeamCreate`. If teams are not available (the experimental flag is off, or the environment doesn't support it), the FO should detect this and tell the user it's operating in a fallback mode — sequential dispatch without team coordination.

From task 033's experiment: when team tools are unavailable, the FO can still function by dispatching via `Agent()` without `team_name`, with ensign output returning via the subagent completion mechanism. The FO should explicitly detect and report this rather than silently adapting or failing.

Proposed behavior:
- At startup, check if TeamCreate is available (via ToolSearch or attempt)
- If available: proceed with team-based dispatch as today
- If not available: report to the captain that teams are unavailable and the FO is operating in bare mode (sequential dispatch, no inter-agent messaging). Then skip TeamCreate and proceed.

---

## Ideation

### 1. README search: proposed grep command with exclusions

The current grep command in the FO template (Startup step 1, line 16 of `templates/first-officer.md`):

```bash
grep -rl '^commissioned-by: spacedock@' --include='README.md' "$project_root"
```

Proposed replacement with `--exclude-dir` flags:

```bash
grep -rl '^commissioned-by: spacedock@' --include='README.md' \
  --exclude-dir=node_modules \
  --exclude-dir=.worktrees \
  --exclude-dir=.git \
  --exclude-dir=vendor \
  --exclude-dir=dist \
  --exclude-dir=build \
  --exclude-dir=__pycache__ \
  "$project_root"
```

**Rationale for each exclusion:**

- `node_modules/` — JS dependency tree, massive, will never contain user workflows
- `.worktrees/` — git worktrees created by spacedock itself, produces duplicate hits for in-progress entities (observed: 10/16 results from worktrees in one session)
- `.git/` — git internals, never relevant
- `vendor/` — Go/PHP dependency vendoring, same rationale as node_modules
- `dist/` and `build/` — compiled output directories, never relevant
- `__pycache__` — Python bytecode cache, never relevant

**Hardcoded vs configurable:** Hardcoded. These directories are universally noise — no workflow will ever live inside them. A configurable list adds complexity with no practical benefit. If a user has an unusual directory to exclude, they can modify their generated FO template directly (it's a local file, not a locked artifact). YAGNI.

### 2. Bare mode: detection mechanism

**Detection approach: ToolSearch probe (not try/catch)**

Based on task 033 Experiment 2 findings, the FO already naturally uses `ToolSearch("select:TeamCreate")` to check tool availability before calling it. The proposal is to formalize this pattern into the template rather than leaving it to model improvisation.

In Startup step 3, before calling `TeamCreate`, the FO should:

```
ToolSearch(query="select:TeamCreate", max_results=1)
```

If the result contains a TeamCreate definition: proceed normally (team mode).
If the result says "No matching deferred tools found": enter bare mode.

**Why ToolSearch over try/catch:**
- ToolSearch is a read-only probe — no side effects, no error recovery needed
- Task 033 Experiment 2 confirmed this is the pattern the model naturally gravitates toward
- A failed TeamCreate call might have side effects (partial team state) that need cleanup
- ToolSearch failure is unambiguous: the tool either exists or it doesn't

**Bare mode startup message to the captain:**

```
Teams are not available in this session. Operating in bare mode:
- Dispatch is sequential (one agent at a time via subagent)
- Agent completion returns via subagent mechanism instead of messaging
- Feedback cycles require sequential re-dispatch instead of inter-agent messaging

All workflow functionality is preserved. Dispatch and gate behavior are unchanged.
```

This message should appear once at startup, right after the detection. It is informational — no captain action required.

### 3. How bare mode affects dispatch, completion, and feedback flows

**Dispatch (Startup step 3 + Dispatch section):**
- Skip `TeamCreate` entirely (no team to create)
- In the `Agent()` call, omit the `team_name` parameter
- Everything else (worktree creation, state updates, checklist assembly) is unchanged
- Dispatch is naturally sequential anyway when using `Agent()` without teams — the FO blocks until the subagent completes. This means concurrent dispatch of multiple entities is not possible in bare mode. The FO should dispatch one entity at a time and process completions inline.

**Completion (after each dispatch):**
- In team mode: ensign sends `SendMessage(to="team-lead")` with completion notice, FO receives it asynchronously
- In bare mode: ensign completes, result returns to FO context via the parent-child subagent mechanism (task_notification). The FO processes the completion inline.
- The FO's post-completion logic (stage report review, gate check, status --next) is identical in both modes — only the delivery mechanism differs.

**Feedback rejection flow:**
- In team mode: FO sends findings to the target-stage agent via `SendMessage`, reviewer and target agent communicate directly
- In bare mode: FO cannot keep agents alive across dispatches (subagents are blocking). The feedback cycle becomes: (1) FO dispatches target-stage agent with findings in the prompt, (2) target agent fixes and completes, (3) FO dispatches reviewer with updated state, (4) reviewer checks and completes. This is sequential rather than concurrent but functionally equivalent.
- The ensign completion protocol changes: instead of `SendMessage(to="team-lead")`, the ensign's work simply returns when it finishes. The ensign template's completion instructions should say "send a completion message to team-lead" (team mode) or just complete with the stage report written (bare mode). Since the ensign also probes for SendMessage via ToolSearch (confirmed in task 033), this degrades naturally without template changes.

**Gate behavior:**
- Unchanged. Gates are FO-to-captain interactions, not agent-to-agent. The FO presents the stage report and waits for captain input regardless of mode.

### 4. Template changes required

**`templates/first-officer.md`:**
1. Startup step 1: Replace grep command with the version including `--exclude-dir` flags
2. Startup step 3: Wrap TeamCreate in a ToolSearch probe. If unavailable, set an internal `bare_mode` flag and report to captain. Skip TeamCreate.
3. Dispatch section: Conditionally include `team_name` only when not in bare mode. Add a note that dispatch blocks in bare mode (sequential).
4. Dispatch section: In the worktree dispatch prompt, add git branch constraint: "Your git branch is {branch}. All commits MUST be on this branch. Do NOT switch branches or commit to main." This is inside the existing `{if worktree}` block — non-worktree stages (which work on main) are unaffected.
5. Post-completion: No changes needed — the FO processes completions the same way regardless of delivery mechanism.
6. Feedback rejection flow: Add a bare-mode variant that dispatches sequentially instead of relying on inter-agent messaging.

**`templates/ensign.md`:** No changes needed. The ensign already naturally probes for SendMessage via ToolSearch and falls back to subagent return (task 033 confirmed this). The branch constraint is injected via the dispatch prompt, not the ensign template.

### 5. Acceptance criteria

1. The FO grep command in `templates/first-officer.md` includes `--exclude-dir` for node_modules, .worktrees, .git, vendor, dist, build, __pycache__
2. The FO startup step 3 probes for TeamCreate via ToolSearch before attempting to call it
3. When TeamCreate is unavailable, the FO prints a bare-mode message to the captain and continues startup
4. In bare mode, `Agent()` dispatch omits `team_name` and operates sequentially
5. The feedback rejection flow has a bare-mode variant that dispatches sequentially
6. No changes to `templates/ensign.md` (natural degradation is sufficient)
7. Commissioning a workflow and running the FO with `--disallowed-tools "TeamCreate,TeamDelete,SendMessage"` completes a full entity lifecycle (backlog -> work -> done) without errors
8. Worktree-stage dispatch prompts include a git branch constraint preventing commits to main
9. Non-worktree-stage dispatch prompts do NOT include the branch constraint (agents work on main)

## Stage Report: ideation

- [x] README search: exact grep command with exclusions proposed
  Proposed grep with 7 `--exclude-dir` flags (node_modules, .worktrees, .git, vendor, dist, build, __pycache__). Hardcoded list — YAGNI on configurability.
- [x] Bare mode: detection mechanism and user-facing message proposed
  ToolSearch probe for TeamCreate (not try/catch), based on task 033 Experiment 2 findings where the FO naturally uses this pattern. Startup message drafted.
- [x] How bare mode affects dispatch/completion/feedback flows
  Dispatch omits team_name and is sequential. Completion returns via subagent mechanism. Feedback cycles become sequential re-dispatch instead of inter-agent messaging. Gates unchanged.
- [x] Acceptance criteria defined
  7 acceptance criteria covering grep exclusions, ToolSearch probe, bare-mode message, sequential dispatch, feedback flow, ensign unchanged, and end-to-end validation.

### Summary

Fleshed out both improvements with concrete proposals. The grep exclusion list is hardcoded (7 directories) based on observed noise from .worktrees and standard dependency/build directories. Bare mode detection uses ToolSearch probe (validated by task 033 Experiment 2), with a clear startup message and well-defined degradation paths for dispatch (sequential, no team_name), completion (subagent return), and feedback (sequential re-dispatch). The ensign template needs no changes — it already degrades naturally.
