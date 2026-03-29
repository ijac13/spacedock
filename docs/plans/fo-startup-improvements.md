---
id: 074
title: First-officer startup improvements — README search and bare mode detection
status: ideation
source: CL
started: 2026-03-29T18:00:00Z
completed:
verdict:
score: 0.70
worktree:
---

Two improvements to the first-officer startup sequence.

## 1. README search should ignore common directories

The FO startup step 1 uses `grep -rl '^commissioned-by: spacedock@' --include='README.md' "$project_root"` to discover workflow directories. This searches everything under the project root, including:

- `node_modules/` — huge, slow, will never have workflows
- `.worktrees/` — copies of the repo, produces duplicate hits
- Other common noise: `.git/`, `vendor/`, `dist/`, `build/`

The search should exclude these directories. Observed in this session: the discovery returned 16 results including 10 from `.worktrees/` that had to be filtered out manually.

## 2. Detect TeamCreate availability and report bare mode

The FO template's startup step 3 calls `TeamCreate`. If teams are not available (the experimental flag is off, or the environment doesn't support it), the FO should detect this and tell the user it's operating in a fallback mode — sequential dispatch without team coordination.

From task 033's experiment: when team tools are unavailable, the FO can still function by dispatching via `Agent()` without `team_name`, with ensign output returning via the subagent completion mechanism. The FO should explicitly detect and report this rather than silently adapting or failing.

Proposed behavior:
- At startup, check if TeamCreate is available (via ToolSearch or attempt)
- If available: proceed with team-based dispatch as today
- If not available: report to the captain that teams are unavailable and the FO is operating in bare mode (sequential dispatch, no inter-agent messaging). Then skip TeamCreate and proceed.
