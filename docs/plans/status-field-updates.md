---
id: 094
title: Status script entity field updates
status: ideation
source: CL — observed FO using T00:00:00Z placeholder timestamps instead of real wallclock times
started: 2026-04-07T19:30:37Z
completed:
verdict:
score: 0.7
worktree:
issue:
pr:
---

# Status script entity field updates

## Problem

The FO manually edits YAML frontmatter for state transitions (status changes, setting `started`, `completed`, `worktree`, etc.). This is error-prone — observed the FO using `T00:00:00Z` placeholder timestamps instead of capturing real wallclock times. The status script already parses all frontmatter fields but currently only reads them.

## Design space

Two approaches to explore in ideation:

1. **`--advance {slug} {stage}`** — purpose-built for the FO's most common operation. Updates `status`, auto-sets `started` with real timestamp if not already set. Simple, narrow scope.

2. **`--set {slug} {field}={value}`** — generic field modifier. Could handle any frontmatter field (`status`, `worktree`, `pr`, `verdict`, etc.) with auto-timestamping as a side effect of specific field changes. More flexible but needs rules about which fields trigger side effects.

The right answer may depend on how many FO frontmatter operations this would replace vs. how much implicit behavior is acceptable in a CLI tool.
