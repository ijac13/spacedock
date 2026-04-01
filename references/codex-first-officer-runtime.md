# Codex First Officer Runtime

This file defines how the shared first-officer core executes on Codex.

## Skill Surface

The user-invocable entrypoint is `spacedock:first-officer`.

Read the shared documents in this order before acting:
1. `~/.agents/skills/spacedock/references/first-officer-shared-core.md`
2. `~/.agents/skills/spacedock/references/code-project-guardrails.md`
3. this file

## Workflow Target

- If the user gives an explicit workflow path, use it.
- If not, discover candidate workflows from the current repository.
- If multiple candidates exist, ask the user which workflow to manage.

## Packaged Worker Registry

- Read packaged worker ids from `~/.agents/skills/spacedock/references/codex-packaged-agents.json`.
- Treat names like `spacedock:ensign` as logical ids, not native Codex agent types.

Split worker identity into:
- `dispatch_agent_id`
- `worker_key`

## Dispatch Adapter

Codex does not natively spawn packaged names like `spacedock:ensign`.

For each dispatch:
1. Resolve the logical id through the packaged worker registry.
2. Resolve the asset path to an absolute path.
3. Create the worktree if required.
4. Spawn a generic worker with `spawn_agent(agent_type="worker")`.
5. In the worker prompt:
   - first instruct the worker to read the resolved role asset and follow it before doing anything else
   - then pass the assignment fields

Always preserve the logical packaged id in summaries and use only `worker_key` in branch/worktree/session names.

## Codex Worker Assignment Fields

Pass these fields to a worker:
- `dispatch_agent_id`
- `worker_key`
- `role_asset_kind`
- `role_asset_path`
- `workflow_dir`
- `entity_path`
- `stage_name`
- `stage_definition_text`
- `worktree_path` when present
- checklist items

## Codex Completion Shape

- Workers report completion by returning a concise final response.
- The first officer treats the entity file and stage report as the source of truth.
- The first officer waits for the worker result before continuing.

## Bounded Prototype Rule

For the current Codex spike:
- stop after the first meaningful outcome
- if the workflow is waiting at a gate, report the gate review and stop
- if a worker returns a verdict or concrete evidence, summarize it and stop
- if a feedback stage rejects, mention the follow-up target even if the full bounce loop is not completed in the same run

