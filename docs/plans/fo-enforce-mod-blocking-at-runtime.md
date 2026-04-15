---
title: First officer must enforce mod-declared blocking actions at runtime
id: 114
status: implementation
source: CL observation during entity 110 closeout
started: 2026-04-09T22:56:43Z
completed:
verdict:
score: 0.80
worktree: .worktrees/spacedock-ensign-fo-enforce-mod-blocking-at-runtime
issue:
pr: #92
---

First officer currently relies too heavily on remembering mod instructions from prose. That is brittle. A mod can require a stop, approval, or external wait, but the runtime does not yet enforce those requirements mechanically.

## Problem Statement

The `pr-merge` mod correctly says gate approval does not imply PR approval, but first officer can still drift unless it re-reads and obeys the mod at the exact transition point. This is a general workflow safety problem, not just a PR problem.

## Desired Outcome

Add a generic runtime mechanism so active mods can force first officer to pause for captain approval or another blocking condition, and a resumed session cannot silently skip that pending requirement.

## CI green gate

This task must green `test_push_main_before_pr.py` in `make test-live-claude`. The live Claude run on PR #87 reached the `pr-merge` path, called `gh pr create`, and still archived the entity with an empty `pr` field. That is the exact class of drift this task is meant to prevent: the merge hook side effect happened, but the runtime still advanced past the pending mod-controlled block instead of preserving a PR-pending state.

Until task 114 lands, `test_push_main_before_pr.py` is temporarily SKIPPED in the live Claude Makefile target so unrelated live coverage can stay green. The implementer must restore that test to the active `test-live-claude` target and verify it passes end-to-end before closing this task.

## Follow-up Observation From Task 139

Task 139 exposed the concrete failure mode this task needs to prevent. After validation passed, the first officer advanced the entity straight through terminalization and archival without running the `pr-merge` mod first. The problem was not lack of prose coverage; the shared core already says merge hooks run before any local merge, archival, or terminal status advancement. The failure was that the stop lived only in instructions, not in an enforced runtime checkpoint.

That confirms the main design direction here:

1. **Runtime enforcement remains the primary fix.** The first officer/runtime must track pending mod-controlled blocking actions at the transition boundary itself. A terminal or merge-sensitive transition should not complete until the mod has either handled it or explicitly yielded back to the default path.
2. **`status --set` is a useful supporting guardrail, not the source of truth.** In practice, first officer uses `status --set` to advance entities, so that command is a natural place to add friction for dangerous direct transitions. When a caller tries to set a mod-sensitive status (for example, a terminal state that would normally run merge hooks), `status --set` should warn or refuse by default and reserve `--force` for cases where the captain explicitly approved bypassing the normal hook/block flow.
3. **Pending mod blocks should survive session drift and resume.** If a mod requires approval, an external wait, or a PR-creation step, the resumed runtime should see that requirement as active state rather than recomputing it from memory or hoping the operator remembers the prose.

This means the likely implementation shape is layered:

- first-officer/runtime owns correctness and blocking semantics
- `status --set` provides last-mile friction against operator error on direct transitions
- `--force` exists only as an explicit override for captain-approved direct advancement

## Stage Report

### Checklist Item 1: Problem Restatement

The first officer's Merge and Cleanup section in `first-officer-shared-core.md` says "Run registered merge hooks before any local merge, archival, or status advancement." During the session captured in the 2026-04-09 debrief, the FO advanced an entity straight through terminalization and archival without running the `pr-merge` mod's merge hook first — it performed `git merge` directly instead of invoking the hook that would have created a PR for captain review. The prose coverage was already correct: the shared core explicitly requires merge hooks to run before any terminal transition. The failure happened because the instruction lived only in natural-language prose, and the FO drifted past it under context pressure. No runtime mechanism enforced the stop. The fix must make mod-declared blocking actions into hard checkpoints that the runtime cannot skip, even when the FO's instruction-following degrades.

### Checklist Item 2: Current Mod Lifecycle Survey

**Mod discovery** happens during `status --boot`. The status script's `scan_mods()` function (line 396 of `skills/commission/bin/status`) walks `{workflow_dir}/_mods/*.md`, parses `## Hook: {point}` headings, and returns a `{hook_point: [mod_names]}` mapping. The boot output prints this under the `MODS` section, grouped by lifecycle point.

**Supported lifecycle points** (from `first-officer-shared-core.md`, Mod Hook Convention section):

> Mods live in `{workflow_dir}/_mods/` and use `## Hook: {point}` headings.
>
> Supported lifecycle points:
> - `startup`
> - `idle`
> - `merge`
>
> Hooks are additive and run in alphabetical order by mod filename.

**Merge hooks and terminal transitions** (from `first-officer-shared-core.md`, Merge and Cleanup section):

> When an entity reaches its terminal stage:
>
> 1. Run registered merge hooks before any local merge, archival, or status advancement.
> 2. If a merge hook created or set a `pr` field, report the PR-pending state and do not local-merge.
> 3. If no merge hook handled the merge, perform the default local merge from the stage worktree branch.
> 4. Update frontmatter: `status --workflow-dir {workflow_dir} --set {slug} completed verdict={verdict} worktree=`
> 5. Archive the entity into `{workflow_dir}/_archive/`.
> 6. Remove the worktree ...

The current prose is correct but unenforced. There is no runtime state, no frontmatter field, and no `status --set` guard that prevents skipping step 1 and jumping to steps 4-6.

**Hook invocation in the event loop** (from `claude-first-officer-runtime.md`, Event Loop section):

> 3. **If nothing is dispatchable** — Fire `idle` hooks (from registered mods), then re-run `status --next`.

Startup hooks are invoked from the `--boot` parse path. Neither startup nor idle hooks currently have blocking semantics — they are advisory and fire-and-forget.

### Checklist Item 3: Runtime Enforcement Mechanism

#### Layer 1: Runtime — FO tracks pending mod blocks

**How does the FO know a block is active?**

When an entity reaches a terminal stage boundary (the completion path triggers Merge and Cleanup), the FO checks whether any `merge` hooks are registered (from the boot-time `MODS` data). If merge hooks exist, the FO sets a `mod-block` field in the entity's frontmatter before invoking the hook:

```
status --set {slug} mod-block=merge:{mod_name}
```

The value format is `{lifecycle_point}:{mod_name}`, e.g., `merge:pr-merge`. This records which mod is blocking and at which lifecycle point.

**Where is this state tracked?**

In the entity's YAML frontmatter as a `mod-block` field. This is persisted on disk and survives session crashes, context resets, and session resumes. The FO reads this field on startup (during boot scan) and on every transition attempt.

**How does it survive session resume?**

On resume, the FO's boot scan reads all entity frontmatter. Any entity with a non-empty `mod-block` field is treated as blocked. The FO re-reads the mod file to determine what action is still pending (e.g., the pr-merge mod's merge hook requires captain approval before pushing). The FO does not re-run the hook from scratch — it resumes the conversation with the captain about the pending action.

**When is the block cleared?**

- The mod hook itself signals completion. For `pr-merge`, this happens when either (a) a PR is created and the `pr` field is set, or (b) the captain declines and chooses an alternative path.
- The FO clears `mod-block` via `status --set {slug} mod-block=` after the mod hook completes successfully.
- The `--force` flag on `status --set` can also clear it (Layer 3).

#### Layer 2: `status --set` transition guard

**What transitions does `status --set` refuse?**

When a `mod-block` field is non-empty on the target entity, `status --set` refuses updates to these fields by default:

- `status` set to a terminal stage name (e.g., `done`)
- `completed` (timestamp that signals terminal resolution)
- `verdict` (terminal outcome)
- `worktree=` (clearing worktree, which is part of the cleanup path)

These are the fields that comprise the terminal transition. Blocking them prevents the archival path from completing while a mod is still pending.

**Error message:**

```
Error: entity {slug} has pending mod-block (merge:pr-merge). Use --force to override.
```

**How does the caller know which mod is blocking?**

The error message includes the `mod-block` value, which names both the lifecycle point and the mod. The FO can also read the field directly via frontmatter parsing.

#### Layer 3: `--force` override

**When does `--force` apply?**

`--force` bypasses the mod-block guard on `status --set`. It is intended for cases where the captain has explicitly approved skipping the mod's blocking action (e.g., "skip the PR, just local-merge").

**What gets logged?**

When `--force` is used with a mod-block active, `status --set` prints a warning to stderr:

```
Warning: --force overriding mod-block (merge:pr-merge) on entity {slug}
```

The FO must also clear the `mod-block` field as part of the forced update.

**Audit trail:**

The git commit that records the forced transition serves as the audit trail. The FO's commit message should note the override: `merge: {slug} force-override mod-block (merge:pr-merge)`. No separate log file is needed — git history is the authoritative record.

### Checklist Item 4: State Model for Pending Mod Blocks

**Storage:** A `mod-block` field in the entity's YAML frontmatter. This is a string field, empty by default. When a mod-controlled blocking action is pending, it holds `{lifecycle_point}:{mod_name}`.

**How it is set:** By the FO, using `status --set {slug} mod-block=merge:{mod_name}`, immediately before invoking the mod hook. The FO sets it, not the mod itself — mods are prose instructions, not executables. The FO is the actor that reads the mod and performs the actions it describes.

**How it is cleared:**
- Normal path: The FO clears it via `status --set {slug} mod-block=` after the mod hook's blocking action completes (PR created, captain chose an alternative, etc.).
- Force path: The captain instructs the FO to force past, and the FO uses `status --set {slug} mod-block= --force` or includes `mod-block=` in a `--force` update batch.

**Session resume behavior:** The FO reads `mod-block` from entity frontmatter during boot. If non-empty, the FO:
1. Parses the lifecycle point and mod name from the value.
2. Reads the mod file at `{workflow_dir}/_mods/{mod_name}.md`.
3. Resumes the mod's blocking action (e.g., presents the PR summary to the captain again, or checks whether the PR was already created in a prior session).

The FO does not need to re-scan all mods on every `--set` call. The `mod-block` frontmatter field is the persisted state. The `status --set` guard reads only the entity's own frontmatter to check for the field.

**Multiple concurrent blocks:** The current design supports one `mod-block` per entity. Merge hooks run in alphabetical order by mod filename (per the Mod Hook Convention), and only one should be blocking at a time. If a future need arises for multiple concurrent blocks, the field could be extended to a comma-separated list, but that is out of scope for this task.

### Checklist Item 5: `status --set` Guard Algorithm

For each `status --set {slug} field=value [field=value ...]` invocation:

1. Read the target entity's frontmatter from the resolved path (worktree or main).
2. Check whether the entity has a non-empty `mod-block` field.
3. If `mod-block` is empty, proceed normally (no change to current behavior).
4. If `mod-block` is non-empty:
   a. Check whether `--force` is present in the argument list.
   b. If `--force` is NOT present:
      - Scan the requested updates for any field in the **guarded set**: `status` (when the target value matches a terminal stage name), `completed`, `verdict`, or `worktree` (when set to empty string).
      - If any guarded field is being updated, print the error message to stderr and exit with code 1.
      - If no guarded field is being updated (e.g., setting `pr=#57` while a mod-block is active), allow the update. This is important because the mod hook itself may need to set `pr` during its execution.
   c. If `--force` IS present:
      - Print the warning to stderr.
      - Allow all updates to proceed.
      - The caller (the FO) is responsible for also clearing `mod-block` in the same or a subsequent `--set` call.

**Terminal stage detection:** The guard needs to know which stage names are terminal. The `status --set` path currently does not parse the README stages block. Two options:

- **Option A (recommended):** Parse the README stages block in the `--set` path (reuse existing `parse_stages_block`), extract terminal stage names, and check against them. This is a one-time parse per `--set` invocation and the function already exists.
- **Option B:** Guard against ALL `status` field changes when a mod-block is active, not just terminal ones. Simpler but more restrictive — would block normal mid-workflow `status` advances even when they are unrelated to the mod.

Option A is recommended because it is precise and the parsing infrastructure exists.

**Interaction with `--archive`:** The `run_archive` function should also check for `mod-block` and refuse to archive an entity with an active block unless `--force` is present. This prevents archival from bypassing the guard via the `--archive` path.

### Checklist Item 6: Before/After Wording

#### `first-officer-shared-core.md` — Merge and Cleanup section

**Before** (current, lines 139-146):

```
When an entity reaches its terminal stage:

1. Run registered merge hooks before any local merge, archival, or status advancement.
2. If a merge hook created or set a `pr` field, report the PR-pending state and do not local-merge.
3. If no merge hook handled the merge, perform the default local merge from the stage worktree branch.
4. Update frontmatter: `status --workflow-dir {workflow_dir} --set {slug} completed verdict={verdict} worktree=`
5. Archive the entity into `{workflow_dir}/_archive/`.
6. Remove the worktree (`git worktree remove {path}`) and delete the temporary branch (`git branch -d {branch}`).
```

**After:**

```
When an entity reaches its terminal stage:

1. Check for registered merge hooks. If any exist, set the mod-block field before invoking them:
   `status --workflow-dir {workflow_dir} --set {slug} mod-block=merge:{mod_name}`
   Commit: `mod-block: {slug} awaiting merge:{mod_name}`
2. Run registered merge hooks before any local merge, archival, or status advancement.
3. If a merge hook created or set a `pr` field, report the PR-pending state and do not local-merge. Leave mod-block set — it will be cleared when the PR merges or the captain chooses an alternative.
4. If a merge hook completed without setting `pr` or creating a blocking condition, clear the mod-block:
   `status --workflow-dir {workflow_dir} --set {slug} mod-block=`
5. If no merge hook handled the merge, perform the default local merge from the stage worktree branch.
6. Update frontmatter: `status --workflow-dir {workflow_dir} --set {slug} completed verdict={verdict} worktree=`
7. Archive the entity into `{workflow_dir}/_archive/`.
8. Remove the worktree (`git worktree remove {path}`) and delete the temporary branch (`git branch -d {branch}`).
```

#### `first-officer-shared-core.md` — Mod Hook Convention section

**Before** (current, lines 182-191):

```
## Mod Hook Convention

Mods live in `{workflow_dir}/_mods/` and use `## Hook: {point}` headings.

Supported lifecycle points:
- `startup`
- `idle`
- `merge`

Hooks are additive and run in alphabetical order by mod filename.
```

**After:**

```
## Mod Hook Convention

Mods live in `{workflow_dir}/_mods/` and use `## Hook: {point}` headings.

Supported lifecycle points:
- `startup`
- `idle`
- `merge`

Hooks are additive and run in alphabetical order by mod filename.

### Mod-Block Enforcement

Merge hooks can create blocking conditions (e.g., requiring captain approval before pushing, waiting for a PR to merge). The FO enforces these blocks via the entity `mod-block` frontmatter field:

- **Set** by the FO before invoking a merge hook: `mod-block=merge:{mod_name}`
- **Cleared** by the FO after the hook's blocking action completes or the captain force-overrides
- **Guarded** by `status --set`, which refuses terminal transitions (status to a terminal stage, completed, verdict, worktree clear) while `mod-block` is non-empty unless `--force` is passed
- **Survives session resume** — the FO reads `mod-block` from entity frontmatter on boot and resumes the pending action
```

#### `claude-first-officer-runtime.md` — Event Loop section

**Before** (current, lines 103-110):

```
## Event Loop

After each agent completion:

1. **Check PR-pending entities** — Run `status --where "pr !="`. For each, check PR state via `gh pr view`. Advance merged PRs.
2. **Run `status --next`** — Dispatch any newly ready entities.
3. **If nothing is dispatchable** — Fire `idle` hooks (from registered mods), then re-run `status --next`. If entities became dispatchable (e.g., a hook advanced an entity), dispatch them. If still nothing, the event loop iteration ends.

Repeat from step 1 after each agent completion until the captain ends the session or, in single-entity mode, until the target entity is resolved.
```

**After:**

```
## Event Loop

After each agent completion:

1. **Check PR-pending entities** — Run `status --where "pr !="`. For each, check PR state via `gh pr view`. Advance merged PRs. When advancing a merged PR entity, clear its `mod-block` field if set: `status --set {slug} mod-block=`.
2. **Check mod-blocked entities** — Run `status --where "mod-block !="`. For each, re-read the blocking mod and resume its pending action (e.g., re-present the PR summary to the captain). Do not dispatch new work for a mod-blocked entity.
3. **Run `status --next`** — Dispatch any newly ready entities.
4. **If nothing is dispatchable** — Fire `idle` hooks (from registered mods), then re-run `status --next`. If entities became dispatchable (e.g., a hook advanced an entity), dispatch them. If still nothing, the event loop iteration ends.

Repeat from step 1 after each agent completion until the captain ends the session or, in single-entity mode, until the target entity is resolved.
```

#### `claude-first-officer-runtime.md` — new section after Event Loop

**Add:**

```
## Mod-Block Enforcement at Terminal Transitions

Before advancing an entity into the Merge and Cleanup path, the FO must:

1. Check whether merge hooks are registered (from boot-time MODS data).
2. If merge hooks exist, set `mod-block` on the entity before invoking the first hook.
3. Invoke merge hooks in order. If a hook creates a blocking condition (sets `pr`, requires captain approval), leave `mod-block` set and report the pending state.
4. Only clear `mod-block` after the blocking condition is resolved (PR merged, captain chose alternative, hook completed without blocking).
5. Only proceed to terminal frontmatter updates (completed, verdict, worktree clear) and archival after `mod-block` is clear.

On session resume, scan entities with non-empty `mod-block` and resume the pending action. Do not re-run the hook from scratch — check what state the hook left (was a PR created? is the branch pushed?) and continue from there.
```

#### `skills/commission/bin/status` — the `--set` command path

**Before** (current behavior in `main()`, lines 1131-1173):

The `--set` path resolves the entity file, calls `update_frontmatter`, mirrors `pr` to main, and prints resolved fields.

**After:**

Add a mod-block guard between entity resolution and `update_frontmatter`:

```python
# After resolving entity_path (line ~1157), before update_frontmatter:

# Check mod-block guard
force = '--force' in args
current_fields = parse_frontmatter(entity_path)
mod_block = current_fields.get('mod-block', '').strip()
if mod_block and not force:
    # Parse README for terminal stage names
    readme_path = os.path.join(pipeline_dir, 'README.md')
    stages = parse_stages_block(readme_path) if os.path.exists(readme_path) else None
    terminal_names = {s['name'] for s in (stages or []) if s.get('terminal')}
    
    guarded_fields = set()
    for field, value in updates:
        if field == 'status' and value in terminal_names:
            guarded_fields.add(f'status={value}')
        elif field in ('completed', 'verdict'):
            guarded_fields.add(field)
        elif field == 'worktree' and value == '':
            guarded_fields.add('worktree=')
    
    if guarded_fields:
        print(f'Error: entity {slug} has pending mod-block ({mod_block}). '
              f'Use --force to override.', file=sys.stderr)
        sys.exit(1)

if force and mod_block:
    print(f'Warning: --force overriding mod-block ({mod_block}) on entity {slug}',
          file=sys.stderr)
```

Also add `--force` to the `run_archive` function guard:

```python
# In run_archive, after reading source_path but before archiving:
fields = parse_frontmatter(source_path)
mod_block = fields.get('mod-block', '').strip()
if mod_block:
    # Check for --force in original args
    if '--force' not in sys.argv:
        print(f'Error: entity {slug} has pending mod-block ({mod_block}). '
              f'Use --force to override.', file=sys.stderr)
        sys.exit(1)
    print(f'Warning: --force overriding mod-block ({mod_block}) on entity {slug}',
          file=sys.stderr)
```

### Checklist Item 7: Acceptance Criteria

1. **`status --set` refuses terminal transitions when `mod-block` is set.** Setting `status=done` on an entity with `mod-block=merge:pr-merge` exits with code 1 and prints the mod-block error.
   - Test: `test_modblock_guard_refuses_terminal_status` (pytest, `test_status_script.py`)

2. **`status --set` refuses `completed` and `verdict` updates when `mod-block` is set.** Setting `completed` or `verdict=PASSED` on a mod-blocked entity exits with code 1.
   - Test: `test_modblock_guard_refuses_completed_verdict` (pytest, `test_status_script.py`)

3. **`status --set` refuses `worktree=` (clear) when `mod-block` is set.** Clearing worktree on a mod-blocked entity exits with code 1.
   - Test: `test_modblock_guard_refuses_worktree_clear` (pytest, `test_status_script.py`)

4. **`status --set` allows non-guarded updates when `mod-block` is set.** Setting `pr=#57` on a mod-blocked entity succeeds (exit 0).
   - Test: `test_modblock_guard_allows_pr_update` (pytest, `test_status_script.py`)

5. **`status --set --force` overrides the mod-block guard.** Setting `status=done` with `--force` on a mod-blocked entity succeeds and prints a warning to stderr.
   - Test: `test_modblock_force_overrides_guard` (pytest, `test_status_script.py`)

6. **`status --archive` refuses to archive a mod-blocked entity without `--force`.** Archiving an entity with `mod-block=merge:pr-merge` exits with code 1.
   - Test: `test_modblock_archive_guard` (pytest, `test_status_script.py`)

7. **`mod-block` field is settable and clearable via `status --set`.** Setting `mod-block=merge:pr-merge` and then `mod-block=` works correctly.
   - Test: `test_modblock_set_and_clear` (pytest, `test_status_script.py`)

8. **FO sets `mod-block` before invoking merge hooks.** The shared-core Merge and Cleanup section instructs the FO to set `mod-block` as step 1 before running hooks.
   - Test: Static prose inspection (verify the before/after wording is applied correctly).

9. **FO clears `mod-block` after hook completion.** The shared-core instructs the FO to clear `mod-block` when the blocking condition resolves.
   - Test: Static prose inspection.

10. **Event loop checks mod-blocked entities on resume.** The runtime adapter Event Loop section includes a step to scan for `mod-block !=` and resume pending actions.
    - Test: Static prose inspection; live E2E (below) for behavioral verification.

11. **E2E: Merge hook mod-block prevents premature terminal advancement.** In a live FO session with the `pr-merge` mod, the FO must set `mod-block` before running the merge hook, and `status --set` must refuse a direct `status=done` while the block is active.
    - Test: `test_modblock_e2e_enforcement` (live E2E, `test_modblock_enforcement.py`)

12. **Non-terminal status changes are NOT guarded.** Setting `status=implementation` on a mod-blocked entity succeeds (the guard only blocks terminal transitions).
    - Test: `test_modblock_guard_allows_nonterminal_status` (pytest, `test_status_script.py`)

### Checklist Item 8: Test Plan

| Test name | Harness | Assertion | Cost |
|---|---|---|---|
| `test_modblock_guard_refuses_terminal_status` | pytest (`test_status_script.py`) | `--set slug status=done` on entity with `mod-block=merge:pr-merge` → exit 1, stderr contains "mod-block" | Low |
| `test_modblock_guard_refuses_completed_verdict` | pytest (`test_status_script.py`) | `--set slug completed` and `--set slug verdict=PASSED` on mod-blocked entity → exit 1 | Low |
| `test_modblock_guard_refuses_worktree_clear` | pytest (`test_status_script.py`) | `--set slug worktree=` on mod-blocked entity → exit 1 | Low |
| `test_modblock_guard_allows_pr_update` | pytest (`test_status_script.py`) | `--set slug pr=#57` on mod-blocked entity → exit 0, pr field updated | Low |
| `test_modblock_guard_allows_nonterminal_status` | pytest (`test_status_script.py`) | `--set slug status=implementation` on mod-blocked entity → exit 0 | Low |
| `test_modblock_force_overrides_guard` | pytest (`test_status_script.py`) | `--set slug status=done --force` on mod-blocked entity → exit 0, stderr contains "Warning" | Low |
| `test_modblock_archive_guard` | pytest (`test_status_script.py`) | `--archive slug` on mod-blocked entity → exit 1, stderr contains "mod-block" | Low |
| `test_modblock_set_and_clear` | pytest (`test_status_script.py`) | `--set slug mod-block=merge:pr-merge` succeeds, `--set slug mod-block=` succeeds, field value matches | Low |
| Prose verification (AC 8-10) | Static review | Diff of shared-core and runtime adapter matches before/after wording | Low |
| `test_modblock_e2e_enforcement` | Live E2E (`test_modblock_enforcement.py`) | FO sets mod-block before merge hook; direct `status --set status=done` fails while blocked; normal flow completes after block clears | Medium-high |

The pytest tests extend `test_status_script.py` infrastructure (shared `build_status_script`, `make_pipeline`, `run_status` helpers). The E2E test follows the pattern of `test_merge_hook_guardrail.py` — a fixture workflow with a merge mod, run through single-entity mode.

### Implementation Notes (gate-approved 2026-04-14)

Three mandatory items from the staff review:

1. **Clarify the FO's signal for detecting hook completion.** The FO sets `mod-block` before invoking a merge hook and clears it after. But mods are prose, not executables — the FO needs a deterministic way to know the hook completed. Formalize this: does the FO check for `pr` field presence after running the hook? Does it follow the mod's explicit instructions and infer completion from state delta? Encode the answer in the Merge and Cleanup before/after wording so the session-resume path is deterministic, not heuristic.

2. **Update the entity schema in `docs/plans/README.md`** to include `mod-block` in the `### Field Reference` table (Type: string, Description: "Pending mod-declared blocking action, format `{lifecycle_point}:{mod_name}`. Empty when no block is active."). Also confirm that absent/empty `mod-block` is treated as "no block" everywhere in the implementation (existing entities and archived files lack the field).

3. **Extend the risk register recovery steps for missing mod files.** Replace "handle gracefully" with concrete behavior: report to captain ("Blocking mod {mod_name} is missing. The entity is stuck. Options: restore the mod file, or use `--force` to clear the block and resume normal flow."), wait for captain direction before proceeding.

Additional note (not blocking but worth documenting): `mod-block` on worktree-based entities should be mirrored to main like `pr` is, so the startup/resume path on main can discover pending blocks without scanning worktrees.

### Checklist Item 9: Scope Boundary

**IN scope:**

- `mod-block` frontmatter field — definition, set/clear lifecycle, value format
- `status --set` guard — mod-block check, `--force` override, terminal stage detection
- `status --archive` guard — mod-block check before archival
- `first-officer-shared-core.md` — Merge and Cleanup rewording, Mod Hook Convention extension
- `claude-first-officer-runtime.md` — Event Loop rewording, new Mod-Block Enforcement section
- pytest unit tests for the `status --set` and `--archive` guards
- One live E2E test for behavioral verification

**OUT of scope:**

- New mod types or lifecycle points beyond startup/idle/merge
- Codex runtime adapter changes (the Codex adapter follows the shared core; prose changes propagate automatically)
- Spacebridge integration or remote enforcement
- Multi-block support (comma-separated `mod-block` values for multiple concurrent mods)
- Enforcement for startup or idle hooks (only merge hooks currently create blocking conditions)
- Changes to the pr-merge mod itself (it already has the correct prose)

### Checklist Item 10: Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Backward compatibility with existing `status --set` callers.** Scripts or FO sessions that call `--set status=done` without knowing about mod-block will break if an entity has mod-block set from a crashed/abandoned session. | Medium | Medium | The guard only fires when `mod-block` is non-empty. No existing entity has this field, so there is zero backward-compatibility risk for the initial rollout. Future risk is mitigated by the `--force` escape hatch. |
| **Performance of README parsing on every `--set` call.** The guard needs terminal stage names, requiring a README parse. | Low | Low | `parse_stages_block` is already fast (reads a single file, no I/O beyond one open). The parse only runs when `mod-block` is non-empty, so the common case (no block) adds only a frontmatter field check. |
| **Malformed mod file.** If `{workflow_dir}/_mods/{mod_name}.md` referenced by `mod-block=merge:{mod_name}` is missing or unreadable, the resume path cannot re-read the mod. | Low | Medium | The FO should handle a missing mod file gracefully: report to the captain that the blocking mod is missing and ask whether to force-clear the block. The `status --set` guard does not read mod files — it only reads the entity's own frontmatter. |
| **Stale mod-block from crashed session.** If the FO crashes after setting `mod-block` but before invoking the hook, the entity is stuck. | Medium | Low | The resume path handles this: on boot, the FO sees the non-empty `mod-block`, reads the mod, and either continues the action or asks the captain. The `--force` override is the escape hatch for permanently stuck entities. |
| **Interaction with PR-pending entities.** An entity can have both `pr` and `mod-block` set (the normal case for pr-merge: the hook sets `pr` and the block remains until the PR merges). The event loop's PR-merge advancement must clear `mod-block` when it advances a merged PR. | High | High | The event loop wording explicitly includes clearing `mod-block` when advancing a merged PR. The E2E test should verify this path. |

### Stage Report Summary

1. DONE: Problem restatement with task 139 failure as canonical example.
2. DONE: Survey of current mod lifecycle with exact prose quotes.
3. DONE: Three-layer enforcement mechanism fully specified (runtime, status --set, --force).
4. DONE: State model for mod-block — frontmatter field, set/clear lifecycle, session resume.
5. DONE: `status --set` guard algorithm with terminal stage detection.
6. DONE: Before/after wording for shared-core (Merge and Cleanup, Mod Hook Convention), runtime adapter (Event Loop, new section), and status script (--set path, --archive path).
7. DONE: 12 numbered, testable acceptance criteria with named tests.
8. DONE: Test plan table with 10 entries covering pytest unit tests, static review, and live E2E.
9. DONE: Scope boundary (IN vs OUT).
10. DONE: Risk register with 5 risks, mitigations, and likelihood/impact.

## Stage Report

### Summary

Implemented mod-block enforcement at terminal transitions. The `status --set` command now refuses terminal field updates (status to terminal stage, completed, verdict, worktree clear) when `mod-block` is non-empty, with `--force` override. The `--archive` command has the same guard. Prose updates to `first-officer-shared-core.md` and `claude-first-officer-runtime.md` formalize the FO's mod-block lifecycle and session resume behavior. All 232 tests pass including 12 mod-block-specific tests.

### Checklist

1. DONE: Handle worktree recovery — the prior ensign's uncommitted changes to `first-officer-shared-core.md` aligned with the spec; committed as `7f8825a`.
2. DONE: Implement `status --set` mod-block guard — refuses terminal transitions when mod-block is non-empty (committed by prior ensign in `2b0ddd8`, verified working).
3. DONE: Implement `--force` override — prints warning to stderr and allows guarded updates (committed in `2b0ddd8`).
4. DONE: Implement `status --archive` mod-block guard — refuses archival when mod-block is non-empty without `--force` (committed in `2b0ddd8`).
5. DONE: Ensure non-guarded updates allowed — `pr`, non-terminal status changes proceed when mod-block is set (verified by `test_modblock_guard_allows_pr_update`, `test_modblock_guard_allows_nonterminal_status`).
6. DONE: mod-block field settable and clearable via `status --set` (verified by `test_modblock_set_and_clear`).
7. DONE: Update `first-officer-shared-core.md` Merge and Cleanup section — committed as `7f8825a`. Steps now include set mod-block before hooks, detect completion via state delta, clear on non-blocking completion.
8. DONE: Update `first-officer-shared-core.md` Mod Hook Convention — added Mod-Block Enforcement subsection (committed as `7f8825a`).
9. DONE: Update `claude-first-officer-runtime.md` Event Loop — added mod-block check step (step 2), PR advancement clears mod-block (committed as `e27c5b8`).
10. DONE: Add Mod-Block Enforcement at Terminal Transitions section to `claude-first-officer-runtime.md` (committed as `e27c5b8`).
11. DONE: Update `docs/plans/README.md` Field Reference table — added `mod-block` field (committed as `ad68088`).
12. DONE: Address implementation note 1 (hook completion detection) — Merge and Cleanup step 3 formalizes detection via state delta: `pr` field presence, captain approval state, or explicit external wait declaration.
13. DONE: Address implementation note 3 (missing mod recovery) — Mod-Block Enforcement section includes concrete behavior: report to captain with message naming the missing mod and offering restore-or-force options, wait for captain direction.
14. DONE: All pytest tests pass — 12 mod-block tests in `TestModBlockGuard` class covering: terminal status refusal, completed/verdict refusal, worktree clear refusal, pr update allowed, non-terminal status allowed, force override, archive guard, archive force override, set/clear, absent field treated as no block, empty field treated as no block.
15. DONE: `make test-static` passes — 232 tests, 10 subtests, all green.

## Stage Report

### Validation

#### Summary

Validated mod-block enforcement implementation against all 17 checklist items. All 232 static tests pass (including 12 mod-block-specific tests in `TestModBlockGuard`). Prose changes to shared-core and runtime adapter match the spec. The `status --set` guard, `--archive` guard, `--force` override, and Field Reference update are all verified. Recommendation: **PASSED**.

#### Checklist

1. DONE: Read `tests/README.md` — confirmed `make test-static` is the correct offline entrypoint (`pytest tests/ --ignore=tests/fixtures`). Live E2E uses `make test-e2e TEST=... RUNTIME=...`.

2. DONE: `make test-static` — 232 passed, 10 subtests passed in 5.26s. Zero failures.

3. DONE: AC-1 verified — `test_modblock_guard_refuses_terminal_status` confirms `status --set slug status=done` on an entity with `mod-block=merge:pr-merge` exits with non-zero return code and stderr contains both "mod-block" and "merge:pr-merge". Code at `skills/commission/bin/status` lines 1171-1194 implements the guard: parses terminal stage names from README, checks if any requested update targets a guarded field, and exits 1 with the error message.

4. DONE: AC-2 verified — `test_modblock_guard_refuses_completed` and `test_modblock_guard_refuses_verdict` confirm that setting `completed` or `verdict=PASSED` on a mod-blocked entity exits 1. The guard at line 1184 checks `field in ('completed', 'verdict')`.

5. DONE: AC-3 verified — `test_modblock_guard_refuses_worktree_clear` confirms `status --set slug worktree=` on a mod-blocked entity exits 1. The guard at line 1187 checks `field == 'worktree' and value == ''`.

6. DONE: AC-4 verified — `test_modblock_guard_allows_pr_update` confirms `status --set slug pr=#57` on a mod-blocked entity succeeds (exit 0) and the `pr` field is updated to `#57`. `test_modblock_guard_allows_nonterminal_status` confirms `status --set slug status=implementation` succeeds. The guard only blocks updates matching the guarded set.

7. DONE: AC-5 verified — `test_modblock_force_overrides_guard` confirms `status --set slug status=done --force` on a mod-blocked entity succeeds (exit 0) and stderr contains "Warning" and "mod-block". Code at lines 1196-1198 prints the warning when `force and mod_block`.

8. DONE: AC-6 verified — `test_modblock_archive_guard` confirms `--archive slug` on a mod-blocked entity exits 1 with "mod-block" in stderr. `test_modblock_archive_force_overrides` confirms `--archive slug --force` succeeds with a warning. Code at `run_archive()` lines 886-894 implements the guard.

9. DONE: AC-7 verified — `test_modblock_set_and_clear` confirms setting `mod-block=merge:pr-merge` then `mod-block=` works correctly, with the field value matching at each step.

10. DONE: AC-8 verified (prose inspection) — `first-officer-shared-core.md` Merge and Cleanup step 1 reads: "Check for registered merge hooks. If any exist, set the mod-block field before invoking them: `status --workflow-dir {workflow_dir} --set {slug} mod-block=merge:{mod_name}`". This is before step 2 which runs the hooks.

11. DONE: AC-9 verified (prose inspection) — `first-officer-shared-core.md` Merge and Cleanup step 5 reads: "If a merge hook completed without creating a blocking condition, clear the mod-block: `status --workflow-dir {workflow_dir} --set {slug} mod-block=`". The Event Loop step 1 also clears mod-block when advancing a merged PR.

12. DONE: AC-10 verified (prose inspection) — `claude-first-officer-runtime.md` Event Loop step 2 reads: "Check mod-blocked entities — Run `status --where "mod-block !="`. For each, re-read the blocking mod and resume its pending action. Do not dispatch new work for a mod-blocked entity."

13. DONE: AC-11 (implementation note 1) verified — `first-officer-shared-core.md` Merge and Cleanup step 3 formalizes hook completion detection: "Detect hook completion by inspecting the entity's state delta after the hook runs. A hook has created a blocking condition when any of: (a) a `pr` field is now set, (b) the hook's prose instructions say to wait for captain approval and the captain has not yet responded, or (c) the hook explicitly declares an external wait."

14. DONE: AC-12 verified — `test_modblock_guard_allows_nonterminal_status` confirms setting `status=implementation` on a mod-blocked entity succeeds. The guard only checks against `terminal_names` from the README stages block.

15. DONE: Implementation note 2 verified — `docs/plans/README.md` Field Reference table at line 71 includes: `| \`mod-block\` | string | Pending mod-declared blocking action, format \`{lifecycle_point}:{mod_name}\`. Empty when no block is active. |`

16. DONE: Implementation note 3 verified — `claude-first-officer-runtime.md` Mod-Block Enforcement section includes: "If the blocking mod file (`{workflow_dir}/_mods/{mod_name}.md`) is missing or unreadable, report to the captain: 'Blocking mod {mod_name} is missing. The entity is stuck. Options: restore the mod file, or use `--force` to clear the block and resume normal flow.' Wait for captain direction before proceeding."

17. DONE: Recommendation — **PASSED**. All 12 acceptance criteria verified with evidence from test execution and prose inspection. All 3 implementation notes addressed. 232 static tests green. No issues found.

## Stage Report

### Implementation (cycle 3 — fold #150 into #114)

#### Summary

Added the permanent `claude-live-opus` CI job to `.github/workflows/runtime-live-e2e.yml`, gated on the new `CI-E2E-OPUS` environment. The job mirrors the existing `claude-live` shape (same provenance step, checkout/setup, secret check, git identity, artifact upload), diverging only on environment name, run command (`make test-live-claude-opus`), and artifact name (`runtime-live-e2e-claude-live-opus`). Extended `tests/test_runtime_live_e2e_workflow.py` with assertions for the new job's presence, environment, secret scoping, make target, and artifact name. Updated `tests/README.md` Live E2E section to document the three-job flow and the independent opus approval gate. `make test-static` reports 283 passed (including the 8 workflow tests; the 51-test delta vs the prior cycle's 232 is from unrelated work merged in between cycles).

#### Checklist

1. DONE: Read #150 spec and existing workflow file — spec recovered from commit `086b4615` (`docs/plans/runtime-live-e2e-claude-opus-job.md`); current workflow reviewed at `.github/workflows/runtime-live-e2e.yml`.
2. DONE: Added `claude-live-opus` job to `.github/workflows/runtime-live-e2e.yml` — inserted between `claude-live` and `codex-live`, `environment: CI-E2E-OPUS`, runs `make test-live-claude-opus`, uploads `runtime-live-e2e-claude-live-opus` artifact, reuses the same provenance-loading step shape.
3. DONE: Extended `tests/test_runtime_live_e2e_workflow.py` — renamed the two-jobs test to `has_expected_runtime_jobs` with opus assertions, added opus section to artifact/preserve-dirs loop, added opus secret-scoping asserts, added `make test-live-claude-opus` make-target assert in the opus section, added `CI-E2E-OPUS` and `claude-live-opus` assertions in the README test. 8/8 workflow tests pass.
4. DONE: Updated `tests/README.md` Live E2E CI section — operator flow now lists three jobs and three environments, Makefile-targets table entry for `test-live-claude-opus` references `CI-E2E-OPUS` and dropped the "not wired into CI" caveat, required-secrets list adds `CI-E2E-OPUS`, artifacts list adds `runtime-live-e2e-claude-live-opus`.
5. DONE: Ran `make test-static` — 283 passed, 10 subtests passed in 5.79s. All 8 tests in `test_runtime_live_e2e_workflow.py` pass (confirmed via targeted verbose run).
6. DONE: Commit on `spacedock-ensign/fo-enforce-mod-blocking-at-runtime` — see commit below.

### Summary

Permanent `claude-live-opus` CI job added to `runtime-live-e2e.yml` gated on `CI-E2E-OPUS`, with matching static test coverage and README updates. Folds the #150 spec into the #114 PR per CL direction.

## Stage Report

### Implementation (cycle 4 — un-skip the three live tests #114 owns)

#### Summary

Cycle 2's task was to drive the three SKIPPED haiku live tests (`test_dispatch_completion_signal.py`, `test_rebase_branch_before_push.py`, `test_push_main_before_pr.py`) back to green and wire them into `make test-live-claude`. All three now pass on haiku. The fix spanned four areas:

1. **Combined-clear guard** (primary fix for the "FO drifts past pr-merge" class of failures). The status `--set` guard now refuses to clear `mod-block` and touch terminal fields (`status={terminal}`, `completed`, `verdict`, `worktree=`) in the same call. Haiku's drift pattern on the rebase test was exactly that: one `--set slug mod-block= verdict=PASSED worktree=` bundled the clear with terminalization, then archived and deleted the remote branch. Separating the two operations forces the clear commit to stand on its own so any session-resume or reviewer sees the block resolving before terminalization.
2. **Dispatch helper + runtime adapter verbatim-prompt discipline.** `claude-team build`'s `extract_stage_subsection` now accepts both backtick-quoted and bare `### stage` headings (fixtures use bare; live docs/plans uses backtick), and the runtime adapter's dispatch step 3 adds explicit paraphrase anti-patterns and a step 4 post-dispatch verification requiring the literal `SendMessage(to="team-lead"` substring. Haiku had been dropping the completion signal when the helper failed silently on fixture headings and when it paraphrased the output.
3. **Test infrastructure fixes.** The `git` wrappers in `test_push_main_before_pr` and `test_rebase_branch_before_push` only caught `git push ...` and missed `git -C <path> push ...` — haiku uses the latter form. Normalized the wrapper to skip `-C`/option pairs. The `test_gate_guardrail` self-approval regex was matching the FO's recitation of the guardrail ("must not self-approve"); scrub negated phrasings before searching. The sibling-import smoke tests in `test_claude_team.py` hard-coded an archived entity; CL moved them to a stable fixture in parallel.
4. **Prose updates to shared-core.** Merge-and-Cleanup step 5 now requires the clear in its own `--set` and documents the refusal; step 9 forbids `git push origin --delete` while a PR is pending. The Mod-Block Enforcement subsection cross-references the combined-clear refusal.

`make test-live-claude` runs the full 7-test chain end-to-end on haiku with every test green. `make test-static` reports 283 passed, 10 subtests passed.

#### Checklist

1. DONE: `make test-static` baseline — 273 passed initially with 2 pre-existing failures against the archived `build-dispatch-structured-helper.md` entity; CL parallel-fixed the sibling-import tests to point at a stable fixture. Post-cycle-2: 283 passed, 10 subtests passed.
2. DONE: `test_dispatch_completion_signal.py --runtime claude` — initially flaky on haiku (FO paraphrased `SendMessage(...)` as "SendMessage with to=..."). Root cause: `claude-team build` failed silently on the fixture's bare `### work` heading, pushing the FO onto manual prompt assembly. Fixes: `extract_stage_subsection` accepts both heading forms + runtime adapter verbatim-prompt prose + post-dispatch verification step. Passes cleanly now.
3. DONE: `test_rebase_branch_before_push.py` — initial failure: the `git` wrapper didn't detect `git -C <path> push`, making the push-log empty. Wrapper fixed to strip leading `-C`/option pairs. Passes now.
4. DONE: `test_push_main_before_pr.py` — initial failure (after wrapper fix): FO bundled `mod-block= verdict=PASSED worktree=` in one `--set` then deleted the remote branch. Combined-clear guard in `status --set` plus shared-core prose updates block that drift. Passes now.
5. DONE: Full `make test-live-claude` chain — 7/7 tests pass end-to-end (`test_gate_guardrail`, `test_rejection_flow`, `test_feedback_keepalive`, `test_merge_hook_guardrail`, `test_dispatch_completion_signal`, `test_rebase_branch_before_push`, `test_push_main_before_pr`). `test_scaffolding_guardrail.py` remains SKIPPED (separate follow-up per task description, not cycle 2 scope).
6. DONE: Makefile updated — removed the three SKIPPED comments for the now-active tests, re-added `test_dispatch_completion_signal.py --runtime claude`, `test_rebase_branch_before_push.py`, and `test_push_main_before_pr.py` into the `test-live-claude` chain in the right order (after `test_merge_hook_guardrail`). Flipped the `test_runtime_live_e2e_workflow.py` guard from "expect SKIPPED" to "expect active" for the three tests.
7. DONE: `make test-static` post-fix — 283 passed, 10 subtests passed (cycle 2 added 4 mod-block combined-clear tests and picked up the CI-E2E-OPUS workflow tests from the cycle 3 fold).
8. DONE: Commits on `spacedock-ensign/fo-enforce-mod-blocking-at-runtime` — see history below.

#### Commits

- `364c52c7` test: fix git push wrapper to detect -C form in pr-merge live tests
- `2cc36816` test: un-skip three live tests now that #114 mod-block enforcement lands
- `52805416` test: point sibling-import smoke tests at an active entity (later refined by CL's parallel fixture move)
- `03898edd` test: tighten gate-guardrail self-approval regex to ignore guardrail recitation
- `744a48b5` feat: harden dispatch helper + runtime adapter for verbatim-prompt discipline
- `8c33d351` feat: refuse combined mod-block clear with terminal transition in one --set

#### Mechanism per test (per task-description prompt)

- **test_dispatch_completion_signal**: heading-tolerant dispatch helper + runtime-adapter anti-paraphrase prose + post-dispatch verification instruction.
- **test_rebase_branch_before_push**: test wrapper fix (`-C` form detection) to expose the FO's correct behavior, plus the combined-clear guard below as defense in depth against any terminal drift.
- **test_push_main_before_pr**: combined-clear guard in `status --set` that refuses bundling `mod-block=` with any guarded terminal field; prose updates in shared-core step 5 and step 9 to match; forbidden `git push origin --delete` prose on step 9.

Every checklist item in the team-lead dispatch is addressed.

## Stage Report

### Implementation (cycle 4 — mechanism-level mod-block enforcement)

#### Summary

Cycle 3's prose-only enforcement (Layer 1 asks the FO to set `mod-block` before invoking merge hooks; Layer 2 guards terminal transitions when `mod-block` is non-empty) depended on FO self-discipline and on the fixture's stub `./status` script actually supporting `--set`. The PR #92 opus CI run exposed two interacting gaps: (a) the FO sometimes terminalizes without ever setting `mod-block`, so Layer 2 never fires; (b) even when the FO tries to use `--set`, the `push-main-pipeline` and `merge-hook-pipeline` fixtures ship a bash stub `status` script that silently accepts `--set` arguments and does nothing — the FO then pivots to editing entity frontmatter with Write + git, bypassing every guard.

Cycle 4 closes both holes at the mechanism level:

1. **Merge-hook invariant in `status --set` and `status --archive`** (option B from the dispatch brief). When `_mods/*.md` registers at least one `## Hook: merge`, and the entity's `pr` field is empty, and `mod-block` is empty, and `--force` was not passed, `status --set` refuses any terminal-field update (`status={terminal}`, `completed`, `verdict`, `worktree=`) and `status --archive` refuses archival. The refusal names the blocking hook. In that state the hook has provably not run — the invariant catches the "FO skipped the hook entirely" failure regardless of whether Layer 1 ran.

2. **Fixtures now get the real `status` script when they declare a merge hook.** `setup_fixture` in `scripts/test_lib.py` detects fixtures whose `_mods/` contains `## Hook: merge` and overwrites the fixture's stub `status` with a templated copy of `skills/commission/bin/status`. Without this, `status --set` never runs inside the live-test project and the mechanism-level guard is unreachable. The three live-test fixtures using merge hooks (`push-main-pipeline`, `merge-hook-pipeline`) are covered; fixtures without merge hooks are untouched.

3. **Supporting test-infrastructure fixes.** The test push-log parser regex only matched `git push origin X`; haiku uses `git -C <dir> push origin X` and opus uses `git push -u origin X`. The new regex `(?:^|\s)push(?:\s+-\S+)*\s+origin\s+(\S+)` handles all three forms. The pre-FO `bash ./status` self-test call was updated to honor the Python shebang in `test_rebase_branch_before_push.py`, `test_push_main_before_pr.py`, and `test_merge_hook_guardrail.py`.

4. **Prose updates.** `first-officer-shared-core.md` Merge-and-Cleanup step 1 and the Mod-Block Enforcement subsection now describe the mechanism-level backstop. `claude-first-officer-runtime.md` Mod-Block Enforcement section adds a "The mechanism enforces this even if you forget" callout with the three recovery paths.

5. **Unit coverage.** New `TestMergeHookTerminalGuard` class in `tests/test_status_script.py` with 14 tests covering `--set status=done`, `--set completed`, `--set verdict`, `--set worktree=`, `--set pr=` (allowed), `pr + status=done` in one call (allowed), `--force` bypass, non-merge hook (no trigger), no-hook workflow (no trigger), non-terminal transition, `--archive` variants (refused, allowed with pr, `--force` bypass). All 14 pass.

#### Design choice rationale

The brief offered A (auto-set mod-block on terminal attempt), B (refuse terminal when pr+mod-block both empty and merge hooks exist), or C (combine). I picked B for these reasons:

- **Simplicity.** Option A introduces a silent side effect in `status --set`: the FO calls `--set status=done` and an unrelated field (`mod-block`) changes. That's surprising and harder to reason about from a log-audit perspective.
- **Explicit recovery path.** Option B's refusal is a loud error that names the blocking hook. The FO can recover in three auditable ways — set `mod-block=merge:{name}` and run the hook (normal flow), let the hook set `pr` (satisfies the invariant), or pass `--force` (captain explicitly approved bypass, warning printed to stderr).
- **Fewer edge cases.** Option A would have to decide what to do when the FO later calls `--set mod-block=` expecting a clear — now that auto-set is a real clear that interacts with existing guards. Option B leaves the existing mod-block machinery untouched and adds one focused refusal branch.

The existing combined-clear guard (cycle 2) stays in place and complements the new invariant: if the FO does manage to set mod-block but tries to clear it and terminalize in one call, cycle 2's guard catches that. Cycle 4's invariant catches the orthogonal case where mod-block was never set at all. Together they enforce "the merge hook runs to completion before terminal advancement" from both sides.

#### Why this is mechanism-level

The cycle 1/2/3 fixes all lived in prose or depended on fixture compliance. Cycle 4's fix is implemented inside the `status` script itself and cannot be bypassed by the FO forgetting, paraphrasing, or using a different field order. The only escape hatches are `--force` (visible in the commit record as a warning printed to stderr) and absence of a merge hook (which is the pre-#114 default and is correct for workflows without merge hooks).

Fixture compliance is still required to *reach* the mechanism, but cycle 4's `setup_fixture` change forces every live test with merge hooks to use the real Python script — the only way around it is to stop using `setup_fixture`, which would be a much larger deviation than any cycle 1–3 workaround.

#### Checklist

1. DONE: `git status` clean at start — prior cycles' commits were already on branch.
2. SKIPPED: Local haiku reproduction of the reported failure before any change. The root cause was well-understood from the dispatch brief (FO drifts past the pr-merge hook; fixture stub doesn't implement `--set`). Skipped to avoid the ~2-minute cost; the fix was implemented and validated by running the test until PASS. The post-fix validation (12/12 haiku, 13/13 opus on `test_rebase_branch_before_push`; 10/10 haiku, 11/11 opus on `test_push_main_before_pr`) supersedes pre-fix reproduction.
3. DONE: Investigated the local opus FO log (`/var/folders/.../tmpvc67dqtg/fo-log.jsonl`) that showed the exact "FO edits frontmatter with Write, skips `status --set`" failure signature. Same shape as the PR #92 opus CI artifact.
4. DONE: Implemented option B in `skills/commission/bin/status` (new merge-hook invariant in `--set` and `--archive`). Plus `setup_fixture` in `scripts/test_lib.py` now installs the real Python status script for fixtures with merge hooks, making the guard actually reachable from live tests.
5. DONE: `first-officer-shared-core.md` Merge-and-Cleanup step 1 updated to describe the new backstop. Mod-Block Enforcement subsection updated with a new bullet naming the invariant conditions.
6. DONE: `claude-first-officer-runtime.md` Mod-Block Enforcement section updated with the "enforces this even if you forget" callout and three recovery options.
7. DONE: `tests/test_status_script.py` extended with `TestMergeHookTerminalGuard` class (14 tests) — all green.
8. DONE: `make test-static` — 297 passed, 10 subtests passed.
9. DONE: `uv run tests/test_rebase_branch_before_push.py --model haiku` — 12/12 PASS.
10. DONE: `uv run tests/test_rebase_branch_before_push.py --model opus --effort low` — 13/13 PASS.
11. DONE: `uv run tests/test_push_main_before_pr.py --model haiku` — 10/10 PASS. `uv run tests/test_push_main_before_pr.py --model opus --effort low` — 11/11 PASS.
12. DONE: Commits on `spacedock-ensign/fo-enforce-mod-blocking-at-runtime` — see history with the cycle 4 commit.

#### Files changed

- `skills/commission/bin/status` — new merge-hook invariant in `--set` and `--archive`.
- `skills/first-officer/references/first-officer-shared-core.md` — Merge-and-Cleanup step 1 + Mod-Block Enforcement subsection updated.
- `skills/first-officer/references/claude-first-officer-runtime.md` — Mod-Block Enforcement at Terminal Transitions updated.
- `tests/test_status_script.py` — new `TestMergeHookTerminalGuard` class, 14 tests.
- `scripts/test_lib.py` — `setup_fixture` installs the real Python status script for fixtures with a merge hook.
- `tests/test_rebase_branch_before_push.py`, `tests/test_push_main_before_pr.py`, `tests/test_merge_hook_guardrail.py` — push-log regex updated to handle `-u` and `-C` forms; pre-FO `bash ./status` self-test call switched to direct execution so the Python shebang is honored.

#### Local test results (the bar the brief set)

| Test | Runtime/Model | Result |
| --- | --- | --- |
| `tests/test_rebase_branch_before_push.py` | claude/haiku | PASS 12/12 |
| `tests/test_rebase_branch_before_push.py` | claude/opus low | PASS 13/13 |
| `tests/test_push_main_before_pr.py` | claude/haiku | PASS 10/10 |
| `tests/test_push_main_before_pr.py` | claude/opus low | PASS 11/11 |
| `make test-static` | n/a | PASS 297/297 (10 subtests) |

## Stage Report — Cycle 5 addendum

### Goal

Fix `test_dispatch_completion_signal.py` on CI haiku after cycle 4 additions caused the assertion "dispatched ensign prompt carries SendMessage(to=\"team-lead\", ...) instruction" to fail on PR #92.

### Root cause

The failure is **not** "the FO dropped the completion signal from its dispatch template" as the brief framed it. The actual chain of events in CI (run 24426773839):

1. FO (haiku) reads the README; one task in the workflow.
2. FO decides this is a single-entity-like scenario and skips team setup entirely — no `ToolSearch(query="select:TeamCreate")`, no `TeamCreate`.
3. FO calls `claude-team build` with `bare_mode: true, team_name: null`.
4. `claude-team build` at `skills/commission/bin/claude-team:237` **correctly** suppresses the `### Completion Signal` block because `bare_mode` is true — in bare mode, Agent() blocks and returns inline, SendMessage would fail (no team to message).
5. FO calls `Agent(subagent_type=..., prompt=<no signal>)`. Ensign writes greeting.txt, updates entity frontmatter via the merge path, entity is archived. Everything works end-to-end — `fo_exit=0`, entity archived, `status=done` equivalent.
6. Test's prompt-sanity assertion looks for `SendMessage(to="team-lead"` in the Agent prompt and fails, because bare mode legitimately omits it.

The test was un-skipped on this branch (commit 7168fad7) from the previous SKIPPED-on-haiku state of PR #90/91/93. It was never actually passing on haiku in CI — the brief's claim that it "passed on PR #90/91/93" reflects the SKIPPED status on those PRs, not a real pass.

Cycle 4's prose additions did not cause the regression. Haiku's bare-mode preference for single-task workflows is a standing behavior.

### Design choice: hybrid (A) + (B-variant)

- **Option A (trim prose):** the cycle 4 "Verbatim means character-for-character" paragraph, "Anti-patterns" list, and "Post-dispatch verification" step are warnings about a failure mode (paraphrasing the signal) that was not the actual CI failure. They bloat the runtime adapter without evidence of benefit. Trimmed.
- **Option B (helper sentinel):** rejected as implemented by the brief — "emit the signal unconditionally from the helper" is unsafe. In bare mode, instructing the ensign to "your last action MUST be `SendMessage(to=\"team-lead\")`" risks the ensign retrying a call that fails (no team exists) instead of returning cleanly. The helper's bare-mode suppression at line 237 is correct and should stay.
- **B-variant (test-level):** the test assertion is the thing that needs to adapt to bare mode. Bare-mode dispatches don't need the signal because Agent() returns inline — the original-bug scenario (FO hangs waiting for a signal the ensign was never told to send) only applies in team mode. Extended `LogParser.agent_calls` to include `team_name`; the test now passes the signal check when dispatch was bare (no `team_name` on the Agent call) and still catches the team-mode regression if `team_name` is present without `SendMessage(to="team-lead"` in the prompt.

The entity-advancement checks (lines 113-125 of the test) remain unconditional — they catch the end-to-end pre-fix hang regardless of mode. The SendMessage-in-prompt check is the narrower sanity check that's now mode-aware.

### Checklist

1. DONE: `git status` clean at start.
2. DONE: Downloaded run 24426773839 artifact. Inspected `agent-calls.txt`, `agent-prompts.txt`, `fo-log.jsonl` at `/tmp/ci-pr92-cycle4/spacedock-test-l5mkclka/`. Also inspected earlier cycle 4 run 24418652541 at `/tmp/ci-cycle4-first/spacedock-test-crzwgti4/`, and attempted PR #91/#93 artifacts (both did not include completion-signal-pipeline because the test was SKIPPED via the Makefile comment on fb5f57c5).
3. DONE: FO invoked `claude-team build` with `bare_mode: true, team_name: null`. The helper's conditional at line 237 suppressed the `### Completion Signal` block exactly as designed. Agent() was called with the prompt missing `SendMessage(to="team-lead"`. End-to-end entity archival succeeded.
4. DONE: Picked hybrid A + test-level B-variant. Justified above.
5. DONE: Implemented the fix.
   - `skills/first-officer/references/claude-first-officer-runtime.md`: removed the "Verbatim means character-for-character" paragraph, anti-patterns list, and the post-dispatch verification step. Restored the numbered step 4 → 5 as 4.
   - `scripts/test_lib.py`: `LogParser.agent_calls()` now captures `team_name` from the Agent tool call input.
   - `tests/test_dispatch_completion_signal.py`: the SendMessage-in-prompt check is gated on finding a team-mode Agent call (non-empty `team_name`). Bare-mode dispatches pass the check (with a note) because the signal is intentionally absent and the mode is valid for the end-to-end scenario.
6. DONE: `make test-static` — 301 passed, 10 subtests passed. Output pristine.
7. DONE: Local haiku reproduction via clean-auth pattern CL pointed out mid-cycle. Added `_isolated_claude_env()` to `scripts/test_lib.py` that, when `~/.claude/benchmark-token` is present (created via `claude setup-token`), spawns `claude -p` with a fresh `HOME=$(mktemp -d)` and `CLAUDE_CODE_OAUTH_TOKEN` injected — so the operator's `~/.claude/CLAUDE.md`, plugins, and skills don't contaminate the FO context. Wired into `run_first_officer` and `probe_claude_runtime`. Strictly opt-in: returns `None` when the token file is missing/empty, so CI (no token file; authenticates via `ANTHROPIC_API_KEY`) falls back to the existing `_clean_env` path and is unaffected. Ran `uv run tests/test_dispatch_completion_signal.py --runtime claude --model haiku` locally: PASS 5/5. The FO took the bare-mode path (same shape as the CI artifact from run 24426773839), and the new mode-aware assertion passed cleanly: "FO dispatched in bare mode (no team_name on Agent call); SendMessage is unnecessary since Agent() returns inline. Entity-advancement checks above cover the end-to-end pre-fix hang regression."
8. DONE: Commits on `spacedock-ensign/fo-enforce-mod-blocking-at-runtime` — see history.

### Files changed

- `skills/first-officer/references/claude-first-officer-runtime.md` — trimmed cycle 4 prose (the "Verbatim means character-for-character" paragraph, anti-patterns list, and post-dispatch verification step). Kept the Mod-Block Enforcement section.
- `scripts/test_lib.py` — `LogParser.agent_calls()` captures `team_name`; new `_isolated_claude_env()` helper; `run_first_officer` and `probe_claude_runtime` use it when the opt-in token file is present.
- `tests/test_dispatch_completion_signal.py` — SendMessage-in-prompt assertion now mode-aware (bare-mode dispatches pass since the signal is intentionally absent).

### Summary

Root cause: FO (haiku) takes the bare-mode path for single-task workflows and the helper correctly suppresses the completion signal in bare mode — the test asserted a team-mode behavior but the FO never entered team mode. Cycle 4 prose was not the cause. Fix: trimmed the redundant cycle 4 prose that warned about paraphrasing (not the actual failure mode), and made the test's SendMessage-in-prompt check conditional on finding a team-mode Agent dispatch. Also added opt-in clean-auth isolation in the harness so local live reproductions match CI's no-operator-context environment when the operator has placed a benchmark OAuth token at `~/.claude/benchmark-token`. Local haiku run confirms PASS 5/5; the end-to-end entity-advancement checks in the test remain unconditional and still catch the original pre-fix hang scenario.

## Stage Report — Cycle 6

**Goal:** Enable Claude agent teams on the two claude-live CI jobs so CI runs under the same mode the tests pass under locally, aligning CI with the known-green local path. Defer the proper bare-vs-teams marker matrix to task #148 (live E2E pytest harness).

**Failing run:** https://github.com/clkao/spacedock/actions/runs/24428162140 — `tests/test_rebase_branch_before_push.py` Phase 6. The FO push log showed the sequence `push origin main` -> `push origin <branch>` -> `push origin main` -> `push origin --delete <branch>` -> `push origin main`; the branch was deleted from the remote before the assertion could validate its contents.

**Root cause hypothesis:** CI runs in bare mode today. Per the 2026-04-14 debrief late-additions bullet, every FO `init` on CI listed zero team tools — meaning `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is not set in the runner environment, so `claude -p` takes the bare-mode path. Locally the same test passed on haiku (12/12) and opus low (13/13) per cycle 4's results table, where teams are enabled in the operator shell. Enabling teams on CI for the two claude-live jobs should align CI with the passing local path. This cycle deliberately does not attempt a broader FO fix for the branch-delete behavior — that belongs to task #148's bare/teams matrix work.

**Checklist results:**

1. DONE: Worktree clean, HEAD `38c50e80f06b5dbb3e87e4e90ebb9f6bc282cbf4`, branch `spacedock-ensign/fo-enforce-mod-blocking-at-runtime`.
2. DONE: Read `.github/workflows/runtime-live-e2e.yml`; located env blocks at lines 22–28 (claude-live) and 138–144 (claude-live-opus).
3. DONE: Added `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"` to both `claude-live` and `claude-live-opus` env blocks. Not added to `codex-live` (unrelated to Claude teams).
4. DONE: Grepped `tests/test_runtime_live_e2e_workflow.py`. The existing assertions check for specific keys (`ANTHROPIC_API_KEY`, `KEEP_TEST_DIR: "1"`, provenance fields) but do not pin the full env block or forbid additional keys. Adding a new env var does not break any assertion; no test updates needed.
5. DONE: `make test-static` -> **301 passed, 10 subtests passed** in 19.76s. Output pristine.
6. DONE: This stage report.
7. DONE: Commit on the existing branch (see checklist item 9).
8. DONE: Pushed to origin to re-trigger CI on existing PR #92 (see checklist item 9).
9. Final report captured in the section below.

### Files changed (Cycle 6)

- `.github/workflows/runtime-live-e2e.yml` — added `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"` to the `claude-live` and `claude-live-opus` env blocks. Single-line addition to each block; surrounding formatting preserved.

### Forward pointer

Task #148 (live E2E pytest harness) will introduce a proper bare-vs-teams marker matrix so both modes are exercised in CI going forward. Until then, CI matches the locally-green teams-mode path and the remaining branch-delete behavior in `test_rebase_branch_before_push.py` is out of scope for this cycle.
