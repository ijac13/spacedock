# Plugin-Shipped Runtime Assets Design

## Goal

Make commissioned workflows data-only. Commission should create the structured workflow README and entity files, while Spacedock ships the runtime assets needed to operate those workflows.

## Scope

- Stop generating workflow-local `status`.
- Stop copying workflow-local `_mods/pr-merge.md`.
- Stop copying workflow-local first-officer and ensign agents.
- Make the first officer resolve plugin-shipped status, mods, and agents at runtime.
- Update tests and fixtures to exercise the plugin-shipped runtime path.

## Design

### Runtime asset model

Spacedock keeps runtime assets in the plugin repo:

- `skills/commission/bin/status` is the canonical status implementation.
- `mods/pr-merge.md` remains the canonical PR lifecycle mod.
- `agents/first-officer.md` and `agents/ensign.md` are the canonical workflow agents.

Commission no longer copies those assets into each workflow. A commissioned workflow becomes:

- `README.md`
- entity markdown files

The workflow is operated with plugin assets:

- `claude --agent spacedock:first-officer`
- first-officer dispatches `spacedock:ensign`
- status and mods resolve from the installed plugin

### Status resolution

The first officer should not assume a workflow-local executable at `{workflow_dir}/status`. Replace that with plugin-path resolution:

- resolve the Spacedock plugin root from the active agent/workflow environment
- run the plugin-shipped status script with the workflow directory as an explicit argument

The status script should support both invocation styles:

- existing local-script mode: `workflow_dir/status`
- plugin mode: `python3 {plugin_root}/skills/commission/bin/status --workflow-dir {workflow_dir}`

This keeps the script usable in tests and transitional environments while removing the need for commission-time copying.

### Mod resolution

The first officer currently discovers mods from `{workflow_dir}/_mods/*.md`. Replace that with plugin-shipped discovery:

- read shipped mods from `{plugin_root}/mods/*.md`
- treat shipped mods as the default active mod set

For now, `pr-merge` is always available as a shipped mod and first officer logic decides when its hooks are relevant.

### Commission/refit behavior

Commission stops:

- generating `{dir}/status`
- creating `{dir}/_mods/`
- copying `mods/pr-merge.md`
- copying first-officer and ensign into `.claude/agents/`

Refit stops treating workflow-local status and mods as managed scaffolding. Existing workflows with local copies can still work, but new commissioned workflows should not receive them.

## Testing

- Update commission tests to assert that workflow-local `status`, `_mods/pr-merge.md`, and copied core agents are absent.
- Update runtime/integration helpers to invoke the plugin-shipped status implementation directly.
- Keep status script unit tests green in plugin mode.

## Non-goals

- No custom per-workflow mod installation flow.
- No local override mechanism in this change.
- No change to workflow entity schema.
