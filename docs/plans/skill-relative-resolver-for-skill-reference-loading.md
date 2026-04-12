---
id: 136
title: Skill-relative resolver for skill reference loading
status: implementation
source: FO observation during Codex first-officer boot on 2026-04-12
score: 0.61
started: 2026-04-12T18:11:17Z
completed:
verdict:
worktree: .worktrees/spacedock-ensign-skill-relative-resolver-for-skill-reference-loading
issue:
pr:
---

Boot-time skill reference loading is currently ambiguous about what relative paths mean. During a `spacedock:first-officer` startup run on Codex, the first-officer skill referenced support documents as `references/...`, but those files lived under `skills/first-officer/references/`. Because the boot path did not resolve includes relative to the current `SKILL.md`, the runtime had to recover by searching the repo for matching files before it could continue.

This task should make skill include resolution deterministic for packaged skills. The intended direction is a skill-relative resolver: references declared by a skill resolve relative to the directory containing that `SKILL.md`, rather than the process working directory. If a declared target exists at that skill-relative path, boot should load it directly without repository-wide searching.

The change should stay focused on boot-time reference loading and operator clarity. We want Codex to stay centered on skills as the execution surface, not on `agents/*.md` files as a secondary indirection layer.
