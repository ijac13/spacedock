---
id: 197
title: "test_commission: commission skill produces leaked templates, absolute paths, unwanted _mods/pr-merge.md"
status: backlog
source: "PR #131 CI (#154 cycle-1 pre-merge) — after #154 lifted the content-drift xfail and swapped test_commission's static content reads to `assembled_agent_content`, 60/63 inner checks pass; 3/63 remain FAIL on all three claude variants (claude-live, claude-live-bare, claude-live-opus)"
started:
completed:
verdict:
score: 0.7
worktree:
issue:
pr:
mod-block:
---

## Problem

After #154 fixed the test-assertion content-home drift (19/65 → 3/63 on test_commission), three deterministic failures remain across all claude variants. These are commission-skill output-quality regressions, not #154 scope (test-assertion-refresh against skill-preload).

### Failure 1: `workflow-local pr-merge mod is not generated`
Commission generates `v0-test-1/_mods/pr-merge.md` alongside the plugin-shipped `mods/pr-merge.md`. The assertion expects ONLY the plugin-shipped file; commission should not emit a workflow-local duplicate.

### Failure 2: `no leaked template variables`
Generated `pr-merge.md` contains unescaped `{number}`, `{branch}` placeholders:
- `gh pr view {number} --json state --jq '.state'` (this is a gh CLI template variable, legit; test regex may be over-broad)
- `**Branch:** {branch} -> main` (this is a literal template slot that leaked)
- `git push origin {branch}` (leaked template)

Some of these are legit jq / gh-CLI template interpolation; others are unrendered workflow template slots.

### Failure 3: `no absolute paths in generated files`
Generated `README.md` contains the CI runner's absolute path: `/home/runner/work/spacedock/spacedock/skills/commission/bin/status --workflow-dir ./v0-test-1/`. Commission should produce the relative path or rely on `$PATH`-resolved invocation.

## Candidate root causes

1. **pr-merge workflow-local generation**: commission skill instruction or template may still prompt the LLM to scaffold a workflow-local mod copy even when the plugin ships one.
2. **Absolute paths**: commission prompt includes absolute paths in its own context (it's generating README while running from `/home/runner/...`), and the LLM transcribes them. Needs explicit guidance to prefer relative paths.
3. **Leaked templates**: commission template handling inconsistency — some `{var}` slots are expected to survive to the output (gh/jq templates), others are meant to be rendered.

## Out of scope for #154

This task tracks commission-skill output-quality regressions. #154 was strictly a test-assertion refresh and has already landed its scope improvements (84% of test_commission's drift fixed via `assembled_agent_content`).

## Acceptance criteria (provisional)

- `test_commission` passes ≥62/63 on `make test-live-claude` across all three claude variants
- Either commission skill stops emitting the 3 failure classes, OR tests' regexes are refined to distinguish legit `{var}` templates (gh/jq) from leaked slots
- Root cause documented per failure class
