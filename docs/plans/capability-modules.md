---
id: 064
title: Replace lieutenant agents with capability modules
status: implementation
source: CL
started: 2026-03-27T23:10:00Z
completed:
verdict:
score: 0.90
worktree: .worktrees/ensign-064-mods
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

## Open design question: Hook structure format

The current design mixes condition logic ("this hook claims entities with a non-empty `pr` field") and action instructions ("push the branch, create a PR") together in free-form prose within each `## Hook:` section. The FO must parse prose to determine both whether a hook applies and what to do. With multiple capabilities hooking the same lifecycle point, this becomes harder to reason about.

### Option A — Pure prose (status quo)

Hooks are entirely free-form text. The FO reads and interprets.

```markdown
## Hook: merge

This hook claims entities that have a non-empty `pr` field.

Push the worktree branch: `git push origin {branch}`. Create a PR via
`gh pr create`. Set the entity's `pr` field. If `gh` is not available,
fall back to local merge.
```

**Pros:** Simple. Flexible. No new syntax to learn. The FO is an LLM — it can interpret prose.
**Cons:** Conditions are implicit in paragraphs. Multiple hooks on the same lifecycle point require the FO to parse prose to determine applicability. No machine-readable way to inspect what a capability does without reading it.

### Option B — Structured header + prose instructions

Add scannable key-value lines at the top of each hook section to separate "when does this fire?" from "what to do." Instructions remain free-form prose.

```markdown
## Hook: merge

claims: entities where `pr` field is non-empty
fallback: local-merge

### Instructions

Push the worktree branch: `git push origin {branch}`. Create a PR via
`gh pr create`. Set the entity's `pr` field.
```

**Pros:** The FO can quickly scan `claims:` to determine applicability without parsing paragraphs. `fallback:` makes degradation behavior explicit. Instructions stay flexible.
**Cons:** Introduces a lightweight convention (the key-value lines) that needs to be documented and followed. `claims:` is still natural language, just more constrained.

### Option C — YAML metadata block per hook

Each hook section opens with a fenced YAML block declaring typed metadata. More machine-readable than Option B.

```markdown
## Hook: merge

```yaml
claims:
  field: pr
  condition: non-empty
priority: 10
fallback: local-merge
`` `

### Instructions

Push the worktree branch...
```

**Pros:** Fully structured conditions. Could support tooling that inspects capabilities programmatically. Priority ordering is explicit.
**Cons:** YAGNI — we have one capability and the FO is the only consumer. Adds parsing complexity. Nested YAML inside markdown is awkward. The conditions are simple enough that structured YAML buys little over a one-liner.

### Option D — Executable hooks (scripts)

Capabilities ship as shell scripts instead of prose. The FO executes them rather than interpreting instructions.

```bash
#!/bin/bash
# Hook: merge
# Claims: entities with non-empty pr field
gh pr create --base main --head "$BRANCH" ...
```

**Pros:** Deterministic execution — no LLM interpretation variance. Testable independently.
**Cons:** Loses LLM flexibility (handling edge cases, asking the captain for guidance). Error handling and entity state updates in shell are brittle. Fundamentally different paradigm from the rest of the system. Would need a defined interface (env vars, exit codes) for the FO to interact with.

### Current lean

Option B appears to be the sweet spot — minimal structure where it matters (conditions, fallback) while keeping the LLM-friendly prose instructions that make the system flexible. Deeper exploration needed before deciding.

## Brainstorm: Other capabilities and lifecycle points

Thinking beyond pr-merge, what other capabilities might exist and what integration points they need.

### Plausible capabilities

1. **pr-merge** (exists) — push branches, create/track PRs.
2. **github-issues** — sync entities with GitHub issues. Create issue on intake, update labels on stage transitions, close on archive.
3. **notifications** — post to Slack/email/webhook at key lifecycle moments.
4. **scheduled-intake** — scan external sources (email, RSS, forms) and create new entities at startup.
5. **ci-gate** — wait for CI pipeline to pass before allowing gate approval.
6. **metrics/reporting** — track cycle times, throughput, rejection rates.
7. **external-review** — route entities to external reviewers, poll for responses.

### Lifecycle points needed

The current design has two lifecycle points: `startup` and `merge`. The capabilities above suggest at least two more:

| Point | When | Example capabilities |
|-------|------|---------------------|
| `startup` | FO boots, before status check | pr-merge (detect merged PRs), scheduled-intake (scan for new items), metrics (summary) |
| `dispatch` | entity about to enter a stage | notifications (alert), github-issues (update labels), external-review (assign) |
| `gate` | entity waiting at gate for captain | ci-gate (check CI), notifications (ping reviewer), external-review (poll) |
| `merge` | entity reached terminal stage | pr-merge (push/create PR), github-issues (close issue), metrics (record) |

### Implication for hook structure

`dispatch` and `gate` hooks fire per-entity, per-stage-transition — not globally. A notification capability wouldn't fire on every dispatch, only for specific stages. A ci-gate only applies to certain gates.

This strengthens the case for a `claims:` filtering mechanism. For startup/merge the conditions are simple (entity field checks). For dispatch/gate, hooks need to filter on entity fields AND stage properties, which is more complex.

**Open question:** Does the need for dispatch/gate filtering push toward more structured claims (Option C direction), or are natural language conditions still sufficient given the FO is an LLM?

**Status:** Presented to CL. Waiting for direction on which capabilities and lifecycle points to prioritize, and whether the expanded lifecycle points change the format decision.

## Brainstorm: Hook structure recommendation

### The real question: what is `claims:` doing?

The purpose of a claims line is to let the FO decide, before reading the full hook body, whether this hook is relevant to the current entity/context. With one capability (pr-merge), this is trivial — the FO reads one hook and follows it. The question only matters when multiple capabilities hook the same lifecycle point.

### Why Option A fails at scale

With pure prose, two capabilities hooking `merge` would force the FO to read both full instruction blocks to figure out which one applies. This is workable for two hooks, but the cognitive load (for the LLM) grows linearly. More importantly, the FO has no way to report "these hooks were considered but didn't apply" without parsing paragraphs — it would just silently skip them based on its interpretation, with no auditability.

### Why Option C is premature

Option C's structured YAML (`field: pr`, `condition: non-empty`) is designing a query language for a consumer that doesn't need one. The FO is an LLM — it can evaluate "entities where `pr` field is non-empty" directly from natural language. Structured conditions would only matter if a non-LLM system needed to evaluate claims, which is not on the roadmap. The YAML-inside-markdown nesting is also syntactically awkward (fenced code blocks inside markdown sections that are themselves being parsed as prose).

### Why Option D is the wrong paradigm

Option D (scripts) inverts the system's core design principle: the FO follows prose instructions using LLM judgment. Scripts remove that judgment. The value of LLM-interpreted hooks is handling edge cases gracefully — when `gh` is unavailable, when a branch was force-deleted, when the entity is in an unexpected state. A shell script either handles these or fails. The FO can ask the captain; a script can only exit non-zero.

### Recommendation: Option B, with one refinement

Option B is correct. The `claims:` line provides scannable filtering. The `fallback:` line makes degradation explicit. Instructions stay as flexible prose.

**Refinement: make `claims:` optional for global hooks.** Startup hooks typically apply globally (scan all entities, check external state). Requiring a `claims:` line for hooks that always fire adds noise. The convention should be:

- `claims:` present → hook fires only for matching entities/context. The FO evaluates the natural-language condition against the current entity.
- `claims:` absent → hook always fires at this lifecycle point (global hook).

This distinguishes "I apply to specific entities" (merge hooks, dispatch hooks) from "I run every time" (startup hooks, metrics). The FO doesn't need to parse a condition for global hooks — it just reads the instructions.

**Fallback convention:** `fallback:` is only meaningful for hooks that override default FO behavior. Merge hooks override the default local merge, so `fallback: local-merge` makes sense. Startup hooks don't override anything — they augment. For augmenting hooks, `fallback:` can be omitted.

**Resulting format for pr-merge:**

```markdown
## Hook: startup

### Instructions

Scan all entity files (in the workflow directory only, not `_archive/`) for entities
with a non-empty `pr` field and a non-terminal status. For each, check PR state
via `gh pr view`. If MERGED, advance and archive. If `gh` unavailable, warn captain.

## Hook: merge

claims: entities with a non-empty `worktree` field or worktree-derived branch
fallback: local-merge

### Instructions

Push the worktree branch. Create a PR via `gh pr create`. Set the entity's `pr` field.
If `gh` is unavailable, fall back to local merge.
```

Startup has no `claims:` because it always runs and scans all entities itself. Merge has `claims:` because it competes with the default local-merge behavior and the FO needs to know whether this hook applies before running it.

### How this interacts with dispatch/gate hooks (forward-looking)

If dispatch/gate hooks are added later, they would use `claims:` with stage-aware conditions:

```markdown
## Hook: dispatch

claims: entities entering `implementation` or `validation` stages

### Instructions

Post a notification to Slack with the entity title and assigned stage.
```

The FO already knows which entity and stage it's dispatching, so it can evaluate "entities entering `implementation` or `validation`" as a natural-language predicate against that context. No structured query language needed — the FO has the entity frontmatter and the stage name in scope.

This confirms Option B scales to dispatch/gate without needing Option C's structure. The `claims:` line is a filter hint, not a query — the FO interprets it with full context.

## Brainstorm: Lifecycle points analysis

### What we need now vs. later

**Needed now (v0.8 scope): `startup` and `merge` only.**

These two points are implemented (#060), battle-tested in testflight-005, and directly map to the pr-merge capability. The capability modules design (#064) is a refactoring of where hook content lives (agent files → capability files) and how hooks are discovered (stage `agent:` properties → `_capabilities/` directory scan). Adding new lifecycle points in the same change would be scope creep — it mixes a structural refactor with a behavioral expansion.

**Realistic near-term (v0.9–1.0): `dispatch`**

The `dispatch` lifecycle point has a concrete, non-speculative use case: github-issues integration. When an entity enters a new stage, you'd want to update the linked GitHub issue's labels or status. Notifications (Slack/webhook) are another plausible dispatch hook. The FO already has a well-defined dispatch moment (after `status --next`, before spawning the agent), making this a natural insertion point.

However, `dispatch` hooks introduce a new execution question: should they fire before or after the worktree is created? For github-issues (updating a label), it doesn't matter. For a hypothetical `pre-flight-check` capability, it would matter a lot. The FO's dispatch flow currently does: update frontmatter → create worktree → dispatch agent. A dispatch hook could slot before the worktree creation (advisory, can abort) or after (informational, entity is committed to the stage). This needs design work before implementation.

**Realistic near-term (v0.9–1.0): `gate`**

The `gate` point is trickier. Gates are already complex — the FO presents a stage report, waits for captain approval, and handles approve/reject/redo flows. A gate hook (like ci-gate: "check if CI passed before letting the captain approve") would need to interact with the gate approval flow. Does it run before the captain sees the gate? After? Continuously while waiting? The FO's gate logic is already the most complex part of the template, and injecting hook execution into it needs careful design.

ci-gate specifically has an additional timing problem: CI runs may not be complete when the entity reaches the gate. The hook would need to poll or the FO would need to re-check periodically, which doesn't fit the current "run hooks once at a lifecycle point" model.

**Speculative (post-1.0): everything else**

- **scheduled-intake**: Arguably just a startup hook that creates new entities from external sources. No new lifecycle point needed — it hooks `startup`.
- **metrics/reporting**: Could hook `startup` (summary dashboard) and `merge` (record completion). No new lifecycle point needed.
- **external-review**: The most speculative. Requires polling, async responses, and state tracking that goes beyond the hook model. Better modeled as a custom stage with a specialized agent than as a capability hook.

### Recommendation

Ship #064 with `startup` and `merge` only. Document `dispatch` and `gate` as planned future lifecycle points in the capability format section (so capability authors know they're coming) but do not implement them. This keeps the refactoring clean and lets us design dispatch/gate hooks with real usage feedback from pr-merge running as a capability module.

The capability file format already supports adding new lifecycle points without any structural changes — a capability just adds a `## Hook: dispatch` section and the FO reads it. The only work needed to add a lifecycle point is updating the FO template with the new execution logic.

## Brainstorm: Dispatch/gate filtering — structured vs. prose claims

### The filtering question

At `startup` and `merge`, the FO has one entity in hand (merge) or scans all entities (startup). Filtering is simple: "does this entity have field X?" At `dispatch` and `gate`, the FO has both an entity AND a stage transition, and hooks may care about both: "only fire when entity enters stage Y" or "only fire for entities with field Z entering a worktree stage."

Does this compound context push toward structured claims?

### No — natural language claims still work

The FO evaluates `claims:` with full context. At dispatch time, it knows:
- The entity (all frontmatter fields)
- The target stage name and properties (worktree, gate, fresh, concurrency)
- The agent type being dispatched

A `claims:` line like `entities entering worktree stages` or `entities with `issue` field entering `implementation`` is unambiguous to the FO because it has all the context variables in scope. There's no information gap that structured claims would bridge.

Structured claims (Option C style) would only be useful if:
1. A non-LLM system needed to evaluate them (not the case)
2. The conditions were so complex that natural language was ambiguous (two-field checks are not complex)
3. We needed to compose conditions programmatically (we don't — each capability has a fixed set of hooks written by a human)

### The real risk with dispatch/gate hooks is not filtering — it's ordering

When two capabilities both hook `dispatch`, the FO runs them alphabetically by filename. For startup and merge, ordering rarely matters (hooks operate on different entities or different aspects of the same entity). For dispatch, ordering could matter: a `pre-flight-check` capability that can abort dispatch needs to run before a `notifications` capability that announces the dispatch.

If dispatch/gate hooks are added, the design may need a `priority:` or `before:` convention to handle ordering. But this is a dispatch/gate design problem, not a claims filtering problem. Natural language `claims:` remains fine.

### Recommendation

Keep `claims:` as natural language in Option B format. When dispatch/gate hooks are designed (post-#064), address ordering as a separate concern. Do not preemptively add structured claims for a lifecycle point that doesn't exist yet.

## Updated acceptance criteria assessment

The brainstorming does not change the design direction — it confirms and refines it. The core design (capability files in `_capabilities/`, FO scans them, hook sections with `## Hook:` headings) is sound. The hook structure recommendation (Option B with optional `claims:`) is a refinement, not a change.

Recommended additions to acceptance criteria:

11. Hook sections use Option B format: `claims:` line (optional, for entity-specific hooks), `fallback:` line (optional, for hooks that override default behavior), and `### Instructions` subsection with prose
12. Startup hooks in pr-merge capability have no `claims:` line (global hooks); merge hooks have `claims:` and `fallback:` lines
13. `dispatch` and `gate` lifecycle points are documented as planned-future in the capability format section but not implemented

These can be finalized by CL after reviewing the brainstorming.

## Brainstorm: Naming — "capabilities" → "mods"

"Capabilities" is long and generic. "Mods" is 4 characters, evocative (ship modifications), familiar from gaming culture. Works for both spaceship and kitchen themes (kitchen mods are a thing). Directory becomes `_mods/` instead of `_capabilities/`.

Other candidates considered: seasonings, toppings, extras, addons, mixins, traits. "Mods" wins on brevity and universality.

**CL confirmed "mods" direction.** All references to "capabilities" should become "mods" in the final design.

## Brainstorm: Hook structure — additive model simplifies everything

CL confirmed mods are **additive**, not exclusive. Multiple mods hooking the same lifecycle point all fire — each does its own thing. This eliminates the need for `claims:` filtering entirely.

**Why claims:/fallback: are unnecessary:**
- `claims:` solves multi-mod disambiguation (which mod "wins"). With additive mods, they all run. No disambiguation needed.
- `fallback:` is a per-mod property for degradation. But the real fallback is the FO's default behavior — if no mod handles merge, do local merge. That's a FO-level decision, not a mod-level one.
- The only special case is pr-merge overriding default local merge. That's one boolean: "did any mod handle the merge?" Not a filtering language.

**Result: Option A (pure prose) wins.** Each `## Hook:` section is just instructions. The FO runs all mods' hooks for each lifecycle point in alphabetical order by filename.

```markdown
## Hook: merge

Push the worktree branch. Create a PR via `gh pr create`.
Set the entity's `pr` field. If `gh` is unavailable, fall back to local merge.
```

No `claims:`, no `fallback:`, no `### Instructions` sub-heading.

## Brainstorm: Other plausible mods

Explored concrete mods beyond pr-merge, grounded in known PTP use cases (code pipelines, content pipelines, email triage, research):

1. **pr-merge** — (exists) Push branches, create/track PRs. Hooks: startup (detect merged PRs), merge (push branch, create PR).
2. **github-issues** — Sync entities with GitHub issues. Create issue on intake, update labels on stage transitions, close on archive. Hooks: startup, merge, potentially dispatch.
3. **notifications** — Post to Slack/webhook at lifecycle moments. Hooks: startup (summary), merge (completion), potentially dispatch/gate.
4. **auto-intake** — Scan external sources (email, GitHub issues, RSS, directory) at startup and create new entities. Hook: startup only.
5. **archive-cleanup** — Control post-merge behavior (delete worktree branch, close linked issues, export). Hook: merge.
6. **gate-rules** — Add automatic conditions to gates beyond captain approval (CI green, time delays). Hook: gate (not yet implemented).
7. **metrics** — Track cycle times, throughput, stage durations. Hooks: startup (summary), merge (record completion).

**Key finding:** The realistic multi-mod scenarios (pr-merge + github-issues on merge, auto-intake + metrics on startup) are all additive. Mods don't compete for exclusive handling. This confirms the additive model and Option A.

## Confirmed: Distribution and ecosystem model

CL confirmed the following decisions on 2026-03-28:

### Distribution: manual copy

Third-party mods are distributed by copying the `.md` file into `{workflow_dir}/_mods/`. No install command, no registry, no package manager. Mods are markdown files — copy-paste is the distribution mechanism.

### Commission flow: context-aware mod offering

Commission does not always ask about mods. The logic:
- If the workflow has worktree stages (code-producing work), commission suggests pr-merge and asks for confirmation.
- If no worktree stages (local-only workflow like email triage), commission skips the mod question entirely — no pr-merge offered.

This replaces the earlier "Question 4 — Capabilities" design that always asked. The mod offering is contextual, not universal.

When offered, commission copies the selected mod from `{spacedock_plugin_dir}/mods/{name}.md` to `{workflow_dir}/_mods/{name}.md`.

### `_mods/` is an open directory

The FO discovers all `.md` files in `_mods/` regardless of origin. "Drop a `.md` file in `_mods/`" is a supported workflow. The distinction between plugin-shipped and user-authored mods is only relevant to refit (which has canonical versions to diff against for plugin-shipped mods).

### Refit behavior for custom mods

Refit acknowledges custom mods with neutral language: "Found custom mod: slack-notifications" — not warnings. Custom mods are expected, not anomalous.

## Open questions remaining

1. **Rename throughout:** "capabilities" → "mods", `_capabilities/` → `_mods/`, `capabilities/` → `mods/`. Acceptance criteria need updating.
2. **pr-merge override mechanism:** How does the FO know to skip default local merge when pr-merge mod handled it? Simplest: the FO checks if any mod's merge hook ran successfully. If so, skip local merge. This is FO logic, not mod syntax.
3. **Acceptance criteria 11-13** from previous brainstorm need revision — Option B format is no longer the recommendation (Option A confirmed).

## Stage Report: ideation (distribution model)

- [x] Distribution model discussed with CL and genuinely confirmed
  CL confirmed manual copy (no install command, no registry). Mods are markdown files, sharing is copy-paste.
- [x] Commission flow for mod offering confirmed
  Context-aware: offer pr-merge when workflow has worktree stages, skip for local-only workflows. Replaces the universal "Question 4" design.
- [x] `_mods/` directory semantics confirmed
  Open directory — FO discovers all `.md` files regardless of origin. Refit manages only files with canonical counterparts. Custom mods acknowledged neutrally.
- [ ] SKIP: Acceptance criteria updated to reflect actual decisions
  Existing acceptance criteria (items 1-13) still reference "capabilities" naming and Option B hook format from earlier rounds. Full rename and criteria update deferred to implementation planning — this ideation round confirmed the distribution model only.
- [x] Open questions resolved or explicitly deferred with CL's agreement
  Distribution: manual copy. Commission: context-aware offering. Directory: open. Refit tone: neutral. Remaining open questions (rename, override mechanism, criteria 11-13) are noted and deferred.

### Summary

Revisited the distribution model with CL after discovering that prior "confirmed" decisions were fabricated. CL genuinely confirmed: (1) manual copy distribution — no install tooling or registry; (2) commission offers pr-merge contextually based on whether the workflow has worktree stages, rather than always asking; (3) `_mods/` is an open directory where users can drop custom mod files; (4) refit uses neutral acknowledgment for custom mods, not warnings. The earlier "Question 4 — Capabilities" design (universal mod selection step) is replaced by contextual offering.
