---
title: First officer must enforce mod-declared blocking actions at runtime
id: 114
status: ideation
source: CL observation during entity 110 closeout
started: 2026-04-09T22:56:43Z
completed:
verdict:
score: 0.80
worktree:
issue:
pr:
---

First officer currently relies too heavily on remembering mod instructions from prose. That is brittle. A mod can require a stop, approval, or external wait, but the runtime does not yet enforce those requirements mechanically.

## Problem Statement

The `pr-merge` mod correctly says gate approval does not imply PR approval, but first officer can still drift unless it re-reads and obeys the mod at the exact transition point. This is a general workflow safety problem, not just a PR problem.

## Desired Outcome

Add a generic runtime mechanism so active mods can force first officer to pause for captain approval or another blocking condition, and a resumed session cannot silently skip that pending requirement.

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
