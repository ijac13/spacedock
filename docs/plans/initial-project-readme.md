---
title: Initial Project README
status: done
source: commission seed
started: 2026-03-22T20:24:00Z
completed: 2026-03-22T20:29:00Z
verdict: PASSED
score: 20
---

## Problem

The Spacedock project has no top-level README. Without one, anyone discovering the repo (human or agent) has no way to understand what Spacedock is, why it exists, or how to use it. The existing documentation is scattered across `v0/spec.md` (implementation spec), `skills/commission/SKILL.md` (skill prompt), and `agents/first-officer.md` (reference doc). None of these serve as an introduction.

A project without a README is effectively invisible — it can't attract contributors, and agents using it as a plugin have no orientation point.

## Proposed Approach

1. **Create a top-level `README.md`** at the repo root with ABOUTME comments.

2. **Structure:** The README should cover these sections in order:
   - **What Spacedock is** — a Claude Code plugin that turns directories of markdown files into lightweight project pipelines (PTP)
   - **What PTP means** — entity = markdown file with YAML frontmatter, directory = pipeline, README = schema + stages, views = self-describing scripts
   - **Why plain text pipelines** — git-native, agent-readable, no external dependencies, human-auditable, works offline
   - **Quick start** — how to install the plugin and run `/spacedock commission`. Installation is via `--plugin-dir` pointing to the local repo (there is no published registry yet in v0). The commission skill supports both interactive (one question at a time) and batch mode (all inputs in one message).
   - **How it works** — brief description of the commission flow (interactive design, file generation, pilot run). Mention the three phases without going deep — point to `v0/spec.md` for the full spec.
   - **Project structure** — show the directory layout so readers can orient themselves: `.claude-plugin/plugin.json` (manifest), `skills/commission/SKILL.md` (the skill), `agents/first-officer.md` (reference doc), `v0/spec.md` (spec). This replaces a lengthy prose explanation of each file.
   - **Current status** — v0 shuttle mode (one pilot agent handles all stages), what's deferred to v1 (starship mode with specialized crew, `/spacedock refit`, multi-pipeline orchestration)

3. **Tone:** Technical but accessible. Written for developers who use Claude Code and want structured agent workflows. Not marketing copy — practical and direct.

4. **Keep it under 150 lines.** A README that's too long defeats its purpose.

5. **Source material:** Draw from `v0/spec.md` for accuracy, but do not duplicate it. The README is an introduction that points readers to the spec for details.

## Acceptance Criteria

- [ ] `README.md` exists at the repo root with ABOUTME comments
- [ ] Explains what Spacedock is in the first paragraph (no jargon without definition)
- [ ] Defines PTP and its core concepts (entity, pipeline, schema, views)
- [ ] Includes installation/usage instructions — `--plugin-dir` for local use, since there's no registry yet
- [ ] Accurately reflects the current v0 state — does not promise features that don't exist
- [ ] Shows the project directory structure
- [ ] Points to `v0/spec.md` for the full specification (does not duplicate it)
- [ ] Under 150 lines
- [ ] No placeholder text or TODOs

## Scoring Breakdown

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Edge | 3 | Every project needs a README — not a differentiator |
| Fitness | 5 | Critical for project discoverability and onboarding |
| Parsimony | 5 | One file, straightforward content |
| Testability | 4 | Easy to verify — does it exist, is it accurate, is it clear |
| Novelty | 3 | Standard practice, but explaining PTP clearly to both humans and agents has some nuance |

## Open Questions (Resolved)

- **Q: Should the README include API documentation?** A: No. The README is an introduction. Detailed docs live in the spec and skill files.
- **Q: Should we include badges or CI status?** A: Not yet — there's no CI pipeline. Add badges when there's something to badge.
- **Q: How to describe installation without a plugin registry?** A: Show `--plugin-dir /path/to/spacedock` as the install mechanism. This is the real v0 workflow — no need to pretend otherwise. When a registry exists, update the README.
- **Q: Should we mention the dogfood pipeline at `docs/plans/`?** A: Yes, briefly. It demonstrates that Spacedock is already managing its own development, which is both practical context and a credibility signal.

## Implementation Summary

Created `/Users/clkao/git/spacedock/README.md` (101 lines). Sections: project intro with PTP definition, why plain text, PTP concepts table, quick start with `--plugin-dir` installation and commission walkthrough, project structure tree, generated pipeline structure, v0 status with what works and what's deferred, dogfood mention pointing to `docs/plans/`. Points to `v0/spec.md` for the full spec without duplicating it. No ABOUTME comments per markdown document convention.

## Validation Report

### Criterion Results

| # | Criterion | Result | Notes |
|---|-----------|--------|-------|
| 1 | `README.md` exists at repo root | **PASS** | File exists at `/Users/clkao/git/spacedock/README.md` |
| 2 | No ABOUTME comments (markdown doc exemption) | **PASS** | CLAUDE.md rule: "Do not add these to document files." Acceptance criteria originally said "with ABOUTME" but that conflicts with project rules. Correctly omitted. |
| 3 | Explains what Spacedock is in first paragraph | **PASS** | Line 3: "Spacedock is a Claude Code plugin for creating PTP (Plain Text Pipeline) pipelines." Defines PTP inline, no unexplained jargon. |
| 4 | Defines PTP core concepts (entity, pipeline, schema, views) | **PASS** | Lines 15-21: PTP Concepts table covers entity, pipeline, schema, stages, and views with clear one-line definitions. |
| 5 | Installation/usage with `--plugin-dir` | **PASS** | Lines 25-30: Shows `git clone` + `claude --plugin-dir /path/to/spacedock`. Lines 34-49: Walks through commission skill with six questions and batch mode mention. |
| 6 | Accurately reflects v0 state | **PASS** | Lines 82-97: Lists what works (commissioning, file generation, pilot run) and what's deferred (crew agents, refit, multi-pipeline, templates). Cross-checked against `v0/spec.md` "Not in v0" section — all deferred items match. Does not promise anything that doesn't exist. |
| 7 | Shows project directory structure | **PASS** | Lines 53-69: Tree showing `.claude-plugin/plugin.json`, `skills/commission/SKILL.md`, `agents/first-officer.md`, `v0/spec.md`, `docs/plans/`. All paths verified to exist on disk. |
| 8 | Points to `v0/spec.md` | **PASS** | Line 97: `See [v0/spec.md](v0/spec.md) for the full specification.` Does not duplicate spec content. |
| 9 | Under 150 lines | **PASS** | 101 lines (`wc -l` verified). |
| 10 | No placeholder text or TODOs | **PASS** | Grep for TODO/FIXME/placeholder/TBD returned no matches. |

### Minor Observations (not blocking)

- The spec (`v0/spec.md` line 16) shows `skills/commission/commission.md` as the skill filename, but the actual file is `skills/commission/SKILL.md`. The README correctly uses `SKILL.md` matching reality. The spec is slightly outdated on this point.
- The spec (line 12) shows `plugin.json` at repo root, but actual location is `.claude-plugin/plugin.json`. The README correctly reflects reality.
- The README mentions "first-officer agent" (line 78) is "generated per-pipeline at the target project root" — accurate per spec line 121-123.

### Recommendation

**PASSED** — All acceptance criteria met. The README is accurate, well-structured, concise at 101 lines, and correctly reflects v0 state. The ABOUTME omission is correct per project rules (markdown docs are exempt).
