---
id: 180
title: Decouple workflow timeline from the code repository
status: ideation
source: "Karen directive during 2026-04-29 session — every entity state change (dispatch / advance / mod-block / complete) commits directly to main without a PR, violating the hygiene rule that every commit on main should be reviewed via a PR. The workflow timeline lives in the same repo as the code it tracks, so timeline writes pollute the protected branch."
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

The first officer commits to the code repo's main on every entity state transition — `dispatch:`, `advance:`, `mod-block:`, `complete:` — and those commits never go through a PR. This violates the hygiene rule that everything landing on main should be reviewed via a PR, and it makes the main branch noisy with non-code state churn.

## Why this matters

- **Branch protection conflict.** Repos that enforce "PR required for main" cannot host a spacedock workflow without exempting the FO, weakening the protection.
- **Audit and history noise.** Code-review tooling, blame, and CHANGELOG generation all see workflow state commits mixed with real code changes.
- **Coupling to git.** The current state log is git-shaped (frontmatter + commits in the code repo). That blocks integrations with surfaces where the captain might prefer to review state — GitHub Projects, Notion databases, Linear projects.

## Direction (re-locked 2026-04-29 with Karen — state-only decoupling)

Two clean concepts:

- **The entity** = the markdown file with id, title, source, design content, stage reports, archive history. **Stays in the code repo** at `docs/plans/{slug}.md` (or wherever the workflow defines it). Browsed and edited like today.
- **The workflow timeline** = the per-entity *state log* — every `status` change, every `dispatch / advance / mod-block / complete` write, every timestamp. **Moves to a separate store.** The code repo never sees these writes again.

This is narrower than the prior framing, which proposed relocating the entire entity file. The entity file stays put. Only the time-varying state moves.

### What's state vs. what stays

| Field | Today | After |
|---|---|---|
| `id`, `title`, `source`, `score`, `issue` | entity file frontmatter | entity file frontmatter (unchanged) |
| `status`, `started`, `completed`, `verdict`, `worktree`, `pr`, `mod-block` | entity file frontmatter | external state store |
| Body content (Problem, Design, `## Stage Report`, `### Feedback Cycles`) | entity file body | entity file body (unchanged) |
| Audit log of state transitions | git log of FO commits on main | external state store |

### What FO commits look like after

| Today's commit pattern | Frequency | After |
|---|---|---|
| `dispatch:` / `advance:` / `mod-block:` / `complete:` | many per entity | Writes to state store. Code repo main never sees these. |
| `task: {slug} ({stage})` (initial entity creation) | rare (captain-driven) | Stays in code repo as a normal file write. Acceptable low-frequency noise; ideation evaluates whether to PR these too. |
| Captain-directed body edits | rare | Same. |
| `_archive/` directory move at terminal stage | once per entity | **Eliminated.** "Archived" becomes a state-store flag, not a file move. |

Net result: code repo main becomes essentially PR-only. Initial entity creation is the only remaining FO-direct write, and it's rare enough to live with — or to PR if the captain wants strict purity.

### What the state store could be (open for ideation)

- A sidecar git repo (small, single-purpose, captain-clonable).
- An orphan branch in the same code repo (no second checkout, but FO juggles the branch).
- A sidecar file per entity (e.g., `.state/{slug}.yml`) synced to an external store.
- A single append-only journal file (`timeline.jsonl`) on a separate branch or repo.
- SQLite DB.
- An external system as canonical (Notion / Linear / GitHub Project) — rejected as canonical store in the prior round; can re-evaluate now that scope is smaller.

Ideation picks one for the first delivery and lays out the data-shape contract so other backends can layer on later as adapters.

## Data-shape contract (state log)

The timeline is a sequence of state events plus the current-state projection of those events. Each event:

| Field | Type | Description |
|---|---|---|
| `entity_id` | string | The entity this event applies to |
| `entity_slug` | string | Convenience denormalization |
| `field` | string | Which state field changed (`status`, `worktree`, `pr`, `mod-block`, `started`, `completed`, `verdict`) |
| `old` | string \| null | Previous value |
| `new` | string \| null | New value |
| `timestamp` | ISO 8601 | When the event happened |
| `actor` | string \| null | FO, ensign name, captain, or hook name |
| `commit_msg` | string \| null | Message that would have gone on the FO commit (e.g., `dispatch: 180 entering ideation`) |

Current state per entity is the most-recent-by-timestamp projection of these events. This is what `status --boot` and `status --next` consume.

This contract is what later adapters (sidecar git repo, orphan branch, journal file, GitHub Projects, Notion, Linear) read and write against.

## Scope for this delivery

This task changes the spacedock **plugin** so any workflow can store its state log outside the code repo. It does not migrate any specific workflow.

- Move the state log out of code-repo main commits.
- Build the first state-store backend (ideation picks one).
- Define and document the data-shape contract above.
- Eliminate `_archive/` directory moves; "archived" becomes a state flag.
- Document a one-page generic cutover guide so any captain can convert an existing workflow.

**Explicitly out of scope:** moving the entity files themselves, building external-UI adapters (Notion / Linear / GitHub Projects), and migrating `docs/plans/` itself. Those are separate operational tasks the captain runs against the finished plugin.

This task **subsumes #165** (`entity-state-sidecar-file`) — same problem, more general formulation. Implementation closes #165. **#167** (`relocate-status-and-claude-team`) is independent and can run in either order.

## Open questions for ideation

- **State-store backend choice.** Pick one for the first delivery. Default candidate: sidecar git repo (preserves history, captain-inspectable, no new infra). Ideation justifies the choice and notes which alternatives are easy to layer on later.
- **State-store discovery.** How does `status` find the state store from the code repo? Config file (`.spacedock`)? Env var? Sibling-directory convention? Default-path inside the code repo on a separate branch?
- **Frontmatter migration.** Existing entity files have state fields in frontmatter. After cutover, those fields move out. How are stale frontmatter values handled — migration script that strips them, or `status` ignores them and treats the state store as authoritative?
- **`_archive/` elimination.** Today, archived entities live under `docs/plans/_archive/`. After: the file stays in `docs/plans/`, just marked archived in the state store. How does `status --archived` and the existing pr-merge startup-hook scan (which excludes `_archive/`) work?
- **Race conditions.** Two captain sessions or two FOs hitting the same state store simultaneously. Single-writer assumption, optimistic concurrency, or rebase-and-retry?
- **Observability.** Captain wants to see "what happened to entity X over time." How does she view the state log? `status --history {slug}`? A separate viewer? Just `git log` against the sidecar store?

## Prior ideation (discarded direction — entity-relocation framing)

The first ideation pass solved the wrong problem: it proposed relocating the entire entity file (frontmatter + body + reports) into a separate workflow repo. Karen clarified afterward that entity files should stay in the code repo and only the state log needs to move.

Discarded design, staff review, and proposed approach are preserved in git history at commit `01b2944` and earlier. Not reproduced here to keep the captain's view clean.

The new ideation pass starts from the state-only framing in `## Direction` above.
