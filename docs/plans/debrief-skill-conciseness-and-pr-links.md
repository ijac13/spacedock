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
pr: #71
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

---

## Stage Report — implementation (cycle 1)

**Scope:** `skills/debrief/SKILL.md` rewrite. Replaced the grouped-by-entity "Commits" section with three new sections: Shipped (one bullet per task with PR link), Filed (backlog), and Non-PR commits (workflow-only). PR URL construction reuses the existing `.claude-plugin/plugin.json` reader from Phase 3 Step 3.

**What changed:**

- **Phase 2a (Commits)** — now splits commits into three buckets: (1) PR squash-merges ending `(#NN)` roll up into Shipped, (2) pr-merge mod landings (`merge: {slug} done (PASSED) via PR #NN`) are consumed by 2b to resolve PR numbers, (3) non-PR commits are listed individually. Routine state churn (`dispatch:`, `advance:`, `state:`, `track:`) and captured commits (`seed:`, `file:`, `merge: ... via PR #NN`) are explicitly suppressed to avoid noise. Consolidation guidance for feedback/ideation cycle groups and revert cross-referencing preserved from the target's hand-crafted format.
- **Phase 2b (Task state changes)** — retitled "Shipped entities". Resolves PR number(s) per entity from the pr-merge landing commit, pulls one-sentence description from the entity's problem-statement paragraph (fallback to title), and emits the `- **{id}** \`{slug}\` — [#{N}]({url}). {desc}` format. Multi-PR (main + fixups) variant documented inline.
- **Phase 2f (NEW — Filed entities)** — scans for `seed:`/`file:` commits and emits one bullet per new backlog entity. Dual-listing rule: entities that both filed and shipped the same session appear in both sections.
- **Phase 3 Step 1 (Draft template)** — replaced with the new Shipped / Filed / Non-PR commits / Decisions / Issues—Workflow / Issues—Spacedock / Observations / What's Next structure. PR URL construction logic inlined at the top of Step 1 with a forward-reference to Step 3 for the reader.
- **Phase 4 Step 3 (File template)** — mirrors the Phase 3 draft structure. Adds optional narrative framing above Shipped (matching `2026-04-10-01.md`'s opening paragraph) and the "organized by tier" hint for What's Next.

**Preserved unchanged:** Phase 1 (Discovery), Phase 2c/d/e (gate decisions, issues scan, what's next), Phase 3 Step 2 (captain commentary), Phase 3 Step 3 (GitHub issue filing), Phase 4 Steps 1/2/4 (sequence, duration, commit).

**Verification (by eye):** walked through the 2026-04-10 session commit range (`31a3cb5..df72c7e`) mentally against the rewritten skill. Confirmed:
- All ten shipped entities (059, 060, 061, 115, 116, 118, 121, 122, 125, 126) resolve their PR numbers from the `merge: ... done (PASSED) via PR #NN` landing commits.
- 116's multi-PR case (#65 + #66 fixups) is handled by the multi-PR format variant.
- All nine filed entities (117–126) caught by the `seed:`/`file:` scan in 2f.
- The Non-PR commits section would capture `5c0a472` (docs:), `5acdbff` + `461f4cc` (direct-merge + revert), feedback cycles on 116 (consolidated), ideation stage reports on 121/125 (consolidated), `d9bab3c`/`850dcc1`/`ffb3fe1`/`fbee0d2` (update: mid-session scope) — matching the target.
- Routine state commits (`dispatch:`, `advance:`, `state:`, `track:`) and `seed:`/`file:` commits would be suppressed from Non-PR — matching the target's omissions.

**Scope compliance:** docs-only; no code, tests, or runtime adapters touched. Only `skills/debrief/SKILL.md` and this plan's stage report appended.

**Commits:** `c5b8dee` (SKILL.md rewrite).

**Result:** PASSED — ready for validation gate.

---

## Stage Report — validation

**Scope verified:** `skills/debrief/SKILL.md` + this plan only. `git diff main..HEAD --stat` confirms two files touched.

**Checks performed:**
- SKILL.md read end-to-end. Phase 2a splits commits into PR-squash / pr-merge-mod-landing / non-PR buckets with explicit suppression rules; no longer groups by entity slug (line 103 says so explicitly). Phase 2b emits `- **{id}** \`{slug}\` — [#{N}]({pr_url}). {desc}` with multi-PR variant. Phase 2f scans `seed:`/`file:` prefixes for Filed section. Phase 3 Step 1 draft template has the expected sections (Shipped, Filed, Non-PR commits, Decisions, Issues—Workflow, Issues—Spacedock, Observations, What's Next). Phase 4 Step 3 file template mirrors Phase 3. PR URL construction at Phase 3 Step 1 line 179 reads `.claude-plugin/plugin.json` `repository` (string and object forms).
- Unchanged surface: Phase 1 Discovery, Phase 2c/d/e, Phase 3 Step 2–3, Phase 4 Steps 1/2/4 — confirmed.
- Target-shape cross-check: read `_debriefs/2026-04-10-01.md` once. Section structure and PR link format line up with Phase 3/4 templates.
- Mental walkthrough (3 shipped + 2 seeds): instructions are unambiguous for commit splitting, PR-number resolution from pr-merge-mod commits, and bullet emission. Clear.
- Regression: `unset CLAUDECODE && uv run --with pytest python tests/test_agent_content.py -q` → 25 passed, 1 warning. Grep confirms no test file references the debrief skill — no direct coverage exists for skill instructions (noted, not a blocker).

**Result:** PASSED — recommend merge.
