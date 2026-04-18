---
id: 187
title: "Refine and land PR #118 — entity-as-folder support (Karen Hsieh)"
status: ideation
source: "external contribution from Karen Hsieh (@ijac13) — PR #118 closes GitHub issue #99 with entity-as-folder scanner support. Spacedock-workflow entity filed to track refinement + review through our standards while preserving contributor attribution on merge."
started: 2026-04-18T00:54:30Z
completed:
verdict:
score: 0.6
worktree:
issue: "#99"
pr: "#118"
mod-block:
---

## Contributor

Karen Hsieh (@ijac13 on GitHub) is the original author and owns the authorship on every commit in `feat/entity-as-folder`. Any refinement we apply must be **additive on top of her branch** (or squash-merge with `Co-authored-by: Karen Hsieh <...>` trailer preserved) — we do NOT rewrite her commits with our authorship. Contributor attribution is load-bearing.

## Why this matters

GitHub issue #99 (filed by CL in 0.9.4) proposed first-class entity-as-folder support so workflows producing many artifacts per entity can organize them under `{slug}/index.md` without breaking the scanner. Karen's PR #118 implements this:

- Scanner descends into `{slug}/index.md` when flat `{slug}.md` is absent.
- `status --set` resolves folder entities by the same rule.
- `status --archive` moves the whole folder to `_archive/{slug}/` and stamps `archived:` inside the inner index.
- `--archived`, `--boot`, `--next`, `--next-id`, `--where` inherit via shared discovery.
- Reserved subdirs (`_archive`, `_mods`) excluded from entity detection.
- Conflict case (both flat + folder present) warns on stderr and prefers folder.
- Flat-file workflows unchanged; 444 tests passing locally per PR body.

This entity exists because **we want to refine the submission through our workflow** before landing — reviewing the design against our standards, verifying coverage, potentially requesting scope adjustments.

## Scope for ideation

- Read the PR diff in full; inventory each change vs the issue-#99 spec.
- Identify refinements (wording, test coverage gaps, edge cases not yet exercised, API-surface questions) to request from Karen OR apply ourselves on a follow-up commit.
- Distinguish "must-fix before merge" refinements from "nice-to-have follow-up."
- Produce a concrete change request list for the PR review, or a clear PASSED-as-is acceptance.
- Confirm CI strategy: PR #118's `Runtime Live E2E` run (24555916111) is currently WAITING for env approval; decide whether to approve before or after ideation.

## Merge strategy

- Preserve authorship. Default path: merge-commit (no squash) so every commit keeps Karen as author.
- If squash is preferred for linear-history reasons, the squash commit MUST include `Co-authored-by: Karen Hsieh <email-from-commit>` in the trailer.
- The FO's `pr-merge` mod's PR-body template does not fit here (this is an external PR, not one we authored). The merge-hook's push step is skipped — the branch is already pushed by the contributor.

## Out of scope

- Rewriting Karen's commits to look like ours.
- Adding a spacedock-workflow-style entity body INSIDE `feat/entity-as-folder` — that's our internal convention, not hers.
- Forcing PR #118 through our ideation-gate-then-implementation pattern — implementation already exists; this workflow entity covers review + refinement only.

## Cross-references

- GitHub issue #99 — the original feature request (authored by CL, 0.9.4)
- PR #118 — the implementation (authored by Karen Hsieh / @ijac13, open)
- CI run 24555916111 — PR #118's Runtime Live E2E, currently WAITING for env approval
