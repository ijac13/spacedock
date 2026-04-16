# Kilo First Officer Runtime

This file defines how the shared first-officer core executes on Kilo.

## Entry Surface

The user-invocable entrypoint is `spacedock:first-officer`.
That skill should immediately bootstrap `../../agents/first-officer.md`.
The packaged first-officer agent asset, not the skill wrapper, should carry the operational contract.

## Runtime Detection

Detect Kilo runtime via:
- `KILO=1` environment variable (primary)
- `KILOCODE_VERSION` or `KILO_PID` (secondary)

Load this adapter when `KILO` is set.

## Workflow Target

- If the user gives an explicit workflow path, use it.
- If not, run `status --discover` to find candidate workflows.
- If exactly one result, use it. If zero, report no workflow found. If multiple, ask the user which to manage.
- If the session is non-interactive and the prompt names a specific entity to process, apply the shared single-entity mode rules.

When the workflow path is explicit, do not spend time rediscovering alternatives. Move directly to:
- README
- `status` output
- the in-scope entity file

When creating a new entity, use `status --next-id` to fetch only the next sequential ID. Reserve `status --boot` for startup diagnostics and broader workflow inventory.

## Packaged Worker Resolution

- Treat names like `spacedock:ensign` as logical ids.
- For Spacedock-packaged ids, the worker resolves its role definition through skill preloading:
  `~/.agents/skills/{namespace}/{name}/SKILL.md`
- Preserve the logical id exactly as `dispatch_agent_id: spacedock:ensign` when that packaged worker is selected.
- Derive the safe naming key as `worker_key: spacedock-ensign`.
- Use `worker_key` for worktree paths as `.worktrees/{worker_key}-{slug}` and branch names as `{worker_key}/{slug}`.

## Dispatch Adapter

Kilo uses the `task` tool to spawn subagents.

**Critical limitation (inherited from OpenCode):**
- The `task` tool is **blocking** — it waits for the subagent to complete before returning
- Subagents are **not addressable** after completion — handles expire
- No `SendMessage` equivalent — cannot communicate with live subagent
- No worker reuse across stages — must fresh dispatch every time

### Dispatch Pattern

```typescript
// Fresh dispatch for every stage
task(
  description="<stage>/<worker_key>",
  prompt="<fully self-contained worker prompt>",
  subagent_type="general"
)
```

The result includes `task_id` but this handle expires immediately after the subagent returns.

### Reuse Flow

**NOT POSSIBLE** — Kilo does not support worker reuse.

| Stage | Pattern |
|-------|---------|
| Initial dispatch | Fresh `task` spawn |
| Feedback bounce | Fresh `task` spawn (cannot reuse) |
| Stage advance | Fresh `task` spawn |

Every stage requires a fresh dispatch. This increases per-entity cost but is acceptable for bounded runs.

### Worker Prompt Requirements

Worker prompts must be fully self-contained — include all context needed since no reuse is possible.

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

## Single-Entity Mode

Single-entity mode works well on Kilo:
- Dispatch worker for the entity
- Wait for completion (blocking by design)
- Commit stage work
- Stop

For bounded runs targeting a single entity, this is acceptable.

## Bounded Stop Rules

For bounded single-entity runs:
1. Dispatch worker with full self-contained prompt
2. Wait for `task` result (blocking)
3. Treat the worker's final response as completion evidence
4. Commit stage work
5. Stop — no further routing is possible anyway

## Merge And Cleanup

- Merge hooks live under `{workflow_dir}/_mods/*.md`.
- Run merge hooks before local merge.
- Stop on `pr_pending`.
- Otherwise perform local merge, archive, terminal commit, and worktree cleanup.

## Completion Shape

- Workers report completion by returning a final response.
- The first officer treats the entity file and stage report as the source of truth.
- Since reuse is not possible, treat the final `task` result as the completion evidence.

## Limitations Summary

| Feature | Kilo Support |
|---------|--------------|
| Worker reuse | ❌ Not possible |
| SendMessage | ❌ Not possible |
| Background agents | ❌ Blocking only |
| Standing teammates | ❌ Not possible |
| Fresh dispatch per stage | ✅ Works |
| Single-entity mode | ✅ Works |

The blocking `task` tool is a known limitation inherited from OpenCode (see issue #5887, #15069, #20872 — all closed not planned).