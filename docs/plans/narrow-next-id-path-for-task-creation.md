---
id: 139
title: Narrow next-id path for task creation
status: ideation
source: FO observation during interactive filing on 2026-04-12
score: 0.57
started: 2026-04-12T18:20:42Z
completed:
verdict:
worktree: 
issue:
pr:
---

The first officer currently reaches for `skills/commission/bin/status --boot` to learn the next available sequential entity id before filing a new task. That works, but it is broader than necessary: `--boot` also gathers mods, orphan worktrees, PR state, and dispatchable entities. In an interactive session this adds avoidable output and encourages the FO to use a startup-oriented command for ordinary task creation.

The shipped `status` script does not currently expose a narrow `--next-id` mode. Its source advertises support for the default table, `--archived`, `--next`, and `--boot`, and the CLI implementation contains no `--next-id` flag. As a result, the FO either has to overuse `--boot` or reimplement next-id discovery ad hoc.

This task should define and implement a narrow, explicit path for task creation. The likely direction is a `status --next-id` mode that prints only the next sequential id across the active workflow and `_archive/`, plus corresponding first-officer guidance to use that mode when filing new entities instead of a full startup scan.
