---
id: 064
title: Replace lieutenant agents with capability modules
status: ideation
source: CL
started: 2026-03-27T23:10:00Z
completed:
verdict:
score: 0.90
worktree:
issue:
pr:
---

Lieutenants were designed as specialized stage agents that also provide lifecycle hooks to the first officer. In practice, the pr-lieutenant is awkward as a stage agent — PR creation is a lifecycle transition, not stage work. The hook-providing role is valuable but doesn't require an agent.

## Problem

Capabilities like PR-based merge cross-cut stages (startup: detect merged PRs, merge: check PR state). Modeling them as stage agents forces them into a single stage, which doesn't fit. The pr-lieutenant exists as an agent that's never dispatched — it's really just a config file in `.claude/agents/`.

Meanwhile, some workflows (e.g., email triage) don't need PR logic at all and use git as a local store only. The capability needs to be modular — enable/disable per workflow.

## Proposed model

Capability modules live in `{workflow_dir}/_capabilities/`. Each is a markdown file with `## Hook:` sections, same format as the current lieutenant hooks. The FO discovers them at startup by scanning the directory.

**Plugin ships canonical capability templates:**
```
capabilities/
  pr-merge.md
```

**Commission copies selected capabilities into the workflow:**
```
docs/plans/
  _capabilities/
    pr-merge.md
```

**Refit** diffs each `_capabilities/*.md` against the plugin's canonical version. Same merge strategy as agent/template files — detect upstream changes, preserve local customizations, flag conflicts.

**FO discovery** changes from "scan agent files referenced by stages" to "scan `_capabilities/*.md`". Everything else stays the same — hook format, lifecycle points (startup, merge), execution model.

## What changes

- `capabilities/pr-merge.md` — new canonical capability template (content from current `templates/pr-lieutenant.md` hooks)
- `templates/pr-lieutenant.md` — removed (replaced by capability module)
- First-officer template — hook discovery scans `_capabilities/` instead of agent files referenced by stages
- Commission skill — offers capabilities during setup, copies selected ones to `_capabilities/`
- Refit skill — manages `_capabilities/` files same as agent files (diff, merge, update)
- FO merge flow — after validation gate approval, FO pushes branch and creates PR (not a stage agent's job)

## What this subsumes

- The pr-lieutenant agent (both template and generated file)
- The `agent:` property on stages (for hook-providing agents — stage-specific worker agents like a hypothetical `data-scientist` ensign variant would still use `agent:`)
- The lieutenant hook discovery mechanism from #060 (replaced by capability discovery)

## Capability file format

Each capability is a markdown file in `{workflow_dir}/_capabilities/`. The plugin ships canonical versions in `capabilities/` at the plugin root.

**Frontmatter:**

```yaml
---
name: pr-merge
description: Push branches and create/track GitHub PRs for workflow entities
version: 0.7.0
---
```

- `name` — identifier, matches the filename (without `.md`). Used by refit to match local files against canonical templates.
- `description` — one-line summary. Displayed during commission's capability selection prompt.
- `version` — the Spacedock version that last changed this capability's content. Refit uses this to detect whether the canonical version has changed since the local copy was made (or last updated). This is the capability content version, not the plugin version — it only bumps when the capability's hook logic actually changes.

**Body: Hook sections**

The body contains `## Hook: {lifecycle_point}` sections, identical in format to the current lieutenant hooks from #060. Each section's prose is instructions the FO reads and follows at that lifecycle point.

```markdown
## Hook: startup

{prose instructions — e.g., scan entities for `pr` field, check PR state via `gh`}

## Hook: merge

{prose instructions — e.g., claim entities with `pr` field, check PR state before merge}
```

No other structural requirements. A capability may include additional markdown sections (e.g., `## Notes`, `## Configuration`) for documentation, but only `## Hook:` sections are functional.

**Why this format works:** It reuses the exact hook format from #060, so the FO's hook execution logic doesn't change — only the discovery source changes. The frontmatter adds just enough metadata for commission (description for selection) and refit (version for diff decisions) without overcomplicating the format.

## Commission UX for capability selection

During Phase 1 (Interactive Design), after Question 3 (Seed Entities) and before Confirm Design, commission adds a new step:

### Question 4 — Capabilities

Commission scans the plugin's `capabilities/` directory for available capability files. For each, it reads the frontmatter `name` and `description`.

Present to the captain:

> **Available capabilities:**
>
> 1. **pr-merge** — Push branches and create/track GitHub PRs for workflow entities
>
> Which capabilities should this workflow include? (Enter numbers, "all", or "none")

Store the selection as `{capabilities}` — a list of capability names. Default: suggest `pr-merge` as selected (since most workflows will want it), but respect the captain's choice.

**Batch mode:** If the user provides capabilities in their batch input, use those. If not mentioned, default to all available capabilities. If the user says "no capabilities" or "none", skip.

**Confirm Design** includes the selected capabilities:

> - **Capabilities:** pr-merge (or "none")

**Phase 2 generation (new step 2g):** For each selected capability, copy the canonical file from `{spacedock_plugin_dir}/capabilities/{name}.md` to `{dir}/_capabilities/{name}.md`. No sed substitution needed — capability files are fully static (they reference "the workflow directory" generically; the FO passes context when executing hooks). Create the `_capabilities/` directory only if at least one capability is selected.

**Generation checklist** adds:
- [ ] `{dir}/_capabilities/{name}.md` exists for each selected capability

**Phase 2f (pr-lieutenant generation) is removed.** The pr-lieutenant template and agent file go away entirely. Any stage that previously referenced `agent: pr-lieutenant` drops that property — all stages use the default ensign.

## Refit merge strategy for capabilities

Refit Phase 2 (Classify Files) adds a row for each capability file found in `{dir}/_capabilities/`:

| File | Strategy | Rationale |
|------|----------|-----------|
| `_capabilities/{name}.md` | **Regenerate** | Compare canonical version against local. Show diff, ask captain for confirmation. |

**Discovery:** Refit scans `{dir}/_capabilities/*.md` and matches each against `{spacedock_plugin_dir}/capabilities/{name}.md` by filename.

**Version comparison:** Read the local file's `version` frontmatter field and the canonical file's `version` field. If they match, the capability is up to date — skip it (report "up to date"). If they differ, show a diff and ask the captain whether to update.

**Local customizations:** Users may edit capability files (e.g., adjust PR body template, add a condition). Refit shows a three-way comparison when the canonical version has changed and the local file has diverged from its original:

1. If local matches the old canonical (no user edits): auto-update (with confirmation).
2. If local differs from old canonical (user edits): show the canonical diff and the local customizations, flag as conflict. Let the captain decide.

In practice for v0, this simplifies to: diff canonical vs local, show the diff, ask the captain. The three-way merge is a future enhancement if capability customization becomes common.

**New capabilities:** If the canonical `capabilities/` directory has files not present in `{dir}/_capabilities/`, refit offers to add them:

> New capability available: **{name}** — {description}. Add it? (y/n)

**Removed capabilities:** If `{dir}/_capabilities/` has files not in the canonical directory, refit warns but does not remove (the user may have created custom capabilities):

> **{name}** is not in the current Spacedock capability catalog. It may be a custom capability or was removed upstream. No action taken.

## FO hook discovery — updated for `_capabilities/` source

The FO's startup step 3 changes from scanning `agent:` properties in README stages to scanning the `_capabilities/` directory:

**Current (from #060):**

> 3. **Discover lieutenant hooks** — Scan the `stages.states` block in the README frontmatter for distinct `agent:` values (excluding `ensign`). For each lieutenant agent name, read `{project_root}/.claude/agents/{agent}.md` and scan for `## Hook:` sections.

**Proposed:**

> 3. **Discover capability hooks** — Scan `{workflow_dir}/_capabilities/*.md`. For each capability file, read it and scan for `## Hook:` sections. Register each hook by lifecycle point (`startup`, `merge`) along with the capability name and the section's body text as the hook instructions. If the `_capabilities/` directory doesn't exist or is empty, proceed with no hooks. Multiple capabilities can hook the same lifecycle point — execute them in alphabetical order by capability filename.

Everything else stays the same:
- Step 4 (Run startup hooks) — unchanged, just iterates over discovered hooks
- Merge step 1 (Run merge hooks) — unchanged, checks if any hook claims the entity
- Hook execution model — read prose instructions and follow them
- Fallback — no hooks means default behavior (no startup actions, local merge)

**Ordering:** Lieutenant hooks used "order they appear in the stages list." Capabilities use alphabetical order by filename. This is deterministic and doesn't depend on stage ordering (which capabilities aren't tied to).

**What happens to the `agent:` stage property?** The `agent:` property no longer serves a hook-discovery role. It remains available for specifying non-default worker agents for a stage (e.g., a hypothetical `data-scientist` ensign variant that has special tools or instructions). But no Spacedock-shipped agent uses it — the pr-lieutenant goes away, and capabilities replace its hook role. If no stage has `agent:`, the FO skips the old discovery entirely. The FO template should remove the lieutenant hook discovery logic and replace it with capability discovery.

## FO merge flow — PR creation after validation gate approval

The pr-lieutenant currently handles PR creation as stage work (push branch, create PR, report PR number). With capabilities, PR creation moves to the FO's merge flow. The capability's merge hook handles the PR interaction, but the FO orchestrates the overall merge lifecycle.

**Merge flow with pr-merge capability enabled:**

When an entity reaches its terminal stage (after validation gate approval):

1. **Run merge hooks** — The pr-merge capability's merge hook fires. Its instructions:
   - Check if the entity already has a `pr` field set:
     - If yes (PR already exists): check PR state via `gh pr view`. If MERGED, skip push/create. If OPEN, report to captain and wait.
     - If no (no existing PR): push the worktree branch (`git push origin {branch}`), create PR via `gh pr create`, set the `pr` field on the entity. Report PR number to captain.
   - After PR creation: wait for captain to confirm PR is merged (or merge it via `gh pr merge` if captain instructs).
2. **Archive** — Once the PR is merged (detected via `gh pr view` or captain confirmation): update frontmatter (`status`, `completed`, `verdict`), archive the entity file, clean up worktree/branch.

**Merge flow without pr-merge capability (local merge):**

When an entity reaches its terminal stage:
1. No merge hooks fire (no `_capabilities/` or no pr-merge capability).
2. Default local merge: read worktree field, derive branch, `git merge --no-commit`, resolve or report conflicts.
3. Update frontmatter, archive, clean up.

**Key difference from the pr-lieutenant model:** The pr-lieutenant was dispatched as a stage agent — it did implementation work AND pushed/created PRs. With capabilities, the ensign does all stage work (implementation, validation). The PR push/create happens at merge time as a lifecycle transition handled by the FO following the capability's hook instructions. This is a cleaner separation: stage work is stage work, PR creation is a merge-time operation.

**Updated pr-merge capability hook content:**

The `## Hook: merge` section in `capabilities/pr-merge.md` needs to handle both the "PR already exists" case (entity was previously advanced to a PR stage) and the "create new PR" case:

```markdown
## Hook: merge

This hook claims entities that were processed in a worktree stage (non-empty `worktree` field or worktree-derived branch exists).

Push the worktree branch: `git push origin {branch}`. If the push fails (no remote, auth error), report to the captain and fall back to local merge.

Create a PR: `gh pr create --base main --head {branch} --title "{entity title}" --body "Workflow entity: {entity title}"`. If `gh` is not available, warn the captain and fall back to local merge.

Set the entity's `pr` field to the PR number (e.g., `#57`). Report the PR to the captain.

Do NOT archive yet. The entity stays in its terminal stage with `pr` set until the PR is merged. The startup hook will detect the merge on next FO startup.
```

The `## Hook: startup` section remains largely the same as the current pr-lieutenant's startup hook — scan for entities with `pr` field, check if merged, auto-advance.

## Migration path from pr-lieutenant to capability module

### For the Spacedock plugin itself

1. Create `capabilities/pr-merge.md` with the hook content from `templates/pr-lieutenant.md` (startup and merge hooks), adapted for the new merge flow (FO creates PR at merge time, not a stage agent at implementation time).
2. Remove `templates/pr-lieutenant.md`.
3. Update `templates/first-officer.md` — replace lieutenant hook discovery with capability discovery.
4. Update `skills/commission/SKILL.md`:
   - Add Question 4 (Capabilities) to Phase 1
   - Add step 2g (copy capabilities) to Phase 2
   - Remove step 2f (pr-lieutenant generation)
   - Update generation checklist
5. Update `skills/refit/SKILL.md`:
   - Add capability file management to Phase 2 and Phase 3
   - Remove lieutenant agent regeneration (step 3e) for pr-lieutenant specifically
   - Add capability version comparison logic

### For existing workflows using pr-lieutenant

Refit handles migration:

1. **Detect legacy state** — If `{project_root}/.claude/agents/pr-lieutenant.md` exists and `{dir}/_capabilities/pr-merge.md` does not, the workflow is using the old model.
2. **Offer migration** — Present to captain:

> **Migration: pr-lieutenant → pr-merge capability**
>
> Your workflow currently uses a pr-lieutenant agent for PR management. Spacedock now uses capability modules instead. I'll:
> 1. Create `{dir}/_capabilities/pr-merge.md` with the PR management capability
> 2. Remove `agent: pr-lieutenant` from any README stage entries
> 3. Regenerate the first-officer with capability discovery
>
> The pr-lieutenant agent file at `.claude/agents/pr-lieutenant.md` will be left in place (in case other workflows use it). You can delete it manually if no longer needed.
>
> Proceed? (y/n)

3. **Execute migration** — Copy `capabilities/pr-merge.md` to `{dir}/_capabilities/pr-merge.md`, update README frontmatter to remove `agent: pr-lieutenant` from stages, regenerate FO.

### For workflows without pr-lieutenant

No migration needed. Workflows that never used a lieutenant have no hooks, no `_capabilities/` directory, and the FO's capability discovery finds nothing — behavior is identical.

## Acceptance criteria (updated)

1. `capabilities/pr-merge.md` exists in the plugin root with frontmatter (`name`, `description`, `version`) and `## Hook: startup` and `## Hook: merge` sections
2. `templates/pr-lieutenant.md` is removed
3. FO template startup step 3 discovers hooks by scanning `{workflow_dir}/_capabilities/*.md` (not agent files)
4. FO template merge flow follows capability merge hook to push branch, create PR, and track PR state
5. Commission Phase 1 includes a capability selection step; Phase 2 copies selected capabilities to `{dir}/_capabilities/`
6. Commission no longer generates pr-lieutenant agent files (step 2f removed)
7. Refit detects capability files, diffs against canonical versions, and offers updates
8. Refit offers migration from pr-lieutenant to pr-merge capability for legacy workflows
9. Workflows without `_capabilities/` behave identically to today (no hooks, local merge)
10. Capability hook execution order is alphabetical by filename (deterministic, stage-independent)

## Stage Report: ideation

- [x] Capability file format specified — frontmatter, hook sections, metadata
  Frontmatter with `name`, `description`, `version` fields. Body uses `## Hook: {point}` sections identical to #060 format. Version field tracks capability content changes for refit diffing.
- [x] Commission UX for capability selection designed
  New Question 4 after seed entities. Scans plugin `capabilities/` dir, presents list with descriptions, captain picks by number/all/none. Batch mode defaults to all. Step 2g copies selected files to `_capabilities/`. Step 2f (pr-lieutenant generation) removed.
- [x] Refit merge strategy for capabilities specified
  Matches local `_capabilities/*.md` against canonical `capabilities/*.md` by filename. Compares `version` frontmatter to detect changes. Shows diff, asks captain. Offers new capabilities found in catalog. Warns about local-only files without removing them.
- [x] FO hook discovery and execution updated for `_capabilities/` source
  Startup step 3 scans `{workflow_dir}/_capabilities/*.md` instead of agent files from README stages. Alphabetical execution order by filename replaces stage-list order. Hook format, lifecycle points, and execution model unchanged from #060.
- [x] FO merge flow specified — PR creation after validation gate approval
  Merge hook pushes worktree branch, creates PR via `gh`, sets `pr` field, reports to captain. Does NOT archive until PR is merged. Startup hook detects merged PRs on next FO startup. Without pr-merge capability, falls back to default local merge.
- [x] Migration path from pr-lieutenant to capability module documented
  Refit detects legacy state (pr-lieutenant agent exists, no _capabilities/pr-merge.md). Offers migration: copy capability, remove `agent:` from README stages, regenerate FO. Leaves pr-lieutenant agent file in place for manual cleanup. Workflows without pr-lieutenant need no migration.
- [x] Acceptance criteria updated and testable
  10 criteria covering capability file format, template removal, FO discovery, commission UX, refit management, migration, and backward compatibility.

### Summary

Fleshed out the capability modules design across all seven design questions. The core model is: capability files live in `{workflow_dir}/_capabilities/` with YAML frontmatter (name, description, version) and `## Hook:` body sections, reusing the exact hook format from #060. The FO discovers hooks by scanning `_capabilities/*.md` instead of agent files referenced by stages. Commission adds a capability selection step and copies canonical files from the plugin's `capabilities/` directory. Refit manages capabilities like other scaffolding files, with version-based diffing and migration support for legacy pr-lieutenant workflows. The PR creation responsibility moves from a stage agent to the FO's merge flow via the pr-merge capability's merge hook, cleanly separating stage work from lifecycle transitions.
