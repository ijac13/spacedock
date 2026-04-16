---
id: 164
title: "`claude-team build` path-doubles when entity_path is passed as a worktree-absolute path"
status: backlog
source: "FO observation during 2026-04-16 session while dispatching #162 implementation — initial build invocation produced entity paths with `.worktrees/` prefix duplicated twice"
started:
completed:
verdict:
score: 0.40
worktree:
issue:
pr:
---

When the FO passes `entity_path` to `claude-team build` as a worktree-absolute path (e.g. `/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-{slug}/docs/plans/{slug}.md`), the helper emits a prompt whose "Read the entity file at..." references a doubled path: `/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-{slug}/.worktrees/spacedock-ensign-{slug}/docs/plans/{slug}.md`. The dispatched ensign follows the instruction and fails at the first Read.

The workaround that works today: pass `entity_path` as the project-root path (`/Users/clkao/git/spacedock/docs/plans/{slug}.md`). The helper then emits the correct worktree path. The FO documented this workaround in-session on 2026-04-15 during #157 dispatch.

## Observed evidence

2026-04-16 session, during #162 implementation dispatch. First build invocation passed `entity_path` as the worktree-absolute path; output contained:

```
Read the entity file at /Users/clkao/git/spacedock/.worktrees/spacedock-ensign-claude-team-respect-stage-model/.worktrees/spacedock-ensign-claude-team-respect-stage-model/docs/plans/claude-team-respect-stage-model.md
```

Rebuilt with `entity_path` at project root — output was correct. Confirms the helper prepends some worktree-derived prefix to whatever `entity_path` it receives, double-applying when the input is already worktree-absolute.

## Root cause (suspected)

In `skills/commission/bin/claude-team` `cmd_build`, the path resolution from `entity_path` to the worker-visible read target appears to compute a worktree path via string concatenation rather than path-aware resolution. When the input is already worktree-absolute, the concatenation adds another worktree segment. When the input is project-root absolute, concatenation produces the correct worktree path.

Needs verification in the helper source — the exact code path hasn't been read line-by-line yet.

## Proposed approach

Options, smallest fix first:

**(a) Validate and normalize on the way in.** `cmd_build` detects if `entity_path` is already under a worktree tree (contains `.worktrees/`) and either (i) errors with a clear message telling the caller to pass project-root paths, or (ii) silently normalizes by stripping the `.worktrees/{key}/` prefix and re-deriving. Prefer (i) — errors are clearer than silent corrections.

**(b) Use path-aware resolution.** Rewrite the path-building logic to use `os.path` operations that produce canonical worktree paths from project-root input regardless of whether `entity_path` was already worktree-form. Removes the class of bug entirely; more invasive change.

**(c) Document the caller contract.** Leave the helper as-is and add a preamble note in the runtime adapter instructing the FO to always pass project-root `entity_path`. Smallest change; doesn't prevent the bug, just documents around it. Least useful.

Recommend **(a)** for v1 — concrete error at the boundary is the cheapest way to surface the misuse without rewriting path logic.

## Acceptance Criteria (draft)

1. **AC-error-on-worktree-path**: `claude-team build` with `entity_path` containing `.worktrees/` in the input rejects with a non-zero exit and a stderr message naming the offending input plus the expected shape. *Verified by* a static test in `tests/test_claude_team.py`.
2. **AC-prompt-uses-correct-worktree-path**: when given a project-root `entity_path`, the emitted prompt's "Read the entity file at..." line contains exactly one `.worktrees/{worker_key}-{slug}/` segment (no doubling). *Verified by* a static test on the helper's output.
3. **AC-caller-guidance**: `claude-team build --help` (or documented usage) states that `entity_path` must be a project-root absolute path. *Verified by* a grep test on the binary's help text output.

## Test Plan

All static, all sub-second:

- 1 error-path test (AC-error-on-worktree-path).
- 1 output-shape test (AC-prompt-uses-correct-worktree-path).
- 1 help-text test (AC-caller-guidance).

No live tests needed — this is a helper input-handling bug with deterministic output.

## Scope Boundary

Fix is ~10 lines of Python in `skills/commission/bin/claude-team` + 3 static tests + 1 docstring update. Do not rewrite any other part of `cmd_build`; do not touch other subcommands.

## Out of Scope

- Fixing any analogous doubling in `spawn-standing` (landed in #162) — cross-check after this ships; separate task if needed.
- Codex runtime's equivalent `entity_path` plumbing — Codex helper is a different binary; file a sibling task if the pattern repeats.
