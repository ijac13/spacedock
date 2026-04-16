---
id: 142
title: Codex plugin scaffold for Spacedock install experience
status: ideation
source: Research on OpenAI Codex plugin packaging docs on 2026-04-12
score: 0.67
started: 2026-04-15T05:18:01Z
completed:
verdict:
worktree:
issue:
pr:
---

Spacedock's Codex install story is still split across manual skill symlinks and legacy `.claude-plugin` packaging. That leaves users with two mismatched install paths and no clear Codex marketplace entry to discover locally. The current goal is packaging and install ergonomics only: make Spacedock installable as a Codex plugin without changing runtime behavior, workflow semantics, or stage execution logic.

## Problem Statement

The repo still tells Codex users to symlink `skills/` into `~/.agents/skills/spacedock`, while the release, refit, and debrief surfaces still read `.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json`. That is brittle and does not match the current Codex plugin contract. The repo needs a single first-class Codex packaging surface with a local marketplace entry, while preserving a migration path for the older Claude Code and symlink-era docs.

## Proposed Approach

Use the repository root as the plugin root, not `plugins/spacedock/`. That keeps the current `skills/`, `agents/`, `references/`, `mods/`, and scripts layout intact and minimizes install friction for local development. The plugin package would live at the repo root via `.codex-plugin/plugin.json`, and the repo-local marketplace would live at `.agents/plugins/marketplace.json` pointing `source.path` at `./`.

The implementation should:

- Add `.codex-plugin/plugin.json` with the current Codex packaging fields
- Include `interface.displayName`, `category`, `policy.installation`, and `policy.authentication` in the marketplace entry
- Add `.agents/plugins/marketplace.json` so Codex can discover the local repo install without a manual file copy
- Update README install docs to explain the Codex install path first, while explicitly labeling the symlink path and `.claude-plugin` surfaces as legacy migration support
- Update `skills/commission/SKILL.md`, `skills/refit/SKILL.md`, `skills/debrief/SKILL.md`, and `scripts/release.sh` to reference the Codex packaging contract where they currently read `.claude-plugin`
- Treat `.claude-plugin/marketplace.json` as a compatibility surface during migration, not the primary install story

If the root-vs-subdirectory decision changes, the task must also update `source.path` and the install docs accordingly. Otherwise, the root choice keeps install ergonomics simple: clone the repo, restart Codex, and install from the local marketplace entry.

## Acceptance Criteria

1. The repo contains a valid `.codex-plugin/plugin.json` for Spacedock at the repository root.
   - Test: parse the manifest and verify it contains `name: "spacedock"`, `version: "0.9.6"` in the current branch state, `description: "Turn directories of markdown files into structured workflows operated by AI agents"`, `author.name: "CL Kao"`, `repository: "https://github.com/clkao/spacedock"`, `license: "Apache-2.0"`, and the expected `keywords` list (`workflow`, `pipeline`, `agents`, `markdown`, `automation`).

2. The repo contains a valid local marketplace file at `.agents/plugins/marketplace.json`.
   - Test: load the JSON and verify the Spacedock entry has `name: "spacedock"`, `interface.displayName: "Spacedock"`, `description` matching the plugin description, `category: "workflow"`, `source.path: "./"`, `policy.installation: "local"`, and `policy.authentication: "none"`.

3. The install docs and workflow helper docs describe the new Codex install path and the migration posture clearly.
   - Test: inspect `README.md`, `skills/commission/SKILL.md`, `skills/refit/SKILL.md`, `skills/debrief/SKILL.md`, `scripts/release.sh`, and `.claude-plugin/marketplace.json` for the updated wording and compatibility notes.

4. Legacy install guidance is not silently removed.
   - Test: confirm the docs either retain the symlink-era path as fallback or explicitly mark it deprecated with a migration note.

5. The package can be discovered and installed by Codex through the local marketplace.
   - Test: run a scripted, noninteractive check that parses `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`, confirms the marketplace entry points at `./`, and proves the manifest/loadability shape is valid; then restart Codex, open `/plugins`, confirm the local marketplace entry appears, install Spacedock, and verify the plugin loads.

## Test Plan

- Static validation of JSON shape and required fields is low cost and should be automated.
- Add a scripted noninteractive check for manifest and marketplace shape so the contract is reproducible without opening Codex.
- Doc/README checks are low cost and can be covered with targeted text assertions.
- The Codex smoke path is higher cost because it requires an interactive restart and plugin UI flow, but it is necessary because the user-visible install experience is the point of the change.
- No E2E workflow-runtime tests are needed; the scope stops at packaging and install experience, not runtime behavior or stage execution.

## Stage Report: ideation

- [DONE] Problem statement reflects the current mismatch between Codex packaging, legacy `.claude-plugin` surfaces, and symlink-era instructions.
- [DONE] Repo-layout decision is explicit: Spacedock stays at the repo root as the plugin root, with `source.path: "./"`.
- [DONE] Coexistence and migration are addressed for README install docs, `skills/commission/SKILL.md`, `skills/refit/SKILL.md`, `skills/debrief/SKILL.md`, `scripts/release.sh`, and `.claude-plugin/marketplace.json`.
- [DONE] Acceptance criteria enumerate the intended keys and values for `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`.
- [DONE] Test plan includes both a scripted manifest/marketplace check and the actual Codex smoke path: restart Codex, open `/plugins`, confirm the local marketplace entry, install, and verify the plugin loads.
- [DONE] Scope is constrained to packaging and install experience; runtime behavior changes are out of scope.
- [SKIPPED] Frontmatter changes are out of scope for this stage refresh.
