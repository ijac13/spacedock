---
title: First officer must enforce mod-declared blocking actions at runtime
id: 114
status: backlog
source: CL observation during entity 110 closeout
started: 2026-04-09T22:56:43Z
completed:
verdict:
score: 0.80
worktree:
issue:
pr:
---

First officer currently relies too heavily on remembering mod instructions from prose. That is brittle. A mod can require a stop, approval, or external wait, but the runtime does not yet enforce those requirements mechanically.

## Problem Statement

The `pr-merge` mod correctly says gate approval does not imply PR approval, but first officer can still drift unless it re-reads and obeys the mod at the exact transition point. This is a general workflow safety problem, not just a PR problem.

## Desired Outcome

Add a generic runtime mechanism so active mods can force first officer to pause for captain approval or another blocking condition, and a resumed session cannot silently skip that pending requirement.
