---
id: 097
title: FO guardrail on repo edits before implementation dispatch
status: backlog
source: "#30"
started:
completed:
verdict:
score:
worktree:
issue: "#30"
pr:
---

The first officer should not edit code, tests, or shared assets outside of a proper worktree dispatch cycle. Changes to repo content must happen in a checked-out worktree owned by a dispatched worker, after the captain approves moving the entity into implementation.

This includes scaffolding files like mods, which should go through refit rather than direct FO edits.
