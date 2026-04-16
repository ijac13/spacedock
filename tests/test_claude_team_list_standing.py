#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ""
# ///
# ABOUTME: Unit tests for `claude-team list-standing` subcommand.
# ABOUTME: Covers AC-9 (sorted absolute paths), AC-10 (missing _mods), AC-11 (only non-standing).

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "skills" / "commission" / "bin" / "claude-team"


_STANDING_MOD = """---
name: {name}
description: A standing teammate
version: 0.1.0
standing: true
---

## Hook: startup

- `subagent_type: general-purpose`
- `name: {name}`
- `model: sonnet`

## Agent Prompt

You are {name}.
"""


_NON_STANDING_MOD = """---
name: pr-merge
description: PR merge helper
version: 0.1.0
---

## Hook: merge

- runs on validation PASSED

## Agent Prompt

Trivial.
"""


def run_list_standing(wf_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "list-standing", "--workflow-dir", str(wf_dir)],
        capture_output=True,
        text=True,
    )


class TestListStandingMixed:
    """AC-9: mixed standing + non-standing mods emit standing paths sorted alphabetically."""

    def test_sorted_absolute_paths(self, tmp_path):
        wf = tmp_path / "workflow"
        wf.mkdir()
        mods = wf / "_mods"
        mods.mkdir()
        (mods / "zz-mod.md").write_text(_STANDING_MOD.format(name="zz-mod"))
        (mods / "aa-mod.md").write_text(_STANDING_MOD.format(name="aa-mod"))
        (mods / "pr-merge.md").write_text(_NON_STANDING_MOD)

        result = run_list_standing(wf)
        assert result.returncode == 0, f"stderr: {result.stderr}"

        expected = (
            f"{os.path.abspath(mods / 'aa-mod.md')}\n"
            f"{os.path.abspath(mods / 'zz-mod.md')}\n"
        )
        assert result.stdout == expected, (
            f"stdout mismatch:\n  got: {result.stdout!r}\n  want: {expected!r}"
        )
        # Non-standing mod must not appear.
        assert "pr-merge" not in result.stdout


class TestListStandingMissingModsDir:
    """AC-10: workflow without a `_mods/` directory emits empty stdout, exit 0."""

    def test_missing_mods_dir_empty_stdout_exit_zero(self, tmp_path):
        wf = tmp_path / "workflow"
        wf.mkdir()
        # Intentionally do NOT create wf/_mods.

        result = run_list_standing(wf)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert result.stdout == ""
        # Tolerate pre-existing interpreter SyntaxWarnings; assert no helper-emitted error.
        assert "error:" not in result.stderr.lower()


class TestListStandingOnlyNonStanding:
    """AC-11: `_mods/` with only non-standing mods emits empty stdout, exit 0."""

    def test_only_non_standing_mods_empty_stdout_exit_zero(self, tmp_path):
        wf = tmp_path / "workflow"
        wf.mkdir()
        mods = wf / "_mods"
        mods.mkdir()
        (mods / "pr-merge.md").write_text(_NON_STANDING_MOD)

        result = run_list_standing(wf)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert result.stdout == ""


class TestListStandingMissingWorkflowDir:
    """Workflow-dir resolution failure surfaces as non-zero exit with stderr message."""

    def test_missing_workflow_dir_exit_nonzero(self, tmp_path):
        missing = tmp_path / "does-not-exist"
        result = run_list_standing(missing)
        assert result.returncode != 0
        assert "workflow directory" in result.stderr.lower() or \
               "not found" in result.stderr.lower()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
