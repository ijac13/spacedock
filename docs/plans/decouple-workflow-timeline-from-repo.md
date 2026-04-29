---
id: 180
title: Decouple workflow timeline from the code repository
status: ideation
source: "CL directive during 2026-04-29 session — every entity state change (dispatch / advance / mod-block / complete) commits directly to main without a PR, violating the hygiene rule that every commit on main should be reviewed via a PR. The workflow timeline lives in the same repo as the code it tracks, so timeline writes pollute the protected branch."
started: 2026-04-29T04:07:14Z
completed:
verdict:
score:
worktree:
issue:
pr:
mod-block:
---

## Problem

Spacedock stores entity files (the workflow timeline) inside the same git repository as the code those entities describe. The first officer commits to main on every state transition — `dispatch:`, `advance:`, `mod-block:`, `complete:` — and those commits never go through a PR. This violates the hygiene rule that everything landing on main should be reviewed via a PR, and it makes the main branch noisy with non-code state churn.

## Why this matters

- **Branch protection conflict.** Repos that enforce "PR required for main" cannot host a spacedock workflow without exempting the FO, weakening the protection.
- **Audit and history noise.** Code-review tooling, blame, and CHANGELOG generation all see workflow state commits mixed with real code changes.
- **Coupling to git.** The timeline today is git-shaped (markdown + frontmatter + commits). That blocks integrations with surfaces where the captain might prefer to review work — GitHub Projects, Notion databases, Linear projects.

## Direction (locked 2026-04-29 with CL)

Two-layer split:

- **Canonical store** = where truth lives. The FO writes here on every state change.
- **Projections** = read-only views (GitHub Project, Notion DB, Linear, plain markdown). Out of scope for this delivery.

For the canonical store, ship a **separate git repo** (e.g. `Claude-recce-workflow`). The FO continues writing markdown + frontmatter + git commits, but to the workflow repo, not the code repo. The code repo's main becomes PR-only.

Rejected alternatives:

- **Branch-on-same-repo** — forces sidecar checkouts; clones don't get timeline by default.
- **Same-repo gitignored** — loses version history of state transitions.
- **External system as source of truth** (Notion / Linear / GitHub Project as canonical store) — vendor lock-in, network dependency, harder to migrate. Acceptable as a projection, unacceptable as the canonical store.

External surfaces become **adapters** layered on top of the canonical store later. Documented but not built in this delivery.

## Data-shape contract

Every projection consumes or emits this entity shape:

| Field | Type | What it maps to in any UI |
|---|---|---|
| `id`, `slug`, `title` | string | Item identity |
| `workflow` | string | Which workflow |
| `stage` | enum (workflow-defined) | Status column / single-select |
| `verdict` | `PASSED \| REJECTED \| null` | Custom field |
| `started`, `completed` | ISO 8601 | Timestamps |
| `source`, `score`, `issue`, `pr`, `mod-block` | string / number | Custom fields |
| `parent` | id ref | Sub-entity link |
| `body` | markdown | Issue body / page content |
| `events[]` | list of `{type, stage, timestamp, actor, message}` | Comments / activity log |

This contract is what future adapters (filesystem-on-sister-repo, github-project, notion, linear) will read and write against.

## Scope for this delivery

- Decouple workflow timeline onto a sister git repo so the code repo's main is PR-only.
- Define and document the data-shape contract above.
- Provide a migration path for the existing `docs/plans/` workflow.
- Build only the filesystem-on-sister-repo adapter. External UI projections are out of scope.

## Open questions for ideation

- **Worktree story.** Worktree-stage workers commit deliverables to the code repo's branch. The entity file (with stage reports) lives in the workflow repo. How does the worker write its stage report back to the entity file in a different repo while still committing code in its worktree?
- **Discovery.** How does `status` find the workflow repo from the code repo? Config file in code repo (`.spacedock.toml`)? Env var? Sibling-directory convention?
- **Migration.** Move existing `docs/plans/` (active + `_archive/`) to the new repo with `git mv` + history transplant, fresh extract, or freeze old + start new?
- **Mod files.** `_mods/` lives with the workflow today. Stays with the workflow repo, presumably — confirm.
- **PR-merge mod compatibility.** The `pr-merge` mod creates PRs against the *code* repo, while it lives in the *workflow* repo. Confirm cross-repo orchestration still works cleanly.

## Acceptance criteria (placeholder — refine in ideation)

- Workflow state changes do not produce direct commits to the code repo's main branch.
- A test workflow runs end-to-end (entity creation → dispatch → completion → archive) using the sister-repo backend.
- The data-shape contract is documented and exposed via a `status --schema` (or equivalent) command for future adapter authors.
- Migration plan for the existing `docs/plans/` workflow is described and tested on a copy.
