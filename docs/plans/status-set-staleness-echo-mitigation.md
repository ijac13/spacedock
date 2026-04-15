---
id: 159
title: "FO shared-core: avoid full-file staleness echoes from Read + `status --set` pattern"
status: backlog
source: "github.com/clkao/spacedock#96 — `status --set` triggers full-file staleness echoes when FO has Read the entity body; Claude Code dumps entire current file as a system-reminder on the turn after a Bash-driven mutation"
started:
completed:
verdict:
score: 0.80
worktree:
issue: "#96"
pr:
---

When the FO Reads an entity file and then calls `status --set` via Bash to update frontmatter, Claude Code's file-staleness safety net emits the **entire current file** as a `<system-reminder>` in the next turn. Cost scales linearly with entity body size. Long-running workflows (triage batches, plans with many cycle reports) silently pay tens of thousands of cache-write tokens per frontmatter transition.

## Why it fires (from upstream #96)

- Claude Code tracks files touched by `Read` / `Edit`.
- `Edit` tool changes are diffed; CC knows what changed.
- Bash-driven changes (incl. `status --set`) are opaque, so CC falls back to dumping the full current state on the next turn so the assistant can't operate on stale knowledge.
- No diff-awareness for external modifications → the reminder includes every line of the file regardless of what changed.

## Proposed fix (pick 1 + 2, defer 3)

1. **Shared-core prose discipline** — update `references/first-officer-shared-core.md` (`## Dispatch`, `## Completion and Gates`) and `references/claude-first-officer-runtime.md` to prefer `Grep` over `Read` for targeted section extraction (`## Stage Report`, `### Feedback Cycles`, specific frontmatter fields). Explicitly warn about the echo cost of `Read` followed by `status --set`.
   - **Unverified assumption:** `Grep` does NOT register as file-tracking for CC's staleness system. Run a small live-test with a large fixture to confirm before landing prose.
2. **Emit frontmatter diff in `status --set` stdout** — `skills/commission/bin/status` already prints before/after for each field. Extend so the caller has the precise mutation without re-reading the file. Combined with (1), removes the reason for the FO to `Read` around mutation.
3. **Sidecar frontmatter file** — split `{slug}.md` into `{slug}.meta.yaml` + `{slug}.md`. Bigger architectural shift; defer until (1) + (2) prove insufficient.

## Scope notes

- This is partially a Claude Code runtime behavior; spacedock can mitigate the common case with prose alone (tests must confirm the Grep-not-tracked assumption).
- Codex may not have the equivalent staleness-echo behavior. Fix lands in the **Claude-specific** runtime adapter and general shared-core guidance, not a universal rule.
- Once shared-core prose changes, it propagates to every commissioned workflow via `refit`.

## Acceptance criteria (draft, ideation will sharpen)

- AC-1 (empirical): a live test proves `Grep` does not trigger the full-file echo where `Read` does, on a >= 20 KB entity file, followed by a `status --set` call.
- AC-2 (prose): shared-core and Claude runtime adapter prose redirect FO inspection of stage reports to `Grep` with section anchors; explicit warning about `Read` + `status --set` pair.
- AC-3 (helper): `status --set` stdout provides enough context that the FO can narrate the mutation without re-reading.
- AC-4 (evidence in-session): a long-running workflow session shows materially lower cache-write tokens per FO turn after the change, against a pre-change baseline.
