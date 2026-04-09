---
id: 109
title: Make skill entrypoints runtime-aware — Codex loads Codex runtime, Claude loads Claude runtime
status: ideation
source: CL diagnosis — Codex main broken, skill loads wrong runtime contract
started: 2026-04-09T18:16:42Z
completed:
verdict:
score: 0.9
worktree:
issue:
pr:
---

## Problem

`skills/first-officer/SKILL.md` and `skills/ensign/SKILL.md` unconditionally load Claude-specific runtime references (`references/claude-first-officer-runtime.md`, `references/claude-ensign-runtime.md`). When Codex runs these skills, it gets Claude Code dispatch instructions (TeamCreate, SendMessage, Agent tool) that don't exist on Codex, causing timeouts and broken dispatch.

The same mismatch exists for both first-officer and ensign skills.

## Approach: runtime split (option 2 from diagnosis)

1. Keep shared core in `references/first-officer-shared-core.md` and `references/ensign-shared-core.md` — platform-agnostic behavioral contracts
2. Make skill SKILL.md files runtime-aware: detect the platform and load the appropriate runtime reference
   - Codex: load `references/codex-first-officer-runtime.md` / `references/codex-ensign-runtime.md`
   - Claude Code: load `references/claude-first-officer-runtime.md` / `references/claude-ensign-runtime.md`
3. Align the Codex packaged worker dispatch path with the existing helper contract (resolve logical id to worker_key, build packaged bootstrap prompt, spawn_agent with fork_context=false)
4. Both first-officer and ensign skills get the same treatment — fix consistently, not just the failing path

## Open question

How does the skill detect which runtime it's on? Options:
- Environment variable (`CODEX_HOME`, `CLAUDECODE`, etc.)
- Platform-specific file presence (`.codex/` vs `.claude/`)
- Separate skill entrypoints per platform (`skills/first-officer/SKILL.md` for Claude, different path for Codex)
- The skill prompt can check which tools are available (TeamCreate exists → Claude Code)

## Acceptance criteria

1. Codex FO loads `codex-first-officer-runtime.md`, not `claude-first-officer-runtime.md`
2. Codex ensign loads `codex-ensign-runtime.md`, not `claude-ensign-runtime.md`
3. Claude Code FO still loads `claude-first-officer-runtime.md` (no regression)
4. Claude Code ensign still loads `claude-ensign-runtime.md` (no regression)
5. Codex packaged-agent E2E test passes
6. Existing Claude Code E2E tests pass
