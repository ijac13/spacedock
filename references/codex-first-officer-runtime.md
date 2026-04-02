# Codex First Officer Runtime

This file defines how the shared first-officer core executes on Codex.

## Entry Surface

The user-invocable entrypoint is `spacedock:first-officer`.
That skill should immediately bootstrap `../../agents/first-officer.md`.
The packaged first-officer agent asset, not the skill wrapper, should carry the operational contract.

## Workflow Target

- If the user gives an explicit workflow path, use it.
- If not, discover candidate workflows from the current repository.
- If multiple candidates exist, ask the user which workflow to manage.
- If the user names a specific entity and asks to process it through the workflow, apply the shared single-entity mode rules.

When the workflow path is explicit, do not spend time rediscovering alternatives. Move directly to:
- README
- `status` output
- the in-scope entity file

## Packaged Worker Resolution

- Treat names like `spacedock:ensign` as logical ids, not native Codex agent types.
- For Spacedock-packaged ids, the worker resolves its role definition by convention:
  `~/.agents/skills/{namespace}/agents/{name}.md`

Split worker identity into:
- `dispatch_agent_id`
- `worker_key`

## Dispatch Adapter

Codex does not natively spawn packaged names like `spacedock:ensign`.

Codex effectively operates in bare-mode dispatch:
- the first officer owns orchestration directly
- worker results return through `spawn_agent` completion, not team messaging
- if the run is bounded to a single entity or first meaningful outcome, terminate once that condition is satisfied

Speed and boundedness matter on the Codex path. Do not spend time on exploratory reads that are not needed for the next dispatch or stop condition.

Avoid these wasteful actions unless a real blocker forces them:
- rereading your own skill files after activation
- opening the packaged worker agent asset just to inspect it
- reading the source code of `{workflow_dir}/status` instead of running it
- scanning unrelated entities when the run is scoped to one entity
- reading large files past the specific stage/entity sections you need

For each dispatch:
1. Resolve the logical id into a safe `worker_key`.
2. Create the worktree if required.
3. Spawn a generic worker with `spawn_agent(..., fork_context=false)`.
4. In the worker prompt:
   - first instruct the worker to resolve its role definition from the logical id and read it before doing anything else
   - then pass the assignment fields

For bounded terminal-completion runs, prefer:
- `python3 ~/.agents/skills/spacedock/scripts/codex_finalize_terminal_entity.py --repo-root "{repo_root}" --workflow-dir "{workflow_dir}" --entity-slug "{slug}"`

Treat that helper output as authoritative for merge-hook execution, PR-pending stop states, archive path, final commit, and worktree cleanup.

Do not rely on inherited thread context. The worker prompt must be fully self-contained so the worker can start with `fork_context=false`.
Never omit `fork_context=false` on worker dispatches in Codex.

Use this exact pattern:

```text
spawn_agent(
  agent_type="worker",
  fork_context=false,
  message="<fully self-contained worker assignment>"
)
wait_agent(...)
```

Always preserve the logical packaged id in summaries and use only `worker_key` in branch/worktree/session names.

## Codex Worker Assignment Fields

Pass these fields to a worker:
- `dispatch_agent_id`
- `worker_key`
- `role_asset_kind`
- `role_asset_name`
- `workflow_dir`
- `entity_path`
- `stage_name`
- `stage_definition_text`
- `worktree_path` when present
- checklist items

If a `worktree_path` is present, `entity_path` should point to the entity file inside that worktree, not the main-branch copy.

## Codex Merge And Cleanup

- Merge hooks live under `{workflow_dir}/_mods/*.md`.
- For a deterministic Codex terminal path, use the finalize helper instead of freehand merge/archive shell sequences.
- The finalize helper should run merge hooks before local merge, stop on `pr_pending`, and otherwise perform local merge, archive, terminal commit, and worktree cleanup.

## Codex Completion Shape

- Workers report completion by returning a concise final response.
- The first officer treats the entity file and stage report as the source of truth.
- The first officer waits for the worker result before continuing.
- In bounded single-entity runs, if the worker completion message already contains the requested verdict, evidence, or terminal outcome, use that message as sufficient evidence for the final response and stop immediately.
- Only reread the entity file or rerun `status` after `wait_agent(...)` when the worker message is missing a detail required by the stated stop condition.

## Bounded Prototype Rule

For the current Codex spike:
- stop after the first meaningful outcome
- if the workflow is waiting at a gate, report the gate review and stop
- if a worker returns a verdict or concrete evidence, summarize it and stop
- if a feedback stage rejects, mention the follow-up target even if the full bounce loop is not completed in the same run
- when the run is explicitly in single-entity mode, prefer the shared single-entity termination/output rules over generic status summaries

For a bounded run, once the stop condition is satisfied:
- send one concise final response
- do not perform extra file reads
- do not start another dispatch cycle
- do not wait for additional agents unless their completion is required by the stated stop condition
