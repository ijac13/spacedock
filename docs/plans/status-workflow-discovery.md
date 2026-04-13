---
id: 100
title: "status tool: add workflow directory discovery"
status: ideation
source: CL observation — Codex startup uses raw rg for discovery
started: 2026-04-13T15:57:56Z
completed:
verdict:
score: 0.60
worktree:
issue:
pr:
---

The startup procedure (step 2) requires searching for README.md files with `commissioned-by: spacedock@` frontmatter to discover workflow directories. Every runtime (Claude Code, Codex) reimplements this as a raw grep/rg call before it can invoke `status --boot`.

Fold discovery into the status tool so there's a single entry point. Either a `--discover` flag that returns workflow directories, or make `--boot` auto-discover when `--workflow-dir` is omitted.
