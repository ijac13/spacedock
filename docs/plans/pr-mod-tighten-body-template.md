---
id: 129
title: "PR merge mod: tighten body template — shorter lead, crisper bullets, less rationale"
status: backlog
source: "CL observation during task 123 merge, 2026-04-11"
score: 0.60
worktree:
started:
completed:
verdict:
issue:
pr:
---

The PR body template in `docs/plans/_mods/pr-merge.md` produces verbose descriptions that bury the actual change in rationale and stage-report artifacts. Observed during task 123 (`status-tool-as-workflow-op-cli`) merge: the drafted body was 205 words for a 3-file fix, with bullets carrying implementer rationale (e.g., `match != before = to avoid splitting inside !=`) and defensive scoping notes ("leave X, Y, Z untouched").

## What a PR reader actually needs, ranked

1. Why this exists — one sentence, scannable.
2. What's in the diff — 3–5 short items, one change per bullet, no rationale.
3. Is it safe to merge — one line of test evidence, pass ratio only.
4. Pointer back to context for archaeology — one line.

The current template allows each section to inflate: the motivation lead gets two dense sentences with parentheticals, bullets carry design rationale, the evidence section includes test-class breakdowns, and "what we deliberately did NOT change" bullets sneak in as defensive scoping.

## Direction (for ideation to refine)

Tighten the template constraints in `docs/plans/_mods/pr-merge.md`:

- **Motivation lead:** 1 sentence, ≤ 25 words, no parentheticals (currently "1–2 sentences blending motivation + end-user value").
- **What changed:** ≤ 5 bullets, each ≤ 15 words, one change per bullet, no rationale inside the bullet (currently "≤ 6 action-verb bullets").
- **Evidence:** 1–2 bullets max; pass ratio + live-test confirmation only; drop the "quantitative results if stage reports called them out" clause that invites breakdowns.
- **Target length:** 60–120 words total (currently 100–200).
- **Explicit extraction rule:** do not include "what we deliberately did NOT change" bullets unless a stage report flagged it as risk.

Keep the overall skeleton — motivation → what changed → evidence → audit metadata — and the metadata-at-bottom choice. The problem is section inflation, not structure.

## Related

- Task 123 (`status-tool-as-workflow-op-cli`) — source observation during its merge gate. The FO session log from 2026-04-11 contains the 205-word before-version and a ~105-word after-version as a concrete before/after reference.
- `docs/plans/_mods/pr-merge.md` — the file this task will edit.
