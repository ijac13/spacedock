---
id: 184
title: "Cherry-pick claude-team find_subagent_jsonl narrowing from #182 branch"
status: backlog
source: "carved out of #182 — the find_subagent_jsonl narrowing change is independently valuable and passed independent review; unbundling it from #182's rejected prose mitigations to land on its own."
started:
completed:
verdict:
score: 0.6
worktree:
issue:
pr:
mod-block:
---

## Why this matters

The `find_subagent_jsonl` narrowing in `skills/commission/bin/claude-team` replaces a global `~/.claude/projects/**/subagents/*.jsonl` glob with a team-scoped lookup. Empirical reduction: ~4816 → 9 files (~535x on a populated machine). The broad scan remains as a fallback when the narrowed lookup misses.

This change was developed and merged-green in PR #117 (entity #182), which is being rejected overall for scope drift. The narrowing change itself was reviewed independently and found sound.

## Scope

- Cherry-pick commit `b09051f4` ("fix: #182 narrow find_subagent_jsonl scan to one team's leadSessionId") from branch `spacedock-ensign/diagnose-opus-4-7-fo-regression` onto a fresh branch.
- Ideation MAY re-evaluate the stderr-warning noise floor and suggest softening to silent-fallthrough if the warning fires on every normal run — but the change as-shipped is acceptable.

## Out of scope

- Any prose mitigations in `skills/first-officer/references/claude-first-officer-runtime.md`.
- Any test-predicate changes (see sibling cherry-pick task).

## Cross-references

- #182 — source branch; being rejected for scope drift
- Independent review of PR #117 — confirmed this change is sound
