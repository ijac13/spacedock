---
id: 205
title: "Audit standing-teammate spawn prompts for Skill-invoke / contract drift (follow-up to #204)"
status: backlog
source: "2026-04-19 session — #204 staff review §F + §G.4. #204 fixes `cmd_build` (ensign dispatch path) to inject `Skill(skill=\"spacedock:ensign\")` and remove duplicated shared-core prose. Standing-teammate spawn goes through a different code path (`cmd_spawn_standing` in `skills/commission/bin/claude-team`, around line 814) that emits the mod's `## Agent Prompt` section verbatim, bypassing `cmd_build` entirely. The one live standing teammate (`comm-officer.md:77`) already does an explicit ToolSearch for its specialty skill, but does NOT load a shared operating contract. If future standing mods are added that need cross-dispatch discipline, the same preload bug bites them."
started:
completed:
verdict:
score: 0.6
worktree:
issue:
pr:
mod-block:
---

Follow-up to #204. Scope: audit the `cmd_spawn_standing` spawn-prompt assembly path in `skills/commission/bin/claude-team` and every file under `docs/plans/_mods/` against the same standards #204 enforces for `cmd_build`.

## Specific questions for ideation

1. Does `cmd_spawn_standing` need a Skill-invoke first-action directive analogous to #204's `cmd_build` fix? If so, which skill — workflow-specific (`spacedock:standing-teammate`?), or mod-declared, or the mod's specialty skill?
2. Do any of the mod files under `docs/plans/_mods/` duplicate prose that belongs in a shared standing-teammate contract? Currently `comm-officer.md` is self-contained (its `## Agent Prompt` is its entire operating manual). Should spacedock ship a `skills/standing-teammate/` shared-core?
3. Is there a common discipline standing teammates should share (idle behavior, shutdown response, routing convention, size limits on replies) that's currently duplicated across every mod's `## Agent Prompt`?

Acceptance criteria and a test plan will be defined during ideation. This is a small scope task — not load-bearing for #203 or #204.

## Related

- #204 (this task's parent — fixes ensign dispatch path)
- #183 (the BashOutput discipline ultimately landed in ensign-shared-core — precedent for shared-contract pattern)
- `docs/plans/_mods/comm-officer.md` (the one live standing teammate)
- `docs/plans/_mods/pr-merge.md` (a merge-hook mod, not a standing teammate — may or may not be in scope)
