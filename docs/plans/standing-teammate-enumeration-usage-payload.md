---
id: 166
title: "Standing-teammate auto-enumeration payload: inline per-teammate usage spec into dispatch prompts"
status: ideation
source: "CL observation during 2026-04-16 session after comm-officer mod gained two new modes (polish-and-write, polish-and-edit) — dispatched ensigns can't discover mode trigger phrases from the current AC-13 section wording"
started: 2026-04-16T16:00:50Z
completed:
verdict:
score: 0.55
worktree:
issue:
pr:
---

## Problem Statement

#162 cycle 2 AC-13 ships `claude-team build` auto-enumeration: every dispatch prompt gains a `### Standing teammates available in your team` section listing alive standing teammates. The current section payload per teammate is:

```
**{name}** ({description}): SendMessage with the relevant input shape; reply format per the mod.
```

"SendMessage with the relevant input shape" is hand-waving. It tells the dispatched ensign a standing teammate exists but not how to address it. A caller who doesn't already know the mod's trigger phrases (like `polish and write to {path}:` or the exact `polish this file` gate) cannot invoke non-trivial modes from that line. They have to go read the mod file itself, which defeats the point of auto-enumeration — the whole mechanism exists to remove the FO's discipline burden of surfacing teammate availability to workers.

## Context

This gap surfaced on 2026-04-16 after the comm-officer mod was updated mid-session to add two new caller patterns: `polish-and-write` (mirrors the Write tool shape) and `polish-and-edit` (mirrors Edit). Both have precise trigger headers. A dispatched ensign reading the current auto-enumeration section could not reconstruct those headers from "the relevant input shape." The FO (who loaded the mod at session boot + authored the updates) knows the patterns, but that knowledge doesn't propagate to freshly-dispatched workers through the AC-13 mechanism as currently implemented.

## Approach tradeoffs

Three options, not mutually exclusive:

**(a) Pull the mod's existing `## Routing guidance` section into the dispatch payload.** Helper extracts the whole section verbatim from each alive teammate's mod and drops it below that teammate's header line in the enumerated section. No mod schema change — the current `## Routing guidance` text becomes caller-facing as written. Costs: the `## Routing guidance` section mixes WHEN-to-use prose with HOW-to-use prose; dropping it all in bloats every dispatch prompt with scope-discipline paragraphs dispatched workers don't need. Also couples the helper to section conventions.

**(b) Introduce a dedicated `## Routing Usage` section (or equivalent) to the mod schema.** Helper pulls this named section per teammate. Mod authors write concise caller-facing trigger-phrase + reply-shape documentation there; general scope discipline stays in `## Routing guidance`. Costs: mod schema gets another required-ish section; existing mods (pr-merge, comm-officer) need to be updated to add it; schema versioning story emerges.

**(c) Encode caller-facing trigger shape in mod frontmatter.** Instead of a free-form markdown section, standardize a `usage:` structured block in frontmatter listing each pattern's trigger, input shape, and reply format. Helper renders it. Costs: frontmatter becomes non-trivial (multi-line structured); loses the "mod file is readable markdown" property; schema evolution is harder than text.

All three address the same asymmetry: the mod file owns the caller-facing usage spec, but today's AC-13 helper doesn't lift enough of it into dispatch prompts for ensigns to use. Option (a) is cheapest to ship but potentially noisy; option (b) adds one schema bit for cleaner separation; option (c) is structured but more invasive.

## Open questions for ideation

- Which of the three options (or a hybrid)?
- Do we include routing usage for non-standing mods too (e.g., pr-merge), or only for standing teammates?
- How verbose should the inlined usage be per teammate? A line, a paragraph, or a full section? Trade-off: dispatch-prompt token cost vs caller autonomy.
- Does the mod's `## Routing guidance` section need a backward-compat strategy if we introduce a new section? Refit?
- Does this mechanism generalize to Codex, or is it Claude-only for v1?

## Out of Scope

- **Whole mod-schema overhaul.** Ideation should not redesign how mods are structured beyond what's needed for this payload.
- **Cross-workflow mod aggregation.** Same single-workflow scope as #162 v1.
- **Codex runtime equivalents.** Codex's dispatch-prompt assembly has its own path; ideation may scope Codex in or out based on cost.
