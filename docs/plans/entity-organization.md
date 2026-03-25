---
title: Make pipeline entities more organizable
status: ideation
source: CL
started: 2026-03-25T05:00:00Z
completed:
verdict:
score: 0.60
worktree:
---

As pipelines grow (this one has 30+ entities), the flat directory of markdown files gets messy. Need a way to keep entities organized and navigable.

Directions to consider:

1. **Archive directory** — move completed/done entities into a subdirectory (e.g., `docs/plans/archive/`) to keep the active working set small. Status script and views would need to scan both locations.

2. **Date prefix in filename** — e.g., `2026-03-24-codex-compatibility.md` so files sort chronologically. Gives natural ordering. Trade-off: longer filenames, slug references change.

3. **Short identifier** — like what beads does, with a variable-length truncated UUID that grows as the entity count increases. Gives stable, compact identifiers for cross-referencing. E.g., `a3f-codex-compatibility.md` or just `a3f.md` with the title in frontmatter.

These aren't mutually exclusive. The solution should keep PTP's plain-text simplicity while scaling to dozens or hundreds of entities.

---

## Debate: Engineer Alpha vs Engineer Beta

### Current state of this pipeline

- 31 entities (excluding README.md), 25 of which are `done`.
- The status script scans `$DIR/*.md` (one flat glob), excluding README.md.
- Slugs are deeply embedded: worktree paths (`.worktrees/ensign-{slug}`), branch names (`ensign/{slug}`), ensign agent names (`ensign-{slug}`), commit messages (`dispatch: {slug} entering {stage}`), and grep-based filtering (`grep -l "status: ideation" docs/plans/*.md`).
- The commission template generates all of this from `{slug}` = filename minus `.md`.

### Option 2 — Date prefix: Rejected

Both engineers agreed this is all cost, no benefit:
- Massive blast radius on slugs: worktree paths, branch names, ensign names, commit messages all become unwieldy (e.g., `ensign-2026-03-24-codex-compatibility`).
- Ambiguous which date to use (created? started? completed?).
- Does not reduce clutter — same number of files, just sorted differently.
- Long filenames (52+ characters).
- Breaks every existing entity reference.
- Does not scale to 100+ entities. Visual ordering does not reduce cognitive load.

### Option 3 — Short identifier (beads-style): Rejected

Both engineers agreed this solves a problem that doesn't exist:
- Opaque identifiers (`a3f`) add cognitive overhead — you have to look them up.
- Same blast radius as date prefix — all slug references change.
- Adds complexity to entity creation (generate + check uniqueness of prefix).
- Not naturally sortable by any meaningful dimension.
- Beads uses content-addressable hashing, which doesn't apply to entities whose content changes throughout their lifecycle. A random UUID prefix is just noise.
- Does not scale to 100+ entities. You still have 100 files in one directory, now with cryptic prefixes.

### Option 1 — Archive directory: Recommended (with tight scoping)

Both engineers converged on this option. The key insight: the problem is not "too many entities" — it's "too many DONE entities cluttering the active view." 25 of 31 are done. Moving terminal entities to a subdirectory drops the main listing from 31 to 6.

**Critical design decision: `done/` not `archive/`.** The subdirectory name maps directly to the pipeline's terminal status. "Archive" introduces a concept that doesn't exist in the pipeline schema. `done/` is self-documenting.

**Critical constraint: do NOT generalize to other status subdirectories.** The moment you have `done/`, `backlog/`, `implementation/`, etc., you've recreated a filesystem kanban board and the status field in frontmatter becomes redundant with directory location. The frontmatter IS the source of truth for status; the directory is a noise reduction mechanism for terminal entities only. `done/` is special because terminal entities never change status again — that's what makes it safe to move them.

### Debate points resolved

**REJECTED entities go to `done/` too.** "Done" means "terminal, no longer active in the pipeline" — not "succeeded." The verdict field in frontmatter distinguishes PASSED from REJECTED. `grep -l "verdict: REJECTED" docs/plans/done/*.md` works.

**Status script change requires bash 3.2 compatibility.** Can't use `**/*.md` globbing (needs `globstar`, unavailable in bash 3.2). Use two globs with a file-existence guard:

```bash
for f in "$DIR"/*.md "$DIR"/done/*.md; do
  [ -f "$f" ] || continue
  [ "$(basename "$f")" = "README.md" ] && continue
  ...
```

The `[ -f "$f" ] || continue` guard handles both "done/ doesn't exist" and "done/ is empty" without needing `shopt -s nullglob`.

**First-officer triggers the move.** As part of the done transition, after the merge to main and setting terminal status/verdict, the first-officer does `git mv {slug}.md done/{slug}.md` in the same commit. This keeps it automated — if manual, it won't happen and the directory accumulates done entities again.

**Slug uniqueness across directories.** Once entities can live in either `$DIR/` or `$DIR/done/`, the slug (filename minus `.md`) must remain unique across both. The first-officer or commission template should check both directories when creating entities to prevent collisions that would break worktree names, branch names, etc.

**Cross-references in entity bodies are a non-issue.** Entity bodies are prose documentation. If one mentions `codex-compatibility.md`, the meaning is clear regardless of which directory it lives in. The slug is the lookup key, not the relative path. `git log --follow` handles rename history.

## CL's Design Direction (overrides debate recommendation)

The engineer debate recommended `done/` scoped to terminal entities. CL broadened the scope:

### `_archive/` instead of `done/`

`_archive/` is a general decluttering mechanism, not coupled to pipeline state. Any entity can be archived — done entities, stalled ideation, parked backlog items. The underscore prefix sorts it to the bottom in directory listings.

Key differences from the debate's `done/` proposal:
- **Not status-coupled**: archived entities keep their original frontmatter status. An archived backlog item is still `status: backlog`, just out of the active view.
- **Resurrection**: entities can be moved back to the main directory when needed. `git mv _archive/{slug}.md {slug}.md` brings it back.
- **First officer ignores `_archive/`**: the first officer only dispatches from the main directory. Archived entities are invisible to the pipeline.

### Status script changes

- Default: scan `$DIR/*.md` only (excludes `_archive/`)
- `--archived` flag: also scan `$DIR/_archive/*.md`
- Bash 3.2 compatible: two globs with `[ -f "$f" ] || continue` guard

### Entity identifier (future cross-referencing)

A short stable identifier per entity, assigned at creation, never changes. Not necessarily in the filename — could be a frontmatter field (`id: a3f`). Enables:
- Cross-system references (e.g., Linear: `SD-a3f`)
- Dependency tracking between entities (`depends: [a3f, b72]`)
- Future in-place DB for state search and reference
- Beads-style variable-length truncation: starts short, grows as entity count increases

This is lower priority than `_archive/` but should be designed together so the archive mechanism works with identifiers.

## Revised Specification

1. **`_archive/` subdirectory** for any entity the captain wants out of the active view
2. **Slug unchanged** — filename minus `.md`, regardless of directory
3. **First-officer moves done entities** to `_archive/` as part of the done transition, atomic with merge commit. Captain can also manually archive stalled entities.
4. **First officer ignores `_archive/`** — only dispatches from main directory
5. **Status script** scans `$DIR/*.md` by default; `--archived` flag adds `$DIR/_archive/*.md`
6. **One-time migration** of existing done entities via batch `git mv`
7. **Slug uniqueness enforced** across both directories
8. **Commission template updated** with `_archive/` convention and the `git mv` step
9. **README "File Naming" section** documents the convention
10. **(Stretch) Entity identifier** — `id:` field in frontmatter schema, assigned at creation. Design the format (variable-length truncated UUID or similar) but implementation can be a follow-up.
