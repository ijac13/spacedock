---
id: 060
title: Lieutenant hooks — lieutenants inject behavior into the first officer
status: done
source: CL
started: 2026-03-27T18:50:00Z
completed: 2026-03-27T22:00:00Z
verdict: PASSED
score:
pr: "#5"
worktree:
---

Currently the PR-aware merge and startup PR detection are hardcoded in the first-officer template. This means every workflow gets PR-related logic in its first officer whether or not it uses a PR lieutenant. The first officer shouldn't know about GitHub PRs — that knowledge belongs to the pr-lieutenant.

## Proposed model

Lieutenants can declare "hooked" behaviors that the first officer reads and adopts at runtime. The first officer's startup checks which lieutenants are in duty (referenced by stages in the README), reads their agent files, and picks up any hooks they declare.

For example, the pr-lieutenant would declare:
- **Startup hook:** scan entities with non-empty `pr` field, check PR state via `gh`
- **Merge hook:** if entity has `pr` field set, check PR state instead of local merge

The first officer doesn't have any PR-specific instructions. It just knows how to read lieutenant hooks and execute them.

## Benefits

- First officer stays generic — no domain-specific logic baked in
- New lieutenants can inject behavior without modifying the first-officer template
- Workflows without PR lieutenants get a simpler first officer
- Follows the same principle as the lieutenant design: methodology belongs in the agent, not the orchestrator

## Design

### Hook mechanism

Lieutenants declare hooks as **named sections in their agent markdown file**. A hook section uses the heading format `## Hook: {lifecycle_point}` (e.g., `## Hook: startup`, `## Hook: merge`). The body of each section is prose instructions that the first officer reads and follows.

No YAML frontmatter changes are needed. The agent file already has frontmatter for `name`, `description`, `tools`, and `commissioned-by`. Adding a `hooks:` list to frontmatter would duplicate what the sections already declare and require keeping two sources in sync. The sections are the hooks — if a `## Hook: startup` section exists, the lieutenant has a startup hook.

This keeps the format simple and self-describing: the first officer reads the lieutenant file, scans for `## Hook:` headings, and collects the instructions under each one.

### Lifecycle points

Two lifecycle points accept hooks:

1. **startup** — Runs after the first officer reads the README and before running `status --next`. Each startup hook receives the full entity list context (the first officer has already read entity files at this point). Startup hooks are for detecting and reacting to external state changes (e.g., a PR was merged upstream, an issue was closed).

2. **merge** — Runs when an entity reaches its terminal stage, before the default local-merge behavior. A merge hook can override the default merge for entities it claims. The hook receives the entity context (frontmatter fields). If no merge hook claims the entity, the first officer falls back to the default local merge. A merge hook "claims" an entity by specifying a condition in its prose (e.g., "if the entity has a non-empty `pr` field").

These two points cover the current PR-specific logic. Additional lifecycle points (e.g., `dispatch`, `completion`) can be added later if lieutenants need them — the pattern is extensible without changing the mechanism.

### Discovery

The first officer already reads the README frontmatter `stages.states` block at startup to find stage definitions. Some stages have an `agent:` property (e.g., `agent: pr-lieutenant`). The discovery process:

1. After reading the README, collect the set of distinct `agent:` values from all stages (excluding the default `ensign`, which has no hooks).
2. For each lieutenant agent name, read its agent file at `{project_root}/.claude/agents/{agent}.md`.
3. Scan the file for `## Hook:` sections. For each section found, register the hook: `{lifecycle_point} → {agent_name} → {hook instructions}`.
4. Multiple lieutenants can hook the same lifecycle point. The first officer executes them in the order the agents appear in the stages list.

If a lieutenant's agent file doesn't exist or has no `## Hook:` sections, it simply has no hooks — no error.

### Concrete example: PR logic migration

**Current state** (hardcoded in first-officer.md):

- Startup step 3: "Detect merged PRs" — scans entities for `pr` field, runs `gh pr view`, auto-advances merged entities.
- Merge step 1: "Check PR field" — if entity has `pr` set, check PR state via `gh` instead of local merge.

**After hooks:**

The first-officer template loses both of these. Its startup becomes:

1. Create team
2. Read the README
3. **Discover lieutenant hooks** — scan stages for `agent:` properties, read each lieutenant's agent file, collect `## Hook:` sections
4. **Run startup hooks** — for each registered startup hook, follow its instructions
5. Run `status --next`

Its merge section becomes:

1. **Run merge hooks** — for each registered merge hook, check if it claims this entity. If claimed, follow the hook's instructions instead of local merge.
2. **Default merge** — if no merge hook claimed the entity: local merge as before (read worktree field, derive branch, `git merge --no-commit`).
3. Update frontmatter, archive, clean up worktree.

The pr-lieutenant template gains two hook sections:

```markdown
## Hook: startup

Scan all entity files (in the workflow directory, not `_archive/`) for entities with a non-empty `pr` field and a non-terminal status. For each, extract the PR number (strip any `#`, `owner/repo#` prefix) and check: `gh pr view {number} --json state --jq '.state'`.

If `MERGED`, advance the entity to its terminal stage: set `status` to the terminal stage, `completed` to ISO 8601 now, `verdict: PASSED`, clear `worktree`, archive the file, and clean up any worktree/branch. Report each auto-advanced entity to the captain.

If `gh` is not available, warn the captain and skip PR state checks.

## Hook: merge

This hook claims entities that have a non-empty `pr` field.

Extract the PR number (strip `#`, `owner/repo#` prefix). Check PR state with `gh pr view {number} --json state --jq '.state'`.

- `MERGED`: The PR was merged on GitHub — skip local merge (the code is already on the target branch). Proceed to archive.
- `OPEN`: The PR is still open — report to the captain and wait. Do not archive until the PR is resolved.
- If `gh` is not available: warn the captain that PR state cannot be checked. Ask the captain whether to proceed with local merge or wait.
```

### What changes per file

- **`templates/first-officer.md`** — Remove startup step 3 (merged-PR detection) and merge step 1 (PR field check). Add hook discovery to startup (new step 3), startup hook execution (new step 4), and merge hook execution (new merge step 1 with fallback to local merge).
- **`templates/pr-lieutenant.md`** — Add `## Hook: startup` and `## Hook: merge` sections containing the PR-specific logic moved out of the first officer.
- **`skills/commission/SKILL.md`** — No changes needed. The commission already generates lieutenant agent files from templates via sed. The hook sections are just more markdown content in the template.
- **`templates/ensign.md`** — No changes. Ensigns don't have hooks.

### Acceptance criteria

1. The first-officer template contains no PR-specific logic (no mention of `gh pr view`, no `pr` field checks, no GitHub-specific behavior).
2. The first-officer template has a hook discovery step that reads lieutenant agent files referenced by stages.
3. The first-officer template has startup hook execution between README reading and `status --next`.
4. The first-officer template has merge hook execution with fallback to default local merge.
5. The pr-lieutenant template declares `## Hook: startup` and `## Hook: merge` sections.
6. The PR startup hook contains the exact logic currently in first-officer startup step 3.
7. The PR merge hook contains the exact logic currently in first-officer merge step 1.
8. Workflows without any lieutenant agents behave identically to before (no hooks discovered, default merge only).
9. The hook section format (`## Hook: {point}`) is documented in the first-officer template so future lieutenant authors know the convention.

## Stage Report: ideation

- [x] Hook mechanism designed — how lieutenants declare hooks (format, location)
  Named markdown sections (`## Hook: {lifecycle_point}`) in the lieutenant agent file body; no frontmatter changes needed.
- [x] Lifecycle points defined — which first-officer lifecycle points accept hooks
  Two points: `startup` (after reading README, before status --next) and `merge` (before default local merge, with claim/fallback pattern).
- [x] Discovery mechanism — how the first officer finds and reads hooks at startup
  Collect distinct `agent:` values from README stages, read each agent file, scan for `## Hook:` headings, register instructions by lifecycle point.
- [x] Concrete example — how the PR logic moves from first-officer to pr-lieutenant hooks
  Startup step 3 becomes `## Hook: startup` in pr-lieutenant; merge step 1 becomes `## Hook: merge` in pr-lieutenant. First officer template loses all PR-specific prose.
- [x] Acceptance criteria written
  Nine criteria covering template changes, behavioral equivalence, and backward compatibility.

### Summary

Designed a hook mechanism where lieutenants declare lifecycle hooks as `## Hook: {point}` sections in their agent markdown files. The first officer discovers hooks by reading lieutenant agent files referenced in README stage definitions, then executes them at startup and merge points. This moves all PR-specific logic out of the first-officer template into the pr-lieutenant template, keeping the first officer generic. The design requires changes to two template files (first-officer.md and pr-lieutenant.md) with no changes to the commission skill or ensign.

## Stage Report: implementation

- [x] First-officer template: PR-specific logic removed (no `gh pr view`, no `pr` field checks)
  `grep -c "gh pr view" templates/first-officer.md` returns 0; no `pr` field references remain.
- [x] First-officer template: hook discovery added to startup
  New startup step 3 scans `stages.states` for `agent:` values, reads agent files, registers `## Hook:` sections.
- [x] First-officer template: startup and merge hook execution added with fallback
  Startup step 4 executes startup hooks; merge step 1 runs merge hooks with fallback to default local merge.
- [x] First-officer template: hook convention documented for lieutenant authors
  New "Lieutenant Hook Convention" section documents the `## Hook: {point}` format and available lifecycle points.
- [x] PR lieutenant template: `## Hook: startup` with PR detection logic
  Contains the exact merged-PR detection logic previously in first-officer startup step 3.
- [x] PR lieutenant template: `## Hook: merge` with PR-aware merge logic
  Contains the exact PR-aware merge logic previously in first-officer merge step 1, with MERGED/OPEN/unavailable handling.
- [x] All changes committed
  Commit b03d7a6 on branch ensign/lt-hooks.

### Summary

Moved all PR-specific logic out of the first-officer template into the pr-lieutenant template as hook sections. The first officer now has a generic hook discovery mechanism (startup step 3) that reads lieutenant agent files referenced in README stage definitions and collects `## Hook:` sections. Startup hooks run before `status --next`, merge hooks run before the default local merge with a claim/fallback pattern. The pr-lieutenant gained `## Hook: startup` and `## Hook: merge` sections containing the exact PR detection and merge logic that was removed from the first officer. A "Lieutenant Hook Convention" section documents the mechanism for future lieutenant authors.

## Stage Report: validation

- [x] Test harness passes (no regressions)
  Full test harness: 64 passed, 0 failed. Commission generates all files correctly, including pr-lieutenant with fully substituted template variables. Initial run caught unsubstituted `__CAPTAIN__`/`__DIR__` in pr-lieutenant hooks; fixed by adding those substitutions to the sed commands in `skills/commission/SKILL.md` and `skills/refit/SKILL.md`.
- [x] First-officer template: no PR-specific logic, hooks mechanism present
  `grep -c "gh pr view" templates/first-officer.md` = 0. Broader grep for `gh pr|pr field|pr:` returns no matches. Hook discovery (startup step 3), startup hook execution (step 4), and merge hook execution (merge step 1 with fallback) all present.
- [x] PR lieutenant template: both hook sections present with correct content
  `## Hook: startup` at line 32 and `## Hook: merge` at line 40. Startup hook scans entities for `pr` field, checks `gh pr view`, auto-advances MERGED. Merge hook claims entities with `pr` field, handles MERGED/OPEN/unavailable states. Both use `__CAPTAIN__` and `__DIR__` template variables correctly.
- [x] Backward compatibility: workflows without lieutenants unaffected
  Discovery step: "Scan... for distinct `agent:` values (excluding `ensign`)" — empty set when no stages have `agent:` property. Step 4: "For each registered startup hook" — zero hooks, nothing runs. Merge step 1: "For each registered merge hook" — zero hooks, falls through to default local merge. Behavior is identical to before.
- [x] PASSED recommendation
  All 9 acceptance criteria verified. Bug found during validation (unsubstituted `__CAPTAIN__`/`__DIR__` in pr-lieutenant hooks) was fixed in both `skills/commission/SKILL.md` and `skills/refit/SKILL.md`. Re-run of test harness confirms 64/64 checks pass.

### Acceptance Criteria Verification

1. First-officer template contains no PR-specific logic: **PASS** — no `gh pr view`, no `pr` field checks, no GitHub-specific behavior.
2. First-officer template has hook discovery step: **PASS** — startup step 3.
3. First-officer template has startup hook execution between README reading and `status --next`: **PASS** — step 4, between step 2 and step 5.
4. First-officer template has merge hook execution with fallback: **PASS** — merge step 1 with claim/fallback pattern.
5. pr-lieutenant template declares `## Hook: startup` and `## Hook: merge`: **PASS** — both present.
6. PR startup hook contains exact logic from old first-officer startup step 3: **PASS** — scans entities for `pr` field, runs `gh pr view`, auto-advances MERGED, warns if `gh` unavailable.
7. PR merge hook contains exact logic from old first-officer merge step 1: **PASS** — claims entities with `pr` field, checks MERGED/OPEN/unavailable.
8. Workflows without lieutenants behave identically: **PASS** — zero hooks discovered, all fallbacks engaged.
9. Hook section format documented in first-officer template: **PASS** — "Lieutenant Hook Convention" section at line 90.

### Summary

Validation initially found a functional bug: the pr-lieutenant template's hook sections used `__CAPTAIN__` and `__DIR__` template variables not handled by the sed substitution commands. Fixed in both `skills/commission/SKILL.md` (section 2f) and `skills/refit/SKILL.md` (section 3e). After the fix, the full test harness passes (64/64 checks) and all 9 acceptance criteria are met. Recommendation: **PASSED**.
