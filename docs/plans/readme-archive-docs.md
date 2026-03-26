---
id: 037
title: Add _archive/ documentation to README template
status: ideation
source: refit gap analysis
started:
completed:
verdict:
score: 0.6
worktree:
---

The commission skill's README template (section 2a in `skills/commission/SKILL.md`) does not include `_archive/` documentation in the File Naming section. However, the first-officer template (section 2d) extensively references `_archive/`:

- Startup step 4: excludes `_archive/` from dispatch scanning
- Merge step 7: `git mv` completed entities to `_archive/`
- State Management: scans both `{dir}/` and `{dir}/_archive/` for sequential ID assignment

The `docs/plans/` pipeline has this documentation as a local addition, but newly commissioned pipelines won't get it. Users would see entities disappear into `_archive/` without any README explanation of what the directory is or how to use it.

Needs ideation to evaluate: what are the adverse effects of this gap? Does it cause real confusion or is the first-officer's behavior self-explanatory enough?
