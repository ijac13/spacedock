---
id: 127
title: "Debrief skill — tighten output: PR links, drop per-PR commit lists, keep non-PR commits"
status: validation
source: "CL feedback during 2026-04-10 debrief: 'a bit too verbose'"
score: 0.60
worktree: .worktrees/spacedock-ensign-debrief-skill-update
started: 2026-04-10T23:31:01Z
completed:
verdict:
issue:
pr:
---

The debrief skill (`skills/debrief/SKILL.md`) currently produces debriefs with a commit list grouped by entity, where each shipped task has its full commit history inlined. For a 10-task session, this produces 100+ lines of commit enumeration that duplicate information already in the shipped PR. Captain feedback during the 2026-04-10 debrief:

> i feel the debrief is a bit too verbose. we don't need the commits for the ones associated with PR. also the shipped one should have pr linked to github. it's worthwhile to note non-PR commits (like workflow changes)

## What to change

**1. Shipped tasks become one-liners with PR links.** Instead of a "Commits" subsection per shipped task, each shipped task is a single bullet: slug, linked PR number (`[#N](https://github.com/{repo}/pull/N)`), one-sentence description. All per-PR commits are implicitly rolled up into the PR link.

**2. Non-PR commits get an explicit section.** State-transition commits, feedback-cycle commits, ideation stage-report commits, and scaffolding edits that didn't flow through a PR deserve their own section. These are the workflow-level changes a future FO needs to know about but can't find by browsing PRs. Format: short list with commit hash + one-liner.

**3. Drop the "Commits" grouped-by-entity section entirely.** It's superseded by the two changes above.

**4. PR link construction needs the repo URL.** The debrief skill already extracts this from `.claude-plugin/plugin.json` for GitHub issue filing (Phase 3 Step 3). Reuse that logic to build the PR URLs.

## Design sketch for the revised output

Current (verbose) shape:

```markdown
## Work Completed
{entity summaries}

## Commits
**115 slug (PR #62):**
- `abc123` seed
- `def456` dispatch: entering implementation
- `ghi789` advance: entering validation
- ... (10-20 lines per task)
```

New (tight) shape:

```markdown
## Shipped
- **115** `slug` — [#62](https://github.com/owner/repo/pull/62). One-sentence description.
- ... (one line per task)

## Filed (backlog)
- **N** `slug` — one-sentence description.
- ...

## Non-PR commits (workflow-only)
- `abc123` description — context
- `def456` feedback: cycle 1 — captain rejected at gate
- ... (only state transitions, feedback cycles, scaffolding, reverts)
```

The verbose draft the skill produced for this session was ~400 lines; the revised shape came out to ~90 lines with the same signal density.

## Scope

Update `skills/debrief/SKILL.md`:

1. **Phase 2a (Commits) — rewrite the extraction logic.** Instead of grouping every commit by entity slug and listing all of them, split commits into two buckets:
   - **PR-associated commits** — any commit that is part of a merged PR's branch. These get rolled up into the PR link in the "Shipped" section; they're not listed individually.
   - **Non-PR commits** — state transitions, feedback cycles, ideation reports, scaffolding edits on main. These appear in their own section with hash + description.

   Mechanism for distinguishing: check if the commit is reachable from a merged PR's head commit (via `git branch --contains` or equivalent), OR match commit prefixes (`dispatch:`, `advance:`, `state:`, `feedback:`, `ideation:`, `seed:`, `update:`, `docs:`, `debrief:`, `merge:` on main, `Revert` commits). The prefix-based heuristic is simpler and sufficient.

2. **Phase 2b/2c (Task state, gate decisions) — unchanged.** These drive the "Shipped" section.

3. **Phase 3 Step 1 (Present the draft) — update the template.** Replace the old "Work Completed / Commits" split with the new "Shipped / Filed / Non-PR commits" structure. Add PR link construction: read the repo URL from `.claude-plugin/plugin.json` (reuse the logic currently used for issue filing in Phase 3 Step 3), build links as `[#N](https://github.com/{owner}/{repo}/pull/N)`.

4. **Phase 4 Step 3 (Write the file) — update the debrief template.** Match the new structure from Phase 3 Step 1.

5. **Test against this session's debrief.** The 2026-04-10 #1 debrief was hand-crafted by the FO to match the target shape. Run the revised skill against the same commit range and confirm it produces a similar shape (not necessarily identical wording — the hand-crafted version has captain-assisted summarization that a skill can't match, but the structure should line up).

## Acceptance Criteria

1. Running `/spacedock:debrief` on a session with ≥5 shipped tasks produces a debrief where the "Shipped" section lists each task as a single-line bullet with a GitHub PR link, not a full commit list.
   - Test: run the revised skill against the 2026-04-10 session (boundary `31a3cb5..`) and confirm the shipped section has 10 bullets, each with a `[#N](...)` link.
2. A "Non-PR commits" section lists state transitions, feedback cycles, ideation stage reports, and scaffolding edits that didn't flow through a PR.
   - Test: same test run; confirm the non-PR section mentions the 116 revert (`461f4cc`), the tests/README.md clarification (`5c0a472`), and at least one feedback-cycle commit.
3. The "Filed (backlog)" section lists new entity seeds from the session.
   - Test: confirm 117, 119, 120, 122, 123, 124, 125, 126 appear in the filed section.
4. PR link construction uses the repo URL from `.claude-plugin/plugin.json`, not a hardcoded owner/repo.
   - Test: grep in `skills/debrief/SKILL.md` for the Phase 2/3 logic; confirm it references `plugin.json` for the repo URL.
5. The revised `skills/debrief/SKILL.md` is internally consistent: Phase 2 extraction feeds Phase 3 draft presentation which feeds Phase 4 file write, all using the new section structure.
   - Test: manual inspection of the updated skill file.
6. Existing debrief workflow (Phase 1 discovery, Phase 3 captain commentary, Phase 3 Step 3 GitHub issue filing, Phase 4 file write + commit) is preserved — this task only changes the output shape and commit-extraction logic, not the overall flow.
   - Test: read through each phase; confirm no unrelated changes.

## Test Plan

- **Manual verification**: run the revised skill against the 2026-04-10 session commit range. Compare the generated structure to the hand-crafted `2026-04-10-01.md` debrief. Not a strict equality check — the captain may have condensed wording — but the sections, PR links, and non-PR commit list should line up structurally.
- **Static inspection**: grep `skills/debrief/SKILL.md` for the new section names ("Shipped", "Filed", "Non-PR commits") and confirm the Phase 3 draft template and Phase 4 write template match.
- **No new E2E test**: the debrief skill is invoked interactively via `/spacedock:debrief`; its output shape is verified by captain review at draft time.
- **No regression suite impact**: the skill is a Claude-invoked markdown instruction file, not code with tests.

## Out of scope

- Changing the Phase 1 discovery logic (session boundary, workflow identification).
- Changing the Phase 3 GitHub issue filing flow.
- Adding new debrief sections beyond the three-way Shipped / Filed / Non-PR split.
- Auto-generating the one-sentence task descriptions (the skill can leave them as placeholders for captain review, OR pull from the entity file's problem statement paragraph — ideation may decide).
- Retroactively rewriting old debriefs to the new format.

## Related

- **Task 116** `readme-and-architecture-refresh` — the session's largest task, contributed to the debrief verbosity observation.
- **Task 118** `pr-merge-mod-rich-body-template` — established the pattern of "roll up detail into structured PR bodies". This task applies the same principle to debriefs.
- **2026-04-10 #1 debrief** — the hand-crafted target shape the revised skill should produce automatically.
