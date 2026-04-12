---
id: 142
title: Codex plugin scaffold for Spacedock install experience
status: backlog
source: Research on OpenAI Codex plugin packaging docs on 2026-04-12
score: 0.67
started:
completed:
verdict:
worktree:
issue:
pr:
---

Spacedock's current Codex install path is still oriented around manual skill exposure and local symlink setup. The official Codex plugin docs now provide a clearer install surface: a plugin rooted by `.codex-plugin/plugin.json`, optionally bundled `skills/`, and a marketplace entry under either `$REPO_ROOT/.agents/plugins/marketplace.json` or `~/.agents/plugins/marketplace.json`. That gives users a much better install experience than manually wiring `~/.agents/skills/` and hoping the layout matches the runtime adapter assumptions.

This task should scaffold Spacedock as a first-class Codex plugin while preserving the existing skill layout. The goal is not to redesign Spacedock's runtime behavior, only to package the existing skills and related metadata in the Codex plugin structure that the official docs recommend.

## Desired Direction

- Add a plugin manifest at `.codex-plugin/plugin.json`
- Point the manifest at the existing packaged `skills/` directory
- Add install-surface metadata suitable for Codex's plugin directory
- Add a repo-local marketplace file at `.agents/plugins/marketplace.json` so this repo can self-host the local install path for testing
- Keep the resulting install story aligned with the official Codex plugin packaging and marketplace docs

## Validation Expectations

Implementation should verify both structure and install ergonomics:

1. static checks for manifest shape and required fields
2. marketplace-path checks proving the repo-local catalog points at the plugin folder correctly
3. a documented manual or scripted smoke path showing that after restart Codex can see/install the local Spacedock plugin from the marketplace

The task should also make clear whether any legacy symlink-based setup instructions can be removed or should remain as fallback guidance during migration.
