---
id: 061
title: Pair implementation and validation agents — validator judges, implementer fixes
status: ideation
source: CL
started: 2026-03-27T22:45:00Z
completed:
verdict:
score:
worktree:
---

Currently the validation ensign both finds bugs and fixes them, then validates its own fixes. This breaks the independence that `fresh: true` is designed to provide.

## Proposed model

Keep the implementation agent alive during validation. When validation finds a bug:
1. Validation reports the finding to the first officer
2. First officer relays to the implementation agent to fix
3. Implementation fixes and commits
4. Validation re-validates (never wrote code, stays independent)

The validator only reads and judges. The implementer only writes and fixes.

## Session boundary case

The implementation agent may already be shut down — either because the session ended between implementation and validation, or because the first officer shut it down before dispatching validation (current behavior).

When validation finds a bug and the implementation agent is gone:
- Respawn a fresh implementation agent in the same worktree
- The worktree has the full git history and the entity file with the implementation stage report — this is the context the respawned agent needs to understand what was built
- The validation ensign's finding (what's wrong, what needs to change) goes into the dispatch prompt

The entity file is the handoff artifact. The implementation stage report documents what was built and where. A respawned implementer reads it and has enough context to fix.

## What changes

- First-officer template: don't shut down implementation agent when dispatching validation
- First-officer template: validation rejection flow relays to implementation agent (or respawns one)
- Validation ensign instructions: do NOT fix bugs yourself — report them and wait for the fix
- Consider: should the ensign template have a "validator mode" flag, or should this be a separate agent type?
