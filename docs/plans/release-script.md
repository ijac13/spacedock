---
id: 040
title: Release script with version bumping and changelog
status: implementation
source: CL
started: 2026-03-26T17:35:00Z
completed:
verdict:
score: 0.85
worktree: .worktrees/ensign-release-script
---

## Problem

The release process is manual and error-prone. Version numbers live in two places (`.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`) and must stay in sync. There's no changelog generation and no automated tag-and-push workflow.

## Reference

`/tmp/release.sh` from agentlore shows the pattern: validate version format, check for clean working tree, generate changelog via AI, prompt for confirmation, create annotated tag, push. Spacedock needs the same flow plus version bumping in both metadata files.

## Requirements

### 1. Version bumping

The release script must update the `version` field in:
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json` (both top-level metadata and the plugin entry in the `plugins` array)

The version bump should be committed before tagging.

### 2. Changelog generation

Generate a changelog from git log between the previous tag and HEAD. The agentlore pattern uses a `changelog.sh` helper that calls Claude to summarize changes. Adapt this for Spacedock — either a separate `changelog.sh` or inline in the release script.

### 3. Release flow

```
./release.sh 0.4.0 [extra_instructions]
```

1. Validate version format (semver)
2. Check tag doesn't already exist
3. Check clean working tree
4. Update version in plugin.json and marketplace.json
5. Commit version bump
6. Generate changelog from git log since last tag
7. Show changelog, prompt for confirmation
8. Create annotated git tag with changelog as message
9. Push tag and main to origin

### 4. File location

`release.sh` at repo root (or `scripts/release.sh` — CL's preference).

## Acceptance Criteria

1. Running `./release.sh X.Y.Z` updates version in both plugin.json and marketplace.json
2. Versions stay in sync across both files
3. Changelog is generated from git history
4. Script is interactive (confirm before tagging)
5. Clean error handling (dirty tree, existing tag, bad version format)
6. GitHub release URL points to clkao/spacedock (not agentlore)

## Implementation

Created `scripts/release.sh` with the full release flow:

1. Validates semver format, checks tag doesn't exist, checks clean working tree
2. Bumps version in both `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` using python3 JSON manipulation (preserves formatting)
3. Commits the version bump as `release: spacedock@X.Y.Z`
4. Generates changelog via `claude -p` if available, falls back to raw `git log --oneline`
5. Shows changelog and prompts for confirmation
6. Creates annotated tag with changelog as message
7. Pushes branch and tag to origin
8. Prints GitHub release URL pointing to clkao/spacedock
