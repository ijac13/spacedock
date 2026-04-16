---
id: 142
title: Codex plugin scaffold for Spacedock install experience
status: done
source: Research on OpenAI Codex plugin packaging docs on 2026-04-12
score: 0.67
started: 2026-04-15T05:18:01Z
completed: 2026-04-16T14:26:54Z
verdict: PASSED
worktree: 
issue:
pr:
---

Spacedock's Codex install story is still split across manual skill symlinks and legacy `.claude-plugin` packaging. That leaves users with two mismatched install paths and no clear Codex marketplace entry to discover locally. The current goal is packaging and install ergonomics only: make Spacedock installable as a Codex plugin without changing runtime behavior, workflow semantics, or stage execution logic.

## Problem Statement

The repo still tells Codex users to symlink `skills/` into `~/.agents/skills/spacedock`, while the release, refit, and debrief surfaces still read `.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json`. That is brittle and does not match the current Codex plugin contract. The repo needs a single first-class Codex packaging surface with a local marketplace entry, while preserving a migration path for the older Claude Code and symlink-era docs.

## Proposed Approach

Use the repository root as the source of truth for the plugin package, but make the repo-plugin marketplace path explicit: the local catalog should point at `./plugins/spacedock` and the implementation must make that exact on-disk path exist. The concrete mechanism should be a checked-in symlink at `plugins/spacedock` that resolves to the repo root, so Codex can load the plugin without any resolver indirection. That keeps the current `skills/`, `agents/`, `references/`, `mods/`, and scripts layout intact while still matching the marketplace schema. The plugin package would live at the repo root via `.codex-plugin/plugin.json`, and the repo-local marketplace would live at `.agents/plugins/marketplace.json`.

The implementation should:

- Add `.codex-plugin/plugin.json` with the current Codex packaging fields
- Include `interface.displayName`, `category`, `policy.installation`, and `policy.authentication` in the marketplace entry, using the schema's allowed values (`policy.installation`: `NOT_AVAILABLE`, `AVAILABLE`, or `INSTALLED_BY_DEFAULT`; `policy.authentication`: `ON_INSTALL` or `ON_USE`)
- Add `.agents/plugins/marketplace.json` so Codex can discover the local repo install without a manual file copy, with `source.path: "./plugins/spacedock"` and a checked-in symlink at `plugins/spacedock` that resolves to the repo root
- Update README install docs to explain the Codex install path first, while explicitly labeling the symlink path and `.claude-plugin` surfaces as legacy migration support
- Update `skills/commission/SKILL.md`, `skills/refit/SKILL.md`, `skills/debrief/SKILL.md`, and `scripts/release.sh` to treat `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json` as the release source of truth, while reading or regenerating the `.claude-plugin` compatibility mirrors where they currently read `.claude-plugin`
- Require a synchronized compatibility copy at `.claude-plugin/plugin.json` that mirrors `.codex-plugin/plugin.json` so legacy consumers continue to resolve the version source during migration
- Require `.claude-plugin/marketplace.json` to be a generated mirror of `.agents/plugins/marketplace.json`, regenerated from the Codex marketplace surface rather than maintained independently

If the root-vs-subdirectory decision changes, the task must also update `source.path` and the install docs accordingly. For the repo-plugin layout, the marketplace `source.path` must follow the current contract from the plugin spec: `./plugins/spacedock`. The implementation must make that path work on disk by checking in `plugins/spacedock` as a symlink to the repo root.

## Acceptance Criteria

1. The repo contains a valid `.codex-plugin/plugin.json` for Spacedock at the repository root.
   - Test: parse the manifest and verify it contains `name: "spacedock"`, `version: "0.9.6"` in the current branch state, `description: "Turn directories of markdown files into structured workflows operated by AI agents"`, `author.name: "CL Kao"`, `repository: "https://github.com/clkao/spacedock"`, `license: "Apache-2.0"`, `keywords: ["workflow", "pipeline", "agents", "markdown", "automation"]`, and `skills: "./skills/"`.

2. The repo contains a valid local marketplace file at `.agents/plugins/marketplace.json`.
   - Test: load the JSON and verify the marketplace-level `interface.displayName: "Spacedock"`, and the Spacedock entry has `name: "spacedock"`, `category: "workflow"`, `source.source: "local"`, `source.path: "./plugins/spacedock"`, `policy.installation: "AVAILABLE"`, and `policy.authentication: "ON_INSTALL"`. Do not require a top-level `description` field on the marketplace entry unless the schema explicitly adds one later.

3. The repo contains the real plugin path that the marketplace targets.
   - Test: verify `plugins/spacedock` exists as a symlink, resolves to the repository root, and exposes the same plugin root contents Codex would load from `./plugins/spacedock`.

4. Legacy install guidance, manifest consumers, and marketplace mirrors remain synchronized.
   - Test: confirm the docs either retain the symlink-era path as fallback or explicitly mark it deprecated with a migration note, confirm `.claude-plugin/plugin.json` is a synchronized compatibility copy of `.codex-plugin/plugin.json`, and confirm `.claude-plugin/marketplace.json` is a generated mirror of `.agents/plugins/marketplace.json` that legacy consumers in `skills/refit/SKILL.md`, `skills/debrief/SKILL.md`, and `scripts/release.sh` can continue to read.

5. The package can be discovered and installed by Codex through the local marketplace.
   - Test: run a scripted, noninteractive contract check that parses `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`, `.agents/plugins/marketplace.json`, and `.claude-plugin/marketplace.json`, verifies the manifests are synchronized where intended, verifies the marketplace enum values, confirms `plugins/spacedock` resolves to the repo root, and confirms `scripts/release.sh` reads `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json` as authoritative while regenerating the `.claude-plugin` mirrors. Separately, perform the manual Codex smoke path with explicit prerequisites: Codex is restarted, `/plugins` is opened, the local marketplace entry appears, Spacedock is installed, and the plugin loads.

## Test Plan

- Static validation of JSON shape and required fields is low cost and should be automated.
- Add a scripted noninteractive check for manifest and marketplace shape so the contract is reproducible without opening Codex.
- Add a scripted noninteractive check that `plugins/spacedock` is a symlink to the repo root and that `.claude-plugin/plugin.json` matches `.codex-plugin/plugin.json` byte-for-byte or by normalized JSON comparison.
- Add a scripted noninteractive check that `.claude-plugin/marketplace.json` is regenerated from `.agents/plugins/marketplace.json`, that `.claude-plugin/plugin.json` matches `.codex-plugin/plugin.json`, and that `scripts/release.sh` uses `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json` as the authoritative release inputs.
- Doc/README checks are low cost and can be covered with targeted text assertions.
- The Codex smoke path is higher cost because it requires an interactive restart and plugin UI flow, but it is necessary because the user-visible install experience is the point of the change.
- No E2E workflow-runtime tests are needed; the scope stops at packaging and install experience, not runtime behavior or stage execution.

## Stage Report: ideation

- [DONE] Problem statement reflects the current mismatch between Codex packaging, legacy `.claude-plugin` surfaces, and symlink-era instructions.
- [DONE] Repo-layout decision is explicit: Spacedock stays at the repo root as the source of truth, `plugins/spacedock` is a checked-in symlink to the root, and the marketplace path is `./plugins/spacedock`.
- [DONE] Coexistence and migration are addressed with `.claude-plugin/plugin.json` as a synchronized copy, `.claude-plugin/marketplace.json` as a generated mirror of the Codex marketplace, and the existing README/install-doc migration notes and legacy helper consumers.
- [DONE] Acceptance criteria enumerate the intended keys and values for `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`, `.agents/plugins/marketplace.json`, and `.claude-plugin/marketplace.json`, and directly verify the symlinked plugin path.
- [DONE] Test plan separates the scripted contract checks from the manual Codex smoke path, with explicit prerequisites for restart, `/plugins`, install, load verification, and release-tooling regeneration behavior.
- [DONE] Scope is constrained to packaging and install experience; runtime behavior changes are out of scope.
- [SKIPPED] Frontmatter changes are out of scope for this stage refresh.

### Feedback Cycles

1. `validation -> implementation` (2026-04-16): `REJECTED` on AC5 only. Scripted contract checks passed, but the required manual Codex smoke path initially lacked evidence: restart Codex, open `/plugins`, confirm the local Spacedock entry appears, install it, and verify the plugin loads. This was addressed in implementation cycle 2 and later validation passed.

## Stage Report: implementation

- DONE: Implement the Codex plugin scaffold at the repo root with a valid `.codex-plugin/plugin.json` matching the task’s approved manifest contract.
  Evidence: `.codex-plugin/plugin.json` added and verified by `tests/test_codex_plugin_packaging.py::test_codex_plugin_manifest_matches_approved_contract`.
- DONE: Create the real marketplace target path `plugins/spacedock` as the approved checked-in symlink to the repo root.
  Evidence: `plugins/spacedock -> ..`; verified by `tests/test_codex_plugin_packaging.py::test_plugins_spacedock_symlink_resolves_to_repo_root`.
- DONE: Add `.agents/plugins/marketplace.json` with the approved marketplace shape and make `.claude-plugin/marketplace.json` the generated legacy mirror of that Codex marketplace surface.
  Evidence: `.agents/plugins/marketplace.json` added; `.claude-plugin/marketplace.json` synchronized; verified by the marketplace and mirror tests in `tests/test_codex_plugin_packaging.py`.
- DONE: Make `.claude-plugin/plugin.json` the generated synchronized legacy mirror of `.codex-plugin/plugin.json`.
  Evidence: `.claude-plugin/plugin.json` now mirrors `.codex-plugin/plugin.json`; verified by `tests/test_codex_plugin_packaging.py::test_legacy_plugin_manifest_is_a_synchronized_mirror`.
- DONE: Update `README.md`, `skills/commission/SKILL.md`, `skills/refit/SKILL.md`, `skills/debrief/SKILL.md`, and `scripts/release.sh` so release tooling and helper surfaces treat `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json` as authoritative while preserving the documented legacy `.claude-plugin` compatibility surfaces.
  Evidence: Codex-first install docs and legacy notes added in `README.md`; the three skills now read `.codex-plugin/plugin.json`; `scripts/release.sh` now uses authoritative path variables plus `sync_legacy_plugin_manifest` and `sync_legacy_marketplace`.
- DONE: Add scripted noninteractive verification for the approved contract: manifest shape, marketplace shape, `plugins/spacedock` symlink, legacy mirror synchronization, and release-script source-of-truth behavior.
  Evidence: new `tests/test_codex_plugin_packaging.py` covers the full contract and passed after implementation.
- DONE: Run the relevant tests/checks added or touched, and record results.
  Evidence: `unset CLAUDECODE && uv run pytest tests/test_codex_plugin_packaging.py -v` -> `7 passed`; `unset CLAUDECODE && uv run pytest tests/test_agent_content.py tests/test_codex_plugin_packaging.py -v` -> `52 passed`; `bash -n scripts/release.sh` -> exit 0.
- DONE: Update the entity body in the worktree with an `## Stage Report: implementation` section that uses DONE/SKIPPED/FAILED markers and points to the produced deliverables and verification evidence.
  Evidence: this appended stage report in `docs/plans/codex-plugin-scaffold-for-spacedock-install.md`.
- DONE: Commit the implementation work on the worktree branch before reporting completion.
  Evidence: implementation payload committed as `10f67572` on `spacedock-ensign/codex-plugin-scaffold-for-spacedock-install`.

### Summary

The repo now exposes a Codex-first plugin package at `.codex-plugin/plugin.json`, a repo-local marketplace at `.agents/plugins/marketplace.json`, and the real `plugins/spacedock` symlink target Codex resolves through the local catalog. Legacy `.claude-plugin` manifest and marketplace files were kept as synchronized compatibility mirrors, and release/docs surfaces were updated to treat the Codex packaging files as authoritative.

The scripted verification added for this task is green. The remaining validation work is the manual Codex UI smoke path from the acceptance criteria: restart Codex, open `/plugins`, confirm the local Spacedock entry appears, install it, and verify the plugin loads from the repo-local marketplace.

## Stage Report: validation

- DONE: Verify AC1: `.codex-plugin/plugin.json` exists and matches the approved contract.
  Evidence: direct inspection shows `name: "spacedock"`, `version: "0.9.6"`, the approved description/author/repository/license/keywords, and `skills: "./skills/"`; `unset CLAUDECODE && uv run pytest tests/test_codex_plugin_packaging.py -v` passed `test_codex_plugin_manifest_matches_approved_contract`.
- DONE: Verify AC2: `.agents/plugins/marketplace.json` exists and matches the approved marketplace contract.
  Evidence: direct inspection shows `interface.displayName: "Spacedock"` and plugin entry `name: "spacedock"`, `category: "workflow"`, `source.source: "local"`, `source.path: "./plugins/spacedock"`, `policy.installation: "AVAILABLE"`, and `policy.authentication: "ON_INSTALL"`; the task-specific pytest passed `test_codex_marketplace_matches_approved_contract`.
- DONE: Verify AC3: `plugins/spacedock` exists as the required symlink and resolves to the repo root.
  Evidence: `ls -l plugins` shows `spacedock -> ..`; a `Path.resolve()` check in the worktree resolved the symlink to `/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-codex-plugin-scaffold-for-spacedock-install`, and `.codex-plugin/plugin.json` is reachable through that path; pytest passed `test_plugins_spacedock_symlink_resolves_to_repo_root`.
- DONE: Verify AC4: legacy `.claude-plugin` mirrors, helper consumers, and release-tooling source-of-truth behavior match the approved migration contract.
  Evidence: `.claude-plugin/plugin.json` matches `.codex-plugin/plugin.json`, `.claude-plugin/marketplace.json` matches `.agents/plugins/marketplace.json`, `README.md` retains `~/.agents/skills/spacedock` as legacy fallback, `skills/commission/SKILL.md`, `skills/refit/SKILL.md`, and `skills/debrief/SKILL.md` read `.codex-plugin/plugin.json`, and `scripts/release.sh` uses authoritative `.codex-plugin/plugin.json` / `.agents/plugins/marketplace.json` with `sync_legacy_plugin_manifest` and `sync_legacy_marketplace`; relevant tests passed.
- FAILED: Verify AC5: package discovery/install evidence is sufficient, including the manual Codex `/plugins` smoke path.
  Evidence: the scripted contract checks passed, but no evidence was found that Codex was restarted, `/plugins` was opened, the local Spacedock entry appeared, install completed, and the plugin loaded; the implementation report explicitly states that manual smoke path remained for validation.
- DONE: Run the applicable scripted checks/tests and report exact commands and outcomes.
  Evidence: `unset CLAUDECODE && uv run pytest tests/test_codex_plugin_packaging.py -v` -> `7 passed`; `unset CLAUDECODE && uv run pytest tests/test_agent_content.py tests/test_codex_plugin_packaging.py -v` -> `52 passed`; `bash -n scripts/release.sh` -> exit `0`.
- DONE: Append `## Stage Report: validation` to the entity file with DONE/SKIPPED/FAILED markers, explicit evidence for each acceptance criterion, and a clear final verdict.
  Evidence: this section is appended at the end of the worktree entity file and records the acceptance-criteria evidence and verdict.
- DONE: Commit the validation report on the worktree branch before reporting completion.
  Evidence: the report is prepared in the worktree copy for commit on `spacedock-ensign/codex-plugin-scaffold-for-spacedock-install`.

### Summary

Validation confirms that the Codex plugin manifest, local marketplace, repo-root symlink target, legacy compatibility mirrors, and release-tooling authority all match the approved contract. The deliverable still fails AC5 because the required manual Codex `/plugins` discovery/install smoke path was not executed or at least not evidenced in the worktree. Final verdict: REJECTED.

## Stage Report: implementation (cycle 2)

- DONE: Attempt the approved manual Codex smoke path in this environment from a fresh interactive Codex session.
  Evidence: launched `codex --no-alt-screen -C /Users/clkao/git/spacedock/.worktrees/spacedock-ensign-codex-plugin-scaffold-for-spacedock-install`; Codex CLI `0.120.0` opened an interactive TUI in the assigned worktree.
- DONE: Open `/plugins` and confirm the local Spacedock entry appears in the marketplace UI.
  Evidence: entering `/plugins` showed `Plugins` and `Loading available plugins...`; searching `spacedock` updated the list to `› Spacedock  Available`.
- DONE: Install Spacedock from the `/plugins` UI and capture the install result.
  Evidence: opening the plugin details showed `Spacedock · Can be installed · spacedock`; selecting `2. Install plugin` produced `Installed Spacedock plugin. No additional app authentication is required.` and returned to the plugin list with `› Spacedock                    Installed`.
- DONE: Verify the plugin loads after install.
  Evidence: the plugin detail view listed the shipped skills `spacedock:commission`, `spacedock:debrief`, `spacedock:ensign`, `spacedock:first-officer`, and `spacedock:refit`, and `~/.codex/config.toml` now contains `[plugins."spacedock@spacedock"]` with `enabled = true`.
- DONE: Record the AC5 follow-up evidence in the worktree entity file and commit it on the implementation branch.
  Evidence: this follow-up report is appended in the worktree copy for commit on `spacedock-ensign/codex-plugin-scaffold-for-spacedock-install`.

### Summary

The previously missing AC5 evidence has now been gathered directly in this environment. A fresh Codex interactive session reached `/plugins`, the local `Spacedock` marketplace entry appeared, the install completed successfully, and the installed plugin exposed the expected Spacedock skills with persisted enabled state in Codex config.

## Stage Report: validation (cycle 2)

- DONE: Verify AC1: `.codex-plugin/plugin.json` exists and matches the approved contract.
  Evidence: direct inspection in the worktree shows `name: "spacedock"`, `version: "0.9.6"`, the approved description, `author.name: "CL Kao"`, `repository: "https://github.com/clkao/spacedock"`, `license: "Apache-2.0"`, the approved keywords, and `skills: "./skills/"`; fresh run `unset CLAUDECODE && uv run pytest tests/test_codex_plugin_packaging.py -v` passed `test_codex_plugin_manifest_matches_approved_contract`.
- DONE: Verify AC2: `.agents/plugins/marketplace.json` exists and matches the approved marketplace contract.
  Evidence: direct inspection shows `interface.displayName: "Spacedock"` and plugin entry `name: "spacedock"`, `category: "workflow"`, `source.source: "local"`, `source.path: "./plugins/spacedock"`, `policy.installation: "AVAILABLE"`, and `policy.authentication: "ON_INSTALL"`; the fresh pytest run passed `test_codex_marketplace_matches_approved_contract`.
- DONE: Verify AC3: `plugins/spacedock` exists as the required symlink and resolves to the repo root.
  Evidence: `plugins/spacedock` is a checked-in symlink with target `..`, and a fresh `Path.resolve()` check resolved it to `/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-codex-plugin-scaffold-for-spacedock-install`; `.codex-plugin/plugin.json` is reachable through that path; the fresh pytest run passed `test_plugins_spacedock_symlink_resolves_to_repo_root`.
- DONE: Verify AC4: legacy `.claude-plugin` mirrors, helper consumers, and release-tooling source-of-truth behavior match the approved migration contract.
  Evidence: direct JSON inspection shows `.claude-plugin/plugin.json` mirrors `.codex-plugin/plugin.json` and `.claude-plugin/marketplace.json` mirrors `.agents/plugins/marketplace.json`; `README.md` retains the `~/.agents/skills/spacedock` legacy fallback while describing the Codex-first install path; `skills/commission/SKILL.md`, `skills/refit/SKILL.md`, and `skills/debrief/SKILL.md` read `.codex-plugin/plugin.json`; `scripts/release.sh` treats `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json` as authoritative and defines `sync_legacy_plugin_manifest` plus `sync_legacy_marketplace`; the fresh pytest run passed the mirror/doc/release assertions and `bash -n scripts/release.sh` exited `0`.
- DONE: Verify AC5, including the added manual Codex smoke evidence, and judge whether it is sufficient.
  Evidence: implementation cycle 2 committed the missing manual smoke path in `a62c3d51`, recording a fresh interactive Codex session, `/plugins`, the visible `Spacedock` entry, successful install, and loaded skills; that evidence is corroborated by current local state because `~/.codex/config.toml` contains `[plugins."spacedock@spacedock"]` with `enabled = true`; the scripted contract checks also passed on this validation pass. Judgment: the combined committed UI evidence plus persisted config state is sufficient for AC5.
- DONE: Run the applicable scripted checks/tests and report exact commands and outcomes.
  Evidence: `unset CLAUDECODE && uv run pytest tests/test_codex_plugin_packaging.py -v` -> `7 passed in 0.01s`; `bash -n scripts/release.sh` -> exit `0`.
- DONE: Append `## Stage Report: validation` to the entity file with DONE/SKIPPED/FAILED markers, explicit evidence for each acceptance criterion, and a clear final verdict.
  Evidence: this `validation (cycle 2)` section is appended at the end of the worktree entity file and supersedes the earlier rejected validation now that AC5 has evidence.
- DONE: Commit the validation report on the worktree branch before reporting completion.
  Evidence: this report is prepared in the assigned worktree for commit on `spacedock-ensign/codex-plugin-scaffold-for-spacedock-install`.

### Summary

The earlier rejection was caused solely by missing AC5 evidence. That gap is now closed by the committed manual Codex smoke-path report in implementation cycle 2, corroborated by current Codex config state and a fresh green run of the task-specific contract checks. Final verdict: PASSED.
