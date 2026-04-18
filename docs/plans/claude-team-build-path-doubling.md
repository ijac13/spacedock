---
id: 164
title: "`claude-team build` path-doubles when entity_path is passed as a worktree-absolute path"
status: validation
source: "FO observation during 2026-04-16 session while dispatching #162 implementation — initial build invocation produced entity paths with `.worktrees/` prefix duplicated twice"
started: 2026-04-18T07:59:13Z
completed:
verdict:
score: 0.40
worktree: .worktrees/spacedock-ensign-claude-team-build-path-doubling
issue:
pr: #129
mod-block: merge:pr-merge
---

When the FO passes `entity_path` to `claude-team build` as a worktree-absolute path (e.g. `/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-{slug}/docs/plans/{slug}.md`), the helper emits a prompt whose "Read the entity file at..." references a doubled path: `/Users/clkao/git/spacedock/.worktrees/spacedock-ensign-{slug}/.worktrees/spacedock-ensign-{slug}/docs/plans/{slug}.md`. The dispatched ensign follows the instruction and fails at the first Read.

The workaround that works today: pass `entity_path` as the project-root path (`/Users/clkao/git/spacedock/docs/plans/{slug}.md`). The helper then emits the correct worktree path. The FO documented this workaround in-session on 2026-04-15 during #157 dispatch.

## Observed evidence

2026-04-16 session, during #162 implementation dispatch. First build invocation passed `entity_path` as the worktree-absolute path; output contained:

```
Read the entity file at /Users/clkao/git/spacedock/.worktrees/spacedock-ensign-claude-team-respect-stage-model/.worktrees/spacedock-ensign-claude-team-respect-stage-model/docs/plans/claude-team-respect-stage-model.md
```

Rebuilt with `entity_path` at project root — output was correct. Confirms the helper prepends some worktree-derived prefix to whatever `entity_path` it receives, double-applying when the input is already worktree-absolute.

## Root cause (confirmed)

In `skills/commission/bin/claude-team` `cmd_build` at lines 238–240:

```python
if worktree_path:
    entity_rel = os.path.relpath(entity_path, git_root)
    worktree_entity_path = os.path.join(worktree_path, entity_rel)
```

When `entity_path` is project-root absolute (`/repo/docs/plans/f.md`), `entity_rel` is `docs/plans/f.md` and the join produces the correct worktree path. When `entity_path` is worktree-absolute (`/repo/.worktrees/X/docs/plans/f.md`), `entity_rel` is `.worktrees/X/docs/plans/f.md`, and the join with `worktree_path = /repo/.worktrees/X` produces `/repo/.worktrees/X/.worktrees/X/docs/plans/f.md`. Line 312 then uses `worktree_entity_path` as the entity read reference, propagating the doubled path into the emitted prompt.

## Proposed approach

Options, smallest fix first:

**(a) Validate and normalize on the way in.** `cmd_build` detects if `entity_path` is already under a worktree tree (contains `.worktrees/`) and either (i) errors with a clear message telling the caller to pass project-root paths, or (ii) silently normalizes by stripping the `.worktrees/{key}/` prefix and re-deriving. Prefer (i) — errors are clearer than silent corrections.

**(b) Use path-aware resolution.** Rewrite the path-building logic to use `os.path` operations that produce canonical worktree paths from project-root input regardless of whether `entity_path` was already worktree-form. Removes the class of bug entirely; more invasive change.

**(c) Document the caller contract.** Leave the helper as-is and add a preamble note in the runtime adapter instructing the FO to always pass project-root `entity_path`. Smallest change; doesn't prevent the bug, just documents around it. Least useful.

**Chosen: option (a)** — reject-with-error at the boundary. Captain agreed live in the 2026-04-18 session. Concrete pinning:

- File: `skills/commission/bin/claude-team`
- Function: `cmd_build` (defined at line 77)
- Insertion point: after the `entity_path = inp['entity_path']` extraction (line 105) and before the `os.path.isfile(entity_path)` check (line 119), so the rejection fires before any other path-resolution work.
- Detection predicate: the input `entity_path` contains a `.worktrees/` path segment (match the literal substring `/.worktrees/` to avoid false positives on unrelated filenames, and also handle a path that starts with `.worktrees/` if ever passed relative).
- Exit code: reuse the existing `_build_error` helper (returns non-zero exit via the established error-emission path — matches every other Rule violation in `cmd_build`).
- Draft stderr message (literal, so downstream tests can assert against it):

  ```
  entity_path must be a project-root absolute path; got worktree path '{entity_path}'. Pass the project-root location (e.g. '/repo/docs/plans/{slug}.md'), not the worktree copy. The helper derives the worktree read target internally.
  ```

## Acceptance criteria

**AC-1 — `claude-team build` rejects worktree-absolute `entity_path` with a non-zero exit and a stderr message naming the offending input.**
Verified by: new test `test_build_rejects_worktree_entity_path` in `tests/test_claude_team.py`. Test invokes the helper via `subprocess` with an `entity_path` containing `/.worktrees/`, asserts non-zero `returncode`, asserts stderr (or the error JSON body, matching the existing `_build_error` contract used by other tests in that file) contains the literal substring `must be a project-root absolute path` and the offending `entity_path` value.

**AC-2 — When given a project-root `entity_path`, the emitted build prompt's "Read the entity file at ..." line contains exactly one `.worktrees/` segment.**
Verified by: new test `test_build_prompt_entity_path_not_doubled` in `tests/test_claude_team.py`. Test constructs a fixture worktree under a tmp git root, invokes build with project-root `entity_path`, captures stdout, asserts `prompt.count('/.worktrees/')` on the "Read the entity file at" line equals exactly 1.

**AC-3 — `claude-team build --help` text names the `entity_path` project-root requirement.**
Verified by: new test `test_build_help_documents_entity_path_contract` in `tests/test_claude_team.py`. Test runs `claude-team build --help`, asserts stdout contains the literal substring `entity_path must be a project-root absolute path` (same phrasing as the error message, so caller and error are consistent). Implementation adds one line to the build subcommand's help/usage string in `cmd_build` (or the argparse wiring that fronts it).

## Test Plan

All static, all sub-second, all in `tests/test_claude_team.py` alongside the existing build-rule tests:

1. `test_build_rejects_worktree_entity_path` — error-path (AC-1).
2. `test_build_prompt_entity_path_not_doubled` — output-shape (AC-2).
3. `test_build_help_documents_entity_path_contract` — help-text (AC-3).

E2E not required — this is a deterministic helper input-handling bug; static invocation via `subprocess` is sufficient and matches the pattern of the existing `tests/test_claude_team.py` cases.

## Scope Boundary

Fix is ~10 lines of Python in `skills/commission/bin/claude-team` + 3 static tests + 1 docstring update. Do not rewrite any other part of `cmd_build`; do not touch other subcommands.

## Out of Scope

- Fixing any analogous doubling in `spawn-standing` (landed in #162) — cross-check after this ships; separate task if needed.
- Codex runtime's equivalent `entity_path` plumbing — Codex helper is a different binary; file a sibling task if the pattern repeats.

## Stage Report

### Summary

Ideation complete. Root cause confirmed by reading `cmd_build` lines 238–240 — `os.path.relpath(entity_path, git_root)` on a worktree-absolute input produces a relative path that still contains the `.worktrees/X/` segment, which `os.path.join` with `worktree_path` then doubles. Chosen approach (a) pinned to file, function, insertion point, detection predicate, exit-code contract, and literal stderr message. ACs rewritten to the #193 entity-level format with concrete test names and a named target test file.

### Checklist

1. **Acceptance criteria rewritten to `## Acceptance criteria` entity-level format** — **DONE.** Replaced `## Acceptance Criteria (draft)` with `## Acceptance criteria`. Each AC is now `**AC-N — {end-state property}**` followed by `Verified by: {concrete test name + file}`. Each names a post-merge property of the repo (new named test exists, specific error raised, specific substring present in help output), not a stage action.
2. **Recommendation confirmed concretely** — **DONE.** Entity now pins: file `skills/commission/bin/claude-team`, function `cmd_build` (line 77), insertion point (after line 105, before line 119), detection predicate (`/.worktrees/` substring in `entity_path`), exit-code contract (existing `_build_error` helper), and a literal draft stderr message that AC-1's test asserts against verbatim.
3. **Test plan specifies target file and three concrete test names** — **DONE.** Target file `tests/test_claude_team.py` (confirmed exists at project root, alongside existing build-rule tests). Three test names chosen so implementation can grep for them: `test_build_rejects_worktree_entity_path`, `test_build_prompt_entity_path_not_doubled`, `test_build_help_documents_entity_path_contract`. E2E-not-required confirmed.
