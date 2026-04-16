# Codex Plugin Scaffold For Spacedock Install Implementation Plan

> **For Claude:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json` the authoritative Spacedock packaging surfaces while preserving synchronized legacy `.claude-plugin` mirrors and a real `plugins/spacedock` marketplace target.

**Architecture:** Keep the repo root as the plugin package root. Add one static contract test module that validates manifest shape, marketplace shape, mirror synchronization, the `plugins/spacedock` symlink target, and release-script source-of-truth behavior. Update docs and skill text to point at Codex-first packaging while retaining the legacy `.claude-plugin` files as generated compatibility mirrors.

**Tech Stack:** Python 3.10+, pytest, shell release tooling, JSON manifests, markdown skills/docs

---

### Task 1: Add Packaging Contract Tests

**Files:**
- Create: `tests/test_codex_plugin_packaging.py`

- [ ] **Step 1: Write the failing tests**

Add tests that assert:
- `.codex-plugin/plugin.json` exists with the approved manifest fields and values
- `.agents/plugins/marketplace.json` exists with `interface.displayName`, `source.path: "./plugins/spacedock"`, and the approved enum values
- `plugins/spacedock` exists as a symlink that resolves to the repo root
- `.claude-plugin/plugin.json` matches `.codex-plugin/plugin.json`
- `.claude-plugin/marketplace.json` matches `.agents/plugins/marketplace.json`
- `scripts/release.sh` uses `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json` as authoritative inputs and updates the legacy mirrors
- README and the touched skills mark the legacy `.claude-plugin` and direct skill-symlink path as compatibility surfaces

- [ ] **Step 2: Run the new test file to verify it fails**

Run: `unset CLAUDECODE && uv run pytest tests/test_codex_plugin_packaging.py -v`
Expected: FAIL because the Codex plugin scaffold and authoritative marketplace do not exist yet.

### Task 2: Implement The Codex Packaging Surfaces

**Files:**
- Create: `.codex-plugin/plugin.json`
- Create: `.agents/plugins/marketplace.json`
- Create: `plugins/spacedock` (symlink to `..`)
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Add the authoritative Codex manifest and marketplace**

Create the new Codex-first files with the task-approved values and make `plugins/spacedock` a checked-in symlink to the repository root.

- [ ] **Step 2: Regenerate the legacy mirrors from the authoritative files**

Make `.claude-plugin/plugin.json` mirror `.codex-plugin/plugin.json` and `.claude-plugin/marketplace.json` mirror `.agents/plugins/marketplace.json`.

- [ ] **Step 3: Run the packaging tests to verify the new contract passes**

Run: `unset CLAUDECODE && uv run pytest tests/test_codex_plugin_packaging.py -v`
Expected: PASS

### Task 3: Update Docs And Release Tooling

**Files:**
- Modify: `README.md`
- Modify: `skills/commission/SKILL.md`
- Modify: `skills/refit/SKILL.md`
- Modify: `skills/debrief/SKILL.md`
- Modify: `scripts/release.sh`

- [ ] **Step 1: Update docs and skill text**

Document `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json` as the source of truth, with `.claude-plugin/*` and the direct `~/.agents/skills/spacedock` layout described as legacy compatibility or bootstrap surfaces.

- [ ] **Step 2: Update release tooling**

Switch the release script to bump the version from `.codex-plugin/plugin.json`, update `.agents/plugins/marketplace.json`, and regenerate both `.claude-plugin` mirror files from those authoritative inputs.

- [ ] **Step 3: Run the focused packaging tests again**

Run: `unset CLAUDECODE && uv run pytest tests/test_codex_plugin_packaging.py -v`
Expected: PASS

### Task 4: Run Broader Verification And Record The Stage Report

**Files:**
- Modify: `docs/plans/codex-plugin-scaffold-for-spacedock-install.md`

- [ ] **Step 1: Run the touched static suite**

Run: `unset CLAUDECODE && uv run pytest tests/test_agent_content.py tests/test_codex_plugin_packaging.py -v`
Expected: PASS

- [ ] **Step 2: Update the entity body with the implementation stage report**

Append `## Stage Report: implementation` with DONE/SKIPPED/FAILED entries for every checklist item, referencing changed files, verification commands, and commit SHA.

- [ ] **Step 3: Commit the worktree changes**

Run:
```bash
git add .codex-plugin .agents/plugins .claude-plugin README.md skills/commission/SKILL.md skills/refit/SKILL.md skills/debrief/SKILL.md scripts/release.sh tests/test_codex_plugin_packaging.py docs/superpowers/plans/2026-04-16-codex-plugin-scaffold-for-spacedock-install.md docs/plans/codex-plugin-scaffold-for-spacedock-install.md plugins/spacedock
git commit -m "feat: add codex plugin scaffold for spacedock install"
```
