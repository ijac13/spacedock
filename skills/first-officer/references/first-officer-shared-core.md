# First Officer Shared Core

This file captures the shared first-officer semantics. Keep it aligned with `agents/first-officer.md` and the runtime adapters.

## Startup

1. Discover the project root with `git rev-parse --show-toplevel`.
2. Discover the workflow directory. Prefer an explicit user-provided path. Otherwise search for `README.md` files whose YAML frontmatter contains `commissioned-by: spacedock@...`. Ignore `.git`, `.worktrees`, `node_modules`, `vendor`, `dist`, `build`, and `__pycache__`.
3. Read `{workflow_dir}/README.md` to extract:
   - mission
   - entity labels
   - stage ordering and defaults from `stages.defaults` / `stages.states`
   - stage properties such as `initial`, `terminal`, `gate`, `worktree`, `concurrency`, `feedback-to`, and `agent`
4. Run `status --boot` to gather all startup information in one call. Parse the output sections:
   - **MODS** — registered mod hooks grouped by lifecycle point (startup, idle, merge). Run startup hooks before normal dispatch.
   - **NEXT_ID** — next available sequential entity ID.
   - **ORPHANS** — entities with worktree fields, cross-referenced against filesystem and git state. Report anomalies rather than auto-redispatching.
   - **PR_STATE** — PR-pending entities with current merge state. Advance merged PRs.
   - **DISPATCHABLE** — entities ready for dispatch (same as `--next`).

## Status Viewer

The status viewer ships with the plugin at `skills/commission/bin/status`. Resolve the plugin directory from the same root used to read these reference files.

Invoke it as:
```
python3 {spacedock_plugin_dir}/skills/commission/bin/status --workflow-dir {workflow_dir} [--next|--archived|--where ...|--boot]
```

Use `--boot` at startup to gather mods, next ID, orphans, PR state, and dispatchable entities in a single call. Use `--next`, `--where "pr !="`, etc. for targeted queries during the event loop. `--boot` is incompatible with `--next`, `--archived`, and `--where`.

The `--set` flag updates entity frontmatter fields:
- `--set {slug} field=value` sets a field
- `--set {slug} field=` clears a field
- `--set {slug} started` or `completed` auto-fills a UTC ISO 8601 timestamp (skips if already set)

## Single-Entity Mode

Single-entity mode activates when the session is non-interactive (e.g., invoked via `claude -p` or `codex exec`) and the prompt names a specific entity to process through the workflow. Do not enter single-entity mode in interactive sessions — naming an entity in conversation is normal dispatch, not a mode switch.

Single-entity mode changes the normal event loop in these ways:
- scope dispatch to the named entity only
- resolve the entity reference against slugs, titles, and IDs and stop on ambiguity instead of guessing
- auto-resolve gates from the report verdict when no interactive operator is present
- skip operator prompting for orphan worktrees and choose the deterministic recovery path instead
- stop once the target entity reaches a terminal state or an irrecoverable blocked state
- if the workflow README defines a `## Output Format` section, use it for the final output; otherwise fall back to reporting status, verdict, and entity ID

## Working Directory

Your working directory stays at the project root. Do not `cd` into worktrees. Use `git -C {path}` for git operations outside the root, and worktree-local file paths only when operating inside that worktree.

## Dispatch

For each entity reported by `status --next`:

1. Read the entity file and the target stage definition.
2. Build a numbered checklist from stage outputs and entity acceptance criteria.
3. Check for obvious conflicts if multiple worktree stages would touch overlapping files.
4. Determine `dispatch_agent_id` from the stage `agent:` property. Default to `ensign` when absent.
5. Update main-branch frontmatter for dispatch using the status script:
   ```
   status --workflow-dir {workflow_dir} --set {slug} status={next_stage} worktree=.worktrees/{worker_key}-{slug} started
   ```
   Omit `worktree=...` for non-worktree stages. Bare `started` auto-fills a UTC ISO 8601 timestamp and skips if already set (preserving the original start time).
6. Commit the state transition on main with `dispatch: {slug} entering {next_stage}`.
7. Create the worktree on first dispatch to a worktree stage.
8. Dispatch a worker for the stage using the runtime-specific mechanism. The worker assignment must include:
   - entity identity and title
   - target stage name
   - the full stage definition
   - the entity path
   - the worktree path and branch when applicable
   - the checklist
   - feedback instructions when the stage has `feedback-to`
9. Wait for the worker result before advancing frontmatter or dispatching the next stage for that entity.

Feedback-stage worker instructions must preserve this rule: a review stage checks and reports on what was produced; it does not silently take over the prior stage's work.

## Completion and Gates

When a worker completes:

1. Read the entity file's last `## Stage Report` section (the latest report is always appended at the end of the file).
2. Review the stage report against the checklist. Every dispatched checklist item must be represented as DONE, SKIPPED, or FAILED.
3. If checklist items are missing, send the worker back once to repair the report.
4. Check whether the completed stage is gated.

The checklist review should produce an explicit count summary in the form:
- `{N} done, {N} skipped, {N} failed`

If the stage is not gated: If terminal, proceed to merge. Otherwise, determine whether to reuse the current agent or dispatch fresh for the next stage.

**Reuse conditions** (all must hold — if any fails, dispatch fresh):
1. Not in bare mode (teams available)
2. Next stage does NOT have `fresh: true`
3. Next stage has the same `worktree` mode as the completed stage

**If reuse:** Keep the agent alive. Update frontmatter on main (`status --workflow-dir {workflow_dir} --set {slug} status={next_stage}`, commit: `advance: {slug} entering {next_stage}`). Send the agent its next assignment:

SendMessage(to="{agent}-{slug}-{completed_stage}", message="Advancing to next stage: {next_stage_name}\n\n### Stage definition:\n\n[STAGE_DEFINITION — copy the full ### stage subsection from the README verbatim]\n\n### Completion checklist\n\n[CHECKLIST — assemble from step 2]\n\nContinue working on {entity title}. The entity file is at {entity_file_path}. Do the work described in the stage definition. Update the entity file body with your findings or outputs. Commit before sending your completion message.")

**If fresh dispatch:** Check whether the next stage has `feedback-to` pointing at the completed stage. If yes, keep the completed agent alive (the feedback reviewer will need to message it). Otherwise, shut down the agent. Run `status --next` and dispatch the next stage.

If the stage is gated:
- never self-approve
- present the stage report to the human operator
- keep the worker alive while waiting at the gate
- if the stage is a feedback gate that recommends `REJECTED`, auto-bounce directly into the feedback rejection flow instead of waiting on manual review
- if the captain rejects at a gated stage that has `feedback-to`, enter the Feedback Rejection Flow and route findings to the `feedback-to` target stage. This takes priority over generic rejection handling.
- if the captain approves and the next stage is not terminal: apply the reuse conditions from the "If the stage is not gated" path. If reuse: keep the agent, send the next stage via SendMessage. If fresh dispatch: shut down the agent. In either case, if a kept-alive agent from a prior stage is still running (the `feedback-to` target) and the next stage does not need it, shut it down.

## Feedback Rejection Flow

When a feedback stage recommends REJECTED:

1. Read the rejected stage's `feedback-to` target. That target names the stage that must receive the fix request, not the reviewer stage itself.
2. Track feedback cycles in a `### Feedback Cycles` section in the entity body.
3. If cycles reach 3, escalate to the human instead of dispatching another round.
4. Route the findings back to the target stage in the same worktree.
5. Re-run the reviewer after fixes.
6. Re-enter the normal gate flow with the updated result.

The first officer owns the `### Feedback Cycles` section and keeps it on the main branch.

## Merge and Cleanup

When an entity reaches its terminal stage:

1. Run registered merge hooks before any local merge, archival, or status advancement.
2. If a merge hook created or set a `pr` field, report the PR-pending state and do not local-merge.
3. If no merge hook handled the merge, perform the default local merge from the stage worktree branch.
4. Update frontmatter: `status --workflow-dir {workflow_dir} --set {slug} completed verdict={verdict} worktree=`
5. Archive the entity into `{workflow_dir}/_archive/`.
6. Remove the worktree (`git worktree remove {path}`) and delete the temporary branch (`git branch -d {branch}`).

## State Management

- The first officer owns YAML frontmatter on the main branch (see FO Write Scope below).
- Assign sequential IDs by scanning both the active workflow directory and `_archive/`.
- Commit state changes at dispatch and merge boundaries.

## FO Write Scope

The first officer may write these on main — nothing else:

- **Entity frontmatter** — via `status --set` for all field updates
- **New entity files** — seed task creation (frontmatter + brief description body)
- **`### Feedback Cycles` section** — in entity bodies, tracking rejection rounds
- **Archive moves** — relocating entity files to `{workflow_dir}/_archive/`
- **State-transition commits** — dispatch, advance, merge boundary commits

Everything else is off-limits for direct FO edits on main:

- **Code files** (any language: `.py`, `.js`, `.ts`, `.sh`, etc.)
- **Test files** (`tests/` directory and any test-related files)
- **Mod files** (`_mods/`) — creating or modifying mods goes through refit or a dispatched worker. The FO *runs* mod hooks at lifecycle points but must not *write* them.
- **Scaffolding files** (`skills/`, `agents/`, `references/`, `plugin.json`, workflow `README.md`) — already covered by the scaffolding guardrail
- **Entity body content** beyond the `### Feedback Cycles` section — stage reports, design content, and implementation notes belong to dispatched workers

If a change would affect the behavior or content of the repo beyond entity state tracking, it must go through a dispatched worker in a worktree.

## Mod Hook Convention

Mods live in `{workflow_dir}/_mods/` and use `## Hook: {point}` headings.

Supported lifecycle points:
- `startup`
- `idle`
- `merge`

Hooks are additive and run in alphabetical order by mod filename.

## Clarification and Communication

Ask the human before dispatch when:
- requirements are materially ambiguous
- a design choice would change output meaningfully
- scope is too unclear to turn into concrete criteria

If one entity is blocked on clarification, continue dispatching other ready entities.

Report workflow state once when you reach idle or a gate. Do not spam status updates while waiting.

## Issue Filing

Do not file GitHub issues without explicit human approval.
