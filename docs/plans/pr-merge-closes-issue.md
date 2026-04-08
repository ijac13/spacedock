---
id: 098
title: "pr-merge mod: include Closes #X when entity has linked issue"
status: backlog
source: "#48"
started:
completed:
verdict:
score:
worktree:
issue: "#48"
pr:
---

The pr-merge mod's merge hook creates PRs with a static body. When an entity has a non-empty `issue` field in frontmatter, the PR body should include `Closes {issue}` so GitHub auto-closes the linked issue on merge.
