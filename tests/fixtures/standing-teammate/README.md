---
commissioned-by: spacedock@test
mission: Live test — `standing: true` mod spawns a long-lived teammate the FO can route to
entity-label: task
entity-label-plural: tasks
id-style: sequential
stages:
  defaults:
    worktree: false
    fresh: false
    gate: false
    concurrency: 1
  states:
    - name: backlog
      initial: true
    - name: work
    - name: done
      terminal: true
---

# Standing Teammate Test Workflow

A minimal no-gate workflow whose `_mods/` directory declares one standing
teammate (`echo-agent`) via `standing: true`. Used by
`tests/test_standing_teammate_spawn.py` to verify end-to-end that the FO:

1. Invokes `claude-team spawn-standing` during startup.
2. Spawns `echo-agent` as a team member.
3. Can route a SendMessage to `echo-agent` and receive an `ECHO: ` reply.

## File Naming

Entities are named `{id}-{slug}.md` with sequential ids.

### `work`

The ensign adds the line "work done" to the task file and commits.
