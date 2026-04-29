---
id: 180
title: Decouple workflow timeline from the code repository
status: backlog
source: "CL directive during 2026-04-29 session — every entity state change (dispatch / advance / mod-block / complete) commits directly to main without a PR, violating the hygiene rule that every commit on main should be reviewed via a PR. The workflow timeline lives in the same repo as the code it tracks, so timeline writes pollute the protected branch."
started:
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

## Direction (to be refined in ideation)

Separate the workflow timeline from the code repo so timeline writes do not touch main. Possible shapes:

- A dedicated state repo or branch that the FO writes to, leaving main code-only.
- A pluggable timeline backend with adapters for: filesystem (current behavior, legacy), GitHub Projects, Notion DB, Linear project.
- A clean read/write API at the `status` boundary so the FO and ensigns stay UI-agnostic.

## Open questions

- Where does the entity body (stage reports, design content) live when the timeline is non-filesystem? Still markdown in a worktree branch? In the external surface?
- How do worktrees relate to a non-filesystem timeline?
- What is the migration path for in-flight workflows?
- Which backend ships first — does GitHub Projects offer enough fidelity, or does the filesystem stay default?

## Acceptance criteria (placeholder — refine in ideation)

- Workflow state changes do not produce direct commits to the code repo's main branch under the chosen backend.
- At least one non-filesystem backend works end-to-end against an example workflow.
- Existing filesystem workflows continue to function via a legacy adapter or documented migration.
