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

Use the repository root as the source of truth for the plugin package, but make the repo-plugin marketplace path explicit: the local catalog should point at `./plugins/spacedock` if the current contract is preserved. That keeps the current `skills/`, `agents/`, `references/`, `mods/`, and scripts layout intact while still matching the marketplace schema. The plugin package would live at the repo root via `.codex-plugin/plugin.json`, and the repo-local marketplace would live at `.agents/plugins/marketplace.json`.

The implementation should:

- Add `.codex-plugin/plugin.json` with the current Codex packaging fields
- Include `interface.displayName`, `category`, `policy.installation`, and `policy.authentication` in the marketplace entry, using the schema's allowed values (`policy.installation`: `NOT_AVAILABLE`, `AVAILABLE`, or `INSTALLED_BY_DEFAULT`; `policy.authentication`: `ON_INSTALL` or `ON_USE`)
- Add `.agents/plugins/marketplace.json` so Codex can discover the local repo install without a manual file copy, with `source.path: "./plugins/spacedock"` if the current repo-plugin contract remains in force
- Update README install docs to explain the Codex install path first, while explicitly labeling the symlink path and `.claude-plugin` surfaces as legacy migration support
- Update `skills/commission/SKILL.md`, `skills/refit/SKILL.md`, `skills/debrief/SKILL.md`, and `scripts/release.sh` to reference the Codex packaging contract where they currently read `.claude-plugin`
- Require either a synchronized compatibility copy or a fallback resolution path so legacy `.claude-plugin/plugin.json` consumers continue to resolve the version source during migration
- Treat `.claude-plugin/marketplace.json` as a compatibility surface during migration, not the primary install story

If the root-vs-subdirectory decision changes, the task must also update `source.path` and the install docs accordingly. For the repo-plugin layout, the marketplace `source.path` must follow the current contract from the plugin spec: use the exact repo-relative plugin path the schema expects, including `./plugins/spacedock` if that remains the intended layout. If the implementation keeps the root tree as the source of truth, it must add a synchronized compatibility copy or fallback path so `./plugins/spacedock` still resolves cleanly for Codex.

## Acceptance Criteria

1. The repo contains a valid `.codex-plugin/plugin.json` for Spacedock at the repository root.
   - Test: parse the manifest and verify it contains `name: "spacedock"`, `version: "0.9.6"` in the current branch state, `description: "Turn directories of markdown files into structured workflows operated by AI agents"`, `author.name: "CL Kao"`, `repository: "https://github.com/clkao/spacedock"`, `license: "Apache-2.0"`, `keywords: ["workflow", "pipeline", "agents", "markdown", "automation"]`, and `skills: "./skills/"`.

2. The repo contains a valid local marketplace file at `.agents/plugins/marketplace.json`.
   - Test: load the JSON and verify the Spacedock entry has `name: "spacedock"`, `interface.displayName: "Spacedock"`, `category: "workflow"`, `source.source: "local"`, `source.path: "./plugins/spacedock"`, `policy.installation: "AVAILABLE"`, and `policy.authentication: "ON_INSTALL"`. Do not require a top-level `description` field on the marketplace entry unless the schema explicitly adds one later.

3. The install docs and workflow helper docs describe the new Codex install path and the migration posture clearly.
   - Test: inspect `README.md`, `skills/commission/SKILL.md`, `skills/refit/SKILL.md`, `skills/debrief/SKILL.md`, `scripts/release.sh`, and `.claude-plugin/marketplace.json` for the updated wording and compatibility notes.

4. Legacy install guidance is not silently removed.
   - Test: confirm the docs either retain the symlink-era path as fallback or explicitly mark it deprecated with a migration note, and confirm legacy `.claude-plugin/plugin.json` consumers in `skills/refit/SKILL.md`, `skills/debrief/SKILL.md`, and `scripts/release.sh` have either a synchronized compatibility copy or a fallback resolution path.

5. The package can be discovered and installed by Codex through the local marketplace.
   - Test: run a scripted, noninteractive contract check that parses `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`, verifies the manifest keys and marketplace enum values, and confirms `source.path: "./plugins/spacedock"` resolves according to the schema. Separately, perform the manual Codex smoke path with explicit prerequisites: Codex is restarted, `/plugins` is opened, the local marketplace entry appears, Spacedock is installed, and the plugin loads.

## Test Plan

- Static validation of JSON shape and required fields is low cost and should be automated.
- Add a scripted noninteractive check for manifest and marketplace shape so the contract is reproducible without opening Codex.
- Doc/README checks are low cost and can be covered with targeted text assertions.
- The Codex smoke path is higher cost because it requires an interactive restart and plugin UI flow, but it is necessary because the user-visible install experience is the point of the change.
- No E2E workflow-runtime tests are needed; the scope stops at packaging and install experience, not runtime behavior or stage execution.

## Stage Report: ideation

- [DONE] Problem statement reflects the current mismatch between Codex packaging, legacy `.claude-plugin` surfaces, and symlink-era instructions.
- [DONE] Repo-layout decision is explicit: Spacedock stays at the repo root as the source of truth, with marketplace `source.path: "./plugins/spacedock"`.
- [DONE] Coexistence and migration are addressed for README install docs, `skills/commission/SKILL.md`, `skills/refit/SKILL.md`, `skills/debrief/SKILL.md`, `scripts/release.sh`, and `.claude-plugin/marketplace.json`.
- [DONE] Acceptance criteria enumerate the intended keys and values for `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`, including the marketplace enum constraints.
- [DONE] Test plan separates a scripted contract check from the manual Codex smoke path: restart Codex, open `/plugins`, confirm the local marketplace entry, install, and verify the plugin loads.
- [DONE] Scope is constrained to packaging and install experience; runtime behavior changes are out of scope.
- [SKIPPED] Frontmatter changes are out of scope for this stage refresh.
