---
id: 123
title: "Status tool as workflow-op CLI — fix --where, expose custom fields, unify mutation paths"
status: ideation
source: "External FO feedback (GTM + experiment pipelines) during 2026-04-10 session"
score: 0.75
worktree:
started: 2026-04-11T00:40:18Z
completed:
verdict:
issue:
pr:
---

The status tool (`skills/commission/bin/status`) is the primary programmatic interface between the first officer and workflow state, but it's currently a half-tool: it knows the fixed workflow schema, can't query or display custom frontmatter fields, can't write missing fields ([task 122](status-set-missing-field-silent-noop.md)), and doesn't unify the four disjoint state-mutation surfaces. Evolve it into a proper workflow-op CLI so the FO has a single reliable interface for state operations instead of four half-overlapping tools.

## Three related gaps observed this session

Two independent external FOs (one in a GTM/outreach pipeline, one in an experimentation harness) independently flagged adjacent problems with the status tool:

**Gap 1 — `--where` filter returns zero rows for valid queries.** GTM FO ran `status --where "status=watching"` when 21 entities were in the `watching` status and got zero rows. The silence-watcher mod in that workflow already documents a `grep -l "^status: watching$"` workaround ("if `--where` isn't supported, fall back to grep"), which is a tell that this bug is known — the mod author pre-emptively routed around the primary query tool. Either the filter syntax differs from what the docs imply, or the implementation is broken. Either way, the workaround is the load-bearing path.

**Gap 2 — status output shows only a fixed column set.** `status --workflow-dir X` prints ID / SLUG / STATUS / TITLE / SCORE / SOURCE. Custom frontmatter fields are a central spacedock extension point (the discovery-outreach workflow defines `last-outbound-at`, `nudge-count`, `last-inbound-at`, `outcome`, etc.), but the viewer can't display them. To eyeball schema-specific state, the FO falls back to inline Python. The primary observability tool doesn't know about the observability the workflow added.

**Gap 3 — four disjoint mutation paths.** Workflow state currently mutates through four separate mechanisms: `status --set` for frontmatter, `Edit` for entity bodies, dispatched workers for mods/scaffolding, and shell `mv` for archive moves. No single tool understands all four surfaces. Boundaries are maintained by convention + the FO Write Scope prose, not by tool enforcement. Any of these can be misused without the tool noticing — you have to remember which one to reach for.

## Design direction

Evolve `status` into the primary workflow-op CLI for the two surfaces the FO legitimately touches: **frontmatter** (read, query, write) and **archive moves**. Body writes stay with `Edit` (worker-owned). Mod file edits stay with dispatched workers (scaffolding scope).

Not a rewrite — an evolution. Fix the bugs, fill the gaps, keep the Python script surface.

## Scope

1. **Fix `--where` filter.** Equality queries like `status=X` and `custom-field=Y` return the matching entities. Support custom frontmatter fields, not just the fixed schema fields. Ideation should decide whether to also support negation (`pr !=`) and presence (`completed`), though at least simple equality must work.
2. **Add custom-column output.** `status --columns field1,field2,...` or `status --all-fields` or equivalent — display non-default frontmatter fields in the output table. Default columns remain unchanged for backcompat.
3. **Add archive move subcommand.** `status --archive slug` moves the entity to `_archive/` and updates any frontmatter fields that track archival status. This replaces the bare `mv` + commit dance with a tool-level operation.
4. **Land alongside task 122.** Task 122 is the silent-no-op bug on `status --set`. Both target the same tool. Consider a single "status tool reliability + ergonomics" pass that lands 122 + 123 together.

## Out of scope

- Rewriting status in another language.
- Turning status into a full query language (SQL-like). `--where` fix is the minimal query improvement needed.
- Making status mutate body content — Edit stays with workers in worktrees for actual content.
- Editing mod files — stays with dispatched workers (scaffolding).
- Adding a full `--columns` DSL with formatting options. Minimal subset only.

## Acceptance Criteria (ideation to refine)

1. `status --where "status=X"` returns all entities matching the predicate, for both default and custom frontmatter fields.
   - Test: unit tests over a fixture workflow with a mix of default and custom fields.
2. `status --columns pr,worktree,last-outbound-at` (or equivalent flag) includes those columns in the output alongside the default set; `--all-fields` or equivalent includes every non-empty frontmatter field.
   - Test: unit test comparing output to an expected table.
3. `status --archive slug` moves `{workflow_dir}/{slug}.md` to `{workflow_dir}/_archive/{slug}.md` and optionally updates frontmatter (e.g., `archived: <timestamp>`) if the schema defines it.
   - Test: unit test against a fixture.
4. Default behavior (no new flags) is unchanged — existing callers are not broken.
   - Test: regression against the existing suite.
5. Unit tests cover the fixed `--where`, the new `--columns` / `--all-fields`, and the new `--archive` subcommand.

## Test Plan

- Unit tests in a new `tests/test_status_tool.py` (or extend existing status-tool tests if any exist). Low cost, required.
- Regression run on any existing tests that exercise the status tool.
- Manual check against the live self-hosted `docs/plans/` workflow — the three gaps should close.
- No E2E needed; this is a tool-level change.

## Related

- **Task 122** `status-set-missing-field-silent-noop` — the same tool, same session's pain. **Consider merging 122 into this task or landing them back-to-back in the same PR.**
- **Task 121** `fo-context-aware-reuse` — the FO reliability work from this session, tangential.
- GTM FO external feedback (2026-04-10): lists `--where` filter fix as their **#2 priority** after the 122 silent-no-op bug. Custom-columns is listed as a separate papercut of similar weight.
- Experiment FO external feedback (2026-04-10): lists "prose where there should be structure" as the meta-theme; the status tool is one of the few places where it's already structured, so this task stays within the structured zone.
