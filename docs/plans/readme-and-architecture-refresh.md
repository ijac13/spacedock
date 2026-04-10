---
id: 116
title: Refresh README and architectural docs for correctness and time-to-value
status: backlog
source: CL directive during 2026-04-10 session — after 115 validation dispatch
started:
completed:
verdict:
score:
worktree:
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
