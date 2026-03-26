---
id: 037
title: Add _archive/ documentation to README template
status: done
source: refit gap analysis
started: 2026-03-26T15:00:00Z
completed: 2026-03-26T16:34:00Z
verdict: PASSED
score: 0.6
worktree:
---

## Problem

The commission skill's README template (section 2a in `skills/commission/SKILL.md`) does not mention `_archive/` in its File Naming section. However, the first-officer template (section 2d) extensively uses `_archive/`:

- Startup step 4: excludes `_archive/` from dispatch scanning
- Merge step 7: `git mv` completed entities to `_archive/`
- State Management: scans both `{dir}/` and `{dir}/_archive/` for sequential ID assignment

The `docs/plans/` pipeline has `_archive/` documentation as a local addition in its File Naming section, but that paragraph is not in the commission template. Newly commissioned pipelines won't get it.

## Adverse Effects Analysis

### What happens today without the documentation

When the first-officer completes an entity, it runs `git mv {slug}.md _archive/{slug}.md`. The entity vanishes from the main pipeline directory. The `status` script stops showing it (unless `--archived` is passed). The README's Pipeline State section already documents the `--archived` flag, so users can discover how to see archived entities — but the README never explains *what* `_archive/` is or *why* entities move there.

### Is the first-officer's behavior self-explanatory?

Partially. The git log shows `done: {slug} completed pipeline` with a `git mv` to `_archive/`, which is legible if you're watching commits. But if a user comes to the pipeline cold (e.g., a new team member, or the captain returning after weeks), they see:

- A directory called `_archive/` full of `.md` files
- No README explanation of what it means
- No guidance on whether they should touch those files, how to restore one, or what the relationship is between `_archive/` status and frontmatter status

The behavior is *inferable* but not *documented*. A user could reasonably wonder: "Is the archive permanent? Can I move things back? Does the `status` in frontmatter matter once it's archived?"

### Scenarios where lack of documentation causes real problems

1. **Manual entity management.** Users who create or manage entities outside the first-officer (which the README encourages — it has an entity template and `grep` commands) won't know they should use `_archive/` for completed items. They might delete completed entities, or leave them cluttering the main directory.

2. **Restoring archived entities.** Without documentation, a user who wants to re-open a completed entity doesn't know whether `git mv _archive/{slug}.md {slug}.md` is the right move, or if there's some other procedure.

3. **ID collisions.** The first-officer scans `_archive/` for ID assignment. If a user manually manages entities and doesn't know about the archive, they might create an entity with a duplicate ID (though this is an edge case — the first-officer handles ID assignment, not humans typically).

4. **Status script confusion.** The README documents `--archived` but doesn't explain what "archived" means. A user running `bash status` sees fewer entities than expected and has to figure out the flag exists.

### Severity assessment

This is a **documentation gap, not a functional bug.** The first-officer handles `_archive/` correctly. The status script handles `--archived` correctly. The system works — it just doesn't explain itself to humans reading the README.

The severity is **low-to-moderate**: it causes minor confusion for users coming to the pipeline cold, and slightly impedes manual entity management. It does not cause data loss or incorrect behavior.

## Proposal

Add a single paragraph about `_archive/` to the README template's File Naming section in `skills/commission/SKILL.md`. This matches what the `docs/plans/README.md` already has as a local addition.

### Where the fix goes

**README template only** (section 2a in `skills/commission/SKILL.md`). The first-officer's behavior is already correct — it doesn't need changes. The fix is adding one paragraph to the File Naming section of the generated README so that users understand what `_archive/` is.

### What to add

In the README template's File Naming section, after the existing line about file naming, add a paragraph matching the pattern already established in `docs/plans/README.md`:

> The `_archive/` subdirectory holds entities removed from the active view. Archived entities keep their original status in frontmatter — the directory is a noise reduction mechanism, not a status. Use `git mv {slug}.md _archive/{slug}.md` to archive and `git mv _archive/{slug}.md {slug}.md` to restore.

(With `{entity_label_plural}` / `{entity_label}` substitutions as appropriate for the template.)

### Acceptance criteria

1. The README template in `skills/commission/SKILL.md` section 2a includes `_archive/` documentation in the File Naming section
2. The paragraph uses template variables (`{entity_label_plural}`, etc.) consistently with the rest of the template
3. The `docs/plans/README.md` local addition remains unchanged (it already has this content)
4. No changes to the first-officer template (section 2d) — its `_archive/` handling is already correct
5. The test harness (`v0/test-harness.md`) passes — verify that generated README output includes the archive paragraph

## Validation Report

**Scope:** The implementation expanded beyond the original entity description (adding `_archive/` docs to the README template). A devrel specialist rewrote the project root `README.md` entirely. This validation assesses the README overhaul as delivered.

### 1. Does the README work as a first-time user onboarding document?

**Yes, with caveats.** The new README leads with a clear value proposition, explains concepts in a table, and provides a Quick Start section. The flow is: what it is, why it matters, key concepts, install, commission, run. This is a solid onboarding structure.

The Invictus quote after the bullet points is stylistic flair. It's not harmful but adds no information for a first-time user.

### 2. Are all factual claims accurate?

**One factual error found:**

- **Install command.** The README says "Install from the Claude Code plugin marketplace:" followed by `/install github.com/clkao/spacedock`. The old README explicitly stated "There is no registry yet" and used `--plugin-dir` for installation. The project's own archived entity `initial-project-readme.md` says "Installation is via `--plugin-dir` pointing to the local repo (there is no published registry yet in v0)." The archived `precompiled-dist.md` entity confirms: "Claude Code plugins are installed by directory path, not from a marketplace registry." **The marketplace install claim appears incorrect** unless this changed very recently. The Local Development section still shows the `--plugin-dir` method, which contradicts the marketplace claim above it.

**Accurate claims:**

- `/spacedock commission` is the correct skill invocation
- `/spacedock:commission <context>` with args is documented in SKILL.md
- `claude --agent first-officer` is the correct agent invocation
- `/spacedock refit` exists as a real skill (previously listed as deferred to v1, now implemented)
- The list of generated files (`{dir}/README.md`, `{dir}/status`, `{dir}/*.md`, `.claude/agents/first-officer.md`) is accurate
- "README is the single source of truth" matches the spec and SKILL.md
- "Experimental support for other coding agents" is a reasonable summary of the Codex compatibility analysis (entity 018, archived as PASSED)
- The dogfood/bootstrap claim about `docs/plans/` is accurate
- Worktree isolation for parallel processing is accurate

### 3. Are the install/usage commands correct?

- **`/install github.com/clkao/spacedock`** — likely incorrect (see above)
- **`/spacedock commission`** — correct
- **`/spacedock:commission <context>`** — correct syntax per SKILL.md
- **`claude --agent first-officer`** — correct
- **`git clone` + `--plugin-dir`** — correct (in Local Development section)

### 4. Is anything important missing that was in the old README but dropped?

**Dropped content:**

- **Project Structure tree** — The old README had a full directory tree showing the plugin's own file layout. The new README omits this. This is **acceptable** — the project structure is developer-facing, not user-facing, and the "What Gets Generated" section covers the user-relevant output.
- **Detailed commission steps** — The old README listed all 6 interactive design questions. The new one says "defining your mission, entity type, stages, and seed items." This is a reasonable summary, though it omits approval gates and location as interactive inputs (these are now auto-derived, matching the current SKILL.md which derives them rather than asking).
- **v0 status / shuttle vs starship** — The old README had a "Current Status: v0 (Shuttle Mode)" section explaining what works and what's deferred. The new README drops all version/mode language. This is **intentional per the scope description** ("Removes internal jargon: shuttle mode, starship mode"). However, users lose visibility into what's v0 vs future — there's no mention of current limitations.
- **Link to spec** — The old README linked to `v0/spec.md`. The new one doesn't. Minor loss — most users won't need the spec.
- **Old "Why" bullets** — "Git-native", "Human-auditable", "No dependencies", and composability via unix tools were dropped. The new bullets emphasize agent-native workflow and self-containment. The loss of "git-native" and "human-auditable" is notable — these were differentiating features. The new "agent-native" framing is reasonable but de-emphasizes the human-readable, no-dependency angle.

### 5. Is the tone appropriate?

**Mostly yes.** The tone is informative and concise. A few observations:

- The Invictus quote is an unusual stylistic choice for a technical README. It's not marketing-heavy but it is decorative.
- "You are the captain" framing is engaging without being excessive.
- The Use Cases section reads as illustrative rather than promotional.
- "Experimental support for other coding agents" is appropriately hedged.

### Recommendation: REJECTED

**Reason:** The marketplace install instruction (`/install github.com/clkao/spacedock`) appears factually incorrect based on the project's own documentation history. This is a first-time user's first interaction with the project — an install command that doesn't work would immediately undermine trust.

**To pass, the README needs:**
1. Fix the install command — either confirm `/install` is now a real command and the marketplace exists, or revert to the `--plugin-dir` installation method as the primary path
2. Consider whether the Local Development section should be the only install path (if there's still no marketplace), or restructure to show both paths if `/install` now works

The rest of the README is well-constructed and would pass validation once the install path is corrected.
