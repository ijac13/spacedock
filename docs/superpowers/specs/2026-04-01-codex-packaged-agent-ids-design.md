# Codex Packaged Agent IDs Design

**Goal:** Support Spacedock-owned logical agent ids such as `spacedock:first-officer` and `spacedock:ensign` in the Codex prototype without relying on native Codex agent registration.

## Context

The current Codex spike uses a repo-hosted first-officer prompt and a single worker prompt. Worker identity is still implicit and is overloaded:

- the stage `agent:` value acts like a dispatch id
- the same value is reused in worktree paths
- the same value is reused in git branch names

That is safe only for simple bare ids like `ensign`. It breaks once a logical packaged id contains `:` because git refs and path conventions cannot safely reuse the same string unchanged.

## Design

### 1. Treat packaged agent ids as logical ids

For the Codex path, `spacedock:ensign` is a logical worker identifier owned by Spacedock. It is not a native Codex `--agent` registration and does not need Codex to resolve it.

The Codex first officer resolves the logical id itself before spawning a worker.

### 2. Split dispatch identity from filesystem identity

Introduce two concepts in the Codex prototype:

- `dispatch_agent_id`
  The logical runtime identifier used in FO reasoning and reporting.
- `worker_key`
  A filesystem-safe stem used for worktree paths, git branch names, and worker names.

Example:

- `dispatch_agent_id = "spacedock:ensign"`
- `worker_key = "spacedock-ensign"`

### 3. Add a packaged worker registry

The Codex prototype keeps a Spacedock-owned registry mapping logical ids to prompt assets.

Initial mapping:

- `spacedock:ensign` -> `references/codex-worker-prompt.md`

This keeps the packaged-name behavior explicit and testable while avoiding any dependence on native Codex agent loading.

### 4. Codex FO dispatch flow

For each ready entity:

1. Read the stage `agent:` value from the workflow README.
2. If no stage agent is set, default to `spacedock:ensign` for the Codex path.
3. Resolve the logical id through the packaged worker registry.
4. Derive a safe `worker_key`.
5. Use `worker_key` for:
   - `.worktrees/{worker_key}-{slug}`
   - `{worker_key}/{slug}` branch name
   - spawned worker display name
6. Pass `dispatch_agent_id` to the worker assignment so reporting still names the packaged worker id.

### 5. Test strategy

The Codex path needs direct tests for the new default behavior.

- Unit-level: verify `spacedock:ensign` resolves to the packaged worker prompt and a safe `worker_key`.
- Integration-level: verify the Codex FO path can run against a fixture without leaking `:` into worktree stems or branch names.
- Existing gate and rejection tests should continue to pass under the new default logical id.

## Non-goals

- Native Codex `--agent spacedock:first-officer`
- Codex-visible packaged agent installation
- Full parity for custom stage agent packaging beyond the initial registry hook

## Acceptance Criteria

1. The Codex FO defaults to logical worker id `spacedock:ensign`.
2. Worktree paths and branch names use a filesystem-safe `worker_key`, not the raw logical id.
3. The Codex path can resolve `spacedock:ensign` to the packaged worker prompt asset.
4. The Codex gate and rejection spike tests still pass.
