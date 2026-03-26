---
id: 039
title: Release prep — marketplace metadata, license, and history cleanup
status: implementation
source: CL
started: 2026-03-26T16:45:00Z
completed:
verdict:
score: 0.9
worktree: .worktrees/ensign-release-prep
---

## Problem

Spacedock is being published to the Claude Code marketplace today. The plugin needs marketplace metadata, a license file, and git history cleanup before release.

## Requirements

### 1. Apache-2.0 License
Add `LICENSE` file at repo root with the standard Apache 2.0 license text.

### 2. plugin.json update
Update `.claude-plugin/plugin.json` with marketplace metadata:

```json
{
  "name": "spacedock",
  "version": "0.3.0",
  "description": "Turn directories of markdown files into structured workflows operated by AI agents",
  "author": { "name": "CL Kao" },
  "repository": "https://github.com/clkao/spacedock",
  "license": "Apache-2.0",
  "keywords": ["workflow", "pipeline", "agents", "markdown", "automation"]
}
```

### 3. .gitignore and history cleanup
Add to `.gitignore`:
- `.private-journal/`
- `testflight-*/`
- `.claude/settings.local.json`

Remove these from git tracking AND clean them from git history entirely. Ensure no active branches exist before history rewrite (confirmed: only `main`).

### 4. Version
Stay at 0.3.0 — metadata-only changes don't warrant a bump.

## Acceptance Criteria

1. `LICENSE` file exists at repo root with Apache-2.0 text
2. `plugin.json` has all marketplace fields: name, version, description, author, repository, license, keywords
3. Description matches the plain text workflow framing
4. `.gitignore` excludes `.private-journal/`, `testflight-*/`, `.claude/settings.local.json`
5. Those paths are removed from git tracking and git history
6. No active branches broken by history rewrite
7. `git tag v0.3.0` on the release commit

## Implementation Summary

### Committed in this branch

1. **LICENSE** — Apache-2.0 full text at repo root
2. **`.claude-plugin/plugin.json`** — added marketplace fields: author, repository, license, keywords
3. **`.gitignore`** — added `.private-journal/`, `testflight-*/`, `.claude/settings.local.json`

### History cleanup (run on main after merge)

These commands remove `.private-journal/`, `testflight-*/`, and `.claude/settings.local.json` from all git history. They must be run on the main repo (not a worktree) with no other branches active.

**Using git-filter-repo** (install: `pip install git-filter-repo`):

```bash
# Back up first
cp -r .git .git-backup

# Remove paths from entire history
git filter-repo \
  --invert-paths \
  --path-glob '.private-journal/' \
  --path-glob 'testflight-*/' \
  --path '.claude/settings.local.json' \
  --force

# Re-add remote and force push
git remote add origin https://github.com/clkao/spacedock.git
git push --force --all
git push --force --tags
```

**Tag the release** (after history rewrite and force push):

```bash
git tag v0.3.0
git push origin v0.3.0
```
