---
title: Record Spacedock Version Used for the Commission
status: done
source: commission seed
started: 2026-03-22T20:24:00Z
completed: 2026-03-22T20:29:00Z
verdict: PASSED
score: 0.68
---

## Problem

When a pipeline is commissioned, there is no record of which version of Spacedock generated it. The future `/spacedock refit` command (see `refit-command.md`) needs a baseline to diff against — without the original version, refit cannot distinguish "Spacedock changed this template" from "the user customized this file," making non-destructive upgrades impossible.

Currently `.claude-plugin/plugin.json` has `"version": "0.1.0"` but this is never written into generated pipelines. Confirmed by inspection: the commission skill (`skills/commission/SKILL.md`) has no reference to `plugin.json`, and the existing dogfood pipeline (`docs/plans/`) contains no version stamp in the README, status script, or first-officer agent.

## Proposed Approach

### Implementation mechanism

The commission skill is a prompt (SKILL.md), not executable code. It cannot programmatically read `plugin.json`. Instead, the skill prompt must instruct the executing agent to:

1. Read `.claude-plugin/plugin.json` (relative to the Spacedock plugin directory, not the target project) at the start of Phase 2.
2. Extract the `version` field.
3. Embed the version string into each generated scaffolding file.

The Spacedock plugin directory is the directory containing the `skills/` folder — the agent can resolve this from its own plugin context.

### Version stamp format

Each generated scaffolding file gets a version comment in its native comment syntax, placed as the first line (or after the ABOUTME lines where those exist):

- **README.md** — `<!-- commissioned-by: spacedock@0.1.0 -->`
- **first-officer.md** — `commissioned-by: spacedock@0.1.0` (YAML frontmatter field, since an HTML comment before `---` would break frontmatter parsing)
- **status script** — `# commissioned-by: spacedock@0.1.0` (bash comment, after the shebang)

The HTML comment format avoids polluting visible markdown content. The bash comment format is native to the status script. Both are easy to grep for with a single pattern: `commissioned-by: spacedock@`.

### What gets stamped

Only Spacedock-generated scaffolding: README, status script, first-officer agent. Entity files are user content and are not stamped.

### Changes to SKILL.md

The changes are small and localized to Phase 2:

1. Add a step at the start of Phase 2 instructing the agent to read plugin.json and extract the version.
2. Add the version comment to the README template (section 2a), before the ABOUTME lines.
3. Add the version as a YAML frontmatter field in the first-officer template (section 2d).
4. Add the version comment to the status script template (section 2b), after the shebang line.

## Acceptance Criteria

- [ ] SKILL.md Phase 2 instructs the agent to read `.claude-plugin/plugin.json` and extract the version
- [ ] README template includes `<!-- commissioned-by: spacedock@{version} -->` as the first line
- [ ] First-officer template includes `commissioned-by: spacedock@{version}` as a YAML frontmatter field
- [ ] Status script template includes `# commissioned-by: spacedock@{version}` after the shebang
- [ ] The version string comes from `plugin.json` at generation time, not hardcoded in the skill
- [ ] The existing dogfood pipeline (`docs/plans/`) is retroactively stamped with the current version

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
- **Q: Should the version be in YAML frontmatter or an HTML comment?** A: HTML comment for README (pipeline schema frontmatter shouldn't have tool metadata), bash comment for the status script, and YAML frontmatter field for the first-officer agent (HTML comment before `---` breaks frontmatter parsing).
- **Q: Should we stamp every generated file?** A: Only the three scaffolding files (README, status, first-officer). Entity files are user content.
- **Q: How does the skill read plugin.json if it's just a prompt?** A: The skill instructs the executing agent to read the file using the Read tool. The agent has access to the filesystem. The skill needs to specify the path relative to the Spacedock plugin directory.
- **Q: Should we retroactively stamp the existing dogfood pipeline?** A: Yes. The dogfood pipeline was commissioned with 0.1.0 and should be stamped to match. This also serves as the initial test case.
- **Q: Where exactly is plugin.json?** A: At `.claude-plugin/plugin.json` relative to the Spacedock repo root (confirmed by inspection). The spec's example shows it at the root, but the actual location is inside `.claude-plugin/`.

## Implementation Summary

### SKILL.md changes (`skills/commission/SKILL.md`)

1. Added "Read Spacedock Version" subsection at the start of Phase 2 — instructs the executing agent to read `.claude-plugin/plugin.json` and extract `{spacedock_version}`.
2. README template (2a): added `<!-- commissioned-by: spacedock@{spacedock_version} -->` as the first line.
3. Status script template (2b): added `# commissioned-by: spacedock@{spacedock_version}` after the shebang.
4. First-officer template (2d): added `commissioned-by: spacedock@{spacedock_version}` as a YAML frontmatter field (HTML comment before `---` would break frontmatter parsing).

### Dogfood pipeline retroactive stamps

- `docs/plans/README.md` — `<!-- commissioned-by: spacedock@0.1.0 -->` added as first line.
- `docs/plans/status` — `# commissioned-by: spacedock@0.1.0` added after shebang.
- `.claude/agents/first-officer.md` — `commissioned-by: spacedock@0.1.0` added as frontmatter field.

## Validation Report

### Criterion 1: SKILL.md Phase 2 instructs the agent to read `.claude-plugin/plugin.json` and extract the version
**PASS** — `skills/commission/SKILL.md` lines 124-131 contain a "Read Spacedock Version" subsection at the start of Phase 2 that instructs the executing agent to read `.claude-plugin/plugin.json` from the Spacedock plugin directory and extract the `version` field as `{spacedock_version}`.

### Criterion 2: README template includes `<!-- commissioned-by: spacedock@{version} -->` as the first line
**PASS** — `skills/commission/SKILL.md` line 160 shows `<!-- commissioned-by: spacedock@{spacedock_version} -->` as the first line of the README template (before the ABOUTME lines and title).

### Criterion 3: First-officer template includes `commissioned-by: spacedock@{version}` as a YAML frontmatter field
**PASS** — `skills/commission/SKILL.md` line 362 shows `commissioned-by: spacedock@{spacedock_version}` as a field in the YAML frontmatter block of the first-officer template. This correctly uses a YAML field instead of an HTML comment (which would break frontmatter parsing).

### Criterion 4: Status script template includes `# commissioned-by: spacedock@{version}` after the shebang
**PASS** — `skills/commission/SKILL.md` line 275 shows `# commissioned-by: spacedock@{spacedock_version}` immediately after the `#!/bin/bash` shebang line.

### Criterion 5: The version string comes from `plugin.json` at generation time, not hardcoded in the skill
**PASS** — All three templates use the `{spacedock_version}` variable, which is populated dynamically by reading `.claude-plugin/plugin.json` at generation time (lines 124-131). No hardcoded version string appears in any template.

### Criterion 6: The existing dogfood pipeline is retroactively stamped with the current version
**PASS** — All three scaffolding files are stamped with `spacedock@0.1.0`, matching the version in `.claude-plugin/plugin.json`:
- `docs/plans/README.md` line 1: `<!-- commissioned-by: spacedock@0.1.0 -->`
- `docs/plans/status` line 2: `# commissioned-by: spacedock@0.1.0` (after shebang)
- `.claude/agents/first-officer.md` line 5: `commissioned-by: spacedock@0.1.0` (YAML frontmatter field)

### Recommendation: PASSED

All six acceptance criteria are met. The version stamp is consistent across all file types, uses the correct format for each (HTML comment, bash comment, YAML field), and the dogfood pipeline retroactive stamps match the current plugin version.
