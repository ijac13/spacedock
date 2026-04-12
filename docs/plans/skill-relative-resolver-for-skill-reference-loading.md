---
id: 136
title: Skill-relative resolver for skill reference loading
status: implementation
source: FO observation during Codex first-officer boot on 2026-04-12
score: 0.61
started: 2026-04-12T18:11:17Z
completed:
verdict:
worktree: .worktrees/spacedock-ensign-skill-relative-resolver-for-skill-reference-loading
issue:
pr:
---

Boot-time skill reference loading is currently ambiguous about what relative paths mean. During a `spacedock:first-officer` startup run on Codex, the first-officer skill referenced support documents as `references/...`, but those files lived under `skills/first-officer/references/`. Because the boot path did not resolve includes relative to the current `SKILL.md`, the runtime had to recover by searching the repo for matching files before it could continue.

This task should make skill include resolution deterministic for packaged skills. The intended direction is a skill-relative resolver: references declared by a skill resolve relative to the directory containing that `SKILL.md`, rather than the process working directory. If a declared target exists at that skill-relative path, boot should load it directly without repository-wide searching.

The change should stay focused on boot-time reference loading and operator clarity. We want Codex to stay centered on skills as the execution surface, not on `agents/*.md` files as a secondary indirection layer.

## Proposed Approach

### Resolver behavior

The resolver should treat the directory containing the active `SKILL.md` as the root for relative includes. For a reference like `references/first-officer-shared-core.md`, the first lookup is the skill-local path next to that `SKILL.md`. If the file exists there, load it immediately and skip any repo search.

### Scope boundaries

This change applies only to skill include resolution on the Codex boot path for packaged skills. It does not redefine arbitrary filesystem path handling, it does not change how `agents/*.md` are discovered, and it does not add a new global search mechanism. The goal is to make packaged skills self-contained and predictable.

### Failure and recovery behavior

If the direct skill-relative path is missing, boot should fall back in a bounded way instead of silently wandering the repository. The fallback should still report the final resolved path in boot logs or equivalent boot output. If no bounded candidate resolves the target, boot should fail fast with an explicit error that names the missing include and the skill that requested it.

### Recommended shape

Keep the implementation close to the existing boot loader so the resolution rule is applied uniformly for every include read from a `SKILL.md`. That keeps the fix small and reduces the chance that one skill path behaves differently from another.

## Acceptance Criteria

1. Relative includes in a skill resolve from the directory containing that `SKILL.md`
   - Test: boot a packaged skill whose include lives under `skills/<skill>/references/` and verify the include loads without any repo-wide search.
2. The success path does not need repo-wide search
   - Test: inspect boot logs for the first-officer startup and confirm the loader reports the direct skill-relative path, not a repository scan.
3. Missing skill-relative includes use a bounded fallback and expose the resolved path
   - Test: boot with one intentionally missing include and verify the fallback path is reported explicitly in boot output.
4. Boot fails loudly when no bounded candidate resolves the include
   - Test: simulate an include that exists nowhere in the bounded search set and verify the error names the missing include and the owning skill.
5. The fix stays centered on skills as the execution surface
   - Test: verify there are no changes to `agents/*.md` as a workaround path and no behavior that depends on agent wrappers for resolution.

## Test Plan

Static checks are cheap and should cover the path semantics directly:
- Verify the loader or resolver code treats the current skill directory as the base for relative includes.
- Verify the boot output includes the resolved path on both direct-hit and fallback paths.
- Verify no new repo-wide search is introduced on the success path.

End-to-end coverage is warranted because the bug was observed during live boot:
- Run a packaged Codex first-officer boot with the known nested `skills/first-officer/references/...` layout and confirm boot succeeds without a repository search.
- Run one negative boot case with a missing include to confirm the bounded fallback and explicit error behavior.
- Cost/complexity: low to moderate. This is a boot-path change, so the E2E coverage is worth it, but it should stay focused on a small number of boot scenarios rather than a broad suite.

No dedicated UI or multi-stage E2E coverage is needed; the risk is isolated to boot-time resolution.

## Stage Report: ideation

- DONE: Expanded the seed into a full problem statement
  Captured the live Codex boot failure from 2026-04-12, the mispackaged `references/...` path, and why repo-wide search is the wrong recovery mechanism.
- DONE: Proposed a bounded design for skill-relative include resolution
  The design resolves relative includes from the active `SKILL.md` directory first, limits fallback scope, and requires boot output to show the resolved path.
- DONE: Defined concrete acceptance criteria with testing notes
  Each criterion now states how to verify direct-hit resolution, bounded fallback, loud failure, and the absence of `agents/*.md` as a workaround path.
- DONE: Wrote a proportional test plan
  Split static path-semantics checks from focused boot E2E coverage and kept the test count small because the bug is isolated to boot-time resolution.
- SKIPPED: Implementation work
  This stage is ideation only; no resolver code was changed in this file.

### Summary

The boot bug is caused by resolving skill includes against the wrong base path and then masking the mistake with repo-wide search. The proposed fix is to make `SKILL.md`-relative resolution the default, keep fallback bounded, and surface the final path in boot output so failures are obvious instead of hidden.

## Stage Report: implementation

- DONE - Implement skill-relative include resolution for boot-time skill loading.
  Evidence: `scripts/test_lib.py` now resolves `@...` includes from the active `SKILL.md` directory first via `resolve_skill_include()` and assembles skill contracts recursively with `_assemble_skill_contract()`.
- DONE - Preserve a bounded fallback and make the resolved path visible.
  Evidence: the resolver falls back only to `repo_root/references/` when the direct skill-local file is missing, and `build_codex_worker_bootstrap_prompt()` now surfaces `role_asset_path:` for operator-visible reporting.
- DONE - Ensure the success path no longer relies on repo-wide search.
  Evidence: the resolver performs only the direct skill-relative lookup plus the bounded fallback; there is no repo-wide scan or wildcard search in the new path.
- DONE - Keep the change centered on skills as the execution surface.
  Evidence: no files under `agents/` were modified; the work stayed in `scripts/test_lib.py` and the skill-focused test files.
- DONE - Add targeted tests for direct resolution, bounded fallback/error behavior, and no-repo-search expectations.
  Evidence: `tests/test_codex_packaged_agent_ids.py` now covers direct skill-relative hits, bounded fallback, and missing-include failures; `tests/test_agent_content.py` checks the assembled contract exposes resolved include paths.
- DONE - Run targeted verification and record concrete evidence.
  Evidence: `unset CLAUDECODE && uv run --with pytest pytest tests/test_agent_content.py tests/test_codex_packaged_agent_ids.py -q` passed with `37 passed in 0.06s`; `unset CLAUDECODE && uv run tests/test_codex_packaged_agent_e2e.py` passed with `16 passed, 0 failed`.
- DONE - Append the stage report to the entity file.
  Evidence: this `## Stage Report: implementation` section was added at the end of the entity file without touching frontmatter.
- DONE - Commit the implementation work in the assigned worktree.
  Evidence: committed on `spacedock-ensign/skill-relative-resolver-for-skill-reference-loading` after the verification runs.

### Summary

Skill include loading now resolves from the active `SKILL.md` directory first, with a bounded fallback and explicit path reporting for operators. The static harness and live Codex packaged-agent path both pass, and the work stayed scoped to the skill execution surface rather than introducing agent-wrapper workarounds.
