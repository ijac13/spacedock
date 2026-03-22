---
title: Initial Project README
status: ideation
source: commission seed
started:
completed:
verdict:
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
   - **Quick start** — how to install the plugin and run `/spacedock commission`
   - **How it works** — brief description of the commission flow (interactive design, file generation, pilot run)
   - **Current status** — v0 shuttle mode (one pilot), what's planned for v1

3. **Tone:** Technical but accessible. Written for developers who use Claude Code and want structured agent workflows. Not marketing copy — practical and direct.

4. **Keep it under 150 lines.** A README that's too long defeats its purpose.

## Acceptance Criteria

- [ ] `README.md` exists at the repo root with ABOUTME comments
- [ ] Explains what Spacedock is in the first paragraph (no jargon without definition)
- [ ] Defines PTP and its core concepts (entity, pipeline, schema, views)
- [ ] Includes installation/usage instructions (even if minimal for v0)
- [ ] Accurately reflects the current v0 state — does not promise features that don't exist
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
