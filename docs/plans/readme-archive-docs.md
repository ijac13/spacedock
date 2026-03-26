---
id: 037
title: Add _archive/ documentation to README template
status: ideation
source: refit gap analysis
started: 2026-03-26T15:00:00Z
completed:
verdict:
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
