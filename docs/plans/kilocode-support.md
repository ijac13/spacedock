---
id: "163"
title: "Kilocode support — Kilo as a Spacedock runtime"
status: backlog
source:
started:
completed:
verdict:
score:
worktree:
issue:
pr:
---

Add support for Kilo (kilo.ai) as a third Spacedock runtime alongside Claude Code and Codex.

## Problem Statement

Spacedock currently supports:
- Claude Code (via claude-first-officer-runtime.md)
- Codex (via codex-first-officer-runtime.md)

Kilo is another AI coding assistant that uses subagents. Adding it as a runtime expands the supported execution environments.

## Proposed Approach

1. **Runtime detection**: detect Kilo via environment variables (`KILO_API_KEY` or similar)
2. **Runtime adapter**: create `kilo-first-officer-runtime.md` following the pattern of existing adapters
3. **Dispatch mechanism**: implement worker spawning via Kilo's `task` tool
4. **Entity lifecycle**: map stages (backlog → ideation → implementation → validation → done) to Kilo's execution model

## Acceptance Criteria

- [ ] Runtime detection works (recognizes Kilo environment)
- [ ] FO can dispatch entities to Kilo subagents
- [ ] Basic workflow execution completes under Kilo
- [ ] Merge hooks fire correctly