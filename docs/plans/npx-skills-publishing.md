---
id: 057
title: Publish spacedock via npx skills ecosystem
status: ideation
source: CL
started: 2026-03-27T23:45:00Z
completed:
verdict:
score:
worktree:
---

Make spacedock installable via `npx skills add clkao/spacedock` — the Vercel Labs `skills` CLI (2.3M monthly downloads). This is the dominant distribution channel for Claude Code skills.

## Research findings

- `skills` CLI fetches `.md` skill files from GitHub repos and installs to `.claude/skills/`
- Supports GitHub shorthand: `npx skills add clkao/spacedock`
- Supports multiple agents: Claude Code, Cursor, Codex, OpenCode, Windsurf
- Spacedock's skills live at `skills/commission/SKILL.md` and `skills/refit/SKILL.md`

## Questions to resolve

- Does the `skills` CLI understand spacedock's plugin structure (`.claude-plugin/`, templates, agents)?
- Or does it only install skill `.md` files? If so, spacedock needs more than just skills — it needs templates and agent files too
- Can we make it work alongside the existing `claude plugin marketplace add` flow?
- Should we publish a lightweight npm wrapper that handles the full install?
