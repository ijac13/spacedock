---
id: 116
title: Refresh README and architectural docs for correctness and time-to-value
status: validation
source: CL directive during 2026-04-10 session — after 115 validation dispatch
started: 2026-04-10T17:05:36Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-readme-and-architecture-refresh
issue:
pr:
---

Audit and update Spacedock's README and architectural documentation against two independent lenses: **correctness** (does the written material match how the system actually behaves today?) and **time-to-value for potential users** (can someone landing on the repo understand what this is, decide if they want it, and get a working first workflow up quickly?).

## Why now

Recent sessions have produced several observations suggesting the docs have drifted from reality and from a new user's needs:

- **Upstream Claude Code quirks** are documented in scattered task files (107 team-agent skill loading, 115 completion-signal missing from dispatch template) but not surfaced in any README or architectural overview. A new user hitting these will have no way to find the explanation.
- **Subagent context ceiling** — team-dispatched workers run on the 200k Opus variant, not the 1M variant the FO runs on, unless the user applies the `teammateDefaultModel: null` workaround from anthropics/claude-code#40929. This is a real operational constraint that users need to know before committing.
- **Scaffolding reality** — task 057's debrief note observed that `templates/` is gone but some docs may still reference it; commission/refit paths and the plugin marketplace flow may have moved. The plugin path (`skills/ensign`, `skills/first-officer`, `skills/commission`, runtime adapters per-platform) has been reorganized multiple times and nothing has audited the docs against the current layout.
- **First-run experience is opaque** — there is no clear "here is what Spacedock is, here is your first workflow in 5 minutes" path. Potential users likely bounce before understanding the value proposition.

## Scope

Two tracks, both in scope of this single task (ideation can decide whether to split):

### Track 1: Correctness audit

Inventory and review these documentation surfaces for factual drift:

- Repo-root `README.md` (if present)
- `docs/plans/README.md` — workflow-specific README with stages, schema, testing resources
- Any `AGENTS.md` / `CLAUDE.md` at repo root
- `skills/commission/SKILL.md` and related commission-flow docs
- `skills/ensign/SKILL.md` and runtime adapter references
- `skills/first-officer/SKILL.md` and runtime adapter references
- `tests/README.md` — test authoring guidelines
- Any standalone docs under `docs/` not already part of a workflow

For each, identify:
- Statements that are no longer true (e.g., references to removed directories, deprecated dispatch paths, obsolete stage behaviors)
- Assumptions that are contradicted by known upstream issues (e.g., task 107's "dispatch prompt is self-contained" was wrong; see 115)
- Cross-references that are stale (file moved, skill renamed, etc.)
- Known-issue surfaces that deserve prominent mention: Claude Code #30703 team-agent skill loading, anthropics/claude-code#40929 subagent model ceiling, completion-signal requirement in team mode

### Track 2: Time-to-value for potential users

The working assumption is that a potential user lands on the Spacedock repo and asks three questions in order:

1. **What is this?** Can they answer in under 60 seconds of reading?
2. **Do I want it?** Is the value proposition concrete — what problem does it solve, what workflows fit, what it is NOT good at?
3. **How do I try it right now?** Is there a path from "git clone" (or plugin install) to "running my first workflow with a live agent dispatch" that takes under 15 minutes?

For each of these, inventory the existing answer (if any) and produce concrete before/after proposals. Acceptable outputs include: a rewritten top-level README, a "Getting Started" section, a worked-example workflow, a terminology primer, a diagram of the FO → ensign → gate → merge loop.

Do not scope-creep into marketing copy, branding, or website work. This is repo-local docs only.

## Out of scope

- Writing new code or tests (docs-only task)
- Upstream issue filing against Claude Code (tracked separately; captain approval gate)
- Telemetry / watchdog work (will be its own task after 115 lands)
- Rebranding, logo, website, external marketing

## Starter questions for ideation

The ideation stage should resolve these before implementation:

- Is there a top-level `README.md` at the repo root today, and if so what does it cover? If not, is the plan to create one or to direct users to `docs/plans/README.md`?
- What's the canonical "first workflow" example to walk a new user through? Commission a plans/ workflow? Or something simpler?
- Should the known-issues section live in the main README, in a separate `docs/known-issues.md`, or inlined into the relevant SKILL.md files?
- Does the README need to explain the Claude Code plugin install path, the Codex path, or both?
- What's the minimum-viable value-prop paragraph — the two sentences that tell a potential user "if X, you want this"?

## Related

- Task 107 `team-agent-skill-loading-bug` — a known issue that belongs on the docs surface
- Task 115 `fo-dispatch-template-completion-signal` — in-flight; the fix + its implications should be reflected in docs
- anthropics/claude-code#40929 — subagent model ceiling, operational constraint to document

## Stage Report: ideation

### 1. Seed review — two-track scope and starter questions

- [x] Read the seed body (two-track scope: correctness audit + time-to-value; five starter questions; scope boundaries: docs-only, no upstream issue filing, no rebranding, no telemetry).
  Evidence: entity file lines 15–82 read in full. The five starter questions are enumerated in the "Resolve starter questions" section below.

### 2. Doc surface inventory

Candidate doc surfaces found by reading the repo tree and globbing markdown files outside `.worktrees/`, `_archive/`, `_mods/`, and `_debriefs/`:

| Path | Status | Notes |
|---|---|---|
| `README.md` (repo root) | exists (97 lines) | Already has Concepts, Quick Start, How It Works, Use Cases. Stale reference to `docs/plans/status`. |
| `AGENTS.md` (repo root) | exists (19 lines) | Self-hosted workflow boundaries — ensign vs non-ensign write scope. Correct but has no pointer TO the README from here. |
| `CLAUDE.md` (repo root) | absent | Codex instruction file exists (`AGENTS.md`). No equivalent for Claude Code at repo root. Not necessarily a drift — Claude Code reads agent skills from `skills/` and doesn't require a project-level `CLAUDE.md`. Flag only. |
| `docs/plans/README.md` | exists (202 lines) | Self-hosted workflow scaffolding. Workflow-artifact (refit-owned). Drift: three stale status-script invocations (lines 132, 140, 146) use the broken positional-path form. |
| `skills/commission/SKILL.md` | exists (~480 lines) | Correct in structure; references `{spacedock_plugin_dir}/skills/commission/bin/status` with `--workflow-dir`. No obvious drift. |
| `skills/first-officer/SKILL.md` | exists (18 lines) | Thin pointer: loads shared core + code-project-guardrails and a runtime adapter. Correct. |
| `skills/first-officer/references/first-officer-shared-core.md` | exists (~188 lines) | Operational contract. Does NOT mention #40929 or the 115 completion-signal. Correct for its scope (how to orchestrate) but silent on known upstream issues. |
| `skills/first-officer/references/claude-first-officer-runtime.md` | exists (~102 lines) | Claude Code runtime adapter. Contains the dispatch template that 115 is modifying. Currently lacks completion-signal instruction (that is the 115 fix, PR #62 open). |
| `skills/first-officer/references/codex-first-officer-runtime.md` | exists | Not read in this pass (low-priority; Codex path is experimental). Mark as secondary. |
| `skills/first-officer/references/code-project-guardrails.md` | exists | Not read in this pass. Mark as secondary. |
| `skills/ensign/SKILL.md` | exists (17 lines) | Thin pointer. Correct. |
| `skills/ensign/references/ensign-shared-core.md` | exists (~57 lines) | Correct. |
| `skills/ensign/references/claude-ensign-runtime.md` | exists (~32 lines) | Contains the canonical `## Completion Signal` wording that team-dispatched ensigns can't see because of #30703. |
| `skills/ensign/references/codex-ensign-runtime.md` | exists | Not read in this pass. Secondary. |
| `skills/refit/SKILL.md` | exists (~253 lines) | Structurally correct; Degraded Mode documented. No obvious drift for this audit. |
| `skills/debrief/SKILL.md` | exists (~267 lines) | Correct. Out of critical path for this audit. |
| `tests/README.md` | exists (~188 lines) | Test authoring guidelines. Correct. |
| `agents/first-officer.md` | exists (16 lines) | Thin wrapper (skill preloading). Correct. |
| `agents/ensign.md` | exists (14 lines) | Thin wrapper. Correct. |
| `docs/comparison.md` | exists | Competitive analysis, March 2026 date-stamped. Content correct; not a "getting started" surface. |
| `docs/research-skill-tool-team-restriction.md` | exists | Research note. Out of scope for the refresh. |
| `docs/research/workflow-optimization-prior-art.md` | exists | Research note. Out of scope. |
| `docs/agent-feedback/2026-03-29.md` | exists | Session feedback note. Out of scope. |
| `docs/superpowers/plans/*.md`, `docs/superpowers/specs/*.md` | exist | Superpowers-plan artifacts (a different workflow directory under docs). Out of scope for this refresh — owned by the superpowers workflow. |
| `references/codex-tools.md` (repo root) | exists | Vestigial tool-mapping research file. A single file in a repo-root `references/` directory that only exists to hold it. Candidate for relocation to `docs/research/` or deletion in a separate task. Flag only. |
| `tests/fixtures/*/README.md` (13 files) | exist | Fixture READMEs. Out of scope — these document individual test fixtures. |
| `scripts/test-harness.md` | exists | Referenced from `docs/plans/README.md` Testing Resources table. Not audited in this pass; worth a correctness spot-check during implementation. |
| `templates/` (repo-root) | **absent** | Confirmed. Task 057 debrief note was correct — no `templates/` directory exists, and no active docs reference it. The `templates/` drift has already been naturally cleaned up. No action needed. |

Absent directories I checked explicitly: `templates/` (gone, no references). Present directories not surfaced as docs: `mods/` (contains `pr-merge.md` as an asset), `references/` (see above), `scripts/` (utility scripts + `test-harness.md`).

**Inventory size:** ~17 primary surfaces (excluding experimental Codex runtime files, secondary research notes, and test-fixture READMEs). The correctness audit's scope is tractable.

### 3. Correctness audit — concrete drift list

Findings are specific: each item quotes or references the offending content and proposes a concrete fix.

**3.1 `README.md` line 96 — stale status-script path.**

> Quote: `Spacedock is self-hosted and bootstrapped: it manages its own development with a plain text workflow at [docs/plans/](docs/plans/). Run docs/plans/status to see the current state.`

Drift: `docs/plans/status` does not exist. The status script now ships with the plugin at `skills/commission/bin/status` and must be invoked via `python3 skills/commission/bin/status --workflow-dir docs/plans`.

Fix (proposed wording):

> Spacedock is self-hosted and bootstrapped: it manages its own development with a plain text workflow at [`docs/plans/`](docs/plans/). Run `python3 skills/commission/bin/status --workflow-dir docs/plans` to see the current state.

**3.2 `docs/plans/README.md` lines 132, 140, 146 — broken status-script invocations (positional path).**

> Quotes:
> - L132: `` ```bash\nskills/commission/bin/status docs/plans\n``` ``
> - L140: `` ```bash\nskills/commission/bin/status docs/plans --archived\n``` ``
> - L146: `` ```bash\nskills/commission/bin/status docs/plans --next\n``` ``

Drift: I verified at the shell that `python3 skills/commission/bin/status docs/plans` silently returns an empty table (no entities, zero exit code) — this is a silent failure, not just a recommendation drift. The script requires `--workflow-dir` to find entities. The positional form may have worked in an older revision.

**IMPORTANT — scope note:** `docs/plans/README.md` is a workflow-artifact owned by refit (see `AGENTS.md`, "Ensigns must NOT edit" list). The FO cannot modify it and ensigns shouldn't either. There are two options to address this drift:

- (a) Treat it as refit-material: fix the generated template in `skills/commission/SKILL.md` and upgrade `docs/plans/README.md` via `/spacedock:refit`. Commission already uses the correct `--workflow-dir` form (SKILL.md lines 301, 309, 315). So refit would naturally fix it the next time it runs. **No code change needed in commission.**
- (b) As a one-time carve-out, patch the three lines directly. Requires captain approval because it touches a refit-owned file.

**Recommendation:** Option (a) — surface this as a refit trigger, not as scope of this task. Add a note to the implementation Stage Report when the time comes.

Fix (proposed wording for each line):

> ```bash
> python3 skills/commission/bin/status --workflow-dir docs/plans
> ```
> (and `--archived` / `--next` variants appended after `docs/plans`)

**3.3 `README.md` section "What Gets Generated" line 81 — lists `skills/commission/bin/status` as generated, but it is plugin-shipped.**

> Quote: `- **skills/commission/bin/status** -- plugin-shipped status viewer used against the workflow directory`

Drift: this bullet is IN the "## What Gets Generated" section alongside `{dir}/README.md` and `{dir}/*.md`, which implies generated-per-workflow. It is explicitly labeled "plugin-shipped" inline, but listing it under "What Gets Generated" is misleading. Similarly, `agents/first-officer.md` on line 80 is listed as "plugin-shipped AI agent" in a "what gets generated" section, which is contradictory (the plugin ships it; commission does not generate a local copy any more).

Fix: split the "What Gets Generated" section into two subsections — "Generated into your workflow directory" (`{dir}/README.md`, `{dir}/*.md`, optionally `{dir}/_mods/`) and "Shipped by the Spacedock plugin" (`spacedock:first-officer`, `spacedock:ensign`, the status viewer). This removes the ambiguity.

**3.4 `README.md` — Known-issues surface is entirely absent.**

The README has no mention of:
- `anthropics/claude-code#40929` (subagent model ceiling — `teammateDefaultModel: null` workaround)
- Claude Code `#30703` (team-agent skill loading bug — task 107)
- The completion-signal team-mode requirement (task 115, PR #62)

A new user hitting any of these has no way to find the explanation. The seed explicitly flags these three as things that "belong on the docs surface."

Fix: decide on a location (see starter-question 3 below) and add a "Known Issues" section. **Recommendation:** add a short "Known Issues" subsection in the README with one-line summaries and links to authoritative sources — task entities in `docs/plans/` and upstream GitHub issue numbers. Keep it short; don't re-document bugs.

**3.5 `README.md` line 5 — Quick-start line says "Experimental support for other coding agents."**

> Quote: `Install it as a Claude Code plugin. Run /spacedock:commission to design a workflow, and claude --agent spacedock:first-officer to run it. Experimental support for other coding agents.`

Not a correctness drift per se — the Codex runtime adapters exist and "experimental" is accurate. No fix needed; flag only.

**3.6 `README.md` "Local Development" section — incomplete command.**

> Quote: `claude --plugin-dir /path/to/spacedock`

Drift: `claude --plugin-dir` is not a complete invocation pattern — it typically needs to be paired with `--agent spacedock:first-officer` (or equivalent) to actually run the FO. Users running this will get a bare Claude session with the plugin loaded but no agent selected. Also, the typical command for local development is `claude --plugin-dir . --agent spacedock:first-officer` when run from the spacedock source tree itself, or `claude --plugin-dir /path/to/spacedock --agent spacedock:first-officer` from a target project.

Fix: clarify the command. Proposed:

> ```bash
> # From inside the spacedock repo:
> claude --plugin-dir . --agent spacedock:first-officer
> # From a separate project directory:
> claude --plugin-dir /path/to/spacedock --agent spacedock:first-officer
> ```

**3.7 `README.md` "Concepts" table — `First officer` description is opaque for a first-time reader.**

> Quote: `The plugin-shipped spacedock:first-officer agent that reads workflow state, dispatches ensigns, and reports to you at gates`

Not a drift; it's a clarity gap. First-time readers encountering "dispatches ensigns" haven't yet learned what an ensign is. The row order in the table lists "First officer" before "Ensign". Minor; fix by swapping rows or making the definition self-contained.

**3.8 `first-officer-shared-core.md` — no mention of known upstream issues.**

This is the right place for an Operations / Known Issues section? Or not. The shared core is an operational contract. Adding upstream-bug awareness to it risks polluting behavioral guidance. **Recommendation:** do NOT add known-issue content to the operating contract; keep it in README / a dedicated known-issues page. Mark as "no change".

**3.9 `AGENTS.md` — no entry point for a new human contributor.**

`AGENTS.md` only talks about ensign write-scope boundaries. For a Codex user landing on the repo, this file is their primary context but it says nothing about what Spacedock is, how to run it, or where the README lives. Not a drift, but a gap.

Fix (optional): add a one-paragraph pointer at the top: "Spacedock is a Claude Code plugin. See `README.md` for user-facing docs. This file describes ensign write-scope boundaries for agents working on Spacedock itself."

**3.10 `references/codex-tools.md` (repo-root) — orphaned research asset.**

Not a drift in content, but its placement (repo-root `references/` with a single file) is misleading — users might confuse it with `skills/first-officer/references/` (operational references). Flag for a cleanup task: relocate to `docs/research/` or delete. **Out of scope for this refresh.**

**3.11 Stale references to task 107's incorrect assumption.**

Task 107 currently documents: "Completion protocol — SendMessage back to FO works (learned from dispatch prompt)" — this is wrong (task 115 corrected it). 107 is an entity file, not a doc surface, but if we add a Known Issues section pointing at 107, readers may be misled. 115's body already notes this. **Action:** when 115 lands, the validator or a follow-up should update task 107's body to remove the false claim. Out of scope for this refresh (touches an entity body, not a doc surface).

**Summary of 3:** 11 concrete findings. 6 are in-scope fixes for this task (3.1, 3.2 via refit, 3.3, 3.4, 3.6, 3.7). 5 are flag-only or out-of-scope (3.5, 3.8, 3.9 optional, 3.10, 3.11).

### 4. Time-to-value audit — three starter questions

For each, record current state, gap, and dependencies.

**Q1: "What is this?"**

- Current state: **partial**. README.md line 3 gives the canonical 2-sentence answer: *"Spacedock turns directories of markdown files into structured workflows operated by AI agents. Each file is a work item that moves through defined stages. An AI first officer manages the workflow: dispatching subagents, isolating work in git worktrees, and pausing at approval gates for human review."* This is good. The follow-up line 5 *"Install it as a Claude Code plugin..."* is an install instruction, not a what-is-this.
- Gap: the paragraph is present but there is no visual/structural aid. A reader scanning quickly sees a wall of text with no diagram. Proposed addition: a small ASCII or mermaid diagram showing `captain → first-officer → ensigns → gates → merge` right after the first paragraph. Optional; the text answer is already sufficient for a 60-second read.
- Dependencies: none. The answer is already correct.

**Verdict:** Q1 is ~80% there. Recommend keeping the first paragraph verbatim; optionally add a one-line "TL;DR diagram" and nothing else. Low-effort, high-clarity.

**Q2: "Do I want it?"**

- Current state: **partial**. The "Why Plain Text Workflows?" bullet list (README lines 7–13) names 5 value propositions: agent-native, flexible-yet-enforceable, declarative human-in-the-loop, plain-text state, composable. The "Use Cases" section (lines 89–96) lists four concrete scenarios: feature tracking, email triage, content publishing, research workflows.
- Gap: there's no **"not good at"** section. A mature README names its anti-patterns: "do not use Spacedock if you want…". Without this, users bounce after trying and hitting friction they weren't warned about. Examples of honest anti-patterns for Spacedock:
  - You want a UI / Kanban board (Spacedock is terminal + markdown — see `docs/comparison.md`)
  - You want cloud multi-user collaboration (no such thing — git-native only)
  - You want deterministic non-agent automation (Spacedock assumes an agent-operator)
  - You need strict, contractual workflows with transactions (markdown-in-git state is not that)
- Also missing: an explicit target-user sentence. Two-sentence "if X, you want this" proposal:
  > **Who this is for:** Solo technical operators or small teams who want declarative, git-native work-tracking that an AI agent can operate end-to-end, with human approval gates where they matter. **Who this is not for:** teams who need a web UI, cloud multi-user state, or non-AI workflow automation.
- Dependencies: Q2 should reference Q1's diagram if we add one. Otherwise standalone.

**Verdict:** Q2 is ~60% there. Needs a "Who this is for / not for" paragraph and an honest "not good at" clarification. Low effort.

**Q3: "How do I try it right now?"**

- Current state: **partial**. Quick Start (lines 30–59) has the plugin-install command, then `/spacedock:commission`, then `claude --agent spacedock:first-officer`. The commission args-passing examples are good. What's missing:
  - A **worked example** from one command to a visible first result. The current flow says "run commission, answer questions, run first officer" but gives no picture of what a completed run looks like.
  - No explicit **"your first 15 minutes"** section telling a reader what to expect at each step.
  - No explicit **prerequisites** (Claude Code installed? gh CLI? git? uv?).
  - No explicit **"what will I see on success?"** — the happy-path output a user can compare against.
  - The "Local Development" section has a bug (item 3.6 above).
- Gap: a "Getting Started" or "First Run Walkthrough" section. Proposed content:
  - Prerequisites line: Claude Code ≥ v2.1, git, python3 (for the status script). gh only if using PR merge mod.
  - A worked example using the simplest possible mission, e.g. `/spacedock:commission track book ideas through review to decision` — walks through the three commission questions, shows the generated tree, runs the FO, shows the first dispatch.
  - "You have succeeded if:" a short checklist — e.g. "you see a `status: backlog` → `status: ideation` transition in one of your seed files and a commit with prefix `dispatch:`".
- Known-issues integration: the 15-minute path should briefly warn about the three known issues the reader is likely to hit immediately if they're running in interactive Claude Code with team mode — #40929 (model ceiling), #30703 (team agent skill loading), and a pointer to where to check status.
- Dependencies: Q3 depends on Q1 (reader knows what it is) and on the 3.1/3.3/3.4/3.6 correctness fixes (so the commands in the walkthrough work).

**Verdict:** Q3 is ~40% there. This is the biggest gap and the most valuable addition. Medium effort.

**Aggregate:** Time-to-value is the dominant concern. Correctness drift is small (~6 concrete fixes). Onboarding gap is large.

### 5. Track split decision

**Decision: keep as a single task 116.**

Justification:
- Coupling: Track 2 (time-to-value) depends on Track 1 (correctness) — the Getting Started walkthrough uses commands that must be correct.
- Complexity: the correctness audit found only 6 in-scope fixes, all low-effort. Splitting would add coordination overhead disproportionate to the work.
- PR size: a single PR that lands all README and affected-doc changes in one review is easier to grade than two staggered PRs that cross-reference each other.
- Risk: docs-only, so merge-conflict risk is minimal even with a larger single PR.
- If implementation discovers the PR is too large, the implementer can split at that point with captain approval. Keeping it unified for ideation does not preclude splitting later.

### 6. Acceptance criteria (verifiable)

Every AC names the file, the section, the required content, and the test method.

**AC-1: README.md line 96 status-script fix.**
- Requirement: `README.md` must NOT contain the string `docs/plans/status` as a runnable command. It must contain `python3 skills/commission/bin/status --workflow-dir docs/plans` (or an equivalent that uses `--workflow-dir`).
- Test: `grep -n 'docs/plans/status' README.md` returns no lines that refer to a runnable command; `grep -n 'skills/commission/bin/status --workflow-dir' README.md` returns at least one line.

**AC-2: README.md "What Gets Generated" section must distinguish plugin-shipped from generated assets.**
- Requirement: the section must have two subsections (or two lists) labeled to separate "Generated into your workflow directory" from "Shipped by the Spacedock plugin"; the plugin-shipped list must include `spacedock:first-officer`, `spacedock:ensign`, and the status viewer.
- Test: `grep -n 'Shipped by the Spacedock plugin' README.md` returns one line inside the "## What Gets Generated" section; the three items appear as bullets beneath it.

**AC-3: README.md Known Issues section exists and names the three upstream issues.**
- Requirement: README.md contains a `## Known Issues` (or `### Known Issues` under "How It Works") section that names:
  1. Team-agent skill loading (link to `anthropics/claude-code#30703` and task 107)
  2. Subagent model ceiling (link to `anthropics/claude-code#40929`)
  3. Team-mode completion-signal requirement (link to task 115 and PR #62; once merged, link to the commit)
- Test: `grep -n 'Known Issues' README.md` returns one heading line; `grep -nE '30703|40929|115|#62' README.md` returns at least three lines; all mentioned references resolve (manual link check or `lychee` run).

**AC-4: README.md "Who this is for / not for" paragraph exists.**
- Requirement: README.md contains a paragraph or heading that explicitly names the target user in one sentence and the anti-target in one sentence. The anti-target must name at least two of {UI/Kanban, cloud multi-user, deterministic non-agent automation}.
- Test: first-impression check — a fresh reader (human or subagent) reads the first 40 lines of README.md and can answer in one sentence "is this for me?".

**AC-5: README.md Getting Started walkthrough exists.**
- Requirement: README.md contains a `## Getting Started` (or `## First Run`) section that includes:
  - A prerequisites line (Claude Code, git, python3, optional gh)
  - A worked example with a specific mission string (the implementer picks one)
  - An observable-outcome line ("you have succeeded if…")
- Test: structural grep for `## Getting Started` (or equivalent); a fresh-reader dry-run — after reading only this section, can the reader state the first command they will run and what they expect to see?

**AC-6: README.md Local Development command is complete.**
- Requirement: the Local Development code block pairs `--plugin-dir` with `--agent spacedock:first-officer` (or equivalent), covering both the in-source-tree case and the separate-target-project case.
- Test: `grep -nE 'plugin-dir.*agent spacedock:first-officer' README.md` returns at least one line.

**AC-7: No new broken internal links.**
- Requirement: all markdown internal links in the updated files resolve to existing paths.
- Test: `lychee --offline README.md docs/**/*.md skills/**/*.md` (or a manual grep-and-ls loop) returns zero broken links.

**AC-8: docs/plans/README.md drift is either fixed or explicitly deferred.**
- Requirement: EITHER the three stale status-script invocations in `docs/plans/README.md` (lines 132, 140, 146) are corrected to use `--workflow-dir`, OR a note in the implementation Stage Report documents the deferral to refit with the reasoning.
- Test: `grep -n 'skills/commission/bin/status docs/plans' docs/plans/README.md` returns zero lines (if fixed), OR the implementation Stage Report contains a `deferred to refit` entry naming these three lines.

**AC-9: First-impression proxy — fresh reader can answer the three time-to-value questions.**
- Requirement: a fresh reader (independent subagent spawned for this check, or a human cold-read) can, after spending under 3 minutes reading the updated README.md:
  1. Describe what Spacedock is in one sentence.
  2. State whether they are in the target audience and justify with one sentence.
  3. Name the first command they would run to try it, and state the expected first observable outcome.
- Test: during validation, dispatch a fresh reader subagent with a simple prompt ("read README.md at the project root, do not read other files, then answer these three questions"). Pass only if all three answers are substantively correct.

### 7. Test plan

Proportional to the task. Docs-only, not E2E territory.

**7.1 Static checks (cheap, required):**
- `grep` assertions for each AC in section 6. These can live in a single bash checklist that the validator runs. Cost: trivial.
- Optional markdown link check via `lychee --offline` (if installed) on the affected files. If lychee isn't present, manual grep-and-resolve for the updated files. Cost: trivial-to-low.

**7.2 Fresh-reader dry-run (required, medium-cost):**
- Dispatch an independent subagent during validation with a minimal prompt: "read only `README.md` at the project root; do not read any other files; answer three questions: (1) what is this? (2) is this for me? (3) what's the first command you would run?" Score by whether the three answers are substantively aligned with the updated README.
- Cost: one subagent dispatch, low token count (README is short).
- Complexity: low.

**7.3 Verification against the current commission/refit skills (structural):**
- Check that the updated README's Quick Start commands match what `skills/commission/SKILL.md` actually tells a user to do. If the README and commission SKILL diverge on what a user should run, that's a drift to catch now.
- Cost: manual read.

**7.4 E2E: NOT NEEDED.** Docs-only change. No code path exercised.

**7.5 Out of scope for tests:**
- Actually running `/spacedock:commission` end-to-end. That is commission-test-harness territory (task 115's E2E test already does this).
- Running the full `uv run tests/…` suite. Docs don't touch the python test code.

**Cost estimate:** 1 subagent dispatch + some grep. Complexity: low. No test-framework changes needed.

### 8. Resolve starter questions (5 from seed)

**Q-a: Is there a top-level `README.md` at the repo root today, and if so what does it cover? If not, is the plan to create one or to direct users to `docs/plans/README.md`?**

Yes. `README.md` exists (97 lines). It covers: one-paragraph pitch, why-plain-text-workflows bullets, concepts table, Quick Start (plugin install + commission + run), Local Development, How It Works, What Gets Generated, Use Cases. **Plan: extend the existing README in place** — do not create a new one. Do not redirect users to `docs/plans/README.md` (which is a workflow-artifact for Spacedock's own self-hosted development, not a user-facing README).

**Q-b: What's the canonical "first workflow" example to walk a new user through? Commission a plans/ workflow? Or something simpler?**

A simple commission workflow, not a plans workflow. Specifically: a 3-stage "track book ideas" or "track meeting notes" example with 2 seed entities and no approval gates. Rationale: it's mission-neutral, does not assume the reader is a developer, avoids the bootstrap confusion of Spacedock's own `docs/plans/` (which is meta — Spacedock using itself), and exercises the commission → FO → first dispatch path in under 5 minutes. The implementer picks the exact mission string; any 3-stage linear example works.

Defer: the exact mission string is an implementer choice — state the constraints ("3 stages, linear, no gates, mission-neutral domain, 2 seed items") but do not hardcode the string in the ideation.

**Q-c: Should the known-issues section live in the main README, in a separate `docs/known-issues.md`, or inlined into the relevant SKILL.md files?**

**Main README, short form.** One subsection under "How It Works" or at the bottom. Keep it to 3–5 bullets, each a one-liner with a link. Do NOT create a separate `docs/known-issues.md` — that adds an extra surface to maintain and separates issues from the place users will actually see them. Do NOT inline into SKILL.md files — SKILL.md files are operational contracts for agents and should not be polluted with upstream-bug narrative.

If a known issue needs long-form explanation, link from the README to the task entity in `docs/plans/` (e.g., `docs/plans/team-agent-skill-loading-bug.md`) — these already exist and are authoritative.

**Q-d: Does the README need to explain the Claude Code plugin install path, the Codex path, or both?**

**Claude Code only for the Quick Start.** Codex is experimental and should be mentioned in a short "Other Runtimes" paragraph that says something like: "Spacedock has experimental Codex support via the `references/codex-*-runtime.md` adapters. The Claude Code path is the primary supported surface. File an issue if you want to help with Codex parity." Keep it to 2 sentences. Do not write a Codex getting-started — that's its own task if the Codex path ever reaches parity.

**Q-e: What's the minimum-viable value-prop paragraph — the two sentences that tell a potential user "if X, you want this"?**

Proposed (to be refined by the implementer; this is a concrete draft the implementer can adopt or iterate on):

> **You want Spacedock if:** you run an agent-assisted development or knowledge workflow where work items are natural markdown files, approval gates matter, and you want the whole thing to live in git with no external services. **You do not want Spacedock if:** you need a UI, cloud multi-user collaboration, or non-agent workflow automation.

This is the target for AC-4. The implementer may adjust phrasing; the structure ("want it if" + "don't want it if", each one sentence) is the contract.

### 9. Commit instructions

After writing this stage report, commit to `main` (not a worktree — ideation is no-worktree stage):

```bash
git add docs/plans/readme-and-architecture-refresh.md
git commit -m "ideation: readme-and-architecture-refresh stage report"
```

Then send the one-time bootstrap completion signal via `SendMessage(to="team-lead", ...)` as specified in the dispatch body.

### Summary

Spacedock's docs are in reasonable shape but have accumulated small, specific drift (6 concrete in-scope fixes) and a larger time-to-value gap (no Getting Started walkthrough, no "who this is for / not for" paragraph, no known-issues surface). The correctness audit is small enough that Track 1 + Track 2 should stay in a single task. The largest single win is the Getting Started section plus the known-issues callout, which together close most of the 3-minute onboarding gap. The ideation resolves all five seed questions, produces nine verifiable ACs with explicit test methods, and scopes the test plan at static grep checks plus a fresh-reader subagent dry-run — no E2E, no code changes, docs-only.

### Feedback Cycles

**Cycle 1** (2026-04-10 17:50Z) — Captain REJECTED at validation gate.

All 9 mechanical ACs passed, but a parallel staff DevRel reviewer recommended REVISE with 3 P0 blockers that the structural ACs did not catch. The captain accepted the DevRel findings and added additional directives compressing the Getting Started walkthrough. The full feedback has been routed to the kept-alive implementation ensign via SendMessage. Summary of fixes requested this cycle:

- **DevRel P0-1:** Move Concepts table to after Quick Start (the vocabulary landing needs context first).
- **DevRel P0-2:** Move Known Issues above Getting Started, as a "Before You Start" section, so team-mode users see the FO-hang warning before they hit it.
- **DevRel P0-3:** Python3 pre-flight — **subsumed** by the captain's Getting Started rewrite (see below).
- **DevRel P1-1:** Fix L5 three-commands-in-one-sentence.
- **DevRel P1-2:** Remove or relocate "experimental support for other coding agents" noise.
- **DevRel P1-3:** Default `git clone` to HTTPS instead of SSH.
- **DevRel P2-1 / P2-2:** Workflow directory naming phrasing; self-referential `docs/plans/` example relocation.
- **Captain directive:** Getting Started is too long — make it much shorter.
- **Captain directive:** Prerequisites reduce to just "claude or codex" (no python3, git, gh itemization).
- **Captain directive — Claude path:** marketplace install → launch as first officer → run `/spacedock:commission`. Compressed sequence.
- **Captain directive — Codex path:** add a symlink install into `~/.agents/skills/spacedock` (ensign must figure out exact target — likely `ln -s /path/to/spacedock/skills ~/.agents/skills/spacedock` or similar; consult `skills/first-officer/references/codex-first-officer-runtime.md` and `skills/ensign/references/codex-ensign-runtime.md` for the canonical path).
- **Captain addendum (sent mid-cycle):** Concepts table is too implementation-detailed ("The plugin-shipped `spacedock:ensign` worker" etc.). Strip the implementation labels and surface the three user-visible value props early in the README instead: **approval (gates)**, **worktree isolation**, and **declarative & flexible** (plain-text markdown, no runtime, trivially editable and forkable). The Concepts table itself should become much shorter and lose the `spacedock:ensign` / "plugin-shipped" phrasing.

Cycle 1 outcome: implementation applied cycle 1 + addendum. Validation cycle 2 PASSED (all 9 ACs + structural ordering). DevRel cycle 2 said SHIP (0 P0 blockers). Strict AC-9 fresh reader PASS. The captain nonetheless rejected at the cycle-2 gate with new directional guidance (below).

**Cycle 2** (2026-04-10 18:25Z) — Captain REJECTED at cycle-2 validation gate with directional feedback. Routing back to implementation. Items are directional (not exact phrases) — the implementer is expected to apply the intent, not mechanical substitutions.

1. "every change reviewable as a normal git diff" — not helpful framing. Replace with something like "concise and high-signal evidence for approval" (stage reports give the captain approval-grade evidence).
2. "You want Spacedock if" — rewrite the two clauses: (a) "you are a human tired of switching between agent sessions for approval decisions"; (b) "you are an agent that wants to help a human manage repeatable tasks without bothering them for every tiny decision".
3. Worktree isolation is NOT always-on — it's on-demand. The first officer decides whether a stage's work needs isolation. Capture it as optional / as-needed, not universal.
4. Avoid the "No X, no Y, just Z" sentence pattern anywhere it appears.
5. Move the Invictus (Henley) quote to immediately before or after the Captain concept in the Concepts table (implementer's judgment which side).
6. Add a note encouraging users to run in a sandbox so they can safely bypass permission prompts. Also mention Claude Code's agent team support so the captain can optionally chat directly with subagents (Shift+Up/Down) to give feedback without routing through the first officer.
7. "Inside your first-officer session" framing is confusing. Support a faster one-command startup: `claude --agent spacedock:first-officer "/spacedock:commission $prompt"`. Implementer must verify the exact syntax works with the current Claude Code CLI. Add two specific example commissions:
   - **(a) Email triage:** fetch, categorize, and act on Gmail inbox. Entity = a batch of up to 50 emails. Stages: intake (use gws-cli, `triage in:inbox` and read email body if necessary, categorize, propose action per email, output as table) → approval (captain reviews proposal) → execute (carry out approved actions, do NOT mark as read). Use `gws-cli` (https://github.com/googleworkspace/cli/tree/main/skills/gws-gmail), `GOOGLE_WORKSPACE_CLI_CONFIG_DIR=~/.config/gws/<account>` for different accounts. Walk the user through gws-cli setup if not already done.
   - **(b) Dev task workflow:** superpowers-style design → plan → implement → review, with `## Design` and `## Implementation Plan` inlined in the entity body (no separate spec/plan files). Implement on isolated worktrees with strict TDD. Design and review stages gated for approval.
8. Drop `codex exec` from the Codex Quick Start — show only interactive Codex.
9. Known Quirks don't belong in a user-facing README. Remove the "Before You Start — Known Quirks in Team Mode" section entirely. (Cycle 1 moved it above Getting Started; cycle 2 removes it outright.)
10. Mission is not a role — drop the Mission row from the Concepts table.
11. "Generated into your workflow directory:" → reword to frame the generation as "when a workflow is commissioned".
12. Drop the Local Development section entirely. That's contributor-facing, not user-facing.
13. Add a License section (repo has a LICENSE file — check it and link/cite appropriately).
14. Drop the standalone Dogfooding section. Instead, add "dogfooding Spacedock's own development" as one item in the existing Use Cases list.

**Additional additive:** mention the session debrief skill (`skills/debrief/SKILL.md`) somewhere in the README — either as a Use Case bullet or in a brief "and more" mention in How It Works / Use Cases.

Fresh validation + DevRel cycle-3 review will be dispatched after the implementation ensign reports the fix round complete. **Note:** this is cycle 2 of feedback; one more rejection would hit the 3-cycle escalation limit and force human escalation instead of another automatic round. The 116 impl ensign's context budget is at 80.7% of 200k as of cycle 2 start — implementer may need to work tersely or escalate to fresh dispatch if context becomes a problem.



