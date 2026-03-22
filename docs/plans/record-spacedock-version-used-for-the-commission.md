---
title: Record Spacedock Version Used for the Commission
status: ideation
source: commission seed
started:
completed:
verdict:
score: 17
---

## Problem

When a pipeline is commissioned, there is no record of which version of Spacedock generated it. This means the future `/spacedock refit` command (see `refit-command.md`) has no baseline to diff against. Without knowing the original version, refit cannot distinguish between "Spacedock changed this template" and "the user customized this file" — making non-destructive upgrades impossible.

Currently `plugin.json` has `"version": "0.1.0"` but this is never written into generated pipelines.

## Proposed Approach

1. **Add a `spacedock-version` field to the pipeline README's YAML frontmatter** (or an HTML comment at the top). The commission skill writes the current Spacedock version from `plugin.json` into the generated README during Phase 2.

   Preferred format — an HTML comment in the README header:
   ```markdown
   <!-- commissioned-by: spacedock@0.1.0 -->
   ```
   This avoids polluting the README's visible content and is easy to grep for.

2. **Also record the version in the first-officer agent file**, using the same comment format. This lets refit know which first-officer template version was used.

3. **The commission skill reads the version from `plugin.json`** at generation time rather than hardcoding it. This ensures the recorded version always matches the actual plugin version.

4. **No version is recorded in entity files** — entities are user content, not generated templates. Version tracking is only for Spacedock-generated scaffolding (README, status script, first-officer).

## Acceptance Criteria

- [ ] The commission skill reads the version from `plugin.json` during Phase 2
- [ ] Generated `README.md` contains a `<!-- commissioned-by: spacedock@{version} -->` comment
- [ ] Generated `first-officer.md` contains the same version comment
- [ ] The status script contains a version comment in its header
- [ ] The version string matches the `version` field in `plugin.json`
- [ ] Existing pipelines (without version stamps) are handled gracefully by refit (treated as "unknown version")

## Scoring Breakdown

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Edge | 3 | Version tracking is standard practice |
| Fitness | 4 | Prerequisite for refit — important for pipeline longevity |
| Parsimony | 4 | Small change to the commission skill — add a comment to generated files |
| Testability | 3 | Can verify the comment exists; harder to test refit consumption |
| Novelty | 3 | Straightforward version stamping |

## Open Questions (Resolved)

- **Q: Should we use semver?** A: Yes, the version in `plugin.json` already follows semver. No additional format needed.
- **Q: Should the version be in YAML frontmatter or an HTML comment?** A: HTML comment. The README frontmatter is the pipeline schema — mixing in tool metadata would be confusing. HTML comments are invisible in rendered markdown but machine-readable.
- **Q: Should we stamp every generated file?** A: Only the three scaffolding files (README, status, first-officer). Entity files are user content.
