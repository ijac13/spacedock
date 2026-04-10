---
id: 128
title: "status script: restore exec bit + sweep docs to drop redundant python3 prefix"
status: backlog
source: "CL observation during 2026-04-10 debrief — 'why are we always executing the status script with python3?'"
score: 0.55
worktree:
started:
completed:
verdict:
issue:
pr:
---

`skills/commission/bin/status` has a `#!/usr/bin/env python3` shebang but its filesystem exec bit is `-rw-r--r--` — it's not actually executable as a standalone command. Every invocation across the FO runtime, commission skill, and test harness prefixes it with `python3 ...`, which works by accident (the shebang is bypassed) and reads as needless ceremony.

The sibling script `skills/commission/bin/claude-team` (landed in task 121) is correctly `-rwxr-xr-x` and is invoked without a `python3` prefix. This task brings `status` into line and sweeps the documentation.

## Scope

**1. Restore exec bit on `skills/commission/bin/status`.**

```bash
chmod +x skills/commission/bin/status
```

Verify: `ls -la skills/commission/bin/status` shows `-rwxr-xr-x`.

**2. Sweep 6 live doc references to drop the `python3` prefix.**

| File | Line | Current | Proposed |
|---|---|---|---|
| `scripts/test-harness.md` | 109, 188 | `python3 $REPO_ROOT/skills/commission/bin/status ...` | `$REPO_ROOT/skills/commission/bin/status ...` |
| `skills/commission/SKILL.md` | 301, 309, 315, 463 | `python3 {spacedock_plugin_dir}/skills/commission/bin/status ...` | `{spacedock_plugin_dir}/skills/commission/bin/status ...` |
| `skills/first-officer/references/first-officer-shared-core.md` | 27 | `python3 {spacedock_plugin_dir}/skills/commission/bin/status --workflow-dir {workflow_dir} [--next\|--archived\|--where ...\|--boot]` | `{spacedock_plugin_dir}/skills/commission/bin/status --workflow-dir {workflow_dir} [--next\|--archived\|--where ...\|--boot]` |

Archived entity files (`docs/plans/_archive/*.md`) and `docs/superpowers/specs/*.md` are out of scope — those are historical records, not operational instructions.

**3. Add a static regression test.** `tests/test_status_script.py` already exists for status-script behavior. Add one test that asserts the script file has the executable bit set (`os.access(path, os.X_OK)`).

## Why this matters

1. **Cleanliness.** The FO's operating contract tells it to run `python3 {plugin_dir}/skills/commission/bin/status ...` dozens of times per session. Every one of those is a slightly-longer, slightly-more-fragile command than `{plugin_dir}/skills/commission/bin/status ...`. The prefix adds nothing.
2. **Consistency.** `claude-team` is already executable without a prefix. `status` should match its sibling.
3. **Future-proofing.** If the script ever gets rewritten in a different language (shell, Rust, Go), the `python3` prefix becomes actively wrong. A clean shebang-based invocation survives language changes.
4. **Regression prevention.** The exec bit was set at some point (the script runs via `python3` because `#!/usr/bin/env python3` is present — that shebang is only useful if the file is executable). It got stripped. A static test prevents it from happening again silently.

## Acceptance Criteria

1. `skills/commission/bin/status` has its executable bit set on disk and in git's tree.
   - Test: `ls -la skills/commission/bin/status` shows `-rwxr-xr-x`; `git ls-tree HEAD skills/commission/bin/status` shows mode `100755`.
2. The 6 live doc references no longer contain `python3 skills/commission/bin/status` or `python3 {spacedock_plugin_dir}/skills/commission/bin/status`.
   - Test: `grep -rn 'python3.*skills/commission/bin/status' scripts/ skills/` returns zero lines (excluding `.worktrees/`).
3. Running the status script directly (no `python3` prefix) from the repo root works as expected.
   - Test: `./skills/commission/bin/status --workflow-dir docs/plans` exits 0 and prints the entity table. Integration-test this, not unit-test.
4. `tests/test_status_script.py` has a new assertion that the status script file is executable.
   - Test: new test passes on the fix commit and fails on the parent commit.
5. Existing suites stay green — no functional changes, only mode change + docs sweep.
   - Test: `unset CLAUDECODE && uv run --with pytest python tests/test_status_script.py -q`, `tests/test_agent_content.py`, `tests/test_rejection_flow.py`.

## Test Plan

- Unit test for executable bit in `tests/test_status_script.py` (low cost, required).
- Static grep assertion in `tests/test_agent_content.py` optional: assert no `python3.*skills/commission/bin/status` anywhere in the assembled FO content. Belt-and-suspenders with the sweep.
- No E2E needed.

## Out of scope

- Rewriting the status script (language change, interface change) — this is a mode + docs fix.
- Sweeping `docs/plans/_archive/` (historical records).
- Sweeping `docs/superpowers/specs/` (external specs).
- Adding a symlink shim at `{workflow_dir}/status` (separate ergonomics task, e.g., task 123's out-of-scope list).
- Fixing the similar pattern elsewhere if it exists in other scripts — this task is status-script-specific.

## Related

- **Task 121** `fo-context-aware-reuse` (landed) — introduced `claude-team` with the correct exec bit and no `python3` prefix. This task brings `status` into line.
- **Task 123** `status-tool-as-workflow-op-cli` (backlog) — bigger rewrite of the status tool. This task is a prerequisite cleanup that 123 should inherit.
- **Task 122** `status-set-missing-field-silent-noop` (landed) — the recent status-script bug fix. Touched the same file; would have been a natural place to fix the exec bit if it had been noticed then.
