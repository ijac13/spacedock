---
id: 042
title: GitHub issue reference and PR workflow integration
status: ideation
source: CL
started: 2026-03-26T00:00:00Z
completed:
verdict:
score:
worktree:
---

How should Spacedock pipelines incorporate GitHub issue references and PR workflows? Tasks in a pipeline often correspond to GitHub issues, and implementation work naturally produces PRs. Currently there's no structured way to link these.

Questions to explore:
- Should task frontmatter have fields for issue and PR references?
- When in the pipeline lifecycle should issues/PRs be created — at task creation, at implementation, automatically or manually?
- Should the first officer or ensigns create PRs for worktree branches?
- How do PR reviews interact with pipeline approval gates (e.g., validation gate)?
- What's the minimal useful integration vs. over-engineering this?
